from __future__ import annotations

import argparse
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent.parent
PROJECTS_DIR = ROOT / "projects"
HEADING_RE = re.compile(r"^(#{1,6})(\s+.*)$")
HORIZONTAL_RULE_RE = re.compile(r"^\s{0,3}((\*\s*){3,}|(-\s*){3,}|(_\s*){3,})\s*$")


def normalize_headings(markdown_text: str) -> str:
    headings = [match for line in markdown_text.splitlines() if (match := HEADING_RE.match(line))]
    h1_count = sum(1 for match in headings if len(match.group(1)) == 1)
    if h1_count <= 1:
        return markdown_text if markdown_text.endswith("\n") else f"{markdown_text}\n"

    normalized_lines: list[str] = []
    seen_first_h1 = False

    for line in markdown_text.splitlines():
        match = HEADING_RE.match(line)
        if not match:
            normalized_lines.append(line)
            continue

        hashes, title = match.groups()
        level = len(hashes)

        if level == 1 and not seen_first_h1:
            normalized_level = 1
            seen_first_h1 = True
        elif seen_first_h1:
            normalized_level = min(level + 1, 6)
        else:
            normalized_level = level

        normalized_lines.append(f"{'#' * normalized_level}{title}")

    return "\n".join(normalized_lines) + "\n"


def strip_horizontal_rules(markdown_text: str) -> str:
    normalized_lines = [
        line for line in markdown_text.splitlines() if not HORIZONTAL_RULE_RE.match(line)
    ]
    return "\n".join(normalized_lines) + "\n"


def normalize_file(path: Path, *, no_hr: bool = False) -> bool:
    original = path.read_text(encoding="utf-8")
    normalized = normalize_headings(original)
    if no_hr:
        normalized = strip_horizontal_rules(normalized)
    if normalized == original:
        return False

    path.write_text(normalized, encoding="utf-8")
    return True


def iter_markdown_files(target: Path) -> list[Path]:
    if target.is_file():
        return [target]
    return sorted(target.rglob("*.md"))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Normalize Markdown heading hierarchy to a single H1."
    )
    parser.add_argument(
        "target",
        nargs="?",
        default=str(PROJECTS_DIR),
        help="Markdown file or directory to normalize. Defaults to projects/.",
    )
    parser.add_argument(
        "--no-hr",
        action="store_true",
        help="Remove Markdown horizontal rules while normalizing.",
    )
    args = parser.parse_args()

    target = Path(args.target).resolve()
    markdown_files = iter_markdown_files(target)
    if not markdown_files:
        raise SystemExit(f"No markdown files found in {target}")

    for markdown_file in markdown_files:
        changed = normalize_file(markdown_file, no_hr=args.no_hr)
        action = "Normalized" if changed else "Unchanged"
        print(f"{action} {markdown_file.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
