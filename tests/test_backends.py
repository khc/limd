import tempfile
import unittest
from pathlib import Path
from unittest import mock

from limd.llm import backends
from limd.llm.llm_match import format_match
from limd.llm.tailor import REPORT_MARKER, match, tailor


class FakeBackend:
    def __init__(self, response: str) -> None:
        self.response = response
        self.calls: list[tuple[str, str]] = []

    def complete(self, system: str, user: str, max_tokens: int | None = None) -> str:
        self.calls.append((system, user))
        return self.response


class TailorMatchTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.profile = root / "profile"
        self.apps = root / "applications"
        (self.profile).mkdir()
        (self.apps / "acme").mkdir(parents=True)
        (self.profile / "cv.md").write_text("# Jane Doe\n\nMaster CV text", encoding="utf-8")
        (self.profile / "rules.md").write_text("Never invent metrics.", encoding="utf-8")
        (self.apps / "acme" / "job.md").write_text("Seeking an engineering manager", encoding="utf-8")

    def test_tailor_writes_cv_and_report_and_sends_profile_and_job(self) -> None:
        backend = FakeBackend(f"# Jane Doe\n\nTailored\n{REPORT_MARKER}\nReport body")

        cv, report = tailor("acme", backend, profile_dir=self.profile, applications_dir=self.apps)

        self.assertIn("Tailored", cv.read_text(encoding="utf-8"))
        self.assertEqual(report.read_text(encoding="utf-8").strip(), "Report body")
        user_prompt = backend.calls[0][1]
        for expected in ("Never invent metrics.", "Master CV text", "Seeking an engineering manager"):
            self.assertIn(expected, user_prompt)

    def test_tailor_refuses_to_overwrite_and_validates_company(self) -> None:
        backend = FakeBackend("cv")
        tailor("acme", backend, profile_dir=self.profile, applications_dir=self.apps)

        with self.assertRaises(FileExistsError):
            tailor("acme", backend, profile_dir=self.profile, applications_dir=self.apps)
        with self.assertRaises(ValueError):
            tailor("../etc", backend, profile_dir=self.profile, applications_dir=self.apps)

    def test_match_writes_formatted_report(self) -> None:
        (self.apps / "acme" / "cv.md").write_text("# Jane Doe", encoding="utf-8")
        backend = FakeBackend('{"match_score": 72, "summary": "Good", "gaps": ["No Kafka"]}')

        path = match("acme", backend, applications_dir=self.apps)

        text = path.read_text(encoding="utf-8")
        self.assertIn("Score: 72/100", text)
        self.assertIn("- No Kafka", text)

    def test_format_match_keeps_raw_text_when_json_is_invalid(self) -> None:
        self.assertIn("not json", format_match("acme", "not json"))

    def test_unknown_backend_and_missing_binary_raise_backend_error(self) -> None:
        with self.assertRaises(backends.BackendError):
            backends.get_backend("nope")
        with self.assertRaises(backends.BackendError):
            backends._run(["definitely-not-a-real-binary-limd"], None)

    def test_claude_backend_sends_system_prompt_as_flag_and_user_text_on_stdin(self) -> None:
        with mock.patch.object(backends, "_run", return_value=" answer \n") as run:
            result = backends.get_backend("claude", "sonnet").complete("SYSTEM", "USER")

        self.assertEqual(result, "answer")
        argv, stdin = run.call_args.args
        self.assertEqual(argv[:2], ["claude", "-p"])
        self.assertEqual(argv[argv.index("--system-prompt") + 1], "SYSTEM")
        self.assertEqual(argv[argv.index("--model") + 1], "sonnet")
        self.assertEqual(stdin, "USER")


if __name__ == "__main__":
    unittest.main()
