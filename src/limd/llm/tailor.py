"""Tailor a master CV to a job and score the match, via a pluggable backend."""

import argparse
import sys
from pathlib import Path

from limd.files import validate_slug, write_text
from limd.llm.backends import Backend, BackendError, get_backend
from limd.llm.llm_match import format_match, match_with_llm
from limd.paths import APPLICATIONS_DIR, PROFILE_DIR, PROMPTS_DIR

REPORT_MARKER = "<<<REPORT>>>"
OPTIONAL_PROFILE_FILES = (
    ("Rules", "rules.md"),
    ("LinkedIn profile", "linkedin.md"),
    ("About (factual background)", "about.md"),
    ("Strategy", "strategy.md"),
    ("Reference CV (scanability benchmark only)", "reference-cv.md"),
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _job_path(company_dir: Path) -> Path:
    for name in ("job.md", "job.txt"):
        if (company_dir / name).is_file():
            return company_dir / name
    raise FileNotFoundError(f"No job.md or job.txt in {company_dir}")


def _application_dir(company: str, applications_dir: Path) -> Path:
    path = applications_dir / validate_slug(company, "company")
    if not path.is_dir():
        raise FileNotFoundError(f"Application folder not found: {path}")
    return path


def build_tailor_input(profile_dir: Path, job_text: str) -> str:
    cv_path = profile_dir / "cv.md"
    if not cv_path.is_file():
        raise FileNotFoundError(f"Master CV not found: {cv_path}")
    parts = []
    for title, name in OPTIONAL_PROFILE_FILES:
        if (profile_dir / name).is_file():
            parts.append(f"## {title}\n\n{_read(profile_dir / name)}")
    parts += [f"## Master CV\n\n{_read(cv_path)}", f"## Job description\n\n{job_text}"]
    return "\n\n".join(parts)


def tailor(company: str, backend: Backend, force: bool = False, profile_dir: Path = PROFILE_DIR,
           applications_dir: Path = APPLICATIONS_DIR) -> tuple[Path, Path]:
    app_dir = _application_dir(company, applications_dir)
    cv_path, report_path = app_dir / "cv.md", app_dir / "report.md"
    for path in (cv_path, report_path):
        if path.exists() and not force:
            raise FileExistsError(f"{path} already exists; use --force to overwrite")
    system = _read(PROMPTS_DIR / "tailor.md")
    response = backend.complete(system, build_tailor_input(profile_dir, _read(_job_path(app_dir))))
    cv_text, _, report = response.partition(REPORT_MARKER)
    write_text(cv_path, cv_text.strip() + "\n", force=True)
    write_text(report_path, (report.strip() or "The model did not return a report.") + "\n", force=True)
    return cv_path, report_path


def match(company: str, backend: Backend, force: bool = False,
          applications_dir: Path = APPLICATIONS_DIR) -> Path:
    app_dir = _application_dir(company, applications_dir)
    cv_file = app_dir / "cv.md"
    if not cv_file.is_file():
        raise FileNotFoundError(f"Tailored CV not found: {cv_file} (run `limd tailor {company}` first)")
    response = match_with_llm(backend, _read(cv_file), _read(_job_path(app_dir)))
    return write_text(app_dir / "match.md", format_match(company, response), force=force)


def _run(prog: str, action, argv: list[str] | None) -> None:
    parser = argparse.ArgumentParser(prog=prog)
    parser.add_argument("company", help="Folder name under applications/")
    parser.add_argument("--backend", default="claude", help="claude, codex or gemini")
    parser.add_argument("--model", help="Model name passed to the backend")
    parser.add_argument("--force", action="store_true", help="Overwrite existing output files")
    args = parser.parse_args(argv)
    try:
        for path in action(args.company, get_backend(args.backend, args.model), args.force):
            print(f"Wrote {path}")
    except (BackendError, FileNotFoundError, FileExistsError, ValueError) as error:
        sys.exit(f"Error: {error}")


def main_tailor(argv: list[str] | None = None) -> None:
    _run("limd tailor", lambda c, b, f: tailor(c, b, f), argv)


def main_match(argv: list[str] | None = None) -> None:
    _run("limd match", lambda c, b, f: (match(c, b, f),), argv)
