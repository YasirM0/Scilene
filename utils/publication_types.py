"""
Publication type badge formatting (#128).

`journals.publication_type` only ever comes from the Elsevier Source
List today (importers/elsevier.py's "Source Type" column -- in the
real dataset, only "Journal", "Book Series", or "Trade Journal" occur)
-- every other type below is a real, normalized label the schema and
this mapping already support, just not populated by any importer yet.
DOAJ-only journals (no Elsevier match) default to "Journal" because
that's DOAJ's own definitional scope, not a guess; anything else
unmapped or unmatched falls back to "Other", never fabricated.
"""

# Raw value (as a source might spell it) -> normalized label. Values
# are their own keys too, so an already-normalized label passes through.
_TYPE_ALIASES = {
    "journal": "Journal",
    "conference proceedings": "Conference Proceedings",
    "conference": "Conference",
    "book series": "Book Series",
    "book": "Book",
    "book chapter": "Book Chapter",
    "trade journal": "Trade Journal",
    "magazine": "Magazine",
    "report": "Report",
    "repository": "Repository",
}

# label -> (icon, badge classes). Deliberately one consistent muted
# style, not a color per type -- this badge shouldn't compete with the
# recommendation-confidence badge, the one color-coded signal on a
# card that's actually meant to draw the eye.
_BADGE_CLASSES = "px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300"

_ICONS = {
    "Journal": "📄",
    "Conference Proceedings": "🎤",
    "Conference": "🎤",
    "Book Series": "📚",
    "Book": "📖",
    "Book Chapter": "📑",
    "Trade Journal": "🏷️",
    "Magazine": "📰",
    "Report": "📊",
    "Repository": "🗄️",
    "Other": "❓",
}


def normalize_publication_type(raw):
    if not raw:
        return None
    return _TYPE_ALIASES.get(raw.strip().lower(), "Other")


def resolve_publication_type(journal):
    """
    The label to actually show for a journal (#128's "unknown types
    should gracefully fall back to Other", extended with one further,
    real fallback: a DOAJ-sourced journal with no Elsevier match is
    still known to be a journal -- DOAJ doesn't index anything else --
    so that's shown as "Journal", not "Other").
    """
    normalized = normalize_publication_type(journal.publication_type)
    if normalized:
        return normalized
    if "DOAJ" in (journal.sources or []) or journal.source == "DOAJ":
        return "Journal"
    return "Other"


def format_publication_type_badge(journal):
    """{"label", "icon", "classes"} for the template -- always
    returns something (#128: "Display a publication type badge on
    every result")."""
    label = resolve_publication_type(journal)
    return {
        "label": label,
        "icon": _ICONS.get(label, _ICONS["Other"]),
        "classes": _BADGE_CLASSES,
    }
