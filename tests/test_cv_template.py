import unittest

from limd.pdf.build import (
    RESTRICTED_FETCHER,
    check_fetch_allowed,
    output_dir_for,
    render_markdown,
    resolve_schema_path,
)
from limd.paths import APPLICATIONS_DIR, DIST_DIR, FONTS_DIR, PROFILE_DIR, ROOT, TEMPLATES_DIR

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

    def test_front_matter_values_are_escaped_but_markdown_html_is_kept(self) -> None:
        html, _ = render_markdown('---\nemail: "<i>x</i>"\n---\n# X\n\n<b>ok</b>\n')

        self.assertIn("&lt;i&gt;x&lt;/i&gt;", html)
        self.assertNotIn("<i>x</i>", html)
        self.assertIn("<b>ok</b>", html)

    def test_photo_outside_repo_is_ignored(self) -> None:
        html, _ = render_markdown("---\nphoto: /etc/hosts\n---\n# X\n")

        self.assertNotIn("profile-photo", html)

    def test_unsafe_template_name_falls_back_to_cv(self) -> None:
        html, _ = render_markdown("---\ntemplate: ../../x\n---\n# X\n")

        self.assertIn('class="cv-template"', html)

    def test_fetcher_blocks_remote_foreign_and_private_files(self) -> None:
        blocked = (
            "http://example.com/x.css",
            "file:///etc/hosts",
            (PROFILE_DIR / "cv.md").as_uri(),
            (ROOT / "assets" / "about.md").as_uri(),
        )
        for url in blocked:
            with self.assertRaises(ValueError):
                check_fetch_allowed(url)
            with self.assertRaises(ValueError):
                RESTRICTED_FETCHER.fetch(url)

    def test_fetcher_allows_photo_fonts_and_templates(self) -> None:
        for url in (
            (PROFILE_DIR / "photo.png").as_uri(),
            (PROFILE_DIR / "certs" / "psm1.png").as_uri(),
            (FONTS_DIR / "Inter" / "x.ttf").as_uri(),
            (TEMPLATES_DIR / "cv.css").as_uri(),
            "data:text/plain;base64,QQ==",
        ):
            check_fetch_allowed(url)

    def test_pdf_output_is_grouped_by_company(self) -> None:
        self.assertEqual(output_dir_for(APPLICATIONS_DIR / "acme" / "cv.md"), DIST_DIR / "acme")
        self.assertEqual(output_dir_for(PROFILE_DIR / "cv.md"), DIST_DIR / "pdf")

    def test_schema_must_be_a_yaml_file_inside_templates(self) -> None:
        self.assertIsNone(resolve_schema_path({"schema": "Taskfile.yml"}, "cv"))


if __name__ == "__main__":
    unittest.main()
