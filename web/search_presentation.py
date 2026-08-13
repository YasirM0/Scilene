"""
Presentation-only helpers for the search page: option labels, the
confidence badge color/star mapping, visible-results filtering, and
pagination. Deliberately NOT in services/ — none of this is
recommendation logic (that's recommender.py, untouched by this
migration); it's how the web UI presents that data, exactly mirroring
what the Streamlit page did in-line. Kept out of the Jinja2 templates
too, so business rules (like which confidence tiers count as "strong")
live in one reviewable place, not scattered across template
conditionals.
"""

import math

from services.app_info import export_prefix
from services.recommender import STRATEGIES

PAGE_SIZE = 10

# UI label -> real strategy name. All three are backed by real data
# (see services/recommender.py); this mapping is presentation-only.
STRATEGY_LABELS = {
    "⚖️ Balanced (Recommended)": "Balanced",
    "💰 Lowest APC": "Lowest APC",
    "🏆 Highest Prestige": "Highest Prestige",
}
assert set(STRATEGY_LABELS.values()) == set(STRATEGIES)

# Brand mapping (docs/DESIGN_SYSTEM.md): Excellent -> Guiding Gold,
# Strong -> Navigation Navy, Moderate -> Horizon Blue, Weak/Poor ->
# neutral gray (only the first three tiers have a brand color; "Poor"
# was never assigned one, so it stays a plainer, slightly duller gray
# than "Weak" to keep the two visually distinct). Dark-mode pairs use
# navy-50/horizon-50/gold-50 text on a dark badge instead of light-bg
# variants (see recommendation_badge.html) -- a light-tinted 50-shade
# background barely shows up on a dark surface.
CONFIDENCE_COLORS = {
    "Excellent": "bg-gold-50 text-gold-700 dark:bg-gold-700 dark:text-gold-50",
    "Strong": "bg-navy-50 text-navy-700 dark:bg-navy-700 dark:text-navy-50",
    "Moderate": "bg-horizon-50 text-horizon-700 dark:bg-horizon-700 dark:text-horizon-50",
    "Weak": "bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300",
    "Poor": "bg-gray-50 text-gray-500 dark:bg-gray-800 dark:text-gray-400",
}

# Stars were always plain gray-400 before, regardless of tier -- low
# visibility and no relationship to the badge next to them. Now
# colored per tier (same hue as the badge text) so the two reinforce
# each other instead of the stars just fading into the page.
CONFIDENCE_STAR_COLORS = {
    "Excellent": "text-gold-600 dark:text-gold-500",
    "Strong": "text-navy-600 dark:text-navy-300",
    "Moderate": "text-horizon-600 dark:text-horizon-500",
    "Weak": "text-gray-400 dark:text-gray-500",
    "Poor": "text-gray-300 dark:text-gray-600",
}

CONFIDENCE_STARS = {
    "Excellent": "★★★★★",
    "Strong": "★★★★☆",
    "Moderate": "★★★☆☆",
    "Weak": "★★☆☆☆",
    "Poor": "★☆☆☆☆",
}

STRONG_TIERS = {"Excellent", "Strong"}

INDEXING_OPTIONS = ["DOAJ", "Scopus", "SINTA", "Web of Science"]
QUARTILE_OPTIONS = ["Q1", "Q2", "Q3", "Q4"]
SINTA_LEVEL_OPTIONS = [f"SINTA {n}" for n in range(1, 7)]
# Multi-select, matching the indexing/quartile/SINTA pattern (#89) --
# was a single-select Any/English/Indonesian dropdown before. Must
# match services.language_detection.SUPPORTED_LANGUAGES' values.
LANGUAGE_OPTIONS = ["English", "Arabic", "Indonesian"]

# #143 -- the no-abstract "just give me tags" floor (#110 originally
# shipped this at 10; lowered to feel less intimidating to a
# first-time user with only a vague research idea, while still giving
# the recommender enough real signal to narrow 55,000+ journals
# meaningfully). One place both web/routers/search.py's validation and
# every locale's UI copy read from, so the number is never repeated.
MIN_FALLBACK_TAGS = 5

BUDGET_OPTIONS = [
    "Any",
    "Free (No APC)",
    "Low APC (< $100)",
    "Medium APC ($100–300)",
    "High APC (> $300)",
]

REVIEW_TIME_BANDS = {
    "Any": None,
    "Up to 8 weeks": 8,
    "Up to 12 weeks": 12,
    "Up to 20 weeks": 20,
    "Up to 30 weeks": 30,
}


def budget_to_range(budget_choice):
    """Returns (free_only, min_budget, max_budget) for a BUDGET_OPTIONS choice."""
    if budget_choice == "Free (No APC)":
        return True, None, None
    if budget_choice == "Low APC (< $100)":
        return False, None, 99.99
    if budget_choice == "Medium APC ($100–300)":
        return False, 100, 300
    if budget_choice == "High APC (> $300)":
        return False, 300, None
    return False, None, None


def apc_label(result):
    if result["is_free"]:
        return "Free"
    if result["apc_amount"] is not None:
        return f"~${result['apc_amount']:.0f}"
    return "Paid (unconfirmed)"


def is_inactive_scopus(result):
    """
    True if this journal's Scopus entry is explicitly marked inactive
    by the Elsevier Source List (#98) -- False for a confirmed-active
    Scopus journal AND for a journal not indexed in Scopus at all
    (source_details simply won't have a "Scopus" entry, `active` is
    only ever set by importers/elsevier.py).
    """
    for detail in result.get("source_details", []):
        if detail["source"] == "Scopus" and detail.get("active") is False:
            return True
    return False


def filter_visible_results(all_results, show_weaker):
    """
    "Show weaker recommendations" reused, per #98, as the one toggle
    that also reveals inactive-Scopus journals -- no separate filter.
    """
    if show_weaker:
        return all_results
    return [
        r for r in all_results
        if r["confidence"] in STRONG_TIERS and not is_inactive_scopus(r)
    ]


def paginate(results, page):
    total_pages = max(1, math.ceil(len(results) / PAGE_SIZE))
    page = max(1, min(page, total_pages))
    start = (page - 1) * PAGE_SIZE
    return results[start:start + PAGE_SIZE], page, total_pages


def build_export_basename(strategy_label):
    from datetime import datetime, timezone

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
    slug = (
        strategy_label
        .split(" ", 1)[1]
        .replace(" (Recommended)", "")
        .replace(" ", "_")
        .lower()
    )
    return f"{export_prefix()}_{slug}_{timestamp}"
