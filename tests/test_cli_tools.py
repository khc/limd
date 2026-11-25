import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from limd.convert import pdf_to_md
from limd.pdf import fonts as pdf_fonts


class FontVerificationTests(unittest.TestCase):
    def test_existing_font_with_wrong_hash_needs_download(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            font = Path(tmp) / "x.ttf"
            self.assertTrue(pdf_fonts.needs_download(font, "0" * 64))
            font.write_bytes(b"tampered")
            self.assertTrue(pdf_fonts.needs_download(font, "0" * 64))
            self.assertFalse(pdf_fonts.needs_download(font, hashlib.sha256(b"tampered").hexdigest()))


class PdfToMdTests(unittest.TestCase):
    def test_exits_non_zero_when_a_conversion_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.pdf"
            bad.write_text("not a pdf", encoding="utf-8")

            with mock.patch("sys.argv", ["pdf_to_md", "--input", str(bad)]):
                with self.assertRaises(SystemExit) as ctx:
                    pdf_to_md.main()

        self.assertEqual(ctx.exception.code, 1)

    def test_non_pdf_inputs_are_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "cv.md"
            source.write_text("keep me", encoding="utf-8")

            with mock.patch("sys.argv", ["pdf_to_md", "--input", str(source)]):
                with self.assertRaises(SystemExit) as ctx:
                    pdf_to_md.main()

            self.assertEqual(ctx.exception.code, 1)
            self.assertEqual(source.read_text(encoding="utf-8"), "keep me")

    def test_existing_output_is_not_overwritten_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp) / "a.pdf"
            pdf.write_text("not a pdf", encoding="utf-8")
            existing = Path(tmp) / "a.md"
            existing.write_text("keep me", encoding="utf-8")

            with mock.patch("sys.argv", ["pdf_to_md", "--input", str(pdf)]):
                with self.assertRaises(SystemExit) as ctx:
                    pdf_to_md.main()

            self.assertEqual(ctx.exception.code, 1)
            self.assertEqual(existing.read_text(encoding="utf-8"), "keep me")


if __name__ == "__main__":
    unittest.main()
