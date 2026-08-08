"""
Shared, Streamlit-free formatting for a journal's alternate/historical
titles (#100). Used by the recommendation card; mirrors utils/indexing.py's
role for confirmed indexing sources.
"""

# journal_aliases.alias_type as stored (see importers/aliases.py) is
# already close to display-ready, but a couple of types read better
# with different wording on a journal card than as raw provenance --
# this only affects the label shown, never what's stored/matched on.
_DISPLAY_LABELS = {
    "Alternative title": "Also published as",
}


def format_alias_line(aliases):
    """
    One alias to show under a journal's title, or None if it has no
    known aliases. Picks the first one recorded -- a journal card has
    room for a single secondary line, not a full alias list.
    """
    if not aliases:
        return None

    primary = aliases[0]
    label = _DISPLAY_LABELS.get(primary["alias_type"], primary["alias_type"])
    return f"{label}: {primary['alias']}"
