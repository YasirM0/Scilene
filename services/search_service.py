"""
Application-level search service.

This is the seam between any UI (the Streamlit app, the FastAPI web
app, or anything else in the future) and the core recommendation
engine. UI code should call into this module rather than constructing
a JournalRecommender or touching the repository directly — that keeps
the recommendation engine and database access fully independent of any
one frontend.

This module is framework-agnostic and contains no FastAPI-specific logic.
It can be reused by the web application, future desktop application, or other
interfaces.
"""

from services.recommender import JournalRecommender, STRATEGIES, CONFIDENCE_LEVELS
from services.export import export_to_csv
from services.repository import count_journals, count_by_source, count_by_enrichment_provider


def search_journals(
    title,
    keywords=None,
    abstract="",
    language=None,
    free_only=False,
    min_budget=None,
    max_budget=None,
    indexing=None,
    quartiles=None,
    sinta_levels=None,
    max_review_weeks=None,
    strategy="Balanced",
):
    """
    Run a journal search/recommendation. Returns the full, ranked list
    of matching journals (see JournalRecommender.recommend for the
    dict shape) — no pagination or confidence filtering is applied here,
    that's presentation logic and belongs in the caller.
    """

    recommender = JournalRecommender()

    return recommender.recommend(
        title=title,
        keywords=keywords,
        abstract=abstract,
        language=language,
        free_only=free_only,
        min_budget=min_budget,
        max_budget=max_budget,
        indexing=indexing,
        quartiles=quartiles,
        sinta_levels=sinta_levels,
        max_review_weeks=max_review_weeks,
        strategy=strategy,
    )


def export_results_csv(results, context=None):
    """Export a list of recommendation results as CSV bytes."""
    return export_to_csv(results, context=context)


def get_database_stats():
    """
    Aggregate stats for display (e.g. the homepage's statistics
    section). Kept as one function so a UI never needs to know which
    individual repository calls or SQL produce these numbers — just
    "give me the stats to show."
    """
    return {
        "total_journals": count_journals(),
        "by_source": count_by_source(),
        "by_enrichment": count_by_enrichment_provider(),
    }
