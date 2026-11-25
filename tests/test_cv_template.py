import unittest

from src.pdf.pdf_build import render_markdown

SAMPLE_CV = """---
email: jane@example.com
location: Springfield
---

# Jane Doe

Engineering Manager

## Experience

### Acme
Jan 2020 – Present {#period}
Springfield {#place}

- Led a team

## Education {#sidebar}

- BSc Computer Science
"""


class CvTemplateTests(unittest.TestCase):
    def test_renders_name_contact_and_sections(self) -> None:
        html, meta = render_markdown(SAMPLE_CV)

        self.assertIn("<h1>Jane Doe</h1>", html)
        self.assertIn("jane@example.com", html)
        self.assertIn("Experience", html)
        self.assertEqual(meta["location"], "Springfield")

    def test_sidebar_sections_are_split_out(self) -> None:
        html, meta = render_markdown(SAMPLE_CV)

        self.assertIn("BSc Computer Science", meta["sidebar_body"])
        self.assertNotIn("{#sidebar}", html)

    def test_period_moves_into_heading_and_place_is_dropped(self) -> None:
        html, _ = render_markdown(SAMPLE_CV)

        self.assertIn('<span class="period">', html)
        self.assertNotIn("{#place}", html)

    def test_missing_photo_is_omitted(self) -> None:
        html, _ = render_markdown(SAMPLE_CV.replace("---\nemail", "---\nphoto: nope.png\nemail", 1))

        self.assertNotIn("profile-photo", html)


if __name__ == "__main__":
    unittest.main()
