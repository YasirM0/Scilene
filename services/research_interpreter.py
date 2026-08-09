"""
Research Interpreter.

Suggests normalized research concepts (a field of study, a key
research focus) from an abstract -- see docs/RESEARCH_INTERPRETER.md.

"Field of Study" is real as of #53: services/field_detection.py
matches the abstract against the database's own subject vocabulary
(journals.subjects), deterministic and not a fake AI call. "Key
Research Focus" is still UI/interaction scaffolding only -- a fixed
placeholder pool, since extracting a genuine "key focus" concept
(narrower than a field, not literally present in any existing
vocabulary) needs real analysis this project doesn't have yet. Nothing
that calls suggest_concepts()/next_suggestion() needs to know which
category is real and which isn't.

Never imported by services/recommender.py. A suggestion only ever
reaches the recommendation engine after a human confirms it (see
web/routers/interpreter.py's accept route) -- at that point it's just
a plain string in the same `keywords` list a manually-typed tag would
join, indistinguishable from one. The interpreter itself has no path
to influence scoring.
"""

from services.field_detection import detect_fields

# Shown for "Field of Study" only when detect_fields() finds nothing
# in the abstract (no database subject term appears in it) -- keeps
# the suggestion slot non-empty rather than showing nothing. Clearly a
# fallback, not a detection: reusing the pool from before #53.
FIELD_OF_STUDY_FALLBACK_POOL = [
    "Computer Science",
    "Public Health",
    "Environmental Science",
    "Economics",
    "Psychology",
]

KEY_FOCUS_POOL = [
    "Robotics",
    "Climate Adaptation",
    "Behavioral Economics",
    "Machine Learning",
    "Urban Policy",
]

# category -> (label, tag color). No pool baked in here anymore --
# "field_of_study"'s pool depends on the abstract (see _field_pool()),
# "key_focus"'s is still the fixed placeholder above.
CATEGORIES = {
    "field_of_study": ("Field of Study", "blue"),
    "key_focus": ("Key Research Focus", "gold"),
}


def _field_pool(category, abstract):
    if category == "field_of_study":
        detected = detect_fields(abstract)
        return detected if detected else FIELD_OF_STUDY_FALLBACK_POOL
    return KEY_FOCUS_POOL


def suggest_concepts(abstract):
    """
    Returns the initial suggestion for each category -- "field_of_study"
    is the top real match from detect_fields(abstract) (or the fallback
    pool's first entry if nothing matched); "key_focus" is still the
    placeholder pool's first entry. See next_suggestion() for cycling.
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
