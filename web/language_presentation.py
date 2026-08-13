"""
Presentation-only helpers for the language filter card (#89) --
shared between web/routers/search.py (initial page render) and
web/routers/interpreter.py (the /search/interpret abstract-blur
trigger, which is what actually detects and pre-selects a language),
so the two can never disagree about what the card should show for a
given session. Mirrors web/interpreter_presentation.py's role for the
Research Interpreter panel.
"""

from web.filter_defaults import default_languages
from web.search_presentation import LANGUAGE_OPTIONS


def language_form_context(session, locale):
    detected = session.get("detected_language")
    touched = session.get("language_touched", False)
    if detected and not touched:
        selected = [detected]
    elif not touched:
        # No detection yet (empty/too-short abstract, or none typed)
        # -- fall back to the locale's smart default (#143) rather
        # than an unfiltered "Any language".
        selected = default_languages(locale)
    else:
        # User has manually touched the filter at some point this
        # session -- their real current picks live only in the DOM
        # (HTMX architecture), so on a fresh full-page render we can't
        # know them; "Any language" is the safest assumption, same as
        # before this change.
        selected = []
    return {
        "language_options": LANGUAGE_OPTIONS,
        "selected_languages": selected,
        "detected_language": detected,
        "language_touched": touched,
    }
