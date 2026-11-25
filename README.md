# limd

Markdown-to-PDF CV toolkit with helpers for tailoring a CV to a job description.

You keep your CV as a Markdown file, and `limd` renders it to a styled PDF (WeasyPrint). Optional helpers convert PDFs back to Markdown, score a CV against a job posting with an LLM, and fetch your LinkedIn profile.

## Requirements

- Python 3.12+ and [uv](https://docs.astral.sh/uv/)
- [Task](https://taskfile.dev/) (`brew install go-task`)
- WeasyPrint system libraries (macOS: `brew install pango`)
- Optional:
  - [LM Studio](https://lmstudio.ai/) serving a model on `http://localhost:1234/v1`, for `llm:compact` and `llm_match.py`
  - [Codex CLI](https://github.com/openai/codex) or Gemini CLI, for `cv:generate` and `cv:match`
  - `pandoc`, for `pdf:pandoc`

## Setup

```bash
task install        # uv sync
task pdf:fonts      # download the open-licensed fonts (Inter, Playfair Display, Outfit)
cp .env.example .env  # only needed for the LinkedIn fetch
```

## Bring your own data

Personal files are git-ignored and are not part of this repo. Create your own:

| Path | Purpose |
|------|---------|
| `assets/generic-cv.md` | Your CV source (see format below) |
| `assets/images/photo.png` | Optional profile photo for the CV sidebar (or set `photo:` in the front matter) |
| `assets/jobs/<slug>.txt` or `.md` | Job descriptions used by `cv:generate` / `cv:match` |
| `agents.md`, `career.md`, `assets/generic-li.md`, `assets/about.md`, `assets/reference-cv.md` | Instructions and context read by the `cv:generate` / `cv:match` prompts |

### CV format

```markdown
---
photo: assets/images/photo.png   # optional
phone: "+00 000 000 000"
email: you@example.com
linkedin: www.linkedin.com/in/you
website: example.com
github: github.com/you
location: City, Country
---

# Your Name

Headline | Specialty | Specialty

## Professional Summary
...

## Experience

### Employer
#### Role title
Jan 2020 – Present {#period}
City, Country {#place}

- Bullet
- Bullet

## Education {#sidebar}
...
```

- Front matter fields feed the sidebar contact block.
- `{#period}` moves the date into the employer heading, and `{#place}` lines are dropped from the PDF.
- Any `##` section tagged `{#sidebar}` is rendered in the left sidebar.

## Usage

| Task | What it does |
|------|--------------|
| `task pdf:cv input=assets/generic-cv.md` | Render a Markdown file to `dist/pdf/<name>.pdf` |
| `task pdf:pandoc input=in.md output=out.pdf` | Alternative render via Pandoc and `src/pdf/styles/prolab.css` |
| `task pdf:fonts` | Download open-licensed fonts into `assets/fonts/` |
| `task convert:md -- --input cv.pdf` | Convert PDF(s) to Markdown (`--engine pymupdf\|unstructured`) |
| `task cv:generate -- --job <slug>` | Tailor the CV to `assets/jobs/<slug>.*` with Codex; writes `assets/generated/<slug>-cv.md` and `<slug>-report.md` |
| `task cv:match -- --job <slug> [--agent gemini\|codex]` | Score the generated CV against the job description |
| `task llm:compact -- --input file.md` | Compact a Markdown file to plain text with a local LLM |
| `task profile -- --profile <id>` | Fetch a LinkedIn profile as JSON into `li/` (needs `.env` credentials) |

## Layout

```
src/pdf/       Markdown -> PDF builder, Jinja template, CSS
src/convert/   PDF -> Markdown
src/llm/       Local-LLM helpers (LM Studio)
scripts/       Codex / Gemini wrappers for tailoring and matching
format.md      Typography spec used by the CV stylesheet
```

## Tests

```bash
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib uv run python -m unittest discover tests
```

## Known limitations

- The Motiva Sans font used by `cv.css` is commercial and not included. Without it the PDF falls back to a generic sans-serif. Add your own files under `assets/fonts/Motiva/` or change the `@font-face` rules in `src/pdf/templates/cv.css`.
- The LinkedIn fetch (`src/test_api.py`) depends on API scopes LinkedIn may not grant to new apps.
