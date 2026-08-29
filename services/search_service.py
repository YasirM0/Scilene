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
from services.semantic_search import corpus_coverage
from services.export import export_to_csv
from services.repository import (
    count_journals,
    count_by_source,
    count_by_enrichment_provider,
    count_by_country,
    count_by_publisher,
    count_by_subject,
    count_by_quartile,
    count_by_sinta_accreditation,
    count_by_publication_type,
    count_free_vs_paid,
)


def search_journals(
    title,
    keywords=None,
    abstract="",
    languages=None,
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
        languages=languages,
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


def get_dashboard_stats():
    """
    The fuller aggregate set for the Statistics Dashboard (#60) --
    kept separate from get_database_stats() above (used by the
    lightweight homepage) since count_by_subject() scans every
    journal's subject text and isn't worth paying on every homepage
    load for a page that doesn't show it.

    `semantic_coverage` comes from corpus_coverage() (counts only,
    never index_terms text -- see that function's docstring) rather
    than a repository count_by_*(), since journals.index_terms is
    wiped from the database itself after the embeddings are built.
    """
    return {
        "total_journals": count_journals(),
        "by_source": count_by_source(),
        "by_enrichment": count_by_enrichment_provider(),
        "by_country": count_by_country(),
        "by_publisher": count_by_publisher(),
        "by_subject": count_by_subject(),
        "by_quartile": count_by_quartile(),
        "by_sinta_accreditation": count_by_sinta_accreditation(),
        "by_publication_type": count_by_publication_type(),
        "free_vs_paid": count_free_vs_paid(),
        "semantic_coverage": corpus_coverage(),
    }
