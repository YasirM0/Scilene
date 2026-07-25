import math

import streamlit as st

from datetime import datetime

from services import search_service
from services.recommender import STRATEGIES
from services.repository import DB_PATH
from utils.subjects import format_subjects

if "search" not in st.session_state:
    st.session_state.search = None

if "page" not in st.session_state:
    st.session_state.page = 1

if "show_weaker" not in st.session_state:
    st.session_state.show_weaker = False

if "search_history" not in st.session_state:
    st.session_state.search_history = []

MAX_HISTORY_ENTRIES = 10

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

REVIEW_TIME_BANDS = {
    "Any": None,
    "Up to 8 weeks": 8,
    "Up to 12 weeks": 12,
    "Up to 20 weeks": 20,
    "Up to 30 weeks": 30,
}

# Chips get extra spacing (real spaces collapse in HTML) so a row of
# indexing tags is easy to scan rather than run together.
CHIP_GAP = "\u2003\u2003"


def format_index_chips(source_details):
    """
    e.g. '✓ DOAJ    ✓ Scopus (Q1)    ✓ WoS    ✓ SINTA 2'

    Quartile is only shown once, on Scopus — Scopus and Web of Science
    quartiles come from the same underlying SCImago row in this
    database, so repeating it on the WoS chip would just be the same
    number twice, not new information.
    """
    chips = []
    for detail in source_details:
        source = detail["source"]
        if source == "SINTA" and detail.get("accreditation"):
            chips.append(detail["accreditation"])
        elif source == "Scopus" and detail.get("quartile"):
            chips.append(f"Scopus ({detail['quartile']})")
        else:
            chips.append(source)
    return CHIP_GAP.join(f"✓ {chip}" for chip in chips)


@st.cache_data(show_spinner=False)
def cached_search(title, keywords_tuple, abstract, language, free_only,
                   min_budget, max_budget, indexing_tuple, quartiles_tuple,
                   sinta_levels_tuple, max_review_weeks, strategy, _db_mtime):
    """
    Cached wrapper around the (Streamlit-free) search service. `_db_mtime`
    is included purely so the cache key changes automatically whenever
    data/journal_intelligence.db is rebuilt — Streamlit's cache otherwise
    has no way to know the underlying data changed.
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
        max_review_weeks=max_review_weeks,
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

    budget_col, review_col = st.columns(2)

    with budget_col:
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

    with review_col:
        review_time_choice = st.selectbox(
            "Maximum Review Time",
            list(REVIEW_TIME_BANDS.keys()),
            help="Filters by the journal's own typical review time — independent of prestige or cost.",
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

    max_review_weeks = REVIEW_TIME_BANDS[review_time_choice]

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
        max_review_weeks,
        resolved_strategy,
        db_mtime,
    )

    st.session_state.search = {
        "results": results,
        "strategy_label": strategy_label,
    }
    st.session_state.page = 1
    st.session_state.show_weaker = False

    st.session_state.search_history.insert(0, {
        "title": title,
        "keywords": keyword_list,
        "abstract": abstract,
        "language": language,
        "free_only": free_only,
        "min_budget": min_budget,
        "max_budget": max_budget,
        "indexing": tuple(preferred_indexing) if preferred_indexing else None,
        "quartiles": tuple(preferred_quartiles) if preferred_quartiles else None,
        "sinta_levels": tuple(preferred_sinta_levels) if preferred_sinta_levels else None,
        "max_review_weeks": max_review_weeks,
        "strategy": resolved_strategy,
        "strategy_label": strategy_label,
        "result_count": len(results),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
    })
    st.session_state.search_history = st.session_state.search_history[:MAX_HISTORY_ENTRIES]

    if not results:
        st.info(
            """
### No journals matched your current filters.

Try one or more of the following:

