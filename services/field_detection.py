"""
Automatic Research Field Detection (#53).

Deterministic, not a fake AI call -- reuses `journals.subjects`, the
same real vocabulary `services/discipline_detection.py` (#102)
analyzes, applied the other direction: instead of "which subjects are
common among the top search RESULTS," this asks "which of the
database's own subject vocabulary literally appears in this abstract,"
ranked by how many journals actually carry that label -- a genuine
signal of how established a field is, not a guess or a hardcoded list.

Wired into services/research_interpreter.py's "Field of Study"
suggestion slot, replacing what was previously a fixed 5-item pool
unrelated to the abstract's actual content -- the existing accept/
suggest-another/edit UI (#110, #85) needed no changes, only what
powers that one slot did.
"""

import re
from collections import Counter

from services.repository import get_connection
from utils.subjects import extract_subject_tags

TOP_N = 5

_vocabulary_cache = None  # (Counter of {lowercased tag: journal count}, {lowercased tag: display-cased tag})


def _vocabulary():
    """
    Built once per process (mirrors web/search_cache.py's and
    services/online_enrichment.py's in-memory caching -- this data
    doesn't change without a database rebuild) from all 55k+ journals'
    subject tags, not a separately-maintained taxonomy.
    """
    global _vocabulary_cache

    if _vocabulary_cache is not None:
        return _vocabulary_cache

    conn = get_connection()
    rows = conn.execute("SELECT subjects FROM journals WHERE subjects IS NOT NULL").fetchall()
    conn.close()

    counts = Counter()
    display_forms = {}

    for (subjects,) in rows:
        for tag in extract_subject_tags(subjects):
            key = tag.lower()
            counts[key] += 1
            display_forms.setdefault(key, tag)

    _vocabulary_cache = (counts, display_forms)
    return _vocabulary_cache


def detect_fields(text, top_n=TOP_N):
    """
    Real subject-vocabulary tags that appear as whole words/phrases in
    `text` (case-insensitive), ranked by how many journals in the
    database use that tag -- most-recognized field first. Empty list
    if nothing matches or `text` is blank; never invents a field that
    isn't a real, already-imported subject label.
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
