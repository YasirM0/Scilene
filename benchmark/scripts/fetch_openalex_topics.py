"""
OpenAlex per-journal Topics fetcher -- builds a proxy "index terms"
corpus for benchmark/scripts/evaluate_embeddings.py's --corpus-variant
openalex_topics option (#143 follow-up: evaluating whether a richer,
curated-style document per journal changes which embedding model wins,
ahead of the real curated index-terms dataset #73/#74 will eventually
provide).

No curated index-terms field exists yet -- OpenAlex's Sources API
already returns a `topics` array per journal (up to 25, ranked by how
many of that journal's own published papers fall under each topic),
a genuine, real signal standing in for what a curated field will
eventually offer, not a fabricated one.

Mirrors importers/enrichment/openalex.py's own ISSN-keyed lookup (same
endpoint, same print-then-online-ISSN fallback), but that module only
keeps the top 3 topics for on-card display -- this keeps up to
TOPICS_PER_JOURNAL for a richer embedding-corpus signal, and writes a
durable on-disk cache (one HTTP round trip per journal, ever, no
matter how many models/runs get evaluated against it) instead of
re-fetching per run. Resumable: re-running with the same --output
skips journals already cached.

Fetches concurrently (ThreadPoolExecutor, default 10 workers) rather
than one request at a time -- this is pure network I/O (waiting on
OpenAlex's response), completely independent of the CPU-bound
embedding work the rest of this benchmark does, so parallelizing it
costs nothing in result quality (same data, same per-request pacing
budget, just many requests in flight instead of one). At 14k journals
this was the difference between a ~35-minute wait and a couple of
minutes. Still self-rate-limits per worker (REQUEST_DELAY_SECONDS
between that worker's own requests) so aggregate request rate stays
in the same ballpark as build_dataset.py's sequential 0.15s pacing
times the worker count, not unbounded.

Run from the project root:
    python3 -m benchmark.scripts.fetch_openalex_topics \
        --sample-file benchmark/datasets/embedding_sample_ids.json \
        --output benchmark/datasets/openalex_topics_cache.json \
        [--mailto you@example.com] [--workers 10]
"""

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

from services.app_info import APP_VERSION, APP_GITHUB
from services.repository import get_connection
from utils.issn import normalize_issn

OPENALEX_SOURCES_URL = "https://api.openalex.org/sources/issn:{issn}"
REQUEST_TIMEOUT = 10
REQUEST_DELAY_SECONDS = 0.15  # same per-worker pacing as build_dataset.py's sequential fetch
TOPICS_PER_JOURNAL = 10
SAVE_EVERY = 200
DEFAULT_WORKERS = 10


def _fetch_topics(session, issn, mailto):
    params = {"mailto": mailto} if mailto else {}
    try:
        response = session.get(
            OPENALEX_SOURCES_URL.format(issn=issn), params=params, timeout=REQUEST_TIMEOUT
        )
    except requests.RequestException:
        return None

    if response.status_code != 200:
        return None

    try:
        payload = response.json()
    except ValueError:
        return None

    topics = [
        t.get("display_name")
        for t in (payload.get("topics") or [])[:TOPICS_PER_JOURNAL]
        if t.get("display_name")
    ]
    return topics or None


def _fetch_one(session, journal_id, issn_print, issn_online, mailto):
    """Runs in a worker thread -- fetches (falling back print -> online ISSN)
    and returns (journal_id, topics_or_None) for the main thread to record."""
    topics = None
    for raw_issn in (issn_print, issn_online):
        issn = normalize_issn(raw_issn)
        if not issn:
            continue
        topics = _fetch_topics(session, issn, mailto)
        time.sleep(REQUEST_DELAY_SECONDS)
        if topics:
            break
    return journal_id, topics


def run(sample_file, output_path, mailto, workers=DEFAULT_WORKERS):
    with open(sample_file) as f:
        journal_ids = json.load(f)["journal_ids"]

    conn = get_connection()
    placeholders = ",".join("?" * len(journal_ids))
    rows = conn.execute(
        f"SELECT id, issn_print, issn_online FROM journals WHERE id IN ({placeholders})",
        journal_ids,
    ).fetchall()
    conn.close()

    output_path = Path(output_path)
    cache = {}
    if output_path.exists():
        with open(output_path) as f:
            cache = json.load(f)
        print(f"Resuming -- {len(cache)} journals already cached in {output_path}", flush=True)

    pending = [(jid, p, o) for jid, p, o in rows if str(jid) not in cache]
    print(f"Fetching {len(pending)} remaining journals with {workers} concurrent workers ...", flush=True)

    session = requests.Session()
    session.headers.update({"User-Agent": f"Scilene/{APP_VERSION} ({APP_GITHUB}; benchmark tool)"})

    found = 0
    completed = 0
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [
            executor.submit(_fetch_one, session, jid, issn_print, issn_online, mailto)
            for jid, issn_print, issn_online in pending
        ]
        for future in as_completed(futures):
            journal_id, topics = future.result()
            cache[str(journal_id)] = topics  # None is a real, cacheable "no OpenAlex match" result
            if topics:
                found += 1
            completed += 1

            if completed % SAVE_EVERY == 0:
                print(f"  {completed}/{len(pending)} journals checked, {found} matched so far", flush=True)
                with open(output_path, "w") as f:
                    json.dump(cache, f)

    with open(output_path, "w") as f:
        json.dump(cache, f)

    total_found = sum(1 for v in cache.values() if v)
    print(f"Done: {total_found}/{len(cache)} journals matched OpenAlex topics -> {output_path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample-file", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--mailto", default=None)
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    args = parser.parse_args()
    run(args.sample_file, args.output, args.mailto, args.workers)


if __name__ == "__main__":
    main()