- Choose **Any** as the preferred language.
- Choose **Any** as the publication budget or review time.
- Clear the Quartile / SINTA Level filters.
- Select **DOAJ** (or clear indexing filters) — it has the broadest coverage.
- Broaden your manuscript title, abstract, or keywords.
"""
        )
        st.stop()

# ==========================================================
# Search History (session-only — cleared on page reload/new
# browser session, never written to the database). Placed here,
# after the search button, rather than at the top of the page:
# people search first and only revisit past searches afterward,
# so this is closer to where they'll actually look for it.
# ==========================================================

if st.session_state.search_history:

    with st.expander(f"🕘 Search History ({len(st.session_state.search_history)})"):

        st.caption("Kept only for this browser session — not saved anywhere.")

        for i, entry in enumerate(st.session_state.search_history):

            hist_col1, hist_col2 = st.columns([4, 1])

            with hist_col1:
                st.write(f"**{entry['title']}**")
                st.caption(
                    f"{entry['timestamp']} · {entry['strategy_label']} · "
                    f"{entry['result_count']} results"
                )

            with hist_col2:
                if st.button("Rerun", key=f"history_rerun_{i}", width="stretch"):
                    db_mtime = DB_PATH.stat().st_mtime if DB_PATH.exists() else 0
                    results = cached_search(
                        entry["title"],
                        entry["keywords"],
                        entry["abstract"],
                        entry["language"],
                        entry["free_only"],
                        entry["min_budget"],
                        entry["max_budget"],
                        entry["indexing"],
                        entry["quartiles"],
                        entry["sinta_levels"],
                        entry["max_review_weeks"],
                        entry["strategy"],
                        db_mtime,
                    )
                    st.session_state.search = {
                        "results": results,
                        "strategy_label": entry["strategy_label"],
                    }
                    st.session_state.page = 1
                    st.session_state.show_weaker = False
                    st.rerun()

    st.divider()

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
            "Confidence is relative to this search's own results and requires "
            "a minimum absolute match strength — it isn't a validated prediction, "
            "just a way to surface the strongest matches first."
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
    # Compact card answers "should I open this?" — title, confidence,
    # indexing, country, APC, language, and a one-line reason. Publisher,
    # full subjects, ISSN, and license move to "Show more", which answers
    # "should I submit here?". Every card widget is keyed by the
    # journal's database id (not list position) so pagination can't mix
    # up expanded/collapsed state between different journals landing in
    # the same on-page slot.
    # ------------------------------------------------------

    for journal in page_results:

        with st.container(border=True, key=f"card_{journal['id']}"):

            title_col, badge_col = st.columns([4, 1])

            with title_col:
                st.markdown(f"**{journal['title']}**")

            with badge_col:
                st.badge(
                    journal["confidence"],
                    color=CONFIDENCE_COLORS.get(journal["confidence"], "gray"),
                )
                st.caption(CONFIDENCE_STARS.get(journal["confidence"], ""))

            st.write(format_index_chips(journal["source_details"]) or "—")

            if journal.get("explanation"):
                st.caption(journal["explanation"])

            meta_col1, meta_col2, meta_col3 = st.columns(3)

            with meta_col1:
                st.caption("Country")
                st.write(journal["country"] or "—")

            with meta_col2:
                st.caption("Language")
                st.write(journal["languages"] or "—")

            with meta_col3:
                apc_label = "Free" if journal["is_free"] else (
                    f"~${journal['apc_amount']:.0f}"
                    if journal["apc_amount"] is not None
                    else "Paid (unconfirmed)"
                )
                st.caption("APC")
                st.write(apc_label)

            with st.expander("Show more", key=f"expander_{journal['id']}"):

                st.write(f"**Publisher:** {journal['publisher'] or 'Not listed'}")

                subject_tags = format_subjects(journal["subjects"])
                if subject_tags:
                    st.write(f"**Subjects:** {subject_tags}")

                if journal["review_weeks"] is not None:
                    st.write(f"**Typical review time:** ~{journal['review_weeks']} weeks")

                secondary_bits = []
                if journal["issn_print"] or journal["issn_online"]:
                    secondary_bits.append(
                        f"ISSN: {journal['issn_print'] or '—'} (print) / "
                        f"{journal['issn_online'] or '—'} (online)"
                    )
                if journal["license"]:
                    secondary_bits.append(f"License: {journal['license']}")
                if secondary_bits:
                    st.caption("  ·  ".join(secondary_bits))

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
    # Pagination (below the results)
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