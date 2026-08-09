"""
Journal Comparison (#56).

Session-scoped selection (like show_weaker/confirmed_tags) -- a user
checks journals on the search results page, then opens a side-by-side
comparison table. "Scope" (named in the issue) isn't shown: the Scope
& Focus dataset doesn't exist yet (#73, blocked on a separate index-
terms effort) -- every other field the issue names (subject areas,
indexing, metrics, open access status, APC, recommendation scores) is
real, already-available data, so those are what's compared.
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse

from services.recommender import parse_usd_amount
from services.repository import get_journals_by_ids
from web.dependencies import get_session_state, attach_session_cookie
from web.templating import templates

router = APIRouter(prefix="/search/compare")

MAX_COMPARE = 4


def _render(request, name, context, session):
    response = templates.TemplateResponse(request=request, name=name, context=context)
    return attach_session_cookie(response, session)


def _bar_context(session):
    return {
        "compare_ids": session.get("compare_journal_ids", []),
        "max_compare": MAX_COMPARE,
    }


@router.post("/toggle/{journal_id}")
def toggle_compare(request: Request, journal_id: int, session=Depends(get_session_state)):
    selected = session.get("compare_journal_ids", [])
    if journal_id in selected:
        selected.remove(journal_id)
    elif len(selected) < MAX_COMPARE:
        selected.append(journal_id)
    session["compare_journal_ids"] = selected

    return _render(request, "partials/compare_bar.html", _bar_context(session), session)


@router.post("/clear")
def clear_compare(request: Request, session=Depends(get_session_state)):
    session["compare_journal_ids"] = []

    if request.headers.get("HX-Request") == "true" and request.headers.get("HX-Target") == "compare-bar":
        # From the results-page bar -- stay put, just show it empty.
        return _render(request, "partials/compare_bar.html", _bar_context(session), session)

    # From the comparison page itself -- the table it would otherwise
    # leave behind has nothing left to show, so leave the page instead
    # of leaving a stale table under an empty bar.
    response = RedirectResponse(url="/search/compare", status_code=303)
    return attach_session_cookie(response, session)


@router.get("")
def compare_page(request: Request, session=Depends(get_session_state)):
    selected = session.get("compare_journal_ids", [])
    journals = get_journals_by_ids(selected)

    # Recommendation score/confidence live on the recommender's result
    # dicts, not the Journal model (services/repository.py) -- a
    # journal only ever gets added to comparison from a search result
    # card, so it's in session["current_results"] whenever a real
    # score exists to show. None (gracefully omitted by the template)
    # for a journal no longer in the last search's results.
    scores_by_id = {
        result["id"]: {"score": result["score"], "confidence": result["confidence"]}
        for result in (session.get("current_results") or [])
    }

    rows = []
    for journal in journals:
        # Same is_free/usd_amount derivation as services/recommender.py
        # -- apc_amount is free text (e.g. "$500", "USD 500"), not
        # already a number, so it needs the same parsing here.
        is_free = str(journal.apc).lower() == "no"
        usd_amount = None if is_free else parse_usd_amount(journal.apc_amount)
        rows.append({
            "journal": journal,
            "recommendation": scores_by_id.get(journal.id),
            "is_free": is_free,
            "usd_amount": usd_amount,
        })

    return _render(request, "pages/compare.html", {"rows": rows}, session)
