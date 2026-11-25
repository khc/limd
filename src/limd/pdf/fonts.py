from __future__ import annotations

import hashlib
import os
import tempfile
import urllib.request
from pathlib import Path

from limd.paths import FONTS_DIR, REPO_ROOT

# Pinned to a google/fonts commit; each file is verified against its SHA-256 before being written.
FONTS_COMMIT = "6ebe737e44fd64ee736bbc6feed6136a6dbfd222"
BASE_URL = f"https://raw.githubusercontent.com/google/fonts/{FONTS_COMMIT}/ofl"
MAX_FONT_BYTES = 5 * 1024 * 1024

# destination (under assets/fonts) -> (path in google/fonts, sha256)
FONTS = {
    "Inter/Inter-VariableFont_opsz,wght.ttf": (
        "inter/Inter%5Bopsz%2Cwght%5D.ttf",
        "29160a80ff49ddcab2c97711247e08b1fab27a484a329ce8b813d820dc559031",
    ),
    "Inter/Inter-Italic-VariableFont_opsz,wght.ttf": (
        "inter/Inter-Italic%5Bopsz%2Cwght%5D.ttf",
        "acd98e64795781b2058f07b18475e0ecee2a0fe2b42a49e2f9e37d0d6bf66ce6",
    ),
    "Playfair/Playfair-VariableFont_opsz,wdth,wght.ttf": (
        "playfairdisplay/PlayfairDisplay%5Bwght%5D.ttf",
        "c40f2293766a503bc70cce9e512ef844a4ccb7cbcde792fe2ea31d191917d8d6",
    ),
    "Playfair/Playfair-Italic-VariableFont_opsz,wdth,wght.ttf": (
        "playfairdisplay/PlayfairDisplay-Italic%5Bwght%5D.ttf",
        "a5e26dc5e2e77fb2803a0bf02fd4f81ee136ec8dea863ccdb0c59a263b21378b",
    ),
    "Outfit/static/Outfit-ExtraBold.ttf": (
        "outfit/Outfit%5Bwght%5D.ttf",
        "fc7287273e66929776e2ba54f144fe699080bec29f61bf649d70d871468aeade",
    ),
}


def needs_download(dest: Path, sha256: str) -> bool:
    return not dest.exists() or hashlib.sha256(dest.read_bytes()).hexdigest() != sha256


def download_file(url: str, dest: Path, sha256: str) -> None:
    print(f"Downloading to {dest.relative_to(REPO_ROOT)}...")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as response:
        data = response.read(MAX_FONT_BYTES + 1)

    if len(data) > MAX_FONT_BYTES:
        raise ValueError("font file is larger than the allowed size")
    if hashlib.sha256(data).hexdigest() != sha256:
        raise ValueError("SHA-256 mismatch")

    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=dest.parent, suffix=".part", delete=False) as tmp:
        tmp.write(data)
    os.chmod(tmp.name, 0o644)
    os.replace(tmp.name, dest)


def main(argv: list[str] | None = None) -> None:
    for rel_path, (remote_path, sha256) in FONTS.items():
        dest = FONTS_DIR / rel_path
        if not needs_download(dest, sha256):
            print(f"Skipping {rel_path}, already present and verified.")
            continue
        try:
            download_file(f"{BASE_URL}/{remote_path}", dest, sha256)
        except Exception as e:
            print(f"Failed to download {rel_path}: {e}")


if __name__ == "__main__":
    main()
