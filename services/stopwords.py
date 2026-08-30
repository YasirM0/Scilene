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

STOPWORDS itself is shared by every caller of filter_stopwords(),
including recommender.py's real keyword/title/abstract matching --
where a word being dropped means it can never contribute to which
journals get recommended at all, not just downweighted. That's why
category 2 stays out of STOPWORDS even though some of those words
(e.g. "literature", "education", "data") turn out to be near-useless
as a single-word Key Research Focus suggestion (services/
focus_detection.py) -- confirmed directly by stress-testing
detect_focus_terms() against ~550 real OpenAlex abstracts (English and
Indonesian): words like "literature" and "indonesia" won the #1 slot
for totally unrelated topics purely because they're common,
substring-matchable journal keywords, not because they meant anything
about the abstract. Blocklisting them in the SHARED list would also
silently drop them from recommender.py's real matching -- e.g. a user
who deliberately types "literature" as a manual search tag for a
literary-studies search would have it vanish before scoring ever ran.
FOCUS_SUGGESTION_STOPWORDS below is the narrower, lower-stakes fix:
only used to keep single-word noise out of the Key Research Focus
suggestion vocabulary, never touching real keyword/title/abstract
matching.
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

# Narrower than STOPWORDS on purpose -- see the module docstring's
# "STOPWORDS itself is shared" note. Only ever consulted by
# services/focus_detection.py's Key Research Focus vocabulary build,
# never by real keyword/title/abstract matching. Every entry here was
# caught winning the #1 Key Research Focus slot for genuinely unrelated
# abstracts in a real stress test (~550 OpenAlex abstracts, English and
# Indonesian) -- not guessed, measured:
# - "literature": abstract said "...digital divide LITERATURE has been
#   refuting..." (ordinary academic prose, not a topic) and still won.
# - "education", "development", "data", "media", "management": each won
#   #1 across abstracts on completely unrelated subjects (thermoelectric
#   power generation, diabetic nephropathy, software bug detection, ion
#   implantation, post-disaster housing, food microbiology, K-means
#   clustering, Sasak language classification...), purely because
#   they're common substring-matchable journal keywords, not because
#   they described any of those abstracts.
# - "indonesia": wins for nearly any Indonesian-language abstract simply
#   because the country is mentioned somewhere in it (dataset
#   provenance, institution location) -- a geographic mention, not a
#   research focus, and this app's own SINTA/Indonesian-journal corpus
#   makes that mention close to universal rather than a rare fluke.
FOCUS_SUGGESTION_STOPWORDS = {
    "literature", "education", "development", "data", "media", "management",
    "indonesia",
}


def filter_stopwords(words):
    return [w for w in words if w and w.lower() not in STOPWORDS]
