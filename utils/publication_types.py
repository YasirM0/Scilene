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

_looks_like_conference_proceedings() below is a second, title-keyword
signal on top of that -- checked directly against the live database:
Elsevier's own "Journal" tag, for this dataset, is applied to hundreds
of obviously-a-conference-proceedings sources too ("Proceedings of the
IEEE International Conference on Big Data, BigData 2024" is tagged
"Journal", along with 143 other IEEE/ACM/etc. examples found by this
exact search), and a DOAJ-only entry with the same shape of title would
otherwise silently default to "Journal" via the fallback below. Title
text is a real, if imperfect, signal worth acting on before a better
one (OpenAlex's own Sources `type` field -- see
scripts/backfill_openalex_taxonomy.py) exists for every journal.
"""

import re

# Deliberately NOT "proceedings" alone -- "Proceedings of the National
# Academy of Sciences", "Proceedings of the Royal Society B", and
# dozens of other "Proceedings of the/from the [Academy|Society]..."
# titles are real, prestigious, definitely-submittable journals (their
# own long-standing name predates "proceedings" meaning "conference
# output"), verified directly against the live database. Every genuine
# conference-proceedings title found by direct sampling instead
# contains "conference", "symposium", or "workshop" ("SHS Web of
# Conferences", "IEEE ... Symposium on X", "Proceedings of the
# Workshop on Y") -- those three are a clean signal on their own.
_CONFERENCE_KEYWORDS_RE = re.compile(r"\b(conference|symposium|workshop)s?\b", re.IGNORECASE)

# A title that plainly calls itself a "Journal" overrides the keywords
# above -- "History Workshop Journal" and "Symposium: A Quarterly
# Journal in Modern Literatures" are real journals about workshops/
# symposia, not proceedings FROM one, and say so themselves.
_JOURNAL_TITLE_RE = re.compile(r"\bjournal\b", re.IGNORECASE)


def _looks_like_conference_proceedings(title):
    if not title:
        return False
    if _JOURNAL_TITLE_RE.search(title):
        return False
    return bool(_CONFERENCE_KEYWORDS_RE.search(title))

# Raw value (as a source might spell it) -> normalized label. Values
# are their own keys too, so an already-normalized label passes through.
_TYPE_ALIASES = {
    "journal": "Journal",
    "conference proceedings": "Conference Proceedings",
    "conference": "Conference",
    # OpenAlex's own Sources `type` spelling (scripts/
    # backfill_openalex_publication_type.py) -- distinct key from plain
    # "conference" above since a source list might spell it either way.
    "conference series": "Conference Proceedings",
    "book series": "Book Series",
    "book": "Book",
    "book chapter": "Book Chapter",
    "trade journal": "Trade Journal",
    "magazine": "Magazine",
    "report": "Report",
    "repository": "Repository",
    # OpenAlex-only values (rare) -- an ebook platform is closer to a
    # "Book" than a journal; "metadata" (an index/aggregator source,
    # not a publication venue itself) has nothing closer than "Other".
    "ebook platform": "Book",
    "metadata": "Other",
}

# label -> (icon, badge classes). Deliberately one consistent muted
# style, not a color per type -- this badge shouldn't compete with the
# recommendation-confidence badge, the one color-coded signal on a
# card that's actually meant to draw the eye.
_BADGE_CLASSES = "px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300"

# Scilene is a JOURNAL recommendation tool -- these types aren't a venue
# a researcher can submit to the way a journal's open call works
# (a proceedings entry requires attending/being accepted to that one
# conference; a book chapter requires an editor's invitation), so
# they're not a normal, actionable search result. Badged AND hidden by
# default (see web/search_presentation.py's filter_visible_results,
# same "show weaker matches" toggle also reveals these) -- everything
# else (plain "Journal", the overwhelming majority; "Book Series" and
# "Trade Journal", which a researcher genuinely can submit a standalone
# piece to) gets no badge at all, since labeling the default case would
# just be noise. As of this writing, no importer actually populates
# any of these three values yet (utils/publication_types.py's own
# module docstring) -- Elsevier's Source List only ever yields
# "Journal"/"Book Series"/"Trade Journal" for this dataset, so this is
# a no-op today, ready for whenever a source that classifies at this
# granularity (OpenAlex's own Sources `type` field is the candidate --
# see importers/enrichment/openalex.py, which already calls that same
# endpoint for subject taxonomy but doesn't map `type` yet) backfills
# journals.publication_type with a real "Conference Proceedings" or
# "Book Chapter" value.
HIDDEN_BY_DEFAULT_TYPES = {"Conference Proceedings", "Conference", "Book Chapter"}

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
    should gracefully fall back to Other", extended with two further,
    real fallbacks: a DOAJ-sourced journal with no Elsevier match is
    still known to be a journal -- DOAJ doesn't index anything else --
    so that's shown as "Journal", not "Other"; and a title that reads
    as a conference/symposium/workshop's proceedings overrides a
    generic Journal/Other/unclassified result -- see
    _looks_like_conference_proceedings()'s own comment for why this is
    title text, not something invented, and why it only overrides the
    generic case, never a curated non-Journal classification like
    "Book Series"/"Trade Journal" that Elsevier already distinguished
    deliberately).
    """
    normalized = normalize_publication_type(journal.publication_type)
    if normalized in (None, "Journal", "Other") and _looks_like_conference_proceedings(journal.title):
        return "Conference Proceedings"
    if normalized:
        return normalized
    if "DOAJ" in (journal.sources or []) or journal.source == "DOAJ":
        return "Journal"
    return "Other"


def format_publication_type_badge(journal):
    """
    {"label", "icon", "classes"} for the template -- but only for a
    HIDDEN_BY_DEFAULT_TYPES type (see that constant's own comment for
    why). None for everything else, including the plain "Journal" case
    that used to always get a badge (#128) -- a tool that recommends
    journals labeling "this is a journal" on every single result added
    noise, not information. Callers already guard on this being falsy
    (see components/journal_card.html) -- a template that doesn't will
    need its own {% if %}.
    """
    label = resolve_publication_type(journal)
    if label not in HIDDEN_BY_DEFAULT_TYPES:
        return None
    return {
        "label": label,
        "icon": _ICONS.get(label, _ICONS["Other"]),
        "classes": _BADGE_CLASSES,
    }
