import math
import re

from services.repository import search_candidates, keyword_document_frequency, count_journals
from services.stopwords import filter_stopwords
from services.explain import build_explanation

# Strategies we can actually support with the data currently in the
# database. "Highest Prestige" now has real data behind it (Scopus/WoS
# quartile + SJR via SCImago) so it's included for real, not faked.
# "Best Match" (semantic similarity) and "Beginner Friendly" (needs an
# acceptance rate) still don't have underlying data, so they're left out
# entirely rather than faked with a made-up score.
STRATEGIES = ["Balanced", "Lowest APC", "Highest Prestige"]

_QUARTILE_RANK = {"Q1": 4, "Q2": 3, "Q3": 2, "Q4": 1}

# Ordered worst -> best. Used for confidence bucketing below.
CONFIDENCE_LEVELS = ["Poor", "Weak", "Moderate", "Strong", "Excellent"]

# Confidence-tier floor: RELATIVE to this search's own top result, not a
# single fixed number for every search. A 15-keyword fallback query and
# a 2-keyword precise query have structurally different achievable
# ceilings (more keywords make it statistically harder for one journal
# to hit every field for every keyword), so one fixed absolute number
# punished multi-keyword searches unfairly. The absolute floor still
# exists underneath it so that if EVERY candidate in a search is weak
# (a truly poor match overall), the best-of-a-bad-bunch still doesn't
# get called "Excellent."
CONFIDENCE_RELATIVE_FLOOR_RATIO = 0.45
CONFIDENCE_ABSOLUTE_FLOOR = 0.05

# IDF-style down/up-weighting of keywords by how common they are across
# the WHOLE database (not blocklisted words — measured ones). Values
# calibrated against real data: e.g. "medicine" (very common) lands
# near 0.55x, "governance" near 1.4x, "blockchain" (rare) near 2x.
_IDF_REFERENCE = 1.7
_IDF_MIN_MULTIPLIER = 0.4
_IDF_MAX_MULTIPLIER = 2.2

# apc_amount is free text like "40 USD" or "40 USD; 450000 IDR", not a
# clean number. We only trust a figure we can find explicitly in USD;
# we do not guess currency conversions for the rest.
_USD_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*USD", re.IGNORECASE)


def parse_usd_amount(raw):
    """
    Best-effort extraction of a USD figure from a free-text APC value.
    Returns None if no USD amount is present in the text.
    """
    if not raw:
        return None
    match = _USD_PATTERN.search(str(raw))
    if not match:
        return None
    return float(match.group(1))


