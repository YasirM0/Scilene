import re

from services.repository import search_candidates

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
        language=None,
        free_only=False,
        min_budget=None,
        max_budget=None,
        indexing=None,
        quartiles=None,
        sinta_levels=None,
        strategy="Balanced",
    ):
        """
        Recommend journals based on a paper title, keywords, and
        (optionally) an abstract, narrowed by language/budget/indexing
        filters and reordered according to a recommendation strategy.

        Returns the FULL sorted list of matching journals (searches and
        scores the complete candidate set rather than an early-truncated
        sample), each tagged with a relative confidence level. Pagination
        over that list is the caller's responsibility (e.g. the UI).
        """

        keywords = keywords or []

        keywords = [
            keyword.strip()
            for keyword in keywords
            if keyword.strip()
        ]

        # If no keywords are provided, fall back to words from the title
        # and abstract (simple substring matching, not NLP/embeddings).
        if not keywords:
            fallback_text = f"{title} {abstract}"
            fallback_words = [
                word.strip(".,;:()").lower()
                for word in fallback_text.split()
                if len(word.strip(".,;:()")) > 3
            ]
            seen = set()
            keywords = []
            for word in fallback_words:
                if word not in seen:
                    seen.add(word)
                    keywords.append(word)
            keywords = keywords[:15]

        # Only push free_only/indexing to SQL (both are clean columns).
        # Budget filtering happens below, in Python, after parsing.
        candidates = search_candidates(
            keywords,
            language=language,
            free_only=free_only,
            indexing=indexing,
            quartiles=quartiles,
            sinta_levels=sinta_levels,
        )

        recommendations = []

        for journal in candidates:

            is_free = str(journal.apc).lower() == "no"
            usd_amount = None if is_free else parse_usd_amount(journal.apc_amount)

            # Budget filter (Python-side, since apc_amount is free text).
            # Free journals satisfy any band whose floor is $0/unset.
            # Paid journals only count if we found a confirmed USD figure
            # inside the requested range — an unconfirmed/non-USD fee is
            # excluded rather than guessed at.
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

            score = 0
            reasons = []

            for keyword in keywords:

                k = keyword.lower()

                if k in str(journal.title).lower():
                    score += 5
                    reasons.append(f'✓ Title contains "{keyword}"')

                if k in str(journal.subjects).lower():
                    score += 4
                    reasons.append(f'✓ Subject contains "{keyword}"')

                if k in str(journal.keywords).lower():
                    score += 2
                    reasons.append(f'✓ Keywords contain "{keyword}"')

            if score == 0:
                continue

            if is_free:
                reasons.append("✓ No publication fee (APC)")
            elif usd_amount is not None:
                reasons.append(f"APC: ~${usd_amount:.0f}")
            else:
                reasons.append("APC applies (amount not confirmed in USD — check journal site)")

            if journal.review_weeks is not None:
                reasons.append(f"Typical review time: ~{journal.review_weeks} weeks")

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
                "review_weeks": journal.review_weeks,
                "sources": journal.sources,
                "source_details": journal.source_details,
                "score": score,
                "reasons": reasons,
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
        Label each recommendation with a confidence level, relative to
        the other matches found for THIS search.

        This is a rank-based heuristic (which fifth of this search's own
        results a journal falls into), not a statistically validated
        probability of fit or acceptance — there's no outcome data behind
        it. It's here to help scanning, not as a claim about your odds
        with any individual journal.
        """

        n = len(recommendations)

        for position, recommendation in enumerate(recommendations):
            # position 0 is the best match
            percentile_from_top = position / n if n else 0
            bucket_index = min(
                int(percentile_from_top * len(CONFIDENCE_LEVELS)),
                len(CONFIDENCE_LEVELS) - 1,
            )
            # bucket_index 0 = top fifth -> should map to "Excellent" (last in list)
            level = CONFIDENCE_LEVELS[len(CONFIDENCE_LEVELS) - 1 - bucket_index]
            recommendation["confidence"] = level