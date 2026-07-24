"""
Application-level search service.

This is the seam between the UI (Streamlit) and the core recommendation
engine. Streamlit pages should call into this module rather than
constructing a JournalRecommender or touching the repository directly —
that keeps the recommendation engine and database access fully
independent of Streamlit, so they can be reused by another frontend
(a script, a different UI, a desktop wrapper) without changes.

Nothing in this module imports streamlit.
"""

from services.recommender import JournalRecommender, STRATEGIES, CONFIDENCE_LEVELS
from services.export import export_to_csv


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
        strategy=strategy,
    )


def export_results_csv(results):
    """Export a list of recommendation results as CSV bytes."""
    return export_to_csv(results)