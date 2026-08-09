"""
Abstract length validation (#137).

Keeps single-character or otherwise unusably short input from ever
reaching the Research Interpreter -- suggest_concepts()/detect_fields()
have no minimum-length guard of their own and would just produce noise
from too little text to say anything meaningful about. The bar here is
deliberately low (not "is this a good abstract"): real abstracts run
100+ words, so this only catches input that plainly isn't one.
"""

MIN_CHARS = 30
MIN_WORDS = 5


def is_too_short(abstract):
    abstract = (abstract or "").strip()
    if not abstract:
        return False  # empty is its own "empty" state, not a validation error
    return len(abstract) < MIN_CHARS or len(abstract.split()) < MIN_WORDS
