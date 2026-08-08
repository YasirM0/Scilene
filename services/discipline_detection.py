"""
"Detected Research Areas" (#102).

Deliberately NOT a fake AI call: this is a real, deterministic signal
-- the most common subject tags shared across the search's strongest
matches, reusing metadata the app already has (journals.subjects,
imported from DOAJ/SCImago) rather than introducing a new taxonomy or
hardcoded placeholder. This matches the issue's own "Existing
Metadata... Avoid introducing new taxonomies unless necessary"
guidance directly. A future AI-assisted classifier
(docs/AI_ARCHITECTURE.md) could replace or augment this later without
changing the shape anything calls detect_disciplines() with.

Never imported by services/recommender.py -- this only ever runs on
results the deterministic engine has already produced, same rule as
services/research_interpreter.py and services/online_enrichment.py.
"""

from collections import Counter

from utils.subjects import extract_subject_tags

DEFAULT_TOP_N = 5
# Only the strongest matches -- a discipline shared across the top 20
# results is a real signal; diluting it across hundreds of weak
# matches would mostly surface noise.
MAX_RESULTS_CONSIDERED = 20


def detect_disciplines(results, top_n=DEFAULT_TOP_N):
    """
    `results` is the recommender's own ranked list (already sorted
    strongest-first) -- takes the subject tags of the top
    MAX_RESULTS_CONSIDERED, counts them, returns the top_n most common
    as a plain list of strings, most common first. Empty if no result
    has subject data.
    """
    counter = Counter()

    for result in results[:MAX_RESULTS_CONSIDERED]:
        for tag in extract_subject_tags(result.get("subjects")):
            counter[tag] += 1

    return [tag for tag, _count in counter.most_common(top_n)]
