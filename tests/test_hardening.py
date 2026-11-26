import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from limd import paths
from limd.convert import pdf_to_md
from limd.linkedin import export_import
from limd.llm import backends, llm_compact
from limd.llm import tailor as tailor_mod

REPO = Path(__file__).resolve().parent.parent


class FakeBackend:
    def __init__(self, response: str = "answer") -> None:
        self.response = response

    def complete(self, system: str, user: str, max_tokens: int | None = None) -> str:
        return self.response


class BackendIsolationTests(unittest.TestCase):
    def _captured_argv(self, backend: backends.Backend) -> list[str]:
        captured: list[list[str]] = []

        def fake_run(argv: list[str], prompt: str | None, **kwargs) -> str:
            captured.append(argv)
            if "-o" in argv:
                Path(argv[argv.index("-o") + 1]).write_text("answer", encoding="utf-8")
            return "answer"

        with mock.patch.object(backends, "_run", side_effect=fake_run):
            backend.complete("SYSTEM", "USER-CV-TEXT")
        return captured[0]

    def test_subprocesses_run_in_a_temp_dir_outside_the_data_root(self) -> None:
        completed = mock.Mock(returncode=0, stdout="ok", stderr="")
        with mock.patch("subprocess.run", return_value=completed) as run:
            backends._run(["tool"], "prompt")

        cwd = Path(run.call_args.kwargs["cwd"])
        self.assertFalse(cwd.is_relative_to(paths.ROOT))

    def test_claude_runs_without_tools(self) -> None:
        argv = self._captured_argv(backends.ClaudeBackend())

        self.assertEqual(argv[argv.index("--tools") + 1], "")

    def test_codex_does_not_persist_sessions(self) -> None:
        argv = self._captured_argv(backends.CodexBackend())

        self.assertIn("--ephemeral", argv)

    def test_gemini_sends_the_prompt_on_stdin_not_in_argv(self) -> None:
        prompts: list[str | None] = []

        def fake_run(argv: list[str], prompt: str | None, **kwargs) -> str:
            prompts.append(prompt)
            self.assertNotIn("USER-CV-TEXT", " ".join(argv))
            return "answer"

        with mock.patch.object(backends, "_run", side_effect=fake_run):
            backends.GeminiBackend().complete("SYSTEM", "USER-CV-TEXT")

        self.assertIn("USER-CV-TEXT", prompts[0])

    def test_oversized_argument_list_becomes_backend_error(self) -> None:
        with mock.patch("subprocess.run", side_effect=OSError(7, "Argument list too long")):
            with self.assertRaises(backends.BackendError):
                backends._run(["tool"], None)


class GitignoreTests(unittest.TestCase):
    def _ignored(self, path: str) -> bool:
        result = subprocess.run(["git", "check-ignore", "-q", "--no-index", path], cwd=REPO)
        return result.returncode == 0

    def test_linkedin_export_archives_are_ignored(self) -> None:
        for path in ("Basic_LinkedInDataExport.zip", "export.zip", "Profile.csv", "Basic_LinkedInDataExport_2026/Positions.csv"):
            self.assertTrue(self._ignored(path), path)

    def test_examples_are_not_ignored(self) -> None:
        self.assertFalse(self._ignored("examples/profile/cv.md"))


class OverwriteSafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def test_compact_refuses_to_overwrite_without_force(self) -> None:
        source, output = self.tmp / "in.md", self.tmp / "out.md"
        source.write_text("some text", encoding="utf-8")
        output.write_text("keep me", encoding="utf-8")

        with mock.patch.object(llm_compact, "get_backend", return_value=FakeBackend("short")):
            with self.assertRaises(SystemExit):
                llm_compact.main(["--input", str(source), "--output", str(output)])
            self.assertEqual(output.read_text(encoding="utf-8"), "keep me")

            llm_compact.main(["--input", str(source), "--output", str(output), "--force"])
        self.assertEqual(output.read_text(encoding="utf-8"), "short")

    def test_convert_replaces_a_symlink_instead_of_writing_through_it(self) -> None:
        pdf, target, link = self.tmp / "a.pdf", self.tmp / "target.md", self.tmp / "out.md"
        pdf.write_text("x", encoding="utf-8")
        target.write_text("keep me", encoding="utf-8")
        link.symlink_to(target)

        with mock.patch.object(pdf_to_md, "convert_with_pymupdf", return_value="converted\n"):
            pdf_to_md.main(["--input", str(pdf), "--output", str(link), "--force"])

        self.assertEqual(target.read_text(encoding="utf-8"), "keep me")
        self.assertFalse(link.is_symlink())

    def test_tailor_does_not_overwrite_a_file_created_during_the_model_call(self) -> None:
        profile, apps = self.tmp / "profile", self.tmp / "applications"
        (apps / "acme").mkdir(parents=True)
        profile.mkdir()
        (profile / "cv.md").write_text("# CV", encoding="utf-8")
        (apps / "acme" / "job.md").write_text("job", encoding="utf-8")

        class Racing(FakeBackend):
            def complete(self, system: str, user: str, max_tokens: int | None = None) -> str:
                (apps / "acme" / "cv.md").write_text("created meanwhile", encoding="utf-8")
                return "tailored"

        with self.assertRaises(FileExistsError):
            tailor_mod.tailor("acme", Racing(), profile_dir=profile, applications_dir=apps)
        self.assertEqual((apps / "acme" / "cv.md").read_text(encoding="utf-8"), "created meanwhile")


class CliBehaviourTests(unittest.TestCase):
    def test_tailor_tells_the_user_to_review_the_output(self) -> None:
        out = io.StringIO()
        with mock.patch.object(tailor_mod, "get_backend", return_value=FakeBackend()), \
                mock.patch.object(tailor_mod, "tailor", return_value=(Path("cv.md"), Path("report.md"))), \
                contextlib.redirect_stdout(out):
            tailor_mod.main_tailor(["acme"])

        self.assertIn("Review", out.getvalue())

    def test_bad_company_and_missing_folder_exit_with_a_message(self) -> None:
        for main, company in ((tailor_mod.main_tailor, "../etc"), (tailor_mod.main_match, "no-such-company")):
            with mock.patch.object(tailor_mod, "get_backend", return_value=FakeBackend()):
                with self.assertRaises(SystemExit) as ctx:
                    main([company])
            self.assertIsInstance(ctx.exception.code, str)
            self.assertTrue(ctx.exception.code.startswith("Error"))

    def test_import_linkedin_export_runs_through_the_cli(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "export.zip"
            with zipfile.ZipFile(archive, "w") as z:
                z.writestr("Profile.csv", "First Name,Last Name\nJane,Doe\n")
            result = subprocess.run(
                [sys.executable, "-m", "limd.cli", "import", "linkedin-export", str(archive)],
                capture_output=True, text=True, env={**os.environ, "LIMD_ROOT": tmp},
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Jane Doe", (Path(tmp) / "profile" / "linkedin.md").read_text(encoding="utf-8"))


class ExportImporterErrorTests(unittest.TestCase):
    def test_oversized_csv_field_gives_a_clean_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "export.zip"
            with zipfile.ZipFile(archive, "w") as z:
                z.writestr("Profile.csv", "Summary\n" + "x" * 200_000 + "\n")

            with self.assertRaises(SystemExit) as ctx:
                export_import.main([str(archive), "--out", str(Path(tmp) / "out")])

        self.assertIsInstance(ctx.exception.code, str)
        self.assertTrue(ctx.exception.code.startswith("Error"))


class DataRootTests(unittest.TestCase):
    def test_defaults_to_the_checkout_only_when_one_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            checkout, cwd = Path(tmp).resolve() / "checkout", Path(tmp).resolve() / "elsewhere"
            checkout.mkdir()
            cwd.mkdir()
            self.assertEqual(paths.data_root(None, checkout, cwd), cwd)
            (checkout / "pyproject.toml").write_text("", encoding="utf-8")
            self.assertEqual(paths.data_root(None, checkout, cwd), checkout)
            self.assertEqual(paths.data_root(str(cwd), checkout, cwd), cwd)

    def test_limd_root_must_be_a_directory(self) -> None:
        with self.assertRaises(ValueError):
            paths.data_root("/definitely/not/a/dir", REPO, REPO)

        result = subprocess.run(
            [sys.executable, "-c", "import limd.paths"],
            capture_output=True, text=True, env={**os.environ, "LIMD_ROOT": "/definitely/not/a/dir"},
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("LIMD_ROOT", result.stderr)


if __name__ == "__main__":
    unittest.main()
