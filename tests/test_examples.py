import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


class ExampleProfileTests(unittest.TestCase):
    def test_example_cv_builds_a_pdf_and_tailor_inputs_exist(self) -> None:
        for relative in ("profile/cv.md", "profile/rules.md", "applications/acme/job.md"):
            self.assertTrue((EXAMPLES / relative).is_file(), relative)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "examples"
            shutil.copytree(EXAMPLES, root)
            result = subprocess.run(
                [sys.executable, "-m", "limd.cli", "--root", str(root), "cv", "build", "--input", "profile/cv.md"],
                capture_output=True, text=True, env={**os.environ},
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((root / "dist" / "pdf" / "cv.pdf").stat().st_size > 1000)

    def test_cli_rejects_unknown_commands(self) -> None:
        result = subprocess.run([sys.executable, "-m", "limd.cli", "bogus"], capture_output=True, text=True)

        self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
