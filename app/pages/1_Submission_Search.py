import math

import streamlit as st

from datetime import datetime

from services import search_service
from services.recommender import STRATEGIES
from services.repository import DB_PATH

if "search" not in st.session_state:
    st.session_state.search = None

if "page" not in st.session_state:
    st.session_state.page = 1

if "show_weaker" not in st.session_state:
    st.session_state.show_weaker = False

PAGE_SIZE = 10

CONFIDENCE_COLORS = {
    "Excellent": "green",
    "Strong": "blue",
    "Moderate": "yellow",
    "Weak": "orange",
    "Poor": "gray",
}

CONFIDENCE_STARS = {
    "Excellent": "★★★★★",
    "Strong": "★★★★☆",
    "Moderate": "★★★☆☆",
    "Weak": "★★☆☆☆",
    "Poor": "★☆☆☆☆",
}

# By default only the top two confidence tiers are shown.
STRONG_TIERS = {"Excellent", "Strong"}

QUARTILE_OPTIONS = ["Q1", "Q2", "Q3", "Q4"]
SINTA_LEVEL_OPTIONS = [f"SINTA {n}" for n in range(1, 7)]


def format_source_label(detail):
    """e.g. 'Scopus (Q1)', 'SINTA 2', or plain 'DOAJ'."""
    source = detail["source"]
    if source == "SINTA" and detail.get("accreditation"):
        return detail["accreditation"]
    if detail.get("quartile"):
        return f"{source} ({detail['quartile']})"
    return source


@st.cache_data(show_spinner=False)
def cached_search(title, keywords_tuple, abstract, language, free_only,
                   min_budget, max_budget, indexing_tuple, quartiles_tuple,
                   sinta_levels_tuple, strategy, _db_mtime):
    """
    Cached wrapper around the (Streamlit-free) search service. `_db_mtime`
    is included purely so the cache key changes automatically whenever
    data/journal_intelligence.db is rebuilt (e.g. after re-running
    scripts/build_database.py) — Streamlit's cache otherwise has no way
    to know the underlying data changed.
    """
    return search_service.search_journals(
        title=title,
        keywords=list(keywords_tuple),
        abstract=abstract,
        language=language,
        free_only=free_only,
        min_budget=min_budget,
        max_budget=max_budget,
        indexing=list(indexing_tuple) if indexing_tuple else None,
        quartiles=list(quartiles_tuple) if quartiles_tuple else None,
        sinta_levels=list(sinta_levels_tuple) if sinta_levels_tuple else None,
        strategy=strategy,
    )


# ==========================================================
# Page Configuration
# ==========================================================

st.set_page_config(
    page_title="Submission Search",
    page_icon="🔍",
)

st.title("🔍 Journal Search")

st.write(
    "Upload your completed manuscript or enter its information manually "
    "to discover journals that best match your research."
)

st.divider()

# ==========================================================
# Upload Manuscript
# ==========================================================

with st.expander("📎 Upload manuscript (optional)"):

    uploaded_file = st.file_uploader(
        "Upload PDF or DOCX",
        type=["pdf", "docx"],
    )

    if uploaded_file is not None:
        st.info(
            "Automatic extraction of title/abstract/keywords from uploaded "
            "files isn't built yet — please fill in the fields below "
            "manually for now."
        )

    st.caption(
        "🚧 Automatic manuscript extraction will be available in a future version."
    )

st.divider()

# ==========================================================
# Manual Manuscript Entry
# ==========================================================

st.subheader("📄 Enter Manuscript Information")

title = st.text_input(
    "Paper Title *",
    placeholder="Enter your manuscript title...",
)

abstract = st.text_area(
    "Abstract *",
    placeholder="Paste your manuscript abstract here...",
    height=220,
    help="Your abstract helps identify suitable journals when keywords are left blank.",
)

keywords = st.text_input(
    "Keywords (Optional)",
    placeholder="digital governance, e-government, Indonesia",
    help="Separate keywords using commas (,) or semicolons (;).",
)

st.divider()

# ==========================================================
# Publication Preferences
# ==========================================================

st.caption(
    "Customize how Journal Intelligence recommends journals for your manuscript."
)

# All three strategies here are backed by real data: Balanced (keyword
# match), Lowest APC (apc/apc_amount), and Highest Prestige (Scopus/WoS
# quartile + SJR via SCImago).
STRATEGY_LABELS = {
    "⚖️ Balanced (Recommended)": "Balanced",
    "💰 Lowest APC": "Lowest APC",
    "🏆 Highest Prestige": "Highest Prestige",
}

# DOAJ, Scopus, Web of Science, and SINTA are all real, imported
# collections (see scripts/build_database.py). Google Scholar isn't a
# curated list Journal Intelligence can import (no bulk export exists),
# so it's not offered as a filter.
INDEXING_OPTIONS = ["DOAJ", "Scopus", "SINTA", "Web of Science"]

