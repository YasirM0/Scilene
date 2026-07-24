"""
Natural-language "why this journal?" explanations.

Template-based, not an LLM — deliberately, per the v0.1.8 scope (stay
within the current architecture, no embeddings/LLMs). Turns raw
field-hit data ("digital" matched in subjects, "governance" matched in
title) into a couple of plain sentences about manuscript-journal topical
fit specifically. Does NOT mention APC, indexing, language, country, or
review time — those already have their own place on the card, and
repeating them here would be redundant clutter, not an explanation.
"""


def _join_terms(terms):
    if not terms:
        return ""
    if len(terms) == 1:
        return terms[0]
    if len(terms) == 2:
        return f"{terms[0]} and {terms[1]}"
    return ", ".join(terms[:-1]) + f", and {terms[-1]}"


def build_explanation(subject_terms, title_terms, keyword_field_terms):
    """
    subject_terms / title_terms / keyword_field_terms: lists of the
    manuscript's own keywords that were found in that field of the
    journal, in match order, already de-duplicated.
    """

    parts = []

    if subject_terms:
        parts.append(
            f"covers {_join_terms(subject_terms)}, matching your manuscript's subject area"
        )

    if title_terms:
        parts.append(
            f"its own title reflects {_join_terms(title_terms)}"
        )

    if not parts and keyword_field_terms:
        parts.append(
            f"is tagged with {_join_terms(keyword_field_terms)}, related to your manuscript"
        )

    if not parts:
        return "Shares some terms with your manuscript."

    return "This journal " + "; and ".join(parts) + "."
