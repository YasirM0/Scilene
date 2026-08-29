"""
Process-wide cache for services.search_service.search_journals() calls,
keyed by every parameter that affects the result plus the database
file's mtime (so rebuilding the database via scripts/build_database.py
invalidates it automatically, without needing an explicit cache-clear
step). Mirrors what the Streamlit app's own st.cache_data wrapper
already did for the same call, for the same reason: a multi-keyword
search over the full database is real work, and re-running it for an
unchanged query (a double-submitted form, a page refresh, browser
back/forward) is pure waste.

Process-wide rather than per-session (unlike session_store.py): the
result for identical inputs is identical for every user, so there's no
reason to scope this per browser session the way the results/history
themselves are.
"""

from services import search_service
from services.repository import DB_PATH

_CACHE: dict[tuple, list] = {}
_CACHE_MAX_ENTRIES = 200


def _cache_key(**kwargs):
    db_mtime = DB_PATH.stat().st_mtime if DB_PATH.exists() else 0
    return (
        kwargs.get("title"),
        tuple(kwargs.get("keywords") or ()),
        kwargs.get("abstract"),
        tuple(kwargs["languages"]) if kwargs.get("languages") else None,
        kwargs.get("free_only"),
        kwargs.get("min_budget"),
        kwargs.get("max_budget"),
        tuple(kwargs["indexing"]) if kwargs.get("indexing") else None,
        tuple(kwargs["quartiles"]) if kwargs.get("quartiles") else None,
        tuple(kwargs["sinta_levels"]) if kwargs.get("sinta_levels") else None,
        kwargs.get("max_review_weeks"),
        kwargs.get("strategy"),
        tuple(sorted(kwargs["categories"])) if kwargs.get("categories") else None,
        db_mtime,
    )


def cached_search(**kwargs):
    key = _cache_key(**kwargs)

    if key in _CACHE:
        return _CACHE[key]

    results = search_service.search_journals(**kwargs)

    if len(_CACHE) >= _CACHE_MAX_ENTRIES:
        _CACHE.pop(next(iter(_CACHE)))  # drop the oldest entry (dicts preserve insertion order)

    _CACHE[key] = results

    return results
