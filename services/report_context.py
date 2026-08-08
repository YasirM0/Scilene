"""
Bundles everything an exported report needs (search info + results),
independent of Streamlit and independent of export format. Built once
per search and handed to whichever generator in services/reports.py the
person picks — this is the seam a future desktop wrapper or different
frontend would also use.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone

from services.app_info import APP_NAME, APP_VERSION, DATABASE_SOURCES


@dataclass
class ReportContext:
    title: str
    abstract: str
    keywords: list
    strategy_label: str
    filters_summary: list
    results: list
    generated_at: str = ""
    app_name: str = APP_NAME
    app_version: str = APP_VERSION
    database_sources: str = DATABASE_SOURCES

    def __post_init__(self):
        if not self.generated_at:
            # Server-side timestamp, explicitly UTC. Streamlit Community
            # Cloud's containers run in UTC, and datetime.now() without a
            # timezone would be ambiguous about which clock it reflects —
            # labeling it anything else would be a guess, not a fact.
            self.generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")


def build_filters_summary(languages=None, free_only=False, min_budget=None,
                           max_budget=None, indexing=None, quartiles=None,
                           sinta_levels=None, max_review_weeks=None):
    """
    Human-readable lines describing exactly which filters were actually
    applied for a search — used in the "Applied Filters" section of
    every export format. Skips anything left at its default (unset).
    """

    lines = []

    if languages:
        lines.append(f"Language: {', '.join(languages)}")

    if free_only:
        lines.append("Budget: Free (No APC)")
    elif min_budget is not None and max_budget is not None:
        lines.append(f"Budget: ${min_budget:.0f}\u2013${max_budget:.0f}")
    elif max_budget is not None:
        lines.append(f"Budget: up to ${max_budget:.0f}")
    elif min_budget is not None:
        lines.append(f"Budget: over ${min_budget:.0f}")

    if indexing:
        lines.append(f"Indexing: {', '.join(indexing)}")

    if quartiles:
        lines.append(f"Scopus/WoS Quartile: {', '.join(quartiles)}")

    if sinta_levels:
        lines.append(f"SINTA Level: {', '.join(sinta_levels)}")

    if max_review_weeks:
        lines.append(f"Maximum review time: {max_review_weeks} weeks")

    if not lines:
        lines.append("None")

    return lines
