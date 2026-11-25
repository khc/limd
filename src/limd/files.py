"""Small safe-file helpers shared by importers and generators."""

import os
import re
import tempfile
from pathlib import Path

SLUG_RE = re.compile(r"[A-Za-z0-9_-]+")


def validate_slug(value: str, label: str = "name") -> str:
    if not SLUG_RE.fullmatch(value):
        raise ValueError(f"{label} may only contain letters, digits, '-' and '_': {value!r}")
    return value


def write_text(path: Path | str, text: str, force: bool = False) -> Path:
    """Write text atomically; refuse to overwrite an existing file unless force is set."""
    path = Path(path)
    if path.exists() and not force:
        raise FileExistsError(f"{path} already exists; use --force to overwrite")
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, suffix=".part", delete=False) as tmp:
        tmp_name = tmp.name
        try:
            tmp.write(text)
        except BaseException:
            os.unlink(tmp_name)
            raise
    os.replace(tmp_name, path)
    return path
