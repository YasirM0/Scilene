"""
Stopword filtering for keyword extraction and matching.

Two different problems are handled by two different mechanisms in this
codebase, on purpose:

1. Pure function words and academic filler ("the", "using", "based",
   "study", "journal", "international", "review", ...) carry no topical
   signal in ANY manuscript, regardless of subject. Those are filtered
   out here, unconditionally.

2. Words that AREN'T grammatical filler but happen to be common in a
   given manuscript's field ("policy", "system", "development") still
   carry real meaning — just less distinguishing power than a rare
   term. Those are NOT blocklisted here; instead they're down-weighted
   at query time based on how many journals in the actual database
   contain them (see recommender.py's IDF-style weighting). Guessing a
   fixed list of "generic-sounding" content words would inevitably
   block legitimate topics for some field; measuring actual corpus
   frequency is more honest and adapts automatically as the database
   grows.
"""

STOPWORDS = {
    # Function words
    "the", "and", "for", "with", "from", "into", "onto", "this", "that",
    "these", "those", "their", "there", "where", "when", "what", "which",
    "who", "whom", "whose", "why", "how", "are", "was", "were", "been",
    "being", "have", "has", "had", "does", "did", "doing", "can", "could",
    "will", "would", "shall", "should", "may", "might", "must", "about",
    "above", "after", "again", "against", "all", "also", "among", "than",
    "then", "over", "under", "between", "both", "each", "few", "more",
    "most", "other", "some", "such", "only", "same", "very", "just",
    "not", "nor", "but", "off", "out", "own", "here", "our", "your", "its",

    # Academic / manuscript filler — near-universal across every field,
    # so they carry no field-distinguishing signal at all.
    "study", "studies", "research", "analysis", "analyses", "approach",
    "approaches", "using", "based", "review", "overview", "examination",
    "investigation", "investigating", "exploring", "explores", "toward",
    "towards", "journal", "international", "general", "paper", "article",
    "case", "cases", "role", "impact", "effect", "effects", "perspective",
    "perspectives", "framework", "understanding", "assessment", "new",
}


def filter_stopwords(words):
    return [w for w in words if w and w.lower() not in STOPWORDS]
