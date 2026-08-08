"""
Presentation-only normalization for online enrichment results
(#107) -- OpenAlex and Crossref return different shapes (see
importers/enrichment/openalex.py / crossref.py's _map()); this maps
whichever one succeeded into one common display shape so
partials/online_enrichment.html never needs to branch on which
provider answered.
"""

PROVIDER_LABELS = {
    "openalex": "OpenAlex",
    "crossref": "Crossref",
}


def format_enrichment_result(result):
    """
    `result` is services.online_enrichment.enrich()'s return value
    (None, or {"providers": [...], "data": {...}} -- `data` is already
    the merge of every contributing provider's fields, #108). Returns a
    flat dict for the template, or None if there's nothing to show.
    """
    if not result:
        return None

    providers = result["providers"]
    data = result["data"]

    return {
        "source_label": " + ".join(PROVIDER_LABELS.get(p, p) for p in providers),
        "publisher": data.get("publisher"),
        "is_open_access": data.get("is_open_access"),
        "apc_usd": data.get("apc_usd"),
        "topics": data.get("topics") or data.get("subjects") or [],
        "works_count": data.get("works_count") or data.get("total_works"),
        "cited_by_count": data.get("cited_by_count"),
        "homepage_url": data.get("homepage_url"),
    }
