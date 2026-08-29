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


MAX_RETRIES = 4
RETRY_BACKOFF_SECONDS = 1.0  # doubles each retry: 1s, 2s, 4s, 8s


def _fetch_top_topic(session, issn, mailto):
    """
    Returns (domain, field, subfield) on a genuine match, None on a
    genuine "OpenAlex has no source for this ISSN" (404), or raises
    _Retryable for anything else (429 rate-limit, 5xx, a network
    error, unparseable JSON) so the caller can back off and retry
    rather than silently recording a false negative.

    An earlier version of this script treated ANY non-200 response as
    "no data" -- at full scale (32k+ journals, 15 concurrent workers,
    no --mailto) that meant real 429s from OpenAlex got recorded as
    genuine misses. Caught after the first full run: "Marketing
    Science" and 17 other obviously-major journals came back False,
    and a direct, unhurried re-check confirmed OpenAlex has full data
    for all of them. This is the fix.
    """
    params = {"mailto": mailto} if mailto else {}
    try:
        response = session.get(OPENALEX_SOURCES_URL.format(issn=issn), params=params, timeout=REQUEST_TIMEOUT)
    except requests.RequestException:
        raise _Retryable()

    if response.status_code == 404:
        return None
    if response.status_code != 200:
        raise _Retryable()

    try:
        payload = response.json()
    except ValueError:
        raise _Retryable()

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


class _Retryable(Exception):
    """A transient failure (rate limit, 5xx, network error, bad JSON) --
    distinct from a confirmed 404 "no such source", which is a real
    negative, not a failure."""


def _fetch_with_retries(session, issn, mailto):
    delay = RETRY_BACKOFF_SECONDS
    for attempt in range(MAX_RETRIES):
        try:
            return _fetch_top_topic(session, issn, mailto)
        except _Retryable:
            if attempt == MAX_RETRIES - 1:
                return "RETRY_EXHAUSTED"  # distinct from a real None/404 miss
            time.sleep(delay)
            delay *= 2


def _fetch_one(session, journal_id, issn_print, issn_online, mailto):
    """Runs in a worker thread -- fetches (print ISSN, then online ISSN
    as fallback) and returns (journal_id, result) for the main thread
    to write, where result is (domain, field, subfield) on a match,
    None on a confirmed no-source-found, or "RETRY_EXHAUSTED" if every
    attempt hit a transient failure (caller must NOT treat this as a
    confirmed miss -- see _fetch_with_retries())."""
    result = None
    for raw_issn in (issn_print, issn_online):
        issn = normalize_issn(raw_issn)
        if not issn:
            continue
        result = _fetch_with_retries(session, issn, mailto)
        time.sleep(REQUEST_DELAY_SECONDS)
        if result and result != "RETRY_EXHAUSTED":
            break
    return journal_id, result


def run(mailto=None, workers=DEFAULT_WORKERS, limit=None):
    conn = get_connection()
    # openalex_field IS NULL = never attempted (retry these);
    # openalex_field = '' = attempted and confirmed no OpenAlex source
    # (a real negative -- see the confirmed_miss branch below, don't
    # keep re-querying these every run); a real value = already matched.
    query = (
        "SELECT id, issn_print, issn_online FROM journals "
        "WHERE openalex_field IS NULL "
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
    confirmed_miss = 0
    unresolved = 0
    completed = 0
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [
            executor.submit(_fetch_one, session, jid, issn_print, issn_online, mailto)
            for jid, issn_print, issn_online in pending
        ]
        for future in as_completed(futures):
            journal_id, result = future.result()
            completed += 1
            if result == "RETRY_EXHAUSTED":
                # Every attempt hit a transient failure -- leave the row
                # NULL (not a confirmed miss) so a future re-run of this
                # script picks it up again, rather than recording a
                # false negative. See _fetch_top_topic()'s docstring for
                # why this distinction exists.
                unresolved += 1
            elif result:
                domain, field, subfield = result
                conn.execute(
                    "UPDATE journals SET openalex_domain = ?, openalex_field = ?, openalex_subfield = ? WHERE id = ?",
                    (domain, field, subfield, journal_id),
                )
                matched += 1
            else:
                # Confirmed 404 on every ISSN this journal has -- mark
                # with '' (distinct from NULL/"never tried") so future
                # runs don't keep re-querying a journal OpenAlex
                # genuinely doesn't have.
                conn.execute("UPDATE journals SET openalex_field = '' WHERE id = ?", (journal_id,))
                confirmed_miss += 1

            if completed % SAVE_EVERY == 0:
                conn.commit()
                print(f"  {completed}/{len(pending)} checked, {matched} matched, "
                      f"{confirmed_miss} confirmed no-match, {unresolved} unresolved so far", flush=True)

    conn.commit()
    conn.close()
    print(f"Done: {matched} matched, {confirmed_miss} confirmed no-match, "
          f"{unresolved} unresolved (re-run the script to retry these) out of {len(pending)}.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mailto", default=None)
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--limit", type=int, default=None, help="Cap how many journals to fetch (testing).")
    args = parser.parse_args()
    run(mailto=args.mailto, workers=args.workers, limit=args.limit)


if __name__ == "__main__":
    main()
