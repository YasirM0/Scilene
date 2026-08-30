"""
Parse a journal's raw `subjects` field (DOAJ-style hierarchical text,
e.g. "Law: Law of nations | Law: Comparative and uniform law.
Jurisprudence") into clean, de-duplicated tags.
"""


def extract_subject_tags(raw):
    """
    Returns the full, untruncated list of clean tags, e.g.
    ["Law of nations", "Comparative and uniform law", "Jurisprudence"].
    Used both by format_subjects() below (for display) and by
    services/discipline_detection.py (#102 -- frequency analysis needs
    the raw list, not a truncated, joined display string).
    """
    if not raw:
        return []

    entries = [entry.strip() for entry in str(raw).split("|") if entry.strip()]

    tags = []
    seen = set()

    for entry in entries:
        # Keep only the most specific part after the top-level category
        specific = entry.split(":")[-1].strip()

        # Some entries pack multiple related facets separated by ". "
        for fragment in specific.split(". "):
            fragment = fragment.strip().rstrip(".")
            if not fragment:
                continue
            key = fragment.lower()
            if key in seen:
                continue
            seen.add(key)
            tags.append(fragment)

    return tags


def format_subjects(raw, max_tags=6):
    """
    Compact, de-duplicated display string, e.g.
    "Law of nations • Comparative and uniform law • Jurisprudence".
    """
    tags = extract_subject_tags(raw)

    if not tags:
        return None

    if len(tags) > max_tags:
        return " • ".join(tags[:max_tags]) + f" • +{len(tags) - max_tags} more"

    return " • ".join(tags)


def extract_subject_entries(raw, max_tags=6):
    """
    Like extract_subject_tags(), but keeps each tag's top-level LCC
    category alongside its display label, e.g. {"label": "Law of
    nations", "category": "Law"} -- "Law" is the exact string
    services/subject_taxonomy.py indexes journals under (same
    entry.split(":", 1) split it uses), so a UI can drive the existing
    subject-category search filter directly from a displayed tag.

    Returns {"tags": [...up to max_tags], "extra": N} (N > 0 if there
    were more tags than max_tags), or None if there's nothing to show
    -- mirrors format_subjects()'s truncation so the two never drift
    out of sync on how many tags are "compact enough" to display.
    """
    if not raw:
        return None

    entries = [entry.strip() for entry in str(raw).split("|") if entry.strip()]

    results = []
    seen = set()

    for entry in entries:
        category = entry.split(":", 1)[0].strip()
        specific = entry.split(":")[-1].strip()

        for fragment in specific.split(". "):
            fragment = fragment.strip().rstrip(".")
            if not fragment:
                continue
            key = fragment.lower()
            if key in seen:
                continue
            seen.add(key)
            results.append({"label": fragment, "category": category})

    if not results:
        return None

    if len(results) > max_tags:
        return {"tags": results[:max_tags], "extra": len(results) - max_tags}

    return {"tags": results, "extra": 0}
