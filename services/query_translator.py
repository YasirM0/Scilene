"""
Translates a user query to English where we can do it reliably, before
it reaches services/semantic_search.py's English-only "en" model
(all-MiniLM-L12-v2).

Indonesian: dictionary lookup against data/indonesian_academic_dict.json
(913 real academic terms, built from this project's own index_terms
data via Helsinki-NLP/opus-mt-en-id, manually spot-checked -- see
docs/experiments/embedding_benchmarks.md's translation A/B test).
Unknown terms pass through untranslated; all-MiniLM-L12-v2 still
handles whatever's left via cross-lingual/loanword overlap, just with
lower confidence than a matched term.

Arabic translation deferred — ctranslate2/Argos exceed 512MB
RAM budget. Arabic users should search in English for now.
Re-enable when dyno upgraded or translation extracted to
a separate worker service. (Quality was genuinely excellent --
correctly translated cases Helsinki-NLP/opus-mt-ar-en mangled or
returned empty for -- this is a deployment constraint, not a quality
rejection.)
"""

import json
import re
from pathlib import Path

from langdetect import detect, DetectorFactory, LangDetectException

DetectorFactory.seed = 0  # langdetect is non-deterministic by default without this

# In Arabic, not English -- a user who searched in Arabic can't
# necessarily read an English error explaining that. "سطح المكتب"
# ("desktop", the standard Arabic computing term used identically
# across Windows/macOS/Linux localizations) verified in isolation
# against Argos's ar->en model, which is why it renders oddly if
# ever back-translated ("office surface") -- a known weakness of
# that specific reverse direction on this idiom, not a sign the
# Arabic here is wrong.
ARABIC_DESKTOP_MESSAGE = (
    "البحث باللغة العربية متاح في تطبيق Scilene لسطح المكتب. "
    "يرجى البحث باللغة الإنجليزية في النسخة الإلكترونية، "
    "أو تنزيل تطبيق سطح المكتب للحصول على دعم كامل للغة العربية."
)


class ArabicNotSupportedOnline(Exception):
    """
    Arabic search requires the Scilene desktop app.
    The online version supports English and Indonesian only.
    RAM constraints prevent loading the Arabic translation
    model on the hosted server.
    """
    pass

# Load Indonesian dictionary once at module level
_DICT_PATH = Path(__file__).parent.parent / "data" / "indonesian_academic_dict.json"
_ID_DICT: dict = {}


def _load_dict():
    global _ID_DICT
    if not _ID_DICT and _DICT_PATH.exists():
        raw = json.loads(_DICT_PATH.read_text(encoding="utf-8"))
        # Stored as {indonesian: english}; lowercase keys for
        # case-insensitive lookup against a lowercased query below.
        _ID_DICT = {k.lower(): v for k, v in raw.items()}


_load_dict()


def _dict_translate_id(text: str) -> str:
    """
    Translate an Indonesian query using dictionary lookup. Unknown
    terms pass through untranslated (all-MiniLM-L12-v2 handles them).

    Matches on WORD BOUNDARIES (\\b), not raw substrings -- a plain
    str.replace() would also match "seni" inside an unrelated word
    like "kesenian", silently corrupting it. Longest entries are tried
    first so a multi-word phrase ("machine learning") is matched
    whole before any of its individual words get replaced separately.
    """
    result = text.lower()
    for src, tgt in sorted(_ID_DICT.items(), key=lambda x: len(x[0]), reverse=True):
        result = re.sub(rf"\b{re.escape(src)}\b", tgt, result)
    return result


def translate_query(text: str) -> tuple[str, str]:
    """
    Translate a user query to English if we can do it reliably.

    Returns:
        (translated_text, detected_language)

    Language codes: "en", "ar", "id", "unknown"
    """
    if not text or not text.strip():
        return text, "en"

    try:
        lang = detect(text)
    except LangDetectException:
        return text, "unknown"

    if lang == "id":
        return _dict_translate_id(text), "id"

    if lang == "ar":
        raise ArabicNotSupportedOnline(ARABIC_DESKTOP_MESSAGE)

    # English or anything else: pass through
    return text, lang


def supported_languages() -> dict:
    """What translate_query() can actually do per language, for
    anything upstream (UI hints, docs) that wants to say so honestly
    rather than imply uniform support."""
    return {
        "en": {"status": "full", "platform": "web+desktop"},
        "id": {"status": "dictionary", "platform": "web+desktop"},
        "ar": {"status": "desktop_only", "platform": "desktop"},
    }


if __name__ == "__main__":
    # Quick smoke test
    tests = [
        "machine learning natural language processing",
        "biologi kelautan ekosistem pesisir",
        "pembelajaran mesin dan kecerdasan buatan",
    ]
    for t in tests:
        result, lang = translate_query(t)
        print(f"[{lang}] {t[:40]:<40} -> {result}")

    try:
        translate_query("الصحة العامة والوبائيات")
    except ArabicNotSupportedOnline as e:
        print(f"[ar] Arabic query → desktop prompt: {e}")

    print("\nSupported: English (full), Indonesian (dictionary)")
    print("Arabic: pass-through only — search in English for now")
