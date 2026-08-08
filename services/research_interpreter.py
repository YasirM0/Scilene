"""
Research Interpreter (placeholder).

Suggests normalized research concepts (a field of study, a key
research focus) from an abstract. This is UI/interaction scaffolding
only -- see docs/RESEARCH_INTERPRETER.md. The real interpreter is
expected to be an embedding-based classifier, not a generative model,
so this module deliberately exposes no prompt-construction or
LLM-specific shape: just abstract text in, a short list of concept
suggestions out. Swapping the body of suggest_concepts() for a real
model later should not require changing anything that calls it.

Never imported by services/recommender.py. A suggestion only ever
reaches the recommendation engine after a human confirms it (see
web/routers/interpreter.py's accept route) -- at that point it's just
a plain string in the same `keywords` list a manually-typed tag would
join, indistinguishable from one. The interpreter itself has no path
to influence scoring.
"""

FIELD_OF_STUDY_POOL = [
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

# category -> (label, placeholder pool, tag color)
CATEGORIES = {
    "field_of_study": ("Field of Study", FIELD_OF_STUDY_POOL, "blue"),
    "key_focus": ("Key Research Focus", KEY_FOCUS_POOL, "gold"),
}


def suggest_concepts(abstract):
    """
    Returns the initial suggestion for each category. Always the pool's
    first entry for now (deterministic placeholder, not real analysis
    of `abstract`) -- see next_suggestion() for cycling to another one.
    """
    return [
        {
            "category": category,
            "label": label,
            "value": pool[0],
            "color": color,
            "cycled": False,
        }
        for category, (label, pool, color) in CATEGORIES.items()
    ]


def next_suggestion(category, current_value):
    """Cycles a category's suggestion to the next value in its pool."""
    _, pool, _ = CATEGORIES[category]
    try:
        index = pool.index(current_value)
    except ValueError:
        index = -1
    return pool[(index + 1) % len(pool)]
