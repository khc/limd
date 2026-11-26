from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from jinja2 import Environment, FileSystemLoader, select_autoescape
import markdown
import yaml
from weasyprint import CSS, HTML, URLFetcher

from limd.paths import (
    APPLICATIONS_DIR,
    DIST_DIR,
    FONTS_DIR,
    PROFILE_DIR,
    ROOT,
    TEMPLATES_DIR,
)

DEFAULT_PHOTO = "profile/photo.png"

# WeasyPrint may only read fonts, images and stylesheets from these directories while rendering.
ALLOWED_FETCH_DIRS = (
    FONTS_DIR.resolve(),
    PROFILE_DIR.resolve(),
    TEMPLATES_DIR.resolve(),
)
ALLOWED_FETCH_SUFFIXES = {".ttf", ".otf", ".woff", ".woff2", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".css"}
TEMPLATE_NAME_RE = re.compile(r"[A-Za-z0-9_-]+")

JINJA_ENV = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    autoescape=select_autoescape(default=True),
)


def parse_front_matter(markdown_text: str) -> tuple[dict[str, Any], str]:
    if not markdown_text.startswith("---\n"):
        return {}, markdown_text

    # Handle multiple types of markers (e.g., if there's no ending marker)
    end_marker = "\n---\n"
    end_index = markdown_text.find(end_marker, 4)
    if end_index == -1:
        return {}, markdown_text

    front_matter = markdown_text[4:end_index]
    body = markdown_text[end_index + len(end_marker):]
    parsed = yaml.safe_load(front_matter) or {}
    if not isinstance(parsed, dict):
        return {}, markdown_text

    return {str(key).lower(): value for key, value in parsed.items()}, body


def resolve_repo_path(path_value: str | None) -> Path | None:
    if not path_value:
        return None

    path = Path(path_value)
    candidate = (path if path.is_absolute() else ROOT / path).resolve()
    return candidate if candidate.is_relative_to(ROOT) and candidate.exists() else None


def resolve_template_name(meta: dict[str, Any]) -> str:
    name = str(meta.get("template") or "cv")
    return name if TEMPLATE_NAME_RE.fullmatch(name) else "cv"


def check_fetch_allowed(url: str) -> None:
    """Allow only data: URIs and font/image/css files under ALLOWED_FETCH_DIRS."""
    parsed = urlparse(url)
    if parsed.scheme == "data":
        return
    if parsed.scheme == "file":
        path = Path(unquote(parsed.path)).resolve()
        if path.suffix.lower() in ALLOWED_FETCH_SUFFIXES and any(
            path.is_relative_to(allowed) for allowed in ALLOWED_FETCH_DIRS
        ):
            return
    raise ValueError(f"Blocked resource: {url}")


class RestrictedURLFetcher(URLFetcher):
    def fetch(self, url: str, headers: dict[str, str] | None = None) -> Any:
        check_fetch_allowed(url)
        return super().fetch(url, headers)


RESTRICTED_FETCHER = RestrictedURLFetcher(allowed_protocols=("data", "file"), allow_redirects=False)


def resolve_markdown_input(path_value: str) -> Path | None:
    path = Path(path_value)
    candidates = []

    if path.is_absolute():
        candidates.append(path)
    else:
        candidates.append((ROOT / path).resolve())
        candidates.append((PROFILE_DIR / path).resolve())

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return None


def resolve_schema_path(meta: dict[str, Any], template_name: str) -> Path | None:
    explicit_schema = resolve_repo_path(meta.get("schema"))
    if (
        explicit_schema
        and explicit_schema.is_relative_to(TEMPLATES_DIR.resolve())
        and explicit_schema.suffix in (".yaml", ".yml")
    ):
        return explicit_schema

    template_schema = TEMPLATES_DIR / f"{template_name}.schema.yaml"
    if template_schema.exists():
        return template_schema

    return None


def preprocess_markdown(text: str) -> str:
    import re
    # Move period into header with a dash
    text = re.sub(
        r'(###+ .+)\n+(.+)\s+\{#period\}',
        r'\1 <span class="period"> – \2</span>',
        text
    )
    # Remove lines with {#place}
    text = re.sub(
        r'\n+.+\s+\{#place\}',
        '',
        text
    )
    return text


