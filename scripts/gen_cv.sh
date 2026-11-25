#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_DIR="$ROOT_DIR/assets/generated"
JOBS_DIR="$ROOT_DIR/assets/jobs"

job_slug=""
job_path=""

usage() {
  cat <<'EOF'
Usage: task gen:cv -- --job <slug>

Required:
  --job     Job slug. The script will resolve assets/jobs/<slug>.txt or assets/jobs/<slug>.md
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --job)
      shift
      [[ $# -gt 0 ]] || { echo "Missing value for --job" >&2; usage; exit 1; }
      job_slug="$1"
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
  shift
done

[[ -n "$job_slug" ]] || { echo "--job is required" >&2; usage; exit 1; }

if [[ -f "$JOBS_DIR/${job_slug}.txt" ]]; then
  job_path="$JOBS_DIR/${job_slug}.txt"
elif [[ -f "$JOBS_DIR/${job_slug}.md" ]]; then
  job_path="$JOBS_DIR/${job_slug}.md"
else
  echo "Job description file not found for slug '$job_slug' in $JOBS_DIR" >&2
  echo "Expected one of:" >&2
  echo "  $JOBS_DIR/${job_slug}.txt" >&2
  echo "  $JOBS_DIR/${job_slug}.md" >&2
  exit 1
fi

mkdir -p "$OUTPUT_DIR"

job_path="$(cd "$(dirname "$job_path")" && pwd)/$(basename "$job_path")"
output_path="$OUTPUT_DIR/${job_slug}-cv.md"
report_path="$OUTPUT_DIR/${job_slug}-report.md"

last_message_path="${output_path%.md}.codex.txt"
prompt_file="$(mktemp)"
codex_log_file="$(mktemp)"
trap 'rm -f "$prompt_file" "$codex_log_file"' EXIT

cat > "$prompt_file" <<EOF
Use the repository instructions in agents.md.

Task:
Generate a job-specific CV Markdown file at:
$output_path

Also generate a companion tailoring report at:
$report_path

Inputs to use:
- agents.md
- career.md
- assets/generic-cv.md
- assets/generic-li.md
- assets/about.md
- assets/reference-cv.md
- $job_path

Requirements:
- only analyze *.md and *.txt source files when creating the CV and report
- explicitly review assets/generic-cv.md and assets/generic-li.md before generating the tailored CV
- tailor the CV specifically to the supplied job description
- keep the structure compatible with assets/generic-cv.md and the PDF renderer
- follow agents.md as the primary instruction source for structure, positioning, formatting, and factual boundaries
- preserve the strategic positioning from career.md unless the job clearly requires a narrower emphasis
- apply best practices for strong Engineering Manager CVs: lead with scope and leadership value, preserve technical credibility, emphasize team leadership / delivery / platform ownership, and avoid reading like an IC-only resume
- keep the Professional Summary to 3-5 lines, about 80 words, and make sure it covers role/seniority, main expertise, scale/domain, and leadership value
- keep recent roles optimized for recruiter scanability, ATS matching, and Engineering Manager expectations
- make scale visible in important recent roles when the evidence exists, for example team span, platform breadth, organizational reach, or business-critical system scope
- use selective bolding to improve scanability across all roles, with denser emphasis in the most relevant recent roles and lighter emphasis in older roles
- preserve the established generic-cv structure, including YAML front matter, heading hierarchy, role layout, PDF markers, sidebar sections, and italicized technology summary lines
- use assets/generic-cv.md as the primary structural and content baseline, and use assets/generic-li.md to refine positioning, phrasing, and emphasis where useful
- preserve factual accuracy; do not invent deliveries, metrics, or scope
- if a project is early-stage, keep that framing explicit
- use assets/about.md when deciding how to present Java and Python background, and do not overstate hands-on depth
- use assets/reference-cv.md only as a benchmark for scannability and keyword density, not as content to copy
- do not modify assets/generic-cv.md or assets/generic-li.md
- write the tailored CV to the target output path
- write a Markdown report to the report path

The report must include:
- a short summary of the target role and what it emphasizes
- the main tailoring changes made to the CV for this job
- which parts of the background align strongly with the job description
- which requirements are only partially aligned or weaker
- any deliberate omissions or downplayed areas to keep the CV accurate

After writing both files, provide a short summary of the tailoring choices.
EOF

echo "Generating CV for job: $job_path"
echo "Output: $output_path"
echo "Report: $report_path"

codex exec \
  -C "$ROOT_DIR" \
  --full-auto \
  --skip-git-repo-check \
  -m gpt-5.4 \
  -c 'model_reasoning_effort="high"' \
  --color never \
  -o "$last_message_path" \
  < "$prompt_file" \
  > "$codex_log_file" 2>&1 || {
    cat "$codex_log_file" >&2
    exit 1
  }

echo "Tailored CV written to: $output_path"
echo "Tailoring report written to: $report_path"
echo "Codex summary written to: $last_message_path"
