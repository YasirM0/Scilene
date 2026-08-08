"""
Presentation-only helpers for the Research Interpreter panel
(docs/RESEARCH_INTERPRETER.md) -- shared between web/routers/search.py
(initial page render) and web/routers/interpreter.py (HTMX partial
updates), so the two can never disagree about what state the panel
should be in for a given session.
"""


def current_suggestions_context(session):
    suggestions = session.get("interpreter_suggestions") or []
    if suggestions:
        return {"state": "suggestions", "suggestions": suggestions}
    return {"state": "empty"}
