import re

def normalize_whitespace(text: str) -> str:
    """
    Replaces multiple whitespace characters with a single space
    and removes leading/trailing whitespace.
    """
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def remove_page_markers(text: str) -> str:
    """
    Removes common page number patterns from text (e.g., 'หน้า 1', '- 2 -').
    This is specifically tailored for Thai legal documents.
    """
    # Pattern for "หน้า X" (Page X) possibly surrounded by spaces
    text = re.sub(r'^\s*หน้า\s*\d+\s*$', '', text, flags=re.MULTILINE)
    # Pattern for "- X -"
    text = re.sub(r'^\s*-\s*\d+\s*-\s*$', '', text, flags=re.MULTILINE)
    # Pattern for just a number on a line, which is often a page number
    text = re.sub(r'^\s*\d+\s*$', '', text, flags=re.MULTILINE)
    return text

def clean_text_pipeline(raw_text: str) -> str:
    """
    Runs the raw text through a series of cleaning functions.
    """
    if not isinstance(raw_text, str):
        return raw_text

    text = remove_page_markers(raw_text)
    text = normalize_whitespace(text)
    # This regex removes lines that became empty after page marker removal
    text = re.sub(r'^\s*$', '', text, flags=re.MULTILINE)
    # Collapse multiple newlines into a maximum of two
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()