with st.expander("⚙️ Publication Preferences", expanded=False):

    strategy_label = st.selectbox(
        "Recommendation Strategy",
        list(STRATEGY_LABELS.keys()),
        help="Choose what Journal Intelligence should prioritize when ranking journals.",
    )

    st.divider()

    st.markdown("#### Filters")

    col1, col2 = st.columns(2)

    with col1:
        preferred_indexing = st.multiselect(
            "Preferred Indexing",
            INDEXING_OPTIONS,
            default=["DOAJ"],
            help="Only journals confirmed in at least one selected source are shown.",
        )

    with col2:
        preferred_language = st.selectbox(
            "Preferred Language",
            ["Any", "English", "Indonesian"],
        )

    budget_choice = st.selectbox(
        "Publication Budget",
        [
            "Any",
            "Free (No APC)",
            "Low APC (< $100)",
            "Medium APC ($100–300)",
            "High APC (> $300)",
        ],
        help="Maximum publication fee you are willing to pay.",
    )

    level_col1, level_col2 = st.columns(2)

    with level_col1:
        preferred_quartiles = st.multiselect(
            "Scopus / WoS Quartile",
            QUARTILE_OPTIONS,
            default=[],
            help=(
                "Matches if the journal has this quartile in EITHER Scopus "
                "or Web of Science. Leave empty for any quartile (or none)."
            ),
        )

    with level_col2:
        preferred_sinta_levels = st.multiselect(
            "SINTA Level",
            SINTA_LEVEL_OPTIONS,
            default=[],
            help="Leave empty for any SINTA level (or none).",
        )

st.divider()

# ==========================================================
# Journal Recommendation
# ==========================================================

if st.button(
    "🔍 Find Best Matching Journals",
    width="stretch",
):

    if not title or not abstract:
        st.warning("Please enter both a title and an abstract.")
        st.stop()

    keyword_list = tuple(
        k.strip()
        for k in keywords.replace(";", ",").split(",")
        if k.strip()
    )

    language = None if preferred_language == "Any" else preferred_language

    free_only = budget_choice == "Free (No APC)"
    min_budget = None
    max_budget = None
    if budget_choice == "Low APC (< $100)":
        max_budget = 99.99
    elif budget_choice == "Medium APC ($100–300)":
        min_budget, max_budget = 100, 300
    elif budget_choice == "High APC (> $300)":
        min_budget = 300

    resolved_strategy = STRATEGY_LABELS[strategy_label]

    db_mtime = DB_PATH.stat().st_mtime if DB_PATH.exists() else 0

    results = cached_search(
        title,
        keyword_list,
        abstract,
        language,
        free_only,
        min_budget,
        max_budget,
        tuple(preferred_indexing) if preferred_indexing else None,
        tuple(preferred_quartiles) if preferred_quartiles else None,
        tuple(preferred_sinta_levels) if preferred_sinta_levels else None,
        resolved_strategy,
        db_mtime,
    )

    st.session_state.search = {
        "results": results,
        "strategy_label": strategy_label,
    }
    st.session_state.page = 1
    st.session_state.show_weaker = False

    if not results:
        st.info(
            """
### No journals matched your current filters.

Try one or more of the following:

- Choose **Any** as the preferred language.
- Choose **Any** as the publication budget.
- Clear the Quartile / SINTA Level filters.
- Select **DOAJ** (or clear indexing filters) — it has the broadest coverage.
- Broaden your manuscript title, abstract, or keywords.
"""
        )
        st.stop()

# ==========================================================
# Recommendation Results
# ==========================================================

search = st.session_state.search

