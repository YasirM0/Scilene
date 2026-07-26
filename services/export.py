"""
Export service.

Responsible for exporting recommendation results into different formats.

Works with the dictionary-based recommendation format returned by
services.recommender.JournalRecommender.recommend(), not the old
Recommendation dataclass.
"""

from typing import Iterable

import pandas as pd

_QUARTILE_ORDER = ["Q1", "Q2", "Q3", "Q4"]


def _best_quartile(source_details):
    quartiles = [d.get("quartile") for d in source_details if d.get("quartile")]
    for q in _QUARTILE_ORDER:
        if q in quartiles:
            return q
    return ""


def _sinta_accreditation(source_details):
    for d in source_details:
        if d.get("source") == "SINTA" and d.get("accreditation"):
            return d["accreditation"]
    return ""


def recommendations_to_rows(
    recommendations: Iterable[dict],
) -> list[dict]:
    """
    Convert recommendation dicts into flat dictionaries suitable for export.
    """

    rows = []

    for recommendation in recommendations:
        rows.append(
            {
                "Journal Name": recommendation["title"],
                "Confidence": recommendation.get("confidence", ""),
                "Score": round(recommendation["score"], 1),
                "Sources": ", ".join(recommendation.get("sources", [])),
                "Best Quartile": _best_quartile(recommendation.get("source_details", [])),
                "SINTA Accreditation": _sinta_accreditation(recommendation.get("source_details", [])),
                "Publisher": recommendation["publisher"],
                "Country": recommendation["country"],
                "Languages": recommendation["languages"],
                "APC": "Free" if recommendation["is_free"] else recommendation["apc"],
                "APC Amount (USD)": recommendation["apc_amount"],
                "License": recommendation["license"],
                "Review Time (weeks)": recommendation["review_weeks"],
                "ISSN (Print)": recommendation.get("issn_print", ""),
                "ISSN (Online)": recommendation.get("issn_online", ""),
                "Subjects": recommendation.get("subjects", ""),
                "Website": recommendation["website"],
                "DOAJ URL": recommendation["doaj_url"],
                "Why This Journal": recommendation.get("explanation", ""),
            }
        )

    return rows


def export_to_csv(
    recommendations: Iterable[dict],
    context=None,
) -> bytes:
    """
    Export recommendations as CSV data.

    If `context` (a services.report_context.ReportContext) is given,
    the same small metadata block used by the other export formats is
    prepended as '#'-commented lines, so a person opening this in a
    plain viewer still sees it, and tools that skip '#' lines (e.g.
    pandas' read_csv(comment='#')) can still parse the data cleanly.
    """

    rows = recommendations_to_rows(recommendations)

    dataframe = pd.DataFrame(rows)

    csv_text = dataframe.to_csv(index=False)

    if context is not None:
        header_lines = [
            f"# Journal Intelligence v{context.app_version}",
            f"# Generated: {context.generated_at} UTC",
            f"# Search Strategy: {context.strategy_label}",
            f"# Database Sources: {context.database_sources}",
            f"# Total Recommendations: {len(context.results)}",
            "",
        ]
        csv_text = "\n".join(header_lines) + csv_text

    return csv_text.encode("utf-8")
