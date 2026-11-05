import re


def normalize(s: str) -> str:
    return s.lower().replace("’", "'").replace("‘", "'")


def has_term(text: str, term: str) -> bool:
    """True if `term` starts at a word boundary in `text` ("sync" matches "syncing", not "async")."""
    return re.search(r"(?<![a-z0-9])" + re.escape(term), text) is not None
