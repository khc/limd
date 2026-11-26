"""Layout checks for a CV PDF: page fill, stranded headings, split paragraphs, broken words, overflow.

Usage: uv run python .claude/skills/pdf-analyse/check_pdf.py <file.pdf> [--png <dir>] [--dpi 110] [--text]
Prints findings; the agent still has to look at the PNGs for what a script cannot judge.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import fitz

MARGIN_PT = 12 * 72 / 25.4  # @page margin in cv.css
SIDEBAR_EDGE_PT = 150  # sidebar is 40mm wide plus the page margin; main column starts to its right
EMAILISH = re.compile(r"[@/]|www\.|\.(com|pl|org|net|io|dev)\b", re.I)


def lines_of(page: fitz.Page) -> list[dict]:
    out = []
    for b_no, block in enumerate(page.get_text("dict")["blocks"]):
        for line in block.get("lines", []):
            spans = [s for s in line["spans"] if s["text"].strip()]
            if not spans or "".join(s["text"] for s in spans).strip() in {"•", "·", "-", "–"}:
                continue
            out.append({
                "block": b_no, "bbox": line["bbox"], "text": "".join(s["text"] for s in spans).strip(),
                "size": round(spans[0]["size"], 1), "font": spans[0]["font"].split("+")[-1],
            })
    return out


def is_heading(line: dict) -> bool:
    return line["size"] >= 10 or "playfair" in line["font"].lower()


def check_page(n: int, page: fitz.Page, lines: list[dict], findings: list[str]) -> None:
    w, h = page.rect.width, page.rect.height
    body_bottom = h - MARGIN_PT
    main = [l for l in lines if l["bbox"][0] > SIDEBAR_EDGE_PT]
    last = max((l["bbox"][3] for l in main or lines), default=0)
    findings.append(f"[info] page {n}: main column ends at {last:.0f}pt of {body_bottom:.0f}pt usable ({100 * last / body_bottom:.0f}%)")
    for l in lines:
        x0, _, x1, y1 = l["bbox"]
        if x1 > w - MARGIN_PT + 1.5 or x0 < MARGIN_PT - 1.5 or y1 > body_bottom + 1.5:
            findings.append(f"[overflow] page {n}: '{l['text'][:50]}' leaves the margin box")
    by_block: dict[int, list[dict]] = {}
    for l in lines:
        by_block.setdefault(l["block"], []).append(l)
    for ls in by_block.values():
        for a, b in zip(ls, ls[1:]):
            if a["text"].endswith("-") and b["text"][:1].islower():
                tok = a["text"].split()[-1]
                kind = "word-break" if EMAILISH.search(tok) or "." in tok else "hyphen-wrap"
                findings.append(f"[{kind}] page {n}: '{a['text'][-22:]}' / '{b['text'][:18]}'")
            elif EMAILISH.search(a["text"].split()[-1]) and len(b["text"].split()[0]) <= 8 and b["text"][:1].islower() and abs(a["bbox"][0] - b["bbox"][0]) < 1:
                findings.append(f"[word-break] page {n}: address/URL may be split '{a['text'][-24:]}' / '{b['text'][:12]}'")
        for a, b in zip(ls, ls[1:]):
            if len(b["text"]) <= 3 and b["text"].isalnum() and len(a["text"]) > 20:
                findings.append(f"[word-break] page {n}: line is only a fragment '{b['text']}' after '{a['text'][-20:]}'")
        if len(ls) >= 2 and ls[-1]["bbox"][0] > SIDEBAR_EDGE_PT and len(ls[-1]["text"].split()) == 1 and not is_heading(ls[-1]):
            findings.append(f"[widow-word] page {n}: single-word last line '{ls[-1]['text']}' ({ls[0]['text'][:35]}...)")
    for i, a in enumerate(lines):
        for b in lines[i + 1:]:
            if a["block"] != b["block"] and (fitz.Rect(a["bbox"]) & fitz.Rect(b["bbox"])).get_area() > 4:
                findings.append(f"[overlap] page {n}: '{a['text'][:30]}' overlaps '{b['text'][:30]}'")

def check_breaks(pages: list[list[dict]], findings: list[str]) -> None:
    for i in range(len(pages) - 1):
        main_a = sorted((l for l in pages[i] if l["bbox"][0] > SIDEBAR_EDGE_PT), key=lambda l: l["bbox"][1])
        main_b = sorted((l for l in pages[i + 1] if l["bbox"][0] > SIDEBAR_EDGE_PT), key=lambda l: l["bbox"][1])
        if not main_a or not main_b:
            continue
        tail, head = main_a[-1], main_b[0]
        if is_heading(tail):
            findings.append(f"[stranded-heading] page {i + 1} ends with heading '{tail['text'][:40]}' - its content starts on page {i + 2}")
        elif tail["text"][-1:] not in ".!?:)*" and head["text"][:1].islower():
            findings.append(f"[split-paragraph] '{tail['text'][-35:]}' | page {i + 2}: '{head['text'][:35]}'")
        same = [l for l in main_b if l["block"] == head["block"]]
        if len(same) == 1 and not is_heading(head) and head["text"][:1].islower():
            findings.append(f"[widow-line] page {i + 2} starts with one dangling line '{head['text'][:40]}'")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--png", help="directory for page PNGs")
    ap.add_argument("--dpi", type=int, default=110)
    ap.add_argument("--text", action="store_true", help="print plain-text extraction (ATS reading order)")
    args = ap.parse_args()

    doc = fitz.open(args.pdf)
    if not len(doc):
        raise SystemExit("PDF has no pages")
    findings: list[str] = [f"[info] {args.pdf}: {len(doc)} page(s), {doc[0].rect.width:.0f}x{doc[0].rect.height:.0f}pt"]
    fonts = {f[3].split("+")[-1] for p in doc for f in p.get_fonts()}
    findings.append(f"[info] fonts: {', '.join(sorted(fonts))}")
    sizes = {l["size"] for p in doc for l in lines_of(p)}
    if sizes and min(sizes) < 8:
        findings.append(f"[small-text] smallest size {min(sizes)}pt (below 8pt is hard to read in print)")
    pages = [lines_of(p) for p in doc]
    for n, (p, ls) in enumerate(zip(doc, pages), 1):
        check_page(n, p, ls, findings)
    check_breaks(pages, findings)
    print("\n".join(findings))
    problems = [f for f in findings if not f.startswith("[info]")]
    print(f"\n{len(problems)} potential issue(s)")

    if args.png:
        out = Path(args.png)
        out.mkdir(parents=True, exist_ok=True)
        for n, p in enumerate(doc, 1):
            path = out / f"{Path(args.pdf).stem}-p{n}.png"
            p.get_pixmap(dpi=args.dpi).save(path)
            print(f"wrote {path}")
    if args.text:
        print("\n--- plain-text extraction (reading order) ---")
        for n, p in enumerate(doc, 1):
            print(f"## page {n}\n{p.get_text('text')}")


if __name__ == "__main__":
    main()
