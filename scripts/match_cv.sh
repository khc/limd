#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
JOBS_DIR="$ROOT_DIR/assets/jobs"
GENERATED_DIR="$ROOT_DIR/assets/generated"

job_slug=""
agent="gemini"

usage() {
  cat <<'EOF'
Usage: task cv:match -- --job <slug> [--agent gemini|codex]

Required:
  --job       Job slug. The script resolves assets/jobs/<slug>.txt or assets/jobs/<slug>.md

Optional:
  --agent     Analysis agent to use: gemini or codex (default: gemini)
EOF
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --job)
      shift
      [[ $# -gt 0 ]] || usage
      job_slug="$1"
      ;;
    --agent)
      shift
      [[ $# -gt 0 ]] || usage
      agent="$1"
      ;;
    -h|--help)
      usage
      ;;
    *)
      usage
      ;;
  esac
  shift
done

[[ -n "$job_slug" ]] || usage

case "$agent" in
  gemini|codex) ;;
  *)
    echo "Unsupported --agent value: $agent" >&2
    echo "Expected: gemini or codex" >&2
    exit 1
    ;;
esac

# Resolve job file
if [[ -f "$JOBS_DIR/${job_slug}.txt" ]]; then
  job_path="$JOBS_DIR/${job_slug}.txt"
elif [[ -f "$JOBS_DIR/${job_slug}.md" ]]; then
  job_path="$JOBS_DIR/${job_slug}.md"
else
  echo "Job description file not found for slug '$job_slug' in $JOBS_DIR" >&2
  exit 1
fi

cv_path="$GENERATED_DIR/${job_slug}-cv.md"
if [[ ! -f "$cv_path" ]]; then
  echo "Generated CV not found for slug '$job_slug' at $cv_path" >&2
  exit 1
fi

# Prepare the prompt
prompt_file="$(mktemp)"
output_file="$(mktemp)"
codex_log_file="$(mktemp)"
trap 'rm -f "$prompt_file" "$output_file" "$codex_log_file"' EXIT

cat > "$prompt_file" <<EOF
Use the repository instructions in agents.md and the strategic positioning in career.md.

Analyze the match between the provided Job Description and the tailored CV.
Provide a high-signal Markdown match report.

Evaluate the CV against both:
- the specific job description
- the Engineering Manager CV standards and positioning rules defined in the repository instructions

When judging the CV, pay attention to:
- clarity of Engineering Manager positioning
- visible leadership scope and scale
- technical credibility without overstating hands-on depth
- truthful treatment of early-stage work
- recruiter scanability, including effective selective bolding and readable emphasis
- alignment between the role requirements and the CV's wording, ordering, and emphasis

First, provide a short overview paragraph summarizing the overall fit and any major gaps.
Then, provide a Markdown table with exactly these columns: "Area" and "Rating".
The areas must be: "Clarity", "Leadership", "Technical depth", "Credibility", and "Recruiter scan".
Ratings should be expressed as percentages (e.g., 95%).
Finally, provide up to 3 concise bullet points with specific, actionable suggestions for improving the CV for this specific role.

Keep the report concise and practical. Do not rewrite the CV.

Repository instructions:
$(cat "$ROOT_DIR/agents.md")

Strategic notes:
$(cat "$ROOT_DIR/career.md")

Job Description:
$(cat "$job_path")

CV:
$(cat "$cv_path")

Output the overview paragraph, followed by the Markdown table, followed by the improvement bullet points.
EOF

echo "Matching CV for job: $job_path"
echo "CV: $cv_path"
echo "Agent: $agent"

if [[ "$agent" == "gemini" ]]; then
  gemini -m gemini-3.1-pro-preview -p "$(cat "$prompt_file")" > "$output_file"
else
  codex exec \
    -C "$ROOT_DIR" \
    --skip-git-repo-check \
    -m gpt-5.4 \
    -c 'model_reasoning_effort="high"' \
    --color never \
    -o "$output_file" \
    < "$prompt_file" \
    > "$codex_log_file" 2>&1 || {
      cat "$codex_log_file" >&2
      exit 1
    }
fi

if command -v mdcat >/dev/null 2>&1; then
  mdcat "$output_file"
else
  cat "$output_file"
fi
