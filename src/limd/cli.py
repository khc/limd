"""`limd` command line: import, build, tailor and match CVs and LinkedIn profiles."""

import importlib
import os
import sys

# command path -> (module, function). Modules are imported lazily so --root can set LIMD_ROOT first.
COMMANDS = {
    ("import", "linkedin-export"): ("limd.linkedin.export_import", "main"),
    ("import", "pdf"): ("limd.linkedin.pdf_import", "main"),
    ("cv", "build"): ("limd.pdf.build", "main"),
    ("tailor",): ("limd.llm.tailor", "main_tailor"),
    ("match",): ("limd.llm.tailor", "main_match"),
    ("compact",): ("limd.llm.llm_compact", "main"),
    ("convert",): ("limd.convert.pdf_to_md", "main"),
    ("fonts",): ("limd.pdf.fonts", "main"),
    ("normalize",): ("limd.pdf.normalize", "main"),
}
HELP = {
    "import linkedin-export": "import your own profile from LinkedIn's data-export ZIP",
    "import pdf": "import a LinkedIn profile saved as PDF",
    "cv build": "render a Markdown CV to PDF",
    "tailor": "tailor your master CV to applications/<company>/job.md",
    "match": "score applications/<company>/cv.md against the job",
    "compact": "compact a Markdown file with an LLM",
    "convert": "convert PDF(s) to Markdown",
    "fonts": "download the open-licensed PDF fonts",
    "normalize": "normalize Markdown heading levels",
}


def usage() -> str:
    rows = "\n".join(f"  {name:<24}{text}" for name, text in HELP.items())
    return f"usage: limd [--root DIR] <command> [options]\n\n{__doc__}\n\ncommands:\n{rows}\n\nRun `limd <command> --help` for a command's options."


def resolve(argv: list[str]) -> tuple[tuple[str, ...], list[str]] | None:
    for size in (2, 1):
        if tuple(argv[:size]) in COMMANDS:
            return tuple(argv[:size]), argv[size:]
    return None


def main(argv: list[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["--root"] and len(argv) > 1:
        os.environ["LIMD_ROOT"] = argv[1]
        argv = argv[2:]
    elif argv[:1] and argv[0].startswith("--root="):
        os.environ["LIMD_ROOT"] = argv.pop(0).split("=", 1)[1]

    command = resolve(argv)
    if command is None:
        print(usage(), file=sys.stderr if argv and argv[0] not in ("-h", "--help") else sys.stdout)
        sys.exit(2 if argv and argv[0] not in ("-h", "--help") else 0)
    path, rest = command
    module, function = COMMANDS[path]
    getattr(importlib.import_module(module), function)(rest)


if __name__ == "__main__":
    main()
