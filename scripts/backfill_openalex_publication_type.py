"""
Backfills journals.publication_type (#128) from OpenAlex's Sources
`type` field, for journals Elsevier's Source List has no opinion on at
all -- ~23,825 of 55,745 journals (publication_type IS NULL: SINTA-only
and DOAJ/SCImago-only ones Elsevier never matched). Elsevier's own list
is the only other source for this column (importers/elsevier.py), and
only ever yields "Journal"/"Book Series"/"Trade Journal" for this
dataset -- this fills in the same column for the journals it skips
entirely, using OpenAlex's Sources API (same endpoint
scripts/backfill_openalex_taxonomy.py already calls for subject
taxonomy) instead.

Deliberately does NOT re-check journals Elsevier already classified
(publication_type IS NOT NULL) -- verified directly against OpenAlex
that its `type` field is NOT a reliable way to catch MORE conference
proceedings than utils/publication_types.py's own title-keyword check
already does: OpenAlex types "CEUR Workshop Proceedings" and an actual
"Proceedings - IEEE Computer Society Conference on Computer Vision and
Pattern Recognition" entry as plain "journal", not "conference series"
-- so this backfill's real, honest value is filling in the types
OpenAlex DOES distinguish well (confirmed directly: "repository" for
arXiv, "book series" for Lecture Notes in Computer Science) for
journals with no Elsevier data at all, not sharpening proceedings
detection (the title check already does that better, for free, at
render time -- see resolve_publication_type()).

Mirrors backfill_openalex_taxonomy.py's proven concurrent fetch pattern
(ThreadPoolExecutor, per-worker rate limiting, retries that distinguish
a transient failure from a confirmed "no OpenAlex source", periodic
saves for resumability) -- see that script for why each of those
exists; not repeated here.

Run from the project root, after the database is already built:
    python -m scripts.backfill_openalex_publication_type [--mailto you@example.com] [--workers 10] [--limit N]

--mailto is optional but recommended -- OpenAlex's "polite pool" gives
faster, more reliable responses to requests that identify a contact.
"""

import argparse
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

from services.app_info import APP_VERSION, APP_GITHUB
from services.repository import get_connection, update_publication_type
from utils.issn import normalize_issn
from utils.publication_types import normalize_publication_type

OPENALEX_SOURCES_URL = "https://api.openalex.org/sources/issn:{issn}"
REQUEST_TIMEOUT = 10
REQUEST_DELAY_SECONDS = 0.15  # same per-worker pacing as backfill_openalex_taxonomy.py
DEFAULT_WORKERS = 10
SAVE_EVERY = 200

MAX_RETRIES = 4
RETRY_BACKOFF_SECONDS = 1.0  # doubles each retry: 1s, 2s, 4s, 8s


class _Retryable(Exception):
    """A transient failure (rate limit, 5xx, network error, bad JSON) --
    distinct from a confirmed 404 "no such source", which is a real
    negative, not a failure. Same distinction and same reasoning as
    backfill_openalex_taxonomy.py's own _Retryable -- a naive "any
    non-200 is a miss" cost that script real false negatives at full
    concurrency once already."""


def _fetch_type(session, issn, mailto):
    """
    Returns the raw OpenAlex `type` string (e.g. "journal", "repository",
    "book series") on a genuine match, None on a confirmed 404, or
    raises _Retryable for anything transient.
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

    return payload.get("type") or None


def _fetch_with_retries(session, issn, mailto):
    delay = RETRY_BACKOFF_SECONDS
    for attempt in range(MAX_RETRIES):
        try:
            return _fetch_type(session, issn, mailto)
        except _Retryable:
            if attempt == MAX_RETRIES - 1:
                return "RETRY_EXHAUSTED"  # distinct from a real None/404 miss
            time.sleep(delay)
            delay *= 2


def _fetch_one(session, journal_id, issn_print, issn_online, mailto):
    """Runs in a worker thread -- fetches (print ISSN, then online ISSN
    as fallback) and returns (journal_id, result), where result is the
    raw OpenAlex type string on a match, None on a confirmed
    no-source-found, or "RETRY_EXHAUSTED" if every attempt hit a
    transient failure (caller must NOT treat this as a confirmed miss)."""
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
    # publication_type IS NULL = Elsevier never matched this journal
    # (never attempted here either -- retry these); '' = attempted and
    # confirmed no OpenAlex source (a real negative, don't keep
    # re-querying); a real value = already known, from Elsevier or a
    # prior run of this script.
    query = (
        "SELECT id, issn_print, issn_online FROM journals "
        "WHERE publication_type IS NULL "
        "AND (issn_print IS NOT NULL OR issn_online IS NOT NULL)"
    )
    if limit:
        query += f" LIMIT {int(limit)}"
    pending = conn.execute(query).fetchall()

    print(f"Fetching OpenAlex publication type for {len(pending)} journals with {workers} concurrent workers ...", flush=True)

    session = requests.Session()
    session.headers.update({"User-Agent": f"Scilene/{APP_VERSION} ({APP_GITHUB}; publication-type backfill)"})

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
                # false negative.
                unresolved += 1
            elif result:
                # Store the normalized label ("Journal", "Repository",
                # "Book Series", ...), not OpenAlex's own raw, lowercase
                # spelling -- caught by direct testing partway through
                # an earlier run of this script: Elsevier's importer
                # already writes properly-cased labels into this same
                # column, and services.repository.count_by_publication_type()
                # groups by the raw stored string (not through
                # resolve_publication_type()'s normalization), so an
                # unnormalized "journal" alongside an existing "Journal"
                # would silently fork the Statistics dashboard's chart
                # into duplicate rows for what's really one category.
                update_publication_type(conn, journal_id, normalize_publication_type(result))
                matched += 1
            else:
                # Confirmed 404 on every ISSN this journal has -- mark
                # with '' (distinct from NULL/"never tried") so future
                # runs don't keep re-querying a journal OpenAlex
                # genuinely doesn't have.
                conn.execute("UPDATE journals SET publication_type = '' WHERE id = ?", (journal_id,))
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
