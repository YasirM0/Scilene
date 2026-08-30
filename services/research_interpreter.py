"""
Research Interpreter.

Suggests a key research focus, and separately offers field-of-study
EXAMPLES, from an abstract -- see docs/RESEARCH_INTERPRETER.md.

"Key Research Focus" is real as of #113's follow-up:
services/focus_detection.py matches the abstract against
journals.keywords (a narrower, per-journal vocabulary), deterministic
and not a fake AI call -- replacing a fixed 5-item placeholder pool
that suggested things like "Robotics" for an abstract about internet
access and social stratification. It's the one category that still
goes through the full accept/suggest-another/edit interactive flow
(CATEGORIES below), because its matches held up under real testing.

Both this and Field of Study match against English-only vocabulary
(journals.keywords/subjects), so a raw Indonesian abstract mostly
missed both entirely -- confirmed directly: 61.4% of a real 295-
abstract Indonesian sample got zero Field of Study match. `_field_pool()`
and `field_of_study_examples()` below run the abstract through
services/query_translator.py's `translate_for_interpretation()` first
(dictionary translation for Indonesian, unchanged for everything else)
-- stress-tested to cut that miss rate to 28.5%. Not zero: Field of
Study's underlying vocabulary is only ~20-44 broad category names,
too coarse for a lot of abstracts regardless of language (see below) --
translation narrows the language gap, it doesn't fix the vocabulary's
own coarseness.

"Field of Study" (#53's services/field_detection.py, matching
journals.subjects -- only ~20 broad categories) did NOT hold up:
tested directly against a real abstract about internet access and
social stratification in Indonesia, it suggested "Computer Science",
then "Environmental Science", then "Public Health" on retries -- none
accurate. An embedding-similarity alternative was tried too (ranking
category names by cosine similarity to the abstract) and didn't fix
it either (ranked "Technology" above "Social Sciences" for the same
abstract -- a different guess, not a clearly correct one). The
underlying problem is structural: the vocabulary is only ~20-44 broad
category names, too coarse for a specific interdisciplinary topic, not
something either technique fixes. So field_of_study_examples() below
is deliberately NOT presented as a confident "detected" claim the way
key_focus is -- see web/templates/components/search_concepts_section.html,
where its output appears as plain "e.g." inspiration text next to the
tag box, not an accept/reject suggestion.

Never imported by services/recommender.py. A suggestion only ever
reaches the recommendation engine after a human confirms it (see
web/routers/interpreter.py's accept route, or the user typing a field
example into the tag box themselves) -- at that point it's just a
plain string in the same `keywords` list a manually-typed tag would
join, indistinguishable from one. The interpreter itself has no path
to influence scoring.
"""

from services.field_detection import detect_fields
from services.focus_detection import detect_focus_terms
from services.query_translator import translate_for_interpretation

# Shown as example text (never a "detected" claim -- see module
# docstring) when detect_fields() finds nothing in the abstract.
FIELD_OF_STUDY_EXAMPLE_POOL = [
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

# category -> (label, tag color) -- only categories confident enough to
# be an interactive accept/suggest-another/edit suggestion belong here.
# Field of Study is deliberately NOT one of them; see this module's
# docstring.
CATEGORIES = {
    "key_focus": ("Key Research Focus", "gold"),
}


def _field_pool(category, abstract):
    detected = detect_focus_terms(translate_for_interpretation(abstract))
    return detected if detected else KEY_FOCUS_FALLBACK_POOL


def suggest_concepts(abstract):
    """
    Returns the initial suggestion for each interactive category (just
    "key_focus" -- see CATEGORIES) -- the top real match from
    detect_focus_terms(abstract), or the fallback pool's first entry
    if nothing matched. See next_suggestion() for cycling.
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
    """Cycles "key_focus" to the next value in its pool (the real
    detected-focus-terms list, or the fixed fallback pool if nothing
    matched)."""
    pool = _field_pool(category, abstract)
    try:
        index = pool.index(current_value)
    except ValueError:
        index = -1
    return pool[(index + 1) % len(pool)]


def field_of_study_examples(abstract, top_n=3):
    """
    Non-interactive field/subfield EXAMPLES for the tag box (never an
    accept/reject suggestion -- see module docstring for why). Empty
    abstract -> no examples (nothing to base them on, and idea mode's
    tag box has its own separate helper text already). A non-empty
    abstract always returns something: real detect_fields() matches
    when there are any, otherwise the illustrative example pool --
    once nothing here claims to be "detected", showing generic
    examples is honest, not misleading.
    """
    if not abstract or not abstract.strip():
        return []
    detected = detect_fields(translate_for_interpretation(abstract))
    return detected[:top_n] if detected else FIELD_OF_STUDY_EXAMPLE_POOL[:top_n]