def render_markdown(markdown_text: str, external_data: dict[str, Any] | None = None) -> tuple[str, dict[str, Any]]:
    import re
    meta, content = parse_front_matter(markdown_text)
    
    # Merge external data if provided (Markdown front-matter wins)
    if external_data:
        merged_meta = external_data.copy()
        merged_meta.update(meta)
        meta = merged_meta

    # Extract {#sidebar} sections
    sidebar_sections = []
    def extract_sidebar(match):
        sidebar_sections.append(match.group(1))
        return ""

    # Matches a heading with {#sidebar} and everything until the next heading or end of file
    sidebar_pattern = r'(##+ .+\{#sidebar\}[\s\S]*?)(?=\n##+ |$)'
    content = re.sub(sidebar_pattern, extract_sidebar, content)
    
    if sidebar_sections:
        # Join sections and remove the {#sidebar} markers from titles
        sidebar_md = "\n".join(sidebar_sections)
        sidebar_md = re.sub(r'\s+\{#sidebar\}', '', sidebar_md)
        
        md = markdown.Markdown(extensions=["extra", "smarty", "sane_lists"])
        meta["sidebar_body"] = md.convert(sidebar_md)

    content = preprocess_markdown(content)

    # Default to 'cv' template since we removed others
    template_name = resolve_template_name(meta)
    schema_meta: dict[str, Any] = {}
    schema_path = resolve_schema_path(meta, template_name)
    if schema_path:
        loaded_schema = yaml.safe_load(schema_path.read_text(encoding="utf-8")) or {}
        if isinstance(loaded_schema, dict):
            schema_meta = loaded_schema

    md = markdown.Markdown(
        extensions=["extra", "smarty", "sane_lists"],
        output_format="html5",
    )
    body = md.convert(content)

    recipient_lines = meta.get("recipient", [])
    cc_lines = meta.get("cc", [])
    if isinstance(recipient_lines, str):
        recipient_lines = [line.strip() for line in recipient_lines.splitlines() if line.strip()]
    if isinstance(cc_lines, str):
        cc_lines = [line.strip() for line in cc_lines.splitlines() if line.strip()]

    try:
        template = JINJA_ENV.get_template(f"{template_name}.html.j2")
    except Exception:
        # Fallback to cv template
        template = JINJA_ENV.get_template("cv.html.j2")

    schema_document = schema_meta.get("document", {}) if isinstance(schema_meta, dict) else {}
    document_title = (
        meta.get("pdf_title")
        or meta.get("title")
        or schema_document.get("title")
        or "CV"
    )

    photo = resolve_repo_path(meta.get("photo") or DEFAULT_PHOTO)
    photo_rel = photo.relative_to(ROOT).as_posix() if photo else ""

    return template.render(
        photo_path=photo_rel,
        lang="en",
        title=document_title,
        body=body,
        meta=meta,
        schema_meta=schema_meta,
        recipient_lines=recipient_lines,
        cc_lines=cc_lines,
        subject=meta.get("subject", ""),
        letter_date=meta.get("date", ""),
    ), meta


def output_dir_for(source_path: Path) -> Path:
    """dist/<company>/ for files inside applications/<company>/, otherwise dist/pdf/."""
    try:
        company = source_path.resolve().relative_to(APPLICATIONS_DIR.resolve()).parts[0]
    except (ValueError, IndexError):
        return DIST_DIR / "pdf"
    return DIST_DIR / company


def build_pdf(source_path: Path, external_data: dict[str, Any] | None = None) -> Path:
    output_dir = output_dir_for(source_path)

    html, meta = render_markdown(source_path.read_text(encoding="utf-8"), external_data=external_data)

    css_path = TEMPLATES_DIR / f"{resolve_template_name(meta)}.css"
    stylesheets = [CSS(filename=str(css_path), url_fetcher=RESTRICTED_FETCHER)] if css_path.exists() else []

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{source_path.stem}.pdf"
    HTML(string=html, base_url=str(ROOT), url_fetcher=RESTRICTED_FETCHER).write_pdf(
        output_path, stylesheets=stylesheets
    )
    return output_path


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Build a PDF from a Markdown CV.")
    parser.add_argument(
        "--input",
        "--file",
        dest="input",
        required=True,
        help="Path to the Markdown file to build (relative to root or assets/).",
    )
    parser.add_argument(
        "--data",
        help="Path to a JSON file with additional metadata.",
    )
    args = parser.parse_args(argv)

    external_data = {}
    if args.data:
        data_path = Path(args.data).resolve()
        if not data_path.exists():
            data_path = (ROOT / args.data).resolve()

        if data_path.exists():
            external_data = json.loads(data_path.read_text(encoding="utf-8"))
        else:
            print(f"Warning: Data file not found: {args.data}")

    file_path = resolve_markdown_input(args.input)
    if file_path is None:
        raise SystemExit(f"File not found: {args.input}")

    pdf_path = build_pdf(file_path, external_data=external_data)
    print(f"Built {pdf_path}")


if __name__ == "__main__":
    main()