class JournalRecommender:

    def recommend(
        self,
        title,
        keywords=None,
        abstract="",
        languages=None,
        free_only=False,
        min_budget=None,
        max_budget=None,
        indexing=None,
        quartiles=None,
        sinta_levels=None,
        max_review_weeks=None,
        strategy="Balanced",
    ):
        """
        Recommend journals based on a paper title, keywords, and
        (optionally) an abstract, narrowed by language(s)/budget/
        indexing/review-time filters and reordered according to a
        recommendation strategy.

        Returns the FULL sorted list of matching journals (searches and
        scores the complete candidate set rather than an early-truncated
        sample), each tagged with a relative confidence level. Pagination
        over that list is the caller's responsibility (e.g. the UI).
        """

        keywords = keywords or []

        keywords = filter_stopwords([
            keyword.strip()
            for keyword in keywords
            if keyword.strip()
        ])

        # If no keywords are provided, fall back to words from the title
        # and abstract (simple substring matching, not NLP/embeddings),
        # with stopwords removed so filler words don't pollute matching.
        if not keywords:
            fallback_text = f"{title} {abstract}"
            fallback_words = filter_stopwords([
                word.strip(".,;:()").lower()
                for word in fallback_text.split()
                if len(word.strip(".,;:()")) > 3
            ])
            seen = set()
            keywords = []
            for word in fallback_words:
                if word not in seen:
                    seen.add(word)
                    keywords.append(word)
            keywords = keywords[:15]

        # IDF-style weight per keyword, based on how common it actually
        # is across the whole database — not a guessed "generic words"
        # list. A keyword in nearly every journal (e.g. "medicine" in a
        # mixed-field search) contributes much less than a distinctive one.
        total_journals = count_journals()
        keyword_weights = {}
        for keyword in keywords:
            df = keyword_document_frequency(keyword)
            idf = math.log10((total_journals + 1) / (df + 1))
            multiplier = max(_IDF_MIN_MULTIPLIER, min(_IDF_MAX_MULTIPLIER, idf / _IDF_REFERENCE))
            keyword_weights[keyword] = multiplier

        # Only push free_only/indexing/quartile/review-time to SQL (all
        # clean columns). Budget filtering happens below, in Python,
        # after parsing the free-text apc_amount.
        candidates = search_candidates(
            keywords,
            languages=languages,
            free_only=free_only,
            indexing=indexing,
            quartiles=quartiles,
            sinta_levels=sinta_levels,
            max_review_weeks=max_review_weeks,
        )

        recommendations = []

        for journal in candidates:

            is_free = str(journal.apc).lower() == "no"
            usd_amount = None if is_free else parse_usd_amount(journal.apc_amount)

            # Budget filter (Python-side, since apc_amount is free text).
            if not free_only and (min_budget is not None or max_budget is not None):
                if is_free:
                    if min_budget:
                        continue
                else:
                    if usd_amount is None:
                        continue
                    if min_budget is not None and usd_amount < min_budget:
                        continue
                    if max_budget is not None and usd_amount > max_budget:
                        continue

            score = 0.0
            max_possible = 0.0
            title_hits, subject_hits, keyword_field_hits = [], [], []

            for keyword in keywords:

                k = keyword.lower()
                weight = keyword_weights[keyword]
                max_possible += 11 * weight  # 5 + 4 + 2, this keyword's ceiling

                hit_any_field = False

                if k in str(journal.title).lower():
                    score += 5 * weight
                    title_hits.append(keyword)
                    hit_any_field = True

                if k in str(journal.subjects).lower():
                    score += 4 * weight
                    subject_hits.append(keyword)
                    hit_any_field = True

                if k in str(journal.keywords).lower():
                    score += 2 * weight
                    keyword_field_hits.append(keyword)
                    hit_any_field = True

            distinct_hits = len(set(title_hits) | set(subject_hits) | set(keyword_field_hits))

            # Minimum evidence required to include a journal at all. This
            # scales with how many keywords are in play, on purpose: a
            # single strong hit is real evidence when the person typed 2-3
            # precise keywords, but when there are many keywords (typically
            # the title+abstract fallback, up to 15), requiring only ONE
            # match let thousands of journals in on a single fairly common
            # word — diluting the candidate pool so badly that percentile-
            # based confidence became meaningless (the "top 40%" of an
            # 8,000-candidate pool was mostly noise, not genuine matches).
            # Scaling the bar with keyword count fixes that at the source
            # instead of just hiding more of the output after the fact.
            min_required_hits = 1 if len(keywords) <= 3 else max(2, math.ceil(len(keywords) * 0.2))

            if score <= 0 or distinct_hits < min_required_hits:
                continue

            explanation = build_explanation(
                subject_terms=list(dict.fromkeys(subject_hits)),
                title_terms=list(dict.fromkeys(title_hits)),
                keyword_field_terms=list(dict.fromkeys(keyword_field_hits)),
            )

            recommendations.append({
                "id": journal.id,
                "title": journal.title,
                "publisher": journal.publisher or "",
                "country": journal.country or "",
                "website": journal.website or "",
                "doaj_url": journal.doaj_url or "",
                "issn_print": journal.issn_print or "",
                "issn_online": journal.issn_online or "",
                "subjects": journal.subjects or "",
                "languages": journal.languages or "",
                "license": journal.license or "",
                "apc": journal.apc or "",
                "apc_amount": usd_amount,
                "is_free": is_free,
                "review_weeks": int(journal.review_weeks) if journal.review_weeks is not None else None,
                "sources": journal.sources,
                "source_details": journal.source_details,
                # Display-only (docs/ENRICHMENT.md) -- passed through
                "enrichment": journal.enrichment,
                # Display-only (#100) -- passed through, never scored
                "aliases": journal.aliases,
                "score": score,
                "normalized_score": (score / max_possible) if max_possible else 0.0,
                "explanation": explanation,
            })

        recommendations = self._apply_strategy(recommendations, strategy)
        self._assign_confidence(recommendations)

        return recommendations

    def _apply_strategy(self, recommendations, strategy):
        """
        Reorder recommendations according to the chosen strategy.
        Falls back to "Balanced" for any strategy we don't yet support.
        """

        if strategy == "Lowest APC":
            recommendations.sort(
                key=lambda r: (
                    0 if r["is_free"] else 1,
                    r["apc_amount"] if r["apc_amount"] is not None else float("inf"),
                    -r["score"],
                )
            )
            return recommendations

        if strategy == "Highest Prestige":
            def prestige_key(r):
                best_quartile_rank = 0
                best_sjr = 0.0
                for detail in r.get("source_details", []):
                    q_rank = _QUARTILE_RANK.get(detail.get("quartile"), 0)
                    if q_rank > best_quartile_rank:
                        best_quartile_rank = q_rank
                    if detail.get("sjr") and detail["sjr"] > best_sjr:
                        best_sjr = detail["sjr"]
                return (best_quartile_rank, best_sjr, r["score"])

            recommendations.sort(key=prestige_key, reverse=True)
            return recommendations

        # Balanced (default): topical match first, small nudge for free access
        recommendations.sort(
            key=lambda r: (r["score"] + (2 if r["is_free"] else 0)),
            reverse=True,
        )
        return recommendations

    def _assign_confidence(self, recommendations):
        """
        Label each recommendation with a confidence level. Two things
        have to both hold for "Excellent"/"Strong":
          1. Rank — which fifth of THIS search's results it falls in.
          2. A floor — its normalized_score must be at least the larger
             of CONFIDENCE_ABSOLUTE_FLOOR and (this search's own top
             normalized_score × CONFIDENCE_RELATIVE_FLOOR_RATIO).

        The floor exists because #1 alone is fooled by a weak search: if
        every candidate is a mediocre match, the best of that weak bunch
        would still look "Excellent" by comparison, even though it's not
        a strong match in any absolute sense. It's RELATIVE to this
        search's own best result (not one fixed number for every search)
        so a search with many fallback keywords isn't punished for having
        a structurally lower achievable ceiling than a precise 2-keyword
        search. Neither number is a validated probability of fit or
        acceptance — there's no outcome data behind either.
        """

        n = len(recommendations)

        if n == 0:
            return

        top_score = recommendations[0]["normalized_score"]
        floor = max(CONFIDENCE_ABSOLUTE_FLOOR, top_score * CONFIDENCE_RELATIVE_FLOOR_RATIO)

        for position, recommendation in enumerate(recommendations):
            percentile_from_top = position / n if n else 0
            bucket_index = min(
                int(percentile_from_top * len(CONFIDENCE_LEVELS)),
                len(CONFIDENCE_LEVELS) - 1,
            )
            level = CONFIDENCE_LEVELS[len(CONFIDENCE_LEVELS) - 1 - bucket_index]

            if level in ("Excellent", "Strong") and recommendation["normalized_score"] < floor:
                level = "Moderate"

            recommendation["confidence"] = level
