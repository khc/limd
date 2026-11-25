from markdown_it import MarkdownIt


def strip_markdown(text: str) -> str:
    """Uses markdown-it-py to extract plain text from markdown."""
    md = MarkdownIt()
    tokens = md.parse(text)
    
    extracted_text = []
    
    def extract_from_tokens(tokens_list):
        for token in tokens_list:
            if token.type in ('text', 'code_inline', 'fence', 'code_block'):
                extracted_text.append(token.content)
            elif token.type in ('softbreak', 'hardbreak'):
                extracted_text.append('\n')
            elif token.type == 'paragraph_close':
                extracted_text.append('\n\n')
            
            if token.children:
                extract_from_tokens(token.children)

    extract_from_tokens(tokens)
    return "".join(extracted_text).strip()
