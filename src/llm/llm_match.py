import argparse
import sys
import json
from pathlib import Path
from openai import OpenAI
from markdown_it import MarkdownIt

def strip_markdown(text: str) -> str:
    """Uses markdown-it-py to extract plain text from markdown."""
    md = MarkdownIt()
    tokens = md.parse(text)
    
    extracted_text = []
    
    def extract_from_tokens(tokens_list):
        for token in tokens_list:
            if token.type == 'text':
                extracted_text.append(token.content)
            elif token.type in ('softbreak', 'hardbreak'):
                extracted_text.append('\n')
            elif token.type == 'paragraph_close':
                extracted_text.append('\n\n')
            
            if token.children:
                extract_from_tokens(token.children)

    extract_from_tokens(tokens)
    return "".join(extracted_text).strip()

SYSTEM_PROMPT = """You are a strict recruiter evaluating a candidate for an Engineering Manager role.

Compare the CV against the job offer.

Return ONLY valid JSON:
{
  "match_score": 0,
  "summary": "",
  "strengths": [],
  "gaps": [],
  "quick_fixes": [],
  "missing_keywords": []
}

Scoring weights:
- Leadership & people management: 30%
- Delivery / execution ownership: 20%
- Technical depth & architecture: 20%
- Stakeholder collaboration & communication: 15%
- Domain fit: 10%
- Process / agile / hiring / mentoring: 5%

Scoring rules:
- Be strict. Do not inflate scores.
- Penalize missing evidence more than implied capability.
- Prefer explicit leadership examples over senior individual contributor experience.
- Prefer measurable impact over generic claims.
- If a requirement is only partially supported, treat it as a gap.
- Do not reward keyword overlap unless supported by experience.

Output rules:
- summary: max 2 sentences
- strengths: max 5 items, each <= 12 words
- gaps: max 5 items, each <= 12 words
- quick_fixes: max 5 items, each actionable CV edits
- missing_keywords: max 10 items
- No markdown
- No extra text"""

def match_with_llm(cv_text: str, job_text: str) -> str:
    """Uses LMStudio API to compare CV with Job Description and return JSON."""
    client = OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")
    
    user_prompt = f"Job Offer:\n{job_text}\n\n---\n\nCV:\n{cv_text}"
    
    response = client.chat.completions.create(
        model="qwen", # or whatever is loaded in LMStudio
        messages=[
            {
                "role": "system", 
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user", 
                "content": user_prompt
            }
        ],
        temperature=0.2,
        top_p=0.9,
        max_tokens=800,
    )
    
    if not response.choices:
        raise ValueError("No response from LLM")
        
    return response.choices[0].message.content.strip()

def main():
    parser = argparse.ArgumentParser(description="Evaluate CV against a Job Offer using Qwen via LMStudio API.")
    parser.add_argument("--cv", required=True, help="Path to the CV file (Markdown or Text)")
    parser.add_argument("--job", required=True, help="Path to the Job Description file (Markdown or Text)")
    parser.add_argument("--output", help="Path to save the JSON output (prints to stdout if not provided)")
    
    args = parser.parse_args()
    
    cv_path = Path(args.cv)
    job_path = Path(args.job)
    
    if not cv_path.exists():
        print(f"Error: CV file not found: {args.cv}", file=sys.stderr)
        sys.exit(1)
        
    if not job_path.exists():
        print(f"Error: Job file not found: {args.job}", file=sys.stderr)
        sys.exit(1)
        
    cv_text = cv_path.read_text(encoding="utf-8")
    job_text = job_path.read_text(encoding="utf-8")
    
    if cv_path.suffix.lower() == ".md":
        cv_text = strip_markdown(cv_text)
    if job_path.suffix.lower() == ".md":
        job_text = strip_markdown(job_text)
    
    print("Evaluating match via LMStudio API...", file=sys.stderr)
    try:
        match_result = match_with_llm(cv_text, job_text)
    except Exception as e:
        print(f"Failed to communicate with LMStudio: {e}", file=sys.stderr)
        sys.exit(1)
        
    # Attempt to clean up response in case model returned markdown code blocks despite instructions
    if match_result.startswith("```json"):
        match_result = match_result[7:]
    if match_result.startswith("```"):
        match_result = match_result[3:]
    if match_result.endswith("```"):
        match_result = match_result[:-3]
    match_result = match_result.strip()
    
    # Validate JSON
    try:
        parsed_json = json.loads(match_result)
        # Ensure pretty print
        final_output = json.dumps(parsed_json, indent=2)
    except json.JSONDecodeError:
        print("Warning: The model did not return valid JSON. Outputting raw response.", file=sys.stderr)
        final_output = match_result
        
    if args.output:
        Path(args.output).write_text(final_output, encoding="utf-8")
        print(f"Output saved to {args.output}", file=sys.stderr)
    else:
        print(final_output)

if __name__ == "__main__":
    main()
