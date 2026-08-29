"""
Subject taxonomy (#79).

#79 envisioned "a unified subject taxonomy that maps journals, user
queries, and extracted concepts into a consistent hierarchy... support[ing]
semantic search, filtering, research interpretation, and recommendation."

What's genuinely real and shipped here: journals.subjects already
carries a two-level "Category: Subcategory" structure for DOAJ-sourced
journals (Library of Congress Classification, e.g. "Language and
Literature: English language") -- it was just never parsed into a
queryable tree, only used as flat text for keyword substring matching
(services/recommender.py) and field detection (services/field_detection.py).
This module parses that EXISTING structure rather than inventing a new
one or calling an LLM to classify anything.

Coverage: DOAJ-sourced LCC categories cover ~23,000 of the ~55,745
journals (the ones with a DOAJ subjects value at all). The remaining
~32,700 (SINTA-only, Scopus/SCImago-only journals) are covered
instead by journals.openalex_domain/field/subfield -- OpenAlex's own
Domain > Field > Subfield hierarchy, backfilled by
scripts/backfill_openalex_taxonomy.py for exactly the journals DOAJ's
scheme doesn't reach. Verified by direct sampling against the live
API: ~90% coverage even for SINTA/Scopus-only journals (100% in one
15-journal Indonesian-SINTA sample).

get_taxonomy_tree() (DOAJ/LCC) and get_openalex_taxonomy_tree() are
kept as two SEPARATE trees, not merged into one flat namespace: DOAJ's
Library-of-Congress-style categories and OpenAlex's Domain/Field/
Subfield hierarchy are two different, independently coherent
classification schemes with different category vocabularies (e.g.
DOAJ's "Language and Literature" vs. OpenAlex's "Arts and Humanities"
-> "Literature and Literary Theory") -- forcing every DOAJ category
into exactly one OpenAlex field would misrepresent genuinely
multidisciplinary LCC classes like "Science" (dominated by Biology,
Mathematics, AND Computer Science subcategories at roughly similar
weight -- no single OpenAlex field fits without discarding two of the
three) or "Technology". Rather than force a lossy 1:1 crosswalk,
filtering (below) unions the two vocabularies mechanically: a journal
matches a category filter if EITHER its DOAJ category OR its OpenAlex
field equals the selected name. Real, exact-name overlaps (verified:
"Medicine" and "Social Sciences" appear identically in both
vocabularies) collapse into one filter option naturally, with no
manual mapping decision needed for those; everything else stays as
its own distinct, honestly-labeled option -- 44 total across both
sources (20 DOAJ + 26 OpenAlex, minus the 2 exact overlaps).

Wired into filtering (services.repository.filtered_journal_ids() via
`restrict_to_ids`, both search engines -- see journal_ids_for_categories()
below) as of #79's completion pass. NOT wired into the Research
Interpreter: "Field of Study" was already demoted from a confident
suggestion to plain examples earlier in #79's own history because the
underlying vocabulary (DOAJ's subjects text) was too coarse for
specific interdisciplinary abstracts -- adding OpenAlex's equally
broad field-level vocabulary on top doesn't fix that coarseness, so
wiring this taxonomy in there wouldn't add real accuracy, only the
appearance of it.
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


def get_openalex_taxonomy_tree(conn=None):
    """
    {field: {subfield: journal_count}} across every journal with an
    OpenAlex-derived classification (scripts/backfill_openalex_taxonomy.py) --
    the counterpart to get_taxonomy_tree() above, covering the journals
    DOAJ's own scheme doesn't reach. Uses OpenAlex's "field" as the
    category level (26 fields total, the closest match to DOAJ's ~20
    top-level LCC categories in granularity) and "subfield" as the
    subcategory level. See this module's own docstring for why this is
    a separate tree rather than merged with get_taxonomy_tree()'s.
    """
    owns_conn = conn is None
    if owns_conn:
        conn = get_connection()

    rows = conn.execute(
        "SELECT openalex_field, openalex_subfield FROM journals WHERE openalex_field IS NOT NULL AND openalex_field != ''"
    ).fetchall()

    if owns_conn:
        conn.close()

    tree = {}
    for field, subfield in rows:
        bucket = tree.setdefault(field, {})
        key = subfield or ""
        bucket[key] = bucket.get(key, 0) + 1

    return tree


_category_index_cache = None  # {category_name: set(journal_id)}


def _category_index():
    """
    Built once per process (same caching approach as
    services/field_detection.py's own _vocabulary()) -- this data
    doesn't change without a database rebuild. Each journal contributes
    to the index under EVERY DOAJ category it has (there can be
    several, per parse_subjects()) plus its single OpenAlex field, if
    any. A journal with both sources categorizes under both -- never a
    conflict, since filtering is a union: matching either is enough.
    """
    global _category_index_cache
    if _category_index_cache is not None:
        return _category_index_cache

    conn = get_connection()
    rows = conn.execute("SELECT id, subjects, openalex_field FROM journals").fetchall()
    conn.close()

    index = {}
    for journal_id, subjects_text, openalex_field in rows:
        categories = {category for category, _ in parse_subjects(subjects_text)}
        if openalex_field:
            categories.add(openalex_field)
        for category in categories:
            index.setdefault(category, set()).add(journal_id)

    _category_index_cache = index
    return index


def all_categories():
    """
    Every real category name available for filtering -- the union of
    DOAJ's LCC categories and OpenAlex's fields, mechanically (see
    module docstring for why no manual crosswalk exists). Sorted for a
    stable, alphabetical filter UI.
    """
    return sorted(_category_index().keys())


def journal_ids_for_categories(category_names):
    """
    Union of journal ids belonging to ANY of the given categories, from
    EITHER taxonomy source. Empty/falsy input returns an empty set
    (the caller's job to treat "no categories selected" as "don't
    filter" -- this function only ever answers "which ids match what
    was asked").
    """
    if not category_names:
        return set()
    index = _category_index()
    result = set()
    for name in category_names:
        result |= index.get(name, set())
    return result
