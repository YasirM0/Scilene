"""
Locale-aware default filter selections for the Submission Search page
(#143). A session's UI locale is a reasonable proxy for what a user is
likely searching for by default -- e.g. someone browsing in Indonesian
is more likely targeting a SINTA-relevant, Indonesian-language outlet
than the global default of Scopus/English. These are only ever
STARTING points applied on a fresh page load (or after Clear Search);
nothing here restricts what a user can select afterward.
"""

from web.search_presentation import SINTA_LEVEL_OPTIONS

# SINTA 5/6 are being phased out nationally -- still valid, selectable
# options (see SINTA_LEVEL_OPTIONS), just never part of the default.
_SINTA_DEFAULT_LEVELS = {"SINTA 1", "SINTA 2", "SINTA 3", "SINTA 4"}


def default_indexing(locale):
    if locale == "id":
        return ["DOAJ", "SINTA"]
    return ["DOAJ", "Scopus"]


def default_languages(locale):
    if locale == "ar":
        return ["English", "Arabic"]
    if locale == "id":
        return ["English", "Indonesian"]
    return ["English"]


def default_sinta_levels(locale):
    if locale != "id":
        return []
    return [level for level in SINTA_LEVEL_OPTIONS if level in _SINTA_DEFAULT_LEVELS]