if search:

    all_results = search["results"]
    strategy_label = search["strategy_label"]

    st.session_state.show_weaker = st.checkbox(
        "Show weaker matches too (Moderate / Weak / Poor)",
        value=st.session_state.show_weaker,
        help=(
            "Confidence is relative to this search's own results, not a "
            "validated prediction — it just ranks matches into fifths so "
            "the strongest ones are easy to spot."
        ),
    )

    if st.session_state.show_weaker:
        visible_results = all_results
    else:
        visible_results = [r for r in all_results if r["confidence"] in STRONG_TIERS]

    hidden_count = len(all_results) - len(visible_results)

    top_col1, top_col2 = st.columns([3, 1])

    with top_col1:
        st.success(f"Showing {len(visible_results)} of {len(all_results)} recommended journals.")
        if hidden_count and not st.session_state.show_weaker:
            st.caption(f"{hidden_count} weaker matches hidden — tick the box above to see them.")

    with top_col2:
        if st.button("🗑️ Clear Search"):
            st.session_state.search = None
            st.rerun()

    if visible_results:

        timestamp = datetime.now().strftime("%Y%m%d_%H%M")

        strategy_slug = (
            strategy_label
            .split(" ", 1)[1]
            .replace(" (Recommended)", "")
            .replace(" ", "_")
            .lower()
        )

        filename = f"ji_{strategy_slug}_{timestamp}.csv"

        csv_data = search_service.export_results_csv(visible_results)
        st.download_button(
            label="📥 Download Recommendations (CSV)",
            data=csv_data,
            file_name=filename,
            mime="text/csv",
        )

    st.caption(
        "🔒 Search results are stored only for this browser session "
        "and are never saved permanently."
    )
    st.caption(
        "Data: Directory of Open Access Journals (doaj.org) · "
        "SCImago Journal & Country Rank (scimagojr.com) · "
        "SINTA (sinta.kemdikbud.go.id)"
    )

    total_pages = max(1, math.ceil(len(visible_results) / PAGE_SIZE))
    st.session_state.page = min(st.session_state.page, total_pages)

    start = (st.session_state.page - 1) * PAGE_SIZE
    page_results = visible_results[start:start + PAGE_SIZE]

    # ------------------------------------------------------
    # Compact recommendation cards
    #
    # Each card's widgets (expander, etc.) are keyed by the journal's
    # database id, NOT by its position in the list. Without this, if
    # journal A is expanded on page 1 and journal B happens to land in
    # that same on-page position after paginating, Streamlit reuses A's
    # widget state for B — B shows up already expanded. Keying by a
    # stable per-journal id (not list position) fixes that.
    # ------------------------------------------------------

    for journal in page_results:

        with st.container(border=True, key=f"card_{journal['id']}"):

            card_col1, card_col2 = st.columns([3, 1])

            with card_col1:
                st.markdown(f"**{journal['title']}**")
                st.caption(
                    f"{CONFIDENCE_STARS.get(journal['confidence'], '')} "
                    f"{journal['confidence']} Match"
                )

            with card_col2:
                st.badge(
                    journal["confidence"],
                    color=CONFIDENCE_COLORS.get(journal["confidence"], "gray"),
                )

            st.write("**Indexed in:**")
            if journal["source_details"]:
                index_line = "  ".join(
                    f"✓ {format_source_label(d)}" for d in journal["source_details"]
                )
                st.write(index_line)
            else:
                st.write("—")

            summary_col1, summary_col2, summary_col3 = st.columns(3)

            with summary_col1:
                st.caption("Match Score")
                st.write(journal["score"])

            with summary_col2:
                apc_label = "Free" if journal["is_free"] else (
                    f"~${journal['apc_amount']:.0f}"
                    if journal["apc_amount"] is not None
                    else "Paid (unconfirmed)"
                )
                st.caption("APC")
                st.write(apc_label)

            with summary_col3:
                st.caption("Language")
                st.write(journal["languages"] or "—")

            with st.expander("Show more", key=f"expander_{journal['id']}"):

                st.write(f"**Publisher:** {journal['publisher'] or 'Not listed'}")
                st.write(f"**Country:** {journal['country'] or 'Not listed'}")
                st.write(f"**License:** {journal['license'] or 'Not listed'}")

                if journal["review_weeks"] is not None:
                    st.write(f"**Typical review time:** ~{journal['review_weeks']} weeks")

                if journal["subjects"]:
                    st.write(f"**Subjects:** {journal['subjects']}")

                if journal["issn_print"] or journal["issn_online"]:
                    st.write(
                        f"**ISSN:** {journal['issn_print'] or '—'} (print) / "
                        f"{journal['issn_online'] or '—'} (online)"
                    )

                if journal["reasons"]:
                    st.write("**Why this journal?**")
                    for reason in journal["reasons"]:
                        st.write(f"- {reason}")

                link_col1, link_col2 = st.columns(2)
                with link_col1:
                    if journal["website"]:
                        st.link_button(
                            "Visit Journal",
                            journal["website"],
                            key=f"visit_{journal['id']}",
                        )
                with link_col2:
                    if journal["doaj_url"]:
                        st.link_button(
                            "View on DOAJ",
                            journal["doaj_url"],
                            key=f"doaj_{journal['id']}",
                        )

    # ------------------------------------------------------
    # Pagination (below the results, per feedback)
    # ------------------------------------------------------

    st.divider()

    page_col1, page_col2, page_col3 = st.columns([1, 2, 1])

    with page_col1:
        if st.button("⬅️ Previous", disabled=st.session_state.page <= 1, key="prev_page"):
            st.session_state.page -= 1
            st.rerun()

    with page_col2:
        st.markdown(
            f"<div style='text-align:center;'>Page {st.session_state.page} of {total_pages}</div>",
            unsafe_allow_html=True,
        )

    with page_col3:
        if st.button("Next ➡️", disabled=st.session_state.page >= total_pages, key="next_page"):
            st.session_state.page += 1
            st.rerun()