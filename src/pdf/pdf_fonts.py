from __future__ import annotations

import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
FONTS_DIR = ROOT / "assets" / "fonts"

# We fetch the raw .ttf files directly from the Google Fonts GitHub repository
# because the fonts.google.com ZIP download endpoints require browser sessions.
# This approach is faster, requires no ZIP extraction, and directly targets the needed files.
DIRECT_URLS = {
    # Inter
    "Inter/Inter-VariableFont_opsz,wght.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/inter/Inter%5Bopsz%2Cwght%5D.ttf",
    "Inter/Inter-Italic-VariableFont_opsz,wght.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/inter/Inter-Italic%5Bopsz%2Cwght%5D.ttf",
    
    # Playfair Display
    "Playfair/Playfair-VariableFont_opsz,wdth,wght.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/playfairdisplay/PlayfairDisplay%5Bwght%5D.ttf",
    "Playfair/Playfair-Italic-VariableFont_opsz,wdth,wght.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/playfairdisplay/PlayfairDisplay-Italic%5Bwght%5D.ttf",
    
    # Outfit
    "Outfit/static/Outfit-ExtraBold.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/outfit/Outfit%5Bwght%5D.ttf",
}

def download_file(url: str, dest: Path) -> None:
    print(f"Downloading to {dest.relative_to(ROOT)}...")
    dest.parent.mkdir(parents=True, exist_ok=True)
    
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as response:
        dest.write_bytes(response.read())

def main() -> None:
    for rel_path, url in DIRECT_URLS.items():
        dest = FONTS_DIR / rel_path
        if dest.exists():
            print(f"Skipping {rel_path}, already exists.")
            continue
        try:
            download_file(url, dest)
        except Exception as e:
            print(f"Failed to download {rel_path}: {e}")

if __name__ == "__main__":
    main()
