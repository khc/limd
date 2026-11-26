# limd

A toolkit for fine-tuning your CV and LinkedIn profile.

- Keep your CV as Markdown and render it to a styled PDF.
- Import your own LinkedIn profile from LinkedIn's data export, and other people's profiles from a "Save to PDF" file.
- Tailor your master CV to a job description and score the match with the LLM of your choice (Claude Code, Codex CLI or Gemini CLI).

Your personal data stays in two git-ignored folders, `profile/` and `applications/`, so the repo itself is safe to share. A fake sample lives in `examples/`.

## Requirements

- Python 3.12+ and [uv](https://docs.astral.sh/uv/)
- WeasyPrint system libraries (macOS: `brew install pango`)
- For tailoring and matching: the `claude`, `codex` or `gemini` CLI, installed and signed in

## Install

```bash
uv sync
uv run limd fonts      # download the open-licensed fonts (Inter, Playfair Display, Outfit, Figtree)
```

On macOS, WeasyPrint needs `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib`; the Taskfile sets it for you (`task test`, `task limd -- ...`).

## Try it with the example profile

```bash
uv run limd --root examples cv build --input profile/cv.md     # -> examples/dist/pdf/cv.pdf
uv run limd --root examples tailor acme --backend claude       # -> examples/applications/acme/cv.md + report.md
uv run limd --root examples match acme --backend claude        # -> examples/applications/acme/match.md
```

## Workflow

### 1. Create your master CV

```bash
mkdir -p profile
cp examples/profile/cv.md profile/cv.md          # start from the sample, then replace it with your own content
cp ~/Pictures/me.png profile/photo.png           # optional square photo for the sidebar
uv run limd cv build --input profile/cv.md       # -> dist/pdf/cv.pdf
```

On macOS, if the build fails with `cannot load library 'libgobject-2.0-0'`, run `brew install pango` and prefix the command with `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib` (or run it through `task limd -- cv build --input profile/cv.md`).

Edit `profile/cv.md`, rebuild and open `dist/pdf/cv.pdf`; repeat until it looks right. The template is A4 and works best at one or two pages. If you have a LinkedIn profile, import it first (see [LinkedIn import](#linkedin-import)) and copy what you need from `profile/linkedin.md` into the CV. The `pdf-analyse` skill in step 3 can check the layout for you.

### 2. Write your LinkedIn profile

`profile/linkedin.md` is plain Markdown you copy section by section into LinkedIn (`## Headline`, `## About`, `## Experience`, ...). It should tell the same story as the CV in a more conversational voice, with the same dates, titles and claims. See `examples/profile/linkedin.md`. `limd` never writes to LinkedIn; you paste the text yourself.

### 3. Tweak with the analysis skills

The repo ships three [Claude Code skills](https://docs.claude.com/en/docs/claude-code/skills) in `.claude/skills/`. Open Claude Code in this repo and ask in plain language:

| Skill | Ask for | What it does |
|---|---|---|
| `cv-analyse` | "analyse my CV" | Ranked fixes for `profile/cv.md` (or a tailored CV) against your `rules.md`, `strategy.md` and benchmarks |
| `li-analyse` | "analyse my LinkedIn profile" | Headline, About, keywords and visibility advice, and consistency with the CV |
| `pdf-analyse` | "check the PDF" | Layout checks (broken words, page breaks, dangling lines, overflow) plus page images and an ATS reading-order check |

Add benchmark profiles with `limd import pdf` and a `profile/reference-cv.md` for the skills to compare against. The skills report first and only edit when you agree. They may search the web for current best practice, with generic queries that never include your details. Everything they read is sent to the model you are using, so read [Privacy](#privacy).

### 4. Tailor for a job

```bash
mkdir -p applications/acme
# save the job description as applications/acme/job.md
uv run limd tailor acme --backend claude         # -> applications/acme/cv.md + report.md
uv run limd match acme --backend claude          # -> applications/acme/match.md (score vs the job)
uv run limd cv build --input applications/acme/cv.md     # -> dist/acme/cv.pdf
```

Read `report.md` and edit `applications/acme/cv.md` before you send it; the model's output is a draft. Run `pdf-analyse` on the result to check the layout.

## Your data

```
profile/                  you (private)
  cv.md                   master CV (required for tailoring)
  linkedin.md  about.md  rules.md  strategy.md  reference-cv.md   optional context for the LLM
  photo.png               optional CV photo (or `photo:` in the front matter)
  people/<slug>.md|json   profiles imported from PDF
applications/<company>/   one folder per application (private)
  job.md                  the job description (job.txt also works)
  cv.md  report.md        written by `limd tailor`
  match.md                written by `limd match`
dist/                     PDFs (dist/<company>/ for files inside applications/<company>/)
```

`profile/rules.md` is where your own rules live, for example "never invent metrics" or how strongly to word things. It is sent to the model with every tailoring request.

### CV format

```markdown
---
phone: "+00 000 000 000"           # all fields are optional
email: you@example.com
linkedin: www.linkedin.com/in/you
website: www.example.com
github: github.com/you
location: City, Country
photo: profile/photo.png           # defaults to profile/photo.png
---

# Your Name

Headline | Specialty

## Experience

### Employer
#### Role title
Jan 2020 - Present {#period}
City, Country {#place}

- Bullet

## Education {#sidebar}
```

`{#period}` moves the date into the employer heading, `{#place}` lines are dropped from the PDF, and `{#sidebar}` sections render in the left column. See `examples/profile/cv.md` for a complete one-page CV.

## LinkedIn import

LinkedIn offers no public API for reading profiles, and automating the site breaks its Terms of Service, so `limd` never scrapes it. Two supported routes:

- **Your own profile:** LinkedIn → Settings → Data privacy → *Get a copy of your data*, select the profile data, download the ZIP, then:

  ```bash
  uv run limd import linkedin-export ~/Downloads/Basic_LinkedInDataExport.zip     # -> profile/linkedin.json + linkedin.md
  ```

  The importer reads `Profile.csv`, `Positions.csv`, `Education.csv` and `Skills.csv` from anywhere in the ZIP and skips any that are missing. LinkedIn does not document the file layout, so if your archive looks different, please open an issue.
- **Someone else's profile:** open it in your browser, choose *More → Save to PDF*, then:

  ```bash
  uv run limd import pdf Profile.pdf --name jane-doe     # -> profile/people/jane-doe.md + .json
  ```

Existing output is never overwritten unless you pass `--force`.

The export holds far more than your profile (connections, messages, email addresses). Keep the ZIP outside the repo or in `profile/`; `*.zip` and `*.csv` are git-ignored as a safety net.

## Commands

| Command | What it does |
|---|---|
| `limd import linkedin-export <zip>` | Import your own profile from LinkedIn's data export |
| `limd import pdf <file> --name <slug>` | Import a LinkedIn profile saved as PDF |
| `limd cv build --input <file>` | Render a Markdown CV to PDF |
| `limd tailor <company> [--backend] [--model] [--force]` | Tailor `profile/cv.md` to `applications/<company>/job.md` |
| `limd match <company> [--backend] [--model] [--force]` | Score `applications/<company>/cv.md` against the job |
| `limd compact --input <file>` | Compact a Markdown file with an LLM |
| `limd convert --input <pdf>` | Convert PDF(s) to Markdown |
| `limd fonts` | Download the PDF fonts |

Use `--root <dir>` (or `LIMD_ROOT`) to point `limd` at a different data folder. With the Taskfile: `task limd -- --root examples cv build --input profile/cv.md`.

## Privacy

`limd tailor`, `match` and `compact` send your CV, profile text, rules and the job description to the tool behind the backend you choose (`claude`, `codex` or `gemini`), under that provider's terms. Pick the backend accordingly. Job descriptions are untrusted text, so the backends run from an empty temporary directory with tools disabled where the CLI allows it, but you should still read `cv.md` and `report.md` before building or sending them.

## Backends

`--backend claude` (default), `codex` or `gemini`. Each takes a prompt and returns text; `src/limd/llm/backends.py` is about 60 lines if you want to add another.

## Development

```bash
task test      # DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib uv run python -m unittest discover tests
```

PDF rendering only loads fonts from `assets/fonts/`, images from `profile/`, and files from `src/limd/pdf/templates/`; remote URLs and other paths are blocked.

## Known limitations

- The default `cv.css` uses Figtree (open license, fetched by `limd fonts`). To use another font, edit the `@font-face` rules in `src/limd/pdf/templates/cv.css` and add the files under `assets/fonts/`.
- The LinkedIn export and PDF parsers are tolerant but based on third-party descriptions of the formats.
