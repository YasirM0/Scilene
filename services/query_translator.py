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

Arabic: real translation via Argos Translate (#150) when its ar->en
package is actually installed in THIS process's environment --
detected at runtime via _argos_translate_ar_en() below, not a separate
"desktop mode" flag. Never installed as a web dependency (see
requirements.txt) -- Argos/ctranslate2's ~530MB+ RAM footprint is
exactly why Arabic stays blocked on the shared Heroku deployment via
ArabicNotSupportedOnline below. A future desktop build that bundles
Argos gets real Arabic translation automatically, with zero code
changes here. Quality is genuinely good but not perfect -- verified
directly: "الذكاء الاصطناعي" ("artificial intelligence") came back as
"Synthetic intelligence", a real, disclosed imperfection, not
something to hide -- still a large improvement over the alternative
(no Arabic search at all).
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


def _argos_translate_ar_en(text: str):
    """
    Real Arabic->English translation via Argos Translate, ONLY if its
    ar->en language package is actually installed here -- see this
    module's docstring. Returns None (never raises) if Argos isn't
    installed, the ar->en package specifically isn't, or translation
    fails for any other reason -- the caller treats that identically
    to "not available in this environment" and falls back to
    ArabicNotSupportedOnline, exactly the pre-Argos behavior.
    """
    try:
        import argostranslate.package
        import argostranslate.translate
    except ImportError:
        return None

    try:
        installed = argostranslate.package.get_installed_packages()
        if not any(p.from_code == "ar" and p.to_code == "en" for p in installed):
            return None
        return argostranslate.translate.translate(text, "ar", "en")
    except Exception:
        return None


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
        translated = _argos_translate_ar_en(text)
        if translated is not None:
            return translated, "ar"
        raise ArabicNotSupportedOnline(ARABIC_DESKTOP_MESSAGE)

    # English or anything else: pass through
    return text, lang


def translate_for_interpretation(text: str) -> str:
    """
    Best-effort English text for services/research_interpreter.py's
    Key Research Focus / Field of Study detection (services/
    focus_detection.py, services/field_detection.py) -- both match
    against English-only vocabulary (journals.keywords/subjects), so a
    raw Indonesian abstract mostly misses entirely. Stress-tested
    directly: applying the same dictionary translation search already
    uses cut Field of Study's miss rate from 61.4% to 28.5% across 295
    real Indonesian abstracts.

    Deliberately NOT translate_query() reused as-is: that function
    raises ArabicNotSupportedOnline when Argos isn't installed, which
    is the right call for an actual search (no results without it) but
    wrong here -- a suggestion panel that also handles Indonesian and
    English shouldn't start hard-failing on Arabic abstracts just
    because it learned to help Indonesian ones. This never raises:
    Indonesian gets the same dictionary translation, everything else
    (English, Arabic, undetectable) passes through unchanged, exactly
    matching this function's behavior before Indonesian support existed.
    """
    if not text or not text.strip():
        return text

    try:
        lang = detect(text)
    except LangDetectException:
        return text

    if lang == "id":
        return _dict_translate_id(text)

    return text


def _has_argos_ar_en() -> bool:
    try:
        import argostranslate.package
    except ImportError:
        return False
    try:
        installed = argostranslate.package.get_installed_packages()
        return any(p.from_code == "ar" and p.to_code == "en" for p in installed)
    except Exception:
        return False


def supported_languages() -> dict:
    """What translate_query() can actually do per language, for
    anything upstream (UI hints, docs) that wants to say so honestly
    rather than imply uniform support. Arabic's status reflects
    whatever's ACTUALLY installed in this process right now -- "full"
    wherever Argos's ar->en package is present (today, that's only a
    build that bundles it, e.g. a future desktop build), "desktop_only"
    on a plain web deployment like this one."""
    return {
        "en": {"status": "full", "platform": "web+desktop"},
        "id": {"status": "dictionary", "platform": "web+desktop"},
        "ar": (
            {"status": "full", "platform": "wherever Argos is installed"}
            if _has_argos_ar_en()
            else {"status": "desktop_only", "platform": "desktop"}
        ),
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
