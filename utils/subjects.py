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
