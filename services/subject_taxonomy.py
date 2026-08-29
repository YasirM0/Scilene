"""
Subject taxonomy (#79) -- foundation only, not the full issue.

#79 envisioned "a unified subject taxonomy that maps journals, user
queries, and extracted concepts into a consistent hierarchy... support[ing]
semantic search, filtering, research interpretation, and recommendation."
That full scope needs a hierarchy covering the WHOLE catalog plus real
integration into four other subsystems -- too much to respons	ibly
build and validate in one pass.

What's genuinely real and shipped here: journals.subjects already
carries a two-level "Category: Subcategory" structure for DOAJ-sourced
journals (Library of Congress Classification, e.g. "Language and
Literature: English language") -- it was just never parsed into a
queryable tree, only used as flat text for keyword substring matching
(services/recommender.py) and field detection (services/field_detection.py).
This module parses that EXISTING structure rather than inventing a new
one or calling an LLM to classify anything.

Coverage: DOAJ-sourced LCC categories cover ~23,000 of the ~55,745
journals (the ones with a DOAJ subjects value at all) -- the rest
(SINTA-only, Scopus/SCImago-only journals) have no equivalent
structured classification in this database today. Extending coverage
to them would need either new curation work or an embedding-based
classifier against these 19 categories -- unbuilt and unvalidated, a
real next step, not done here.

NOT wired into filtering, semantic search, or the Research Interpreter
yet -- this is the data structure #79 was missing, not the rest of the
issue's scope.
"""

from services.repository import get_connection


def parse_subjects(subjects_text):
    """
    "Language and Literature: English language | Language and
    Literature: English literature" -> [("Language and Literature",
    "English language"), ("Language and Literature", "English literature")].
    A pipe-separated entry with no colon (DOAJ does have some of these)
    yields (category, None) -- a top-level-only classification, still
    real signal, just without a subcategory.
    """
    if not subjects_text:
        return []

    pairs = []
    for entry in subjects_text.split("|"):
        entry = entry.strip()
        if not entry:
            continue
        if ":" in entry:
            category, subcategory = entry.split(":", 1)
            pairs.append((category.strip(), subcategory.strip()))
        else:
            pairs.append((entry, None))
    return pairs


def get_taxonomy_tree(conn=None):
    """
    {category: {subcategory: journal_count}} across every journal with
    a DOAJ-style subjects value. A (category, None) entry (no
    subcategory) is counted under the special key "" so a category
    with only top-level hits still appears with an accurate count.
    Opens its own connection if `conn` isn't supplied, for easy
    one-off/interactive use (e.g. a future "Browse by Subject" page).
    """
    owns_conn = conn is None
    if owns_conn:
        conn = get_connection()

    rows = conn.execute(
        "SELECT subjects FROM journals WHERE subjects IS NOT NULL AND subjects != ''"
    ).fetchall()

    if owns_conn:
        conn.close()

    tree = {}
    for (subjects_text,) in rows:
        for category, subcategory in parse_subjects(subjects_text):
            bucket = tree.setdefault(category, {})
            key = subcategory or ""
            bucket[key] = bucket.get(key, 0) + 1

    return tree
