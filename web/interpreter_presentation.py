"""
Presentation-only helpers for the Research Interpreter panel
(docs/RESEARCH_INTERPRETER.md) -- shared between web/routers/search.py
(initial page render) and web/routers/interpreter.py (HTMX partial
updates), so the two can never disagree about what state the panel
should be in for a given session.
"""

from services.research_interpreter import field_of_study_examples


def current_suggestions_context(session):
    suggestions = session.get("interpreter_suggestions") or []
    # Field of Study examples (see services/research_interpreter.py's
    # module docstring for why these are non-interactive "e.g." text,
    # not a suggestion like `suggestions` above) live in the tag-box
    # component, not this panel -- computed here anyway so both
    # web/routers/search.py's initial render and
    # web/routers/interpreter.py's HTMX updates get the same value
    # from the same abstract snapshot, same reasoning as `suggestions`.
    abstract = session.get("interpreter_abstract_snapshot") or ""
    field_examples = field_of_study_examples(abstract)

    if suggestions:
        return {
            "state": "suggestions",
            "suggestions": suggestions,
            # #110 "✏ Edit" -- which row (if any) shows an inline input
            # instead of its normal ✓/↻ actions.
            "editing_category": session.get("interpreter_editing_category"),
            "field_examples": field_examples,
        }
    return {"state": "empty", "field_examples": field_examples}
