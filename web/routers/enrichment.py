"""
Online metadata enrichment (#107) -- lazy-loaded, per-journal, on
explicit user action only. Stateless: no session involved, this never
touches search results/history, just a live lookup rendered inline.
See docs/ENRICHMENT.md and services/online_enrichment.py.
"""

from fastapi import APIRouter, Request, Form

from services.online_enrichment import enrich
from web.enrichment_presentation import format_enrichment_result
from web.templating import templates

router = APIRouter(prefix="/search")


@router.post("/enrich")
def enrich_journal(request: Request, issn_print: str = Form(""), issn_online: str = Form("")):
    result = enrich(issn_print or None, issn_online or None)
    return templates.TemplateResponse(
        request=request,
        name="partials/online_enrichment.html",
        context={"enrichment": format_enrichment_result(result)},
    )
