"""
Portable Search Sessions -- .sls format (#91, renamed from .jis by #136).

A .sls file is a plain JSON document capturing everything needed to
genuinely RE-RUN a search on another device/session -- not a frozen
snapshot of results. Recommendations depend on the live database, so
"reopen" here means "reproduce," matching the principle search-history
rerun and #102's refine-with-disciplines already establish: exactly
`session["last_search_params"]` is what this format exports, and
importing calls the same _execute_search() a manual search does.

Fields the issue names that aren't real features yet ("notes", "future
AI outputs") are included as reserved, always-null keys rather than
silently dropped -- the format commits to their shape now, but nothing
in this app writes to them yet (no note-taking UI exists to populate
"notes"; "ai_outputs" is reserved for a future Research Idea/Interpreter
export, neither generates anything durable enough to export today).

parse_sls_import() also accepts the legacy .jis format (#136's
required backward compatibility) -- both are the exact same JSON shape,
identified by "format": "jis" instead of "sls", from back when this
project was called Journal Intelligence. New exports always write
"sls"; only import reads the old tag.
"""

import json
from datetime import datetime, timezone

SLS_FORMAT_VERSION = 1
_LEGACY_FORMAT_TAGS = ("sls", "jis")


class InvalidSlsFile(Exception):
    pass


def build_sls_export(session, app_version):
    params = session.get("last_search_params") or {}
    search_meta = session.get("search_meta") or {}

    return {
        "format": "sls",
        "version": SLS_FORMAT_VERSION,
        "app_version": app_version,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "search": {
            "abstract": params.get("abstract", ""),
            # search_meta["keywords"], NOT session["confirmed_tags"] --
            # the latter misses fallback_tags-only searches (typed
            # directly into the "at least 10 tags" field, #110's
            # tag-based path), which never get copied into
            # confirmed_tags. search_meta["keywords"] is exactly what
            # _execute_search() actually searched with either way.
            "confirmed_tags": search_meta.get("keywords", []),
            "strategy_label": params.get("strategy_label", ""),
            "languages": params.get("resolved_languages"),
            "free_only": params.get("free_only", False),
            "min_budget": params.get("min_budget"),
            "max_budget": params.get("max_budget"),
            "indexing": params.get("indexing"),
            "quartiles": params.get("quartiles"),
            "sinta_levels": params.get("sinta_levels"),
            "max_review_weeks": params.get("max_review_weeks"),
        },
        # Informational only -- a preview for a human opening the raw
        # file, never read back on import (results are always
        # regenerated live, not replayed).
        "results_snapshot": {
            "result_count": len(session.get("current_results") or []),
            "display_label": search_meta.get("display_label", ""),
        },
        "notes": None,
        "ai_outputs": None,
    }


def serialize_sls(session, app_version):
    return json.dumps(build_sls_export(session, app_version), indent=2, ensure_ascii=False).encode("utf-8")


def parse_sls_import(raw_bytes):
    """Returns the validated `search` dict, or raises InvalidSlsFile
    with a message safe to show the user directly. Accepts both the
    current .sls format and legacy .jis exports (#136)."""
    try:
        data = json.loads(raw_bytes)
    except (ValueError, UnicodeDecodeError):
        raise InvalidSlsFile("This file isn't valid JSON.")

    if not isinstance(data, dict) or data.get("format") not in _LEGACY_FORMAT_TAGS:
        raise InvalidSlsFile("This doesn't look like a Scilene session file (.sls, or a legacy .jis).")

    search = data.get("search")
    if not isinstance(search, dict):
        raise InvalidSlsFile("This session file is missing its search data.")

    if not search.get("abstract") and len(search.get("confirmed_tags") or []) < 10:
        raise InvalidSlsFile(
            "This session has neither an abstract nor at least 10 tags -- "
            "nothing to search with."
        )

    return search
