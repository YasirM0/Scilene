"""
Research Interpreter.

Suggests normalized research concepts (a field of study, a key
research focus) from an abstract -- see docs/RESEARCH_INTERPRETER.md.

"Field of Study" is real as of #53: services/field_detection.py
matches the abstract against the database's own subject vocabulary
(journals.subjects), deterministic and not a fake AI call. "Key
Research Focus" is real as of #113's follow-up: services/focus_detection.py
does the same thing against journals.keywords (a narrower, per-journal
vocabulary, matching this slot's own narrower intent) -- replacing a
fixed 5-item placeholder pool that suggested things like "Robotics" for
an abstract about internet access and social stratification. Nothing
that calls suggest_concepts()/next_suggestion() needs to know either
category is deterministic keyword-vocabulary matching, not an LLM.

Both fallback pools below only ever show when their respective
detector finds nothing in the abstract at all (no database term of
that kind appears in it) -- keeping the suggestion slot non-empty
rather than showing nothing, not a claim that the fallback is itself
detected from the text.

Never imported by services/recommender.py. A suggestion only ever
reaches the recommendation engine after a human confirms it (see
web/routers/interpreter.py's accept route) -- at that point it's just
a plain string in the same `keywords` list a manually-typed tag would
join, indistinguishable from one. The interpreter itself has no path
to influence scoring.
"""

from services.field_detection import detect_fields
from services.focus_detection import detect_focus_terms

FIELD_OF_STUDY_FALLBACK_POOL = [
    "Computer Science",
    "Public Health",
    "Environmental Science",
    "Economics",
    "Psychology",
]

KEY_FOCUS_FALLBACK_POOL = [
    "Robotics",
    "Climate Adaptation",
    "Behavioral Economics",
    "Machine Learning",
    "Urban Policy",
]

# category -> (label, tag color). No pool baked in here anymore -- both
# pools depend on the abstract, see _field_pool().
CATEGORIES = {
    "field_of_study": ("Field of Study", "blue"),
    "key_focus": ("Key Research Focus", "gold"),
}


def _field_pool(category, abstract):
    if category == "field_of_study":
        detected = detect_fields(abstract)
        return detected if detected else FIELD_OF_STUDY_FALLBACK_POOL
    detected = detect_focus_terms(abstract)
    return detected if detected else KEY_FOCUS_FALLBACK_POOL


def suggest_concepts(abstract):
    """
    Returns the initial suggestion for each category -- the top real
    match from that category's own detector (detect_fields() /
    detect_focus_terms()) against the abstract, or that category's
    fallback pool's first entry if nothing matched. See
    next_suggestion() for cycling.
    """
    return [
        {
            "category": category,
            "label": label,
            "value": _field_pool(category, abstract)[0],
            "color": color,
            "cycled": False,
        }
        for category, (label, color) in CATEGORIES.items()
    ]


def next_suggestion(category, current_value, abstract=""):
    """Cycles a category's suggestion to the next value in its pool
    (the real detected-fields list for "field_of_study", computed from
    the same abstract the current suggestions came from; the fixed
    pool for "key_focus")."""
    pool = _field_pool(category, abstract)
    try:
        index = pool.index(current_value)
    except ValueError:
        index = -1
    return pool[(index + 1) % len(pool)]
