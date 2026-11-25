"""Filesystem layout. Code and fonts live in the repo; user data lives under LIMD_ROOT (default: the repo)."""

import os
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_DIR.parent.parent

ROOT = Path(os.environ.get("LIMD_ROOT") or REPO_ROOT).resolve()
PROFILE_DIR = ROOT / "profile"
APPLICATIONS_DIR = ROOT / "applications"
DIST_DIR = ROOT / "dist"

TEMPLATES_DIR = PACKAGE_DIR / "pdf" / "templates"
PROMPTS_DIR = PACKAGE_DIR / "prompts"
FONTS_DIR = REPO_ROOT / "assets" / "fonts"
