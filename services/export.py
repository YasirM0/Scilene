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
) -> bytes:
    """
    Export recommendations as CSV data.
    """

    rows = recommendations_to_rows(recommendations)

    dataframe = pd.DataFrame(rows)

    return dataframe.to_csv(index=False).encode("utf-8")