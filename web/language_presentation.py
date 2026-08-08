"""
Presentation-only helpers for the language filter card (#89) --
shared between web/routers/search.py (initial page render) and
web/routers/interpreter.py (the /search/interpret abstract-blur
trigger, which is what actually detects and pre-selects a language),
so the two can never disagree about what the card should show for a
given session. Mirrors web/interpreter_presentation.py's role for the
Research Interpreter panel.
"""

from web.search_presentation import LANGUAGE_OPTIONS


def language_form_context(session):
    detected = session.get("detected_language")
    touched = session.get("language_touched", False)
    return {
        "language_options": LANGUAGE_OPTIONS,
        "selected_languages": [detected] if (detected and not touched) else [],
        "detected_language": detected,
        "language_touched": touched,
    }
