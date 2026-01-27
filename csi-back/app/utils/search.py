import re

HIGHLIGHT_MERGE_PATTERN = re.compile(r'</em>(\s*)<em>')

def merge_highlight_tags(text: str | None) -> str | None:
    if not text:
        return text
    return HIGHLIGHT_MERGE_PATTERN.sub(r'\1', text)
