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

def convert_pdf_to_md(pdf_path: Path, output_path: Path = None, engine: str = "pymupdf") -> Path:
    """
    Converts a PDF file to Markdown using the specified engine.
    """
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    if output_path is None:
        output_path = pdf_path.with_suffix(".md")

    print(f"Converting {pdf_path} to {output_path} using engine '{engine}'...")
    
    if engine == "pymupdf":
        md_text = convert_with_pymupdf(pdf_path)
    elif engine == "unstructured":
        md_text = convert_with_unstructured(pdf_path)
    else:
        raise ValueError(f"Unknown engine: {engine}")
    
    output_path.write_text(md_text, encoding="utf-8")
    return output_path

def main():
    parser = argparse.ArgumentParser(description="Convert PDF to Markdown using various engines.")
    parser.add_argument("--input", nargs='+', required=True, help="Path to the input PDF file(s). Supports wildcards and multiple files.")
    parser.add_argument("--output", help="Path to the output Markdown file or directory. Defaults to input with .md suffix or project assets.")
    parser.add_argument("--project", help="Project slug (e.g., 'nova-brine'). If provided and output is absent, saves to projects/{slug}/assets/.")
    parser.add_argument("--engine", choices=["pymupdf", "unstructured"], default="pymupdf", help="Conversion engine to use.")

    args = parser.parse_args()

    # Resolve all inputs (handle both strings that might contain wildcards and already expanded paths)
    input_files = []
    for pattern in args.input:
        p = Path(pattern)
        if p.is_file():
            input_files.append(p)
            continue

        # Case-insensitive globbing
        import fnmatch
        import re
        import os

        # Split into literal base and wildcard part
        parts = p.parts
        base = Path('.')
        wildcard_parts = []
        found_wildcard = False
        for part in parts:
            if any(c in part for c in "*?[]"):
                found_wildcard = True
            if found_wildcard:
                wildcard_parts.append(part)
            else:
                base = base / part
        
        if wildcard_parts:
            wildcard_pattern = os.path.join(*wildcard_parts)
            regex = re.compile(fnmatch.translate(wildcard_pattern), re.IGNORECASE)
            
            if base.exists() and base.is_dir():
                # Search recursively if ** is in pattern, otherwise stay in base
                search_iterator = base.rglob('*') if '**' in wildcard_pattern else base.iterdir()
                for candidate in search_iterator:
                    try:
                        rel_path = str(candidate.relative_to(base))
                        if regex.match(rel_path) and candidate.is_file():
                            input_files.append(candidate)
                    except (ValueError, Exception):
                        continue

    if not input_files:
        print(f"No files matched the input pattern(s).", file=sys.stderr)
        sys.exit(1)

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
        
        if not current_output_path and args.project:
            project_assets = Path("projects") / args.project / "assets"
            project_assets.mkdir(parents=True, exist_ok=True)
            current_output_path = project_assets / pdf_path.with_suffix(".md").name

        try:
            final_path = convert_pdf_to_md(pdf_path, current_output_path, engine=args.engine)
            print(f"Successfully converted: {final_path}")
        except Exception as e:
            print(f"Error converting {pdf_path}: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
