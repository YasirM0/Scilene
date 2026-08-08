"""
In-memory, per-browser-session state for search results and search
history — the FastAPI equivalent of Streamlit's st.session_state, and
scoped the same way on purpose: ephemeral, cleared on server restart,
not shared across processes. This is what lets pagination, the "show
weaker matches" toggle, and search-history "Rerun" all avoid re-running
an expensive search — they just re-read and re-filter what's already
here.

Not safe for a multi-worker/multi-process deployment (each worker
process would have its own dict, so a user could bounce between
workers and see an empty session) -- that's an explicit, disclosed
limitation, not an oversight. It matches Streamlit's own single-process
session model, which is the parity bar for this migration; moving to a
real shared session store (Redis, etc.) is future work if/when this
runs behind multiple workers.
"""

import time
import uuid

_SESSIONS: dict[str, dict] = {}
_SESSION_TTL_SECONDS = 60 * 60 * 4  # 4 hours of inactivity

MAX_HISTORY_ENTRIES = 10


def new_session_id() -> str:
    return uuid.uuid4().hex


def get_session(session_id: str) -> dict:
    """
    Returns the mutable state dict for this session, creating it (with
    sensible defaults) on first use. Callers mutate the dict directly
    and it persists — there's no separate "save" step, same as
    st.session_state.
    """
    _evict_expired()

    if session_id not in _SESSIONS:
        _SESSIONS[session_id] = {
            "current_results": None,      # full, unfiltered results from the last search
            "visible_results": None,      # confidence-filtered results currently on screen (what exports read)
            "search_meta": None,          # abstract/display_label/strategy_label/filters_summary of the last search
            "show_weaker": False,
            "page": 1,
            "history": [],                # list of {results, search_meta, timestamp, result_count}

            # Research Interpreter (docs/RESEARCH_INTERPRETER.md) --
            # suggestions the user hasn't accepted/removed yet.
            "interpreter_suggestions": [],
            # The abstract text suggestions were last generated from,
            # to detect "abstract changed since suggesting" without
            # comparing against confirmed_tags (which can also change
            # for unrelated reasons, e.g. removing a manually-added tag).
            "interpreter_abstract_snapshot": None,
            # Plain strings -- accepted interpreter suggestions and
            # manually-added/fallback tags land here indistinguishably.
            # This list (plus any fallback_tags parsed at submit time)
            # is exactly what becomes the recommender's `keywords`.
            "confirmed_tags": [],

            # Which suggestion category (if any) is currently showing
            # an inline edit input instead of its normal ✓/↻ row (#110,
            # "✏ Edit"). At most one at a time -- like
            # interpreter_suggestions, this is UI state, never read by
            # the recommender.
            "interpreter_editing_category": None,

            # Raw kwargs from the last real search (#102) -- lets
            # "refine with detected disciplines" genuinely re-run the
            # same search with an expanded concept list, rather than
            # faking a recalculation. Set by web/routers/search.py's
            # _execute_search(); search_meta above is the *display*
            # version (human-readable filters_summary, not reusable
            # raw values), which is why this exists separately.
            "last_search_params": None,

            # Cross-language discovery (#89) -- the language the
            # abstract was detected as (services/language_detection.py),
            # and whether the user has manually touched the language
            # checkboxes since (if so, the "detected X" hint stops
            # showing, even though the detected value is kept).
            "detected_language": None,
            "language_touched": False,

            # #85 -- abstract text to pre-fill the Submission Search
            # page's abstract textarea with, set by "Continue to
            # Search" from the Research Idea modal. Popped (read once)
            # by web/routers/search.py's search_page(), not persisted
            # across a later, unrelated page load.
            "prefill_abstract": None,

            # #108 -- whether the "Get more info online" button appears
            # on journal cards at all. On by default (the lazy-click
            # design already means nothing fetches without an explicit
            # per-journal click -- see docs/ENRICHMENT.md's "Implementation
            # note" on why that already satisfies web's consent needs);
            # this lets a user opt all the way out if they'd rather this
            # app never talk to an external API on their behalf.
            "enrichment_enabled": True,
        }

    _SESSIONS[session_id]["_last_access"] = time.time()

    return _SESSIONS[session_id]


def _evict_expired():
    cutoff = time.time() - _SESSION_TTL_SECONDS
    expired = [
        session_id
        for session_id, data in _SESSIONS.items()
        if data.get("_last_access", 0) < cutoff
    ]
    for session_id in expired:
        del _SESSIONS[session_id]
