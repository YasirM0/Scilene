"""
Automatic Key Research Focus Detection (#113 follow-up).

Deterministic, not a fake AI call -- mirrors services/field_detection.py's
approach (#53) but reuses `journals.keywords` (a narrower, per-journal
keyword list) instead of `journals.subjects` (broad LCC categories),
matching this slot's own narrower intent: "a key research focus,
narrower than a field" (see research_interpreter.py's own docstring).

Replaces research_interpreter.py's fixed 5-item KEY_FOCUS_POOL, which
was completely unrelated to the abstract's actual content -- caught
directly: an abstract about internet access and social stratification
in Indonesia suggested "Robotics", then "Climate Adaptation" on retry.
Same problem #53/field_detection.py already solved for Field of Study,
applied to this slot too.

Coverage/quality caveat, disclosed rather than hidden: journals.keywords
only exists for the same ~23,000 DOAJ-sourced journals `subjects` does,
and matching is single-term substring matching, not phrase synthesis --
"internet access" only matches as one phrase if some journal's own
keyword list literally contains that exact phrase; otherwise "internet"
and "access" would each need to appear as standalone keywords. This is
a real, honest improvement over a random placeholder, not a claim of
matching an LLM's abstractive quality.
"""

import re
from collections import Counter

from services.repository import get_connection
from services.stopwords import filter_stopwords

TOP_N = 5

_vocabulary_cache = None  # (Counter of {lowercased term: journal count}, {lowercased term: display-cased term})


def _vocabulary():
    """
    Built once per process (same caching approach as
    services/field_detection.py's own _vocabulary()) from every
    journal's own keyword list, comma-separated per journals.keywords.
    """
    global _vocabulary_cache

    if _vocabulary_cache is not None:
        return _vocabulary_cache

    conn = get_connection()
    rows = conn.execute("SELECT keywords FROM journals WHERE keywords IS NOT NULL AND keywords != ''").fetchall()
    conn.close()

    counts = Counter()
    display_forms = {}

    for (keywords,) in rows:
        for term in keywords.split(","):
            term = term.strip()
            if not term:
                continue
            key = term.lower()
            counts[key] += 1
            display_forms.setdefault(key, term)

    # Drop single-word terms generic enough to be in the shared
    # academic-filler stopword list (e.g. "research", "study") -- real
    # vocabulary entries, just too vague to be a useful focus
    # suggestion on their own. Multi-word terms are never this
    # generic, so only single words are checked.
    for key in list(counts):
        if " " not in key and not filter_stopwords([key]):
            del counts[key]

    _vocabulary_cache = (counts, display_forms)
    return _vocabulary_cache


def detect_focus_terms(text, top_n=TOP_N):
    """
    Real per-journal keyword-vocabulary terms that appear as whole
    words/phrases in `text` (case-insensitive), ranked by how many
    journals use that term -- most-recognized term first. Empty list
    if nothing matches or `text` is blank; never invents a term that
    isn't a real, already-imported journal keyword.
    """
    if not text or not text.strip():
        return []

    counts, display_forms = _vocabulary()

    matches = []
    for key, frequency in counts.items():
        if re.search(r"\b" + re.escape(key) + r"\b", text, re.IGNORECASE):
            matches.append((key, frequency))

    matches.sort(key=lambda pair: -pair[1])
    return [display_forms[key] for key, _frequency in matches[:top_n]]
