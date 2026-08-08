"""
Deterministic language detection (#89).

NOT an LLM/AI call -- langdetect is a statistical n-gram model (a
pure-Python port of Google's language-detection library), seeded for
reproducibility. It only ever pre-selects a journal-language filter
checkbox; an undetected or unsupported language just means no
pre-selection, never an error, and the user can always change the
selection manually (docs/RESEARCH_INTERPRETER.md's "never interrupt,
always let the user override" pattern applies here too).
"""

from langdetect import detect, DetectorFactory, LangDetectException

DetectorFactory.seed = 0  # langdetect is non-deterministic by default without this

# ISO 639-1 code -> the exact label used in web.search_presentation's
# LANGUAGE_OPTIONS and the `journals.languages` filter values.
SUPPORTED_LANGUAGES = {
    "en": "English",
    "ar": "Arabic",
    "id": "Indonesian",
}


def detect_language(text):
    """
    Returns "English"/"Arabic"/"Indonesian" if confidently one of the
    three supported languages, else None -- covers "not enough text",
    "detection failed", and "detected a language we don't filter by"
    identically, since the caller treats all three the same way (skip
    pre-selection).
    """
    if not text or not text.strip():
        return None

    try:
        code = detect(text)
    except LangDetectException:
        return None

    return SUPPORTED_LANGUAGES.get(code)
