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

CONFIDENCE_COLORS = {
    "Excellent": "bg-green-100 text-green-800",
    "Strong": "bg-blue-100 text-blue-800",
    "Moderate": "bg-yellow-100 text-yellow-800",
    "Weak": "bg-orange-100 text-orange-800",
    "Poor": "bg-gray-100 text-gray-600",
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


def filter_visible_results(all_results, show_weaker):
    if show_weaker:
        return all_results
    return [r for r in all_results if r["confidence"] in STRONG_TIERS]


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
    return f"ji_{slug}_{timestamp}"
