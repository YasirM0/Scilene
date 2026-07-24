"""
Format a journal's raw `subjects` field (DOAJ-style hierarchical text,
e.g. "Law: Law of nations | Law: Comparative and uniform law.
Jurisprudence") into compact, de-duplicated tags for display, e.g.
"Law of nations • Comparative and uniform law • Jurisprudence".
"""


def format_subjects(raw, max_tags=6):
    if not raw:
        return None

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

    if not tags:
        return None

    if len(tags) > max_tags:
        return " • ".join(tags[:max_tags]) + f" • +{len(tags) - max_tags} more"

    return " • ".join(tags)
