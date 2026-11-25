import argparse
import sys
import glob
import re
from pathlib import Path

def convert_with_pymupdf(pdf_path: Path) -> str:
    try:
        import pymupdf4llm
    except ImportError:
        raise ImportError("pymupdf4llm not found. Run 'uv add pymupdf4llm'.")
    
    md_text = pymupdf4llm.to_markdown(str(pdf_path))
    
    # Remove placeholders like **==> picture [455 x 42] intentionally omitted <==**
    # and potential trailing whitespace/multiple newlines left after removal
    md_text = re.sub(r'\n?\*\*==> picture \[.*?\] intentionally omitted <==\*\*\n?', '\n', md_text)
    
    return md_text.strip() + "\n"

def convert_with_unstructured(pdf_path: Path) -> str:
    try:
        from unstructured.partition.pdf import partition_pdf
    except ImportError:
        raise ImportError("unstructured[pdf] not found. Run 'uv add \"unstructured[pdf]\"'.")
    
    print(f"Partitioning PDF with unstructured (this may take a while, especially on first run)...")
    elements = partition_pdf(filename=str(pdf_path))
    
    # Simple conversion of elements to markdown-like text
    return "\n\n".join([str(el) for el in elements])

def convert_pdf_to_md(pdf_path: Path, output_path: Path = None, engine: str = "pymupdf", force: bool = False) -> Path:
    """
    Converts a PDF file to Markdown using the specified engine.
    """
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    if output_path is None:
        output_path = pdf_path.with_suffix(".md")

    if output_path.exists() and not force:
        raise FileExistsError(f"{output_path} already exists; use --force to overwrite")

    print(f"Converting {pdf_path} to {output_path} using engine '{engine}'...")
    
    if engine == "pymupdf":
        md_text = convert_with_pymupdf(pdf_path)
    elif engine == "unstructured":
        md_text = convert_with_unstructured(pdf_path)
    else:
        raise ValueError(f"Unknown engine: {engine}")
    
    output_path.write_text(md_text, encoding="utf-8")
    return output_path

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Convert PDF to Markdown using various engines.")
    parser.add_argument("--input", nargs='+', required=True, help="Path to the input PDF file(s). Supports wildcards and multiple files.")
    parser.add_argument("--output", help="Path to the output Markdown file or directory. Defaults to the input with a .md suffix.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing output files.")
    parser.add_argument("--engine", choices=["pymupdf", "unstructured"], default="pymupdf", help="Conversion engine to use.")

    args = parser.parse_args(argv)

    input_files = [
        Path(match)
        for pattern in args.input
        for match in sorted(glob.glob(pattern, recursive=True))
        if Path(match).is_file() and Path(match).suffix.lower() == ".pdf"
    ]

    if not input_files:
        print(f"No files matched the input pattern(s).", file=sys.stderr)
        sys.exit(1)

    failed = False
    for pdf_path in input_files:
        # Determine output path for this specific file
        current_output_path = None
        if args.output:
            out_p = Path(args.output)
            if out_p.is_dir():
                current_output_path = out_p / pdf_path.with_suffix(".md").name
            elif len(input_files) > 1:
                # If multiple inputs and output is a file, we force it to be a directory or append to it?
                # Standard behavior: if multiple inputs, output should be a directory.
                if not out_p.exists():
                    out_p.mkdir(parents=True, exist_ok=True)
                    current_output_path = out_p / pdf_path.with_suffix(".md").name
                else:
                    print(f"Warning: Multiple inputs provided but output '{args.output}' is an existing file. Skipping {pdf_path}.", file=sys.stderr)
                    continue
            else:
                current_output_path = out_p
        
        try:
            final_path = convert_pdf_to_md(pdf_path, current_output_path, engine=args.engine, force=args.force)
            print(f"Successfully converted: {final_path}")
        except Exception as e:
            print(f"Error converting {pdf_path}: {e}", file=sys.stderr)
            failed = True

    if failed:
        sys.exit(1)

if __name__ == "__main__":
    main()
