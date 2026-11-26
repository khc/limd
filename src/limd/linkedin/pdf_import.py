"""Import someone's LinkedIn profile saved as PDF ("Save to PDF") into structured Markdown/JSON."""

import argparse
import json
import re
import sys
from pathlib import Path

from limd.files import validate_slug, write_text
from limd.paths import PROFILE_DIR

SECTIONS = {
    "about": "about",
    "summary": "about",
    "experience": "experience",
    "education": "education",
    "skills": "skills",
    "top skills": "skills",
    "licenses & certifications": "certifications",
    "certifications": "certifications",
    "languages": "languages",
}
HEADING_RE = re.compile(r"^\s*(?:#{1,6}\s*)?(?:\*\*|__)?\s*([A-Za-z&][A-Za-z &]*?)\s*:?\s*(?:\*\*|__)?\s*$")


def parse_profile_markdown(text: str) -> dict[str, str]:
    """Split profile Markdown into sections; text before the first known heading is 'header'."""
    sections: dict[str, list[str]] = {"header": []}
    current = "header"
    for line in text.splitlines():
        match = HEADING_RE.match(line)
        key = SECTIONS.get(match.group(1).strip().lower()) if match else None
        if key:
            current = key
            sections.setdefault(current, [])
        else:
            sections.setdefault(current, []).append(line)
    return {k: "\n".join(v).strip() for k, v in sections.items() if "\n".join(v).strip()}


def render_markdown(name: str, sections: dict[str, str]) -> str:
    parts = [f"# {name}", ""]
    if sections.get("header"):
        parts += [sections["header"], ""]
    for key, text in sections.items():
        if key != "header":
            parts += [f"## {key.capitalize()}", "", text, ""]
    return "\n".join(parts)


def import_pdf(pdf_path: Path | str, name: str, out_dir: Path | str, force: bool = False) -> tuple[Path, Path]:
    from limd.convert.pdf_to_md import convert_with_pymupdf

    slug = validate_slug(name)
    out_dir = Path(out_dir)
    md_path, json_path = out_dir / f"{slug}.md", out_dir / f"{slug}.json"
    for path in (md_path, json_path):
        if path.exists() and not force:
            raise FileExistsError(f"{path} already exists; use --force to overwrite")
    sections = parse_profile_markdown(convert_with_pymupdf(Path(pdf_path)))
    write_text(md_path, render_markdown(slug, sections), force=force)
    write_text(json_path, json.dumps(sections, indent=2, ensure_ascii=False) + "\n", force=force)
    return md_path, json_path


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="limd import pdf", description=__doc__)
    parser.add_argument("pdf", help="LinkedIn profile saved as PDF")
    parser.add_argument("--name", required=True, help="Short slug for the person, e.g. jane-doe")
    parser.add_argument("--out", default=str(PROFILE_DIR / "people"), help="Output directory (default: profile/people/)")
    parser.add_argument("--force", action="store_true", help="Overwrite existing output files")
    args = parser.parse_args(argv)
    try:
        for path in import_pdf(args.pdf, args.name, args.out, args.force):
            print(f"Wrote {path}")
    except (ValueError, FileExistsError, OSError, ImportError) as error:
        sys.exit(f"Error: {error}")
