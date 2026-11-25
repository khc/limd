import tempfile
import unittest
import zipfile
from pathlib import Path

from limd.linkedin import export_import

PROFILE_CSV = "First Name,Last Name,Headline,Summary,Geo Location\nJane,Doe,Engineering Manager,Builds teams,Springfield\n"
POSITIONS_CSV = (
    "Company Name,Title,Description,Location,Started On,Finished On\n"
    "Acme,Engineering Manager,Led 3 teams,Springfield,Jan 2020,\n"
)
SKILLS_CSV = "Name\nPython\nHiring\n"


def make_zip(directory: Path, members: dict[str, str]) -> Path:
    path = directory / "export.zip"
    with zipfile.ZipFile(path, "w") as archive:
        for name, content in members.items():
            archive.writestr(name, content)
    return path


class LinkedInExportTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_parses_nested_and_case_insensitive_files_and_skips_missing_ones(self) -> None:
        archive = make_zip(self.tmp, {
            "export/PROFILE.csv": PROFILE_CSV,
            "export/positions.CSV": POSITIONS_CSV,
            "export/Skills.csv": SKILLS_CSV,
        })

        profile = export_import.normalize(export_import.read_export(archive))

        self.assertEqual(profile["name"], "Jane Doe")
        self.assertEqual(profile["experience"][0]["company"], "Acme")
        self.assertEqual(profile["experience"][0]["start"], "Jan 2020")
        self.assertEqual(profile["skills"], ["Python", "Hiring"])
        self.assertEqual(profile["education"], [])

    def test_writes_json_and_markdown_and_refuses_overwrite_without_force(self) -> None:
        archive = make_zip(self.tmp, {"Profile.csv": PROFILE_CSV, "Positions.csv": POSITIONS_CSV})
        out = self.tmp / "profile"

        json_path, md_path = export_import.import_export(archive, out)

        self.assertIn("### Acme", md_path.read_text(encoding="utf-8"))
        self.assertIn('"name": "Jane Doe"', json_path.read_text(encoding="utf-8"))
        with self.assertRaises(FileExistsError):
            export_import.import_export(archive, out)
        export_import.import_export(archive, out, force=True)

    def test_rejects_oversized_members_and_archives_without_known_files(self) -> None:
        big = make_zip(self.tmp, {"Profile.csv": "x" * (export_import.MAX_MEMBER_BYTES + 1)})
        with self.assertRaises(ValueError):
            export_import.read_export(big)

        other = self.tmp / "other.zip"
        with zipfile.ZipFile(other, "w") as archive:
            archive.writestr("notes.txt", "hello")
        with self.assertRaises(ValueError):
            export_import.read_export(other)

    def test_rejects_path_traversal_members(self) -> None:
        archive = make_zip(self.tmp, {"../Profile.csv": PROFILE_CSV})

        with self.assertRaises(ValueError):
            export_import.read_export(archive)


if __name__ == "__main__":
    unittest.main()
