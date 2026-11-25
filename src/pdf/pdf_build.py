from __future__ import annotations

import argparse
import sys
import json
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape
import markdown
import yaml
from weasyprint import CSS, HTML

ROOT = Path(__file__).resolve().parent.parent.parent
ASSETS_DIR = ROOT / "assets"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Mocking or removing services dependency if not present
try:
    from services.docs_manifest import DEFAULT_MANIFEST_PATH, list_tool_documents, source_path_from_entry
    HAS_MANIFEST = True
except ImportError:
    HAS_MANIFEST = False
    DEFAULT_MANIFEST_PATH = ROOT / "docs-manifest.yaml"

BUILD_DIR_ROOT = ROOT / "dist"
TEMPLATES_DIR = ROOT / "src" / "pdf" / "templates"
# Resilient paths for assets
LOGO_PATH = ROOT / "assets" / "images" / "prolab-logo-26-1.png"
FENG_HEADER_PATH = ROOT / "assets" / "images" / "feng-header-strip.png"
DEFAULT_PHOTO = "assets/images/photo.png"

# Simplified variant mapping for CV
VARIANT_STYLESHEETS = {
    "digital": [
        TEMPLATES_DIR / "cv.css",
    ],
    "print": [
        TEMPLATES_DIR / "cv.css",
    ],
}

JINJA_ENV = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    autoescape=select_autoescape(["html", "xml"]),
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
    if path.is_absolute():
        return path if path.exists() else None

    candidate = ROOT / path
    return candidate if candidate.exists() else None


def resolve_markdown_input(path_value: str) -> Path | None:
    path = Path(path_value)
    candidates = []

    if path.is_absolute():
        candidates.append(path)
    else:
        candidates.append((ROOT / path).resolve())
        candidates.append((ASSETS_DIR / path).resolve())

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return None


def resolve_schema_path(meta: dict[str, Any], template_name: str) -> Path | None:
    explicit_schema = resolve_repo_path(meta.get("schema"))
    if explicit_schema:
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
        r'\1 <span class="period"> — \2</span>',
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
    template_name = meta.get("template", "cv")
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

    logo_rel = ""
    if LOGO_PATH.exists():
        logo_rel = LOGO_PATH.relative_to(ROOT).as_posix()

    feng_rel = ""
    if FENG_HEADER_PATH.exists():
        feng_rel = FENG_HEADER_PATH.relative_to(ROOT).as_posix()

    photo = resolve_repo_path(meta.get("photo") or DEFAULT_PHOTO)
    photo_rel = photo.relative_to(ROOT).as_posix() if photo else ""

    return template.render(
        photo_path=photo_rel,
        lang="en",
        title=document_title,
        body=body,
        meta=meta,
        schema_meta=schema_meta,
        logo_path=logo_rel,
        feng_header_path=feng_rel,
        recipient_lines=recipient_lines,
        cc_lines=cc_lines,
        subject=meta.get("subject", ""),
        letter_date=meta.get("date", ""),
    ), meta


def build_pdf(source_path: Path, variant: str, project_slug: str | None = None, external_data: dict[str, Any] | None = None) -> Path:
    project_slug = project_slug or "default"
    output_dir = BUILD_DIR_ROOT / "pdf"
    
    html, meta = render_markdown(source_path.read_text(encoding="utf-8"), external_data=external_data)
    
    template_name = meta.get("template", "cv")
    css_path = TEMPLATES_DIR / f"{template_name}.css"
    stylesheets = [CSS(filename=str(css_path))] if css_path.exists() else []

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{source_path.stem}.pdf"
    HTML(string=html, base_url=str(ROOT)).write_pdf(output_path, stylesheets=stylesheets)
    return output_path


def select_markdown_files(
    variant: str,
    manifest_path: str | Path = DEFAULT_MANIFEST_PATH,
    project_slug: str | None = None,
) -> list[tuple[Path, str]]:
    if not HAS_MANIFEST:
        return []
    
    selected_entries: list[tuple[Path, str]] = []
    # Use the imported functions if available
    from services.docs_manifest import list_tool_documents, source_path_from_entry # type: ignore
    for entry in list_tool_documents(manifest_path, "pdf"):
        slug = entry.get("path")
        if not slug:
            continue
        if project_slug and slug != project_slug:
            continue
        selected_entries.append((source_path_from_entry(entry), slug))
    return sorted(selected_entries)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build PDFs from Markdown sources.")
    parser.add_argument(
        "--variant",
        choices=sorted(VARIANT_STYLESHEETS),
        default="digital",
        help="Output variant to build.",
    )
    parser.add_argument(
        "--project",
        help="Filter by project slug.",
    )
    parser.add_argument(
        "--file",
        "--input",
        help="Path to a specific Markdown file to build (relative to root).",
    )
    parser.add_argument(
        "--data",
        help="Path to a JSON file with additional metadata.",
    )
    parser.add_argument(
        "--manifest",
        default=str(DEFAULT_MANIFEST_PATH.relative_to(ROOT)) if HAS_MANIFEST else None,
        help="Path to the shared projects manifest file.",
    )
    args = parser.parse_args()

    external_data = {}
    if args.data:
        data_path = Path(args.data).resolve()
        if not data_path.exists():
            data_path = (ROOT / args.data).resolve()
        
        if data_path.exists():
            external_data = json.loads(data_path.read_text(encoding="utf-8"))
        else:
            print(f"Warning: Data file not found: {args.data}")

    if args.file:
        file_path = resolve_markdown_input(args.file)

        if file_path is None:
            raise SystemExit(f"File not found: {args.file}")
        
        entries = [(file_path, args.project or "default")]
    else:
        if not HAS_MANIFEST:
             raise SystemExit("No manifest support and no file provided via --input.")
        entries = select_markdown_files(args.variant, args.manifest, args.project)

    if not entries:
        filter_msg = []
        if args.project: filter_msg.append(f"project {args.project}")
        if args.file: filter_msg.append(f"file {args.file}")
        msg = " and ".join(filter_msg)
        raise SystemExit(f"No PDF-enabled markdown files found for variant {args.variant}{' for ' + msg if msg else ''}")

    for markdown_file, project_slug in entries:
        pdf_path = build_pdf(markdown_file, args.variant, project_slug, external_data=external_data)
        print(f"Built {pdf_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
