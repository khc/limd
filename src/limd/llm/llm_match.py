"""Score a CV against a job description with an LLM backend."""

import json

from limd.llm.backends import Backend
from limd.llm.markdown_text import strip_markdown
from limd.paths import PROMPTS_DIR


def match_with_llm(backend: Backend, cv_text: str, job_text: str) -> str:
    system = (PROMPTS_DIR / "match.md").read_text(encoding="utf-8")
    user = f"Job Offer:\n{strip_markdown(job_text)}\n\n---\n\nCV:\n{strip_markdown(cv_text)}"
    return backend.complete(system, user, max_tokens=800)


def parse_match_json(response: str) -> dict | None:
    text = response.strip()
    if text.startswith("```"):
        text = text.strip("`").removeprefix("json").strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def format_match(company: str, response: str) -> str:
    result = parse_match_json(response)
    if result is None:
        return f"# Match: {company}\n\nThe model did not return valid JSON. Raw response:\n\n{response}\n"
    lines = [f"# Match: {company}", "", f"Score: {result.get('match_score', '?')}/100", "", str(result.get("summary", ""))]
    for title, key in (("Strengths", "strengths"), ("Gaps", "gaps"), ("Quick fixes", "quick_fixes"), ("Missing keywords", "missing_keywords")):
        items = result.get(key) or []
        if items:
            lines += ["", f"## {title}", ""] + [f"- {item}" for item in items]
    return "\n".join(lines) + "\n"
