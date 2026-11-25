"""Compact a Markdown file into dense plain text with an LLM backend."""

import argparse
import sys
from pathlib import Path

from limd.llm.backends import Backend, BackendError, get_backend
from limd.llm.markdown_text import strip_markdown
from limd.paths import PROMPTS_DIR


def compact_with_llm(backend: Backend, text: str) -> str:
    system = (PROMPTS_DIR / "compact.md").read_text(encoding="utf-8")
    estimated_input_tokens = max(100, len(text) // 4)  # ~4 chars per token
    return backend.complete(system, f"Text:\n{text}", max_tokens=int(estimated_input_tokens * 0.7))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="limd compact", description=__doc__)
    parser.add_argument("--input", required=True, help="Path to the input Markdown file")
    parser.add_argument("--output", help="Path to save the output (prints to stdout if not provided)")
    parser.add_argument("--backend", default="claude", help="claude, codex or gemini")
    parser.add_argument("--model", help="Model name passed to the backend")
    args = parser.parse_args(argv)

    input_path = Path(args.input)
    if not input_path.exists():
        sys.exit(f"Error: File not found: {args.input}")
    try:
        text = strip_markdown(input_path.read_text(encoding="utf-8"))
        output = compact_with_llm(get_backend(args.backend, args.model), text)
    except BackendError as error:
        sys.exit(f"Error: {error}")

    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"Output saved to {args.output}", file=sys.stderr)
    else:
        print(output)
