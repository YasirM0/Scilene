"""
Backfills journals.openalex_domain/field/subfield (#79) for journals
DOAJ's own subjects field doesn't cover -- ~32,700 of 55,745 journals
(SINTA-only and Scopus/SCImago-only ones), verified by direct sampling
against the live OpenAlex API to have ~90% coverage even there
(including Indonesian SINTA journals specifically, 15/15 in one
sample) -- see services/subject_taxonomy.py's own docstring for why
this is a SEPARATE column set rather than merged into `subjects`
(DOAJ's Library-of-Congress-style categories and OpenAlex's own
Domain/Field/Subfield hierarchy are two different, independently
coherent classification schemes; concatenating them would produce an
incoherent mixed taxonomy, not a unified one).

Takes each journal's TOP-ranked OpenAlex topic (topics[0] -- OpenAlex
itself ranks by how many of that journal's own papers fall under each
topic, already sorted descending) and stores that topic's
domain/field/subfield display names. Public data, freely re-fetchable
from OpenAlex's own API at any time -- no security concern storing or
committing it, unlike journals.index_terms.

Mirrors benchmark/scripts/fetch_openalex_topics.py's proven concurrent
fetch pattern (ThreadPoolExecutor, per-worker rate limiting, periodic
saves for resumability) -- that script proved this approach handles
~14k journals in a couple of minutes. This version writes straight to
the database instead of a JSON cache, and only targets journals
without existing openalex_field (so re-running after an interruption,
or after new journals are imported, only fetches what's actually
missing).

Run from the project root, after the database is already built:
    python -m scripts.backfill_openalex_taxonomy [--mailto you@example.com] [--workers 10] [--limit N]

--mailto is optional but recommended -- OpenAlex's "polite pool" gives
faster, more reliable responses to requests that identify a contact.
"""

import argparse
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

from services.app_info import APP_VERSION, APP_GITHUB
from services.repository import get_connection
from utils.issn import normalize_issn

OPENALEX_SOURCES_URL = "https://api.openalex.org/sources/issn:{issn}"
REQUEST_TIMEOUT = 10
REQUEST_DELAY_SECONDS = 0.15  # same per-worker pacing as fetch_openalex_topics.py
DEFAULT_WORKERS = 10
SAVE_EVERY = 200


def _fetch_top_topic(session, issn, mailto):
    params = {"mailto": mailto} if mailto else {}
    try:
        response = session.get(OPENALEX_SOURCES_URL.format(issn=issn), params=params, timeout=REQUEST_TIMEOUT)
    except requests.RequestException:
        return None

    if response.status_code != 200:
        return None

    try:
        payload = response.json()
    except ValueError:
        return None

    topics = payload.get("topics") or []
    if not topics:
        return None

    top = topics[0]
    domain = (top.get("domain") or {}).get("display_name")
    field = (top.get("field") or {}).get("display_name")
    subfield = (top.get("subfield") or {}).get("display_name")
    if not field:
        return None
    return domain, field, subfield


def _fetch_one(session, journal_id, issn_print, issn_online, mailto):
    """Runs in a worker thread -- fetches (print ISSN, then online ISSN
    as fallback) and returns (journal_id, (domain, field, subfield)_or_None)
    for the main thread to write."""
    result = None
    for raw_issn in (issn_print, issn_online):
        issn = normalize_issn(raw_issn)
        if not issn:
            continue
        result = _fetch_top_topic(session, issn, mailto)
        time.sleep(REQUEST_DELAY_SECONDS)
        if result:
            break
    return journal_id, result


def run(mailto=None, workers=DEFAULT_WORKERS, limit=None):
    conn = get_connection()
    query = (
        "SELECT id, issn_print, issn_online FROM journals "
        "WHERE (openalex_field IS NULL OR openalex_field = '') "
        "AND (subjects IS NULL OR subjects = '') "
        "AND (issn_print IS NOT NULL OR issn_online IS NOT NULL)"
    )
    if limit:
        query += f" LIMIT {int(limit)}"
    pending = conn.execute(query).fetchall()

    print(f"Fetching OpenAlex taxonomy for {len(pending)} journals with {workers} concurrent workers ...", flush=True)

    session = requests.Session()
    session.headers.update({"User-Agent": f"Scilene/{APP_VERSION} ({APP_GITHUB}; taxonomy backfill)"})

    matched = 0
    completed = 0
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [
            executor.submit(_fetch_one, session, jid, issn_print, issn_online, mailto)
            for jid, issn_print, issn_online in pending
        ]
        for future in as_completed(futures):
            journal_id, result = future.result()
            completed += 1
            if result:
                domain, field, subfield = result
                conn.execute(
                    "UPDATE journals SET openalex_domain = ?, openalex_field = ?, openalex_subfield = ? WHERE id = ?",
                    (domain, field, subfield, journal_id),
                )
                matched += 1

            if completed % SAVE_EVERY == 0:
                conn.commit()
                print(f"  {completed}/{len(pending)} checked, {matched} matched so far", flush=True)

    conn.commit()
    conn.close()
    print(f"Done: {matched}/{len(pending)} journals matched an OpenAlex topic.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mailto", default=None)
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--limit", type=int, default=None, help="Cap how many journals to fetch (testing).")
    args = parser.parse_args()
    run(mailto=args.mailto, workers=args.workers, limit=args.limit)


if __name__ == "__main__":
    main()
