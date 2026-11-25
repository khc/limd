import unittest

from limd.files import validate_slug
from limd.linkedin.pdf_import import parse_profile_markdown

SAMPLE = """Jane Doe
Engineering Manager at Acme

**Summary**
Builds teams.

## Experience
Acme - Engineering Manager

Education
State University

Top Skills
Python, Hiring

Something Else Entirely
"""


class ParseProfileTests(unittest.TestCase):
    def test_splits_known_sections(self) -> None:
        sections = parse_profile_markdown(SAMPLE)

        self.assertTrue(sections["header"].startswith("Jane Doe"))
        self.assertEqual(sections["about"], "Builds teams.")
        self.assertIn("Engineering Manager", sections["experience"])
        self.assertEqual(sections["education"], "State University")
        self.assertIn("Python", sections["skills"])

    def test_unknown_headings_stay_inside_the_current_section(self) -> None:
        sections = parse_profile_markdown(SAMPLE)

        self.assertIn("Something Else Entirely", sections["skills"])

    def test_slug_validation(self) -> None:
        self.assertEqual(validate_slug("jane-doe_1"), "jane-doe_1")
        for bad in ("../x", "a b", "", "x/y"):
            with self.assertRaises(ValueError):
                validate_slug(bad)


if __name__ == "__main__":
    unittest.main()
