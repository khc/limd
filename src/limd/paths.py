"""Filesystem layout. Code and fonts live in the repo; user data lives under LIMD_ROOT (default: the repo)."""

import os
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_DIR.parent.parent



def data_root(env_root: str | None, repo_root: Path, cwd: Path) -> Path:
    """LIMD_ROOT if set, else the source checkout, else the current directory (non-editable installs)."""
    if env_root:
        if not Path(env_root).is_dir():
            raise ValueError(f"LIMD_ROOT is not a directory: {env_root}")
        return Path(env_root).resolve()
    return repo_root if (repo_root / "pyproject.toml").is_file() else cwd.resolve()


try:
    ROOT = data_root(os.environ.get("LIMD_ROOT"), REPO_ROOT, Path.cwd())
except ValueError as error:
    raise SystemExit(f"Error: {error}") from None
PROFILE_DIR = ROOT / "profile"
APPLICATIONS_DIR = ROOT / "applications"
DIST_DIR = ROOT / "dist"

TEMPLATES_DIR = PACKAGE_DIR / "pdf" / "templates"
PROMPTS_DIR = PACKAGE_DIR / "prompts"
FONTS_DIR = REPO_ROOT / "assets" / "fonts"
