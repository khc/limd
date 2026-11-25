"""Import your own profile from LinkedIn's "Get a copy of your data" ZIP archive."""

import argparse
import csv
import io
import json
import re
import sys
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

from limd.files import write_text
from limd.paths import PROFILE_DIR

MAX_MEMBER_BYTES = 10 * 1024 * 1024
WANTED = {
    "profile.csv": "profile",
    "positions.csv": "positions",
    "education.csv": "education",
    "skills.csv": "skills",
}


def _norm(header: str) -> str:
    return re.sub(r"\s+", " ", header.strip().lower())


def _get(row: dict[str, str], *names: str) -> str:
    return next((row[n] for n in names if row.get(n)), "")


def _parse_csv(raw: bytes) -> list[dict[str, str]]:
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    return [{_norm(k): (v or "").strip() for k, v in row.items() if k} for row in reader]


def read_export(zip_path: Path | str) -> dict[str, list[dict[str, str]]]:
    """Return the parsed CSV rows keyed by profile/positions/education/skills; missing files are skipped."""
    data: dict[str, list[dict[str, str]]] = {}
    with zipfile.ZipFile(zip_path) as archive:
        for info in archive.infolist():
            member = PurePosixPath(info.filename)
            if member.is_absolute() or ".." in member.parts:
                raise ValueError(f"Unexpected path in archive: {info.filename}")
            key = WANTED.get(member.name.lower())
            if info.is_dir() or not key or key in data:
                continue
            if info.file_size > MAX_MEMBER_BYTES:
                raise ValueError(f"{info.filename} is larger than {MAX_MEMBER_BYTES} bytes")
            with archive.open(info) as handle:
                raw = handle.read(MAX_MEMBER_BYTES + 1)
            if len(raw) > MAX_MEMBER_BYTES:
                raise ValueError(f"{info.filename} is larger than {MAX_MEMBER_BYTES} bytes")
            data[key] = _parse_csv(raw)
    if not data:
        raise ValueError("No Profile/Positions/Education/Skills CSV files found in the archive")
    return data


def normalize(raw: dict[str, list[dict[str, str]]]) -> dict[str, Any]:
    profile = (raw.get("profile") or [{}])[0]
    skills = [_get(r, "name", "skill") for r in raw.get("skills", [])]
    return {
        "name": " ".join(p for p in (_get(profile, "first name"), _get(profile, "last name")) if p),
        "headline": _get(profile, "headline"),
        "summary": _get(profile, "summary"),
        "location": _get(profile, "geo location", "location"),
        "experience": [
            {
                "company": _get(r, "company name", "company"),
                "title": _get(r, "title"),
                "location": _get(r, "location"),
                "start": _get(r, "started on", "start date"),
                "end": _get(r, "finished on", "end date"),
                "description": _get(r, "description"),
            }
            for r in raw.get("positions", [])
        ],
        "education": [
            {
                "school": _get(r, "school name", "school"),
                "degree": _get(r, "degree name", "degree"),
                "start": _get(r, "start date", "started on"),
                "end": _get(r, "end date", "finished on"),
                "notes": _get(r, "notes"),
            }
            for r in raw.get("education", [])
        ],
        "skills": [s for s in skills if s],
    }


def render_markdown(profile: dict[str, Any]) -> str:
    lines = [f"# {profile['name'] or 'LinkedIn profile'}", ""]
    for text in (profile["headline"], profile["location"]):
        if text:
            lines += [text, ""]
    if profile["summary"]:
        lines += ["## Summary", "", profile["summary"], ""]
    if profile["experience"]:
        lines += ["## Experience", ""]
        for job in profile["experience"]:
            period = " – ".join(p for p in (job["start"], job["end"] or "Present") if p)
            lines += [f"### {job['company']}", f"#### {job['title']}", period]
            if job["location"]:
                lines.append(job["location"])
            lines += ["", job["description"], ""] if job["description"] else [""]
    if profile["education"]:
        lines += ["## Education", ""]
        for school in profile["education"]:
            period = " – ".join(p for p in (school["start"], school["end"]) if p)
            lines += [f"- **{school['school']}** {school['degree']} {period}".rstrip()]
        lines.append("")
    if profile["skills"]:
        lines += ["## Skills", "", ", ".join(profile["skills"]), ""]
    return "\n".join(lines)


def import_export(zip_path: Path | str, out_dir: Path | str = PROFILE_DIR, force: bool = False) -> tuple[Path, Path]:
    profile = normalize(read_export(zip_path))
    out_dir = Path(out_dir)
    json_path = out_dir / "linkedin.json"
    md_path = out_dir / "linkedin.md"
    for path in (json_path, md_path):
        if path.exists() and not force:
            raise FileExistsError(f"{path} already exists; use --force to overwrite")
    write_text(json_path, json.dumps(profile, indent=2, ensure_ascii=False) + "\n", force=True)
    write_text(md_path, render_markdown(profile), force=True)
    return json_path, md_path


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="limd import linkedin-export", description=__doc__)
    parser.add_argument("zip", help="Path to the LinkedIn data export ZIP")
    parser.add_argument("--out", default=str(PROFILE_DIR), help="Output directory (default: profile/)")
    parser.add_argument("--force", action="store_true", help="Overwrite existing output files")
    args = parser.parse_args(argv)
    try:
        for path in import_export(args.zip, args.out, args.force):
            print(f"Wrote {path}")
    except (ValueError, FileExistsError, zipfile.BadZipFile, OSError) as error:
        sys.exit(f"Error: {error}")
