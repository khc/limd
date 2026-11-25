import argparse
import sys
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

def compact_with_llm(text: str) -> str:
    """Uses LMStudio API to compact the text."""
    # Connects to default LMStudio local server
    client = OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")
    
    system_prompt = (
        "Rewrite the text into a compact version.\n\n"
        "Rules:\n"
        "- Preserve ALL facts, numbers, technologies, names\n"
        "- Remove repetition, filler, and generic phrases\n"
        "- Use short, dense sentences\n"
        "- No formatting, no markdown\n"
        "- No explanations, no comments\n"
        "- Do NOT add new information\n"
        "- Keep meaning identical\n\n"
        "Compression target:\n"
        "- Reduce length by ~50%\n\n"
        "Output:\n"
        "- Plain text only"
    )
    
    # Estimate tokens: ~4 chars per token. Target 70% of input length max.
    estimated_input_tokens = max(100, len(text) // 4)
    max_tokens_cap = int(estimated_input_tokens * 0.7)
    
    response = client.chat.completions.create(
        model="qwen", # The exact model name often doesn't matter for LMStudio as it uses the loaded one
        messages=[
            {
                "role": "system", 
                "content": system_prompt
            },
            {
                "role": "user", 
                "content": f"Text:\n{text}"
            }
        ],
        temperature=0.2,
        top_p=0.9,
        max_tokens=max_tokens_cap,
        extra_body={"repeat_penalty": 1.15} # Supported by many local backends like llama.cpp via LMStudio
    )
    
    if not response.choices:
        raise ValueError("No response from LLM")
        
    return response.choices[0].message.content.strip()

def main():
    parser = argparse.ArgumentParser(description="Compact a Markdown file using Qwen via LMStudio API, returning a plain text version.")
    parser.add_argument("--input", required=True, help="Path to the input Markdown file")
    parser.add_argument("--output", help="Path to save the output file (prints to stdout if not provided)")
    
    args = parser.parse_args()
    
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: File not found: {args.input}", file=sys.stderr)
        sys.exit(1)
        
    text = input_path.read_text(encoding="utf-8")
    
    # Always strip markdown before sending to LLM
    text = strip_markdown(text)
        
    print("Sending to LMStudio API for compaction...", file=sys.stderr)
    try:
        final_output = compact_with_llm(text)
    except Exception as e:
        print(f"Failed to communicate with LMStudio: {e}", file=sys.stderr)
        sys.exit(1)
        
    if args.output:
        Path(args.output).write_text(final_output, encoding="utf-8")
        print(f"Output saved to {args.output}", file=sys.stderr)
    else:
        print(final_output)

if __name__ == "__main__":
    main()
