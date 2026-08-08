"""
Benchmark dataset builder (#112, docs/BENCHMARK.md).

Collects real published papers from OpenAlex's public works API,
restricted to journals that already exist in Scilene's local database
(per the design doc: "Only journals present in Scilene's database
should be included") -- these papers become the benchmark's ground
truth: "this abstract was really published in this journal", used by
evaluate.py to check whether the recommender (or the baseline) would
have surfaced that journal.

Uses OpenAlex only (no key required) -- an official, public dataset,
not runtime scraping, per docs/DATABASE.md's design principles. A
`--mailto` flag is available (OpenAlex's "polite pool": including a
contact email gets faster, more reliable rate limits) but not required.

Run from the project root:
    python3 -m benchmark.scripts.build_dataset --num-journals 150

Output: a JSON file under benchmark/datasets/, structured as
{"version", "built_at", "seed", "num_journals_sampled", "num_records",
"records": [...]}. Each record has an `abstract` reconstructed from
OpenAlex's word-position index (OpenAlex doesn't return plain-text
abstracts, for copyright reasons), plus the journal it was really
published in, subject area / category (OpenAlex's topic taxonomy),
publication year, and best-effort first-author affiliation country.
"""

import argparse
import json
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from services.repository import get_connection

OPENALEX_WORKS_URL = "https://api.openalex.org/works"
REQUEST_TIMEOUT = 10
REQUEST_DELAY_SECONDS = 0.15  # polite pacing, well under OpenAlex's rate limit
MIN_ABSTRACT_CHARS = 100

DATASET_DIR = Path(__file__).resolve().parent.parent / "datasets"


def _reconstruct_abstract(inverted_index):
    """
    OpenAlex stores an abstract as {word: [position, position, ...]}
    rather than plain text. Rebuild the original word order.
    """
    if not inverted_index:
        return None

    max_position = max(pos for positions in inverted_index.values() for pos in positions)
    words = [""] * (max_position + 1)
    for word, positions in inverted_index.items():
        for pos in positions:
            words[pos] = word

    return " ".join(words).strip()


def _sample_journals(conn, num_journals, seed):
    rows = conn.execute(
        "SELECT id, title, issn_print, issn_online FROM journals "
        "WHERE issn_print IS NOT NULL OR issn_online IS NOT NULL"
    ).fetchall()

    random.seed(seed)
    return random.sample(rows, k=min(num_journals, len(rows)))


def _fetch_works(issn, min_year, per_journal, mailto, session):
    params = {
        "filter": f"primary_location.source.issn:{issn},publication_year:>{min_year - 1},has_abstract:true",
        "per_page": per_journal,
        "select": "id,title,abstract_inverted_index,primary_topic,publication_year,authorships",
    }
    if mailto:
        params["mailto"] = mailto

    try:
        response = session.get(OPENALEX_WORKS_URL, params=params, timeout=REQUEST_TIMEOUT)
    except requests.RequestException:
        return None

    if response.status_code != 200:
        return None

    return response.json().get("results", [])


def _first_author_country(work):
    for authorship in work.get("authorships") or []:
        for institution in authorship.get("institutions") or []:
            country = institution.get("country_code")
            if country:
                return country
    return None


def build_dataset(num_journals, per_journal, min_year, seed, mailto, output_path):
    conn = get_connection()
    journals = _sample_journals(conn, num_journals, seed)
    conn.close()

    session = requests.Session()
    session.headers["User-Agent"] = "Scilene-Benchmark/1.0 (https://github.com/YasirM0/Scilene)"

    records = []
    journals_with_hits = 0

    for index, (journal_id, title, issn_print, issn_online) in enumerate(journals, start=1):
        issn = issn_print or issn_online
        works = _fetch_works(issn, min_year, per_journal, mailto, session)
        time.sleep(REQUEST_DELAY_SECONDS)

        if not works:
            continue

        journal_hit = False

        for work in works:
            abstract = _reconstruct_abstract(work.get("abstract_inverted_index"))
            if not abstract or len(abstract) < MIN_ABSTRACT_CHARS:
                continue

            topic = work.get("primary_topic") or {}
            records.append({
                "openalex_id": work.get("id"),
                "paper_title": work.get("title"),
                "abstract": abstract,
                "journal_id": journal_id,
                "journal_title": title,
                "issn": issn,
                "subject_area": (topic.get("domain") or {}).get("display_name"),
                "category": (topic.get("field") or {}).get("display_name"),
                "publication_year": work.get("publication_year"),
                "author_country": _first_author_country(work),
            })
            journal_hit = True

        if journal_hit:
            journals_with_hits += 1

        print(f"[{index}/{len(journals)}] {title} -> {sum(1 for _ in works)} candidate work(s)", file=sys.stderr)

    dataset = {
        "version": datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S"),
        "built_at": datetime.now(timezone.utc).isoformat(),
        "seed": seed,
        "min_year": min_year,
        "num_journals_sampled": len(journals),
        "num_journals_with_hits": journals_with_hits,
        "num_records": len(records),
        "records": records,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(dataset, f, indent=2, ensure_ascii=False)

    print(
        f"\nBuilt {len(records)} benchmark records from {journals_with_hits}/{len(journals)} "
        f"sampled journals -> {output_path}"
    )
    return dataset


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--num-journals", type=int, default=150, help="Journals to sample from the local DB")
    parser.add_argument("--per-journal", type=int, default=3, help="Max works to pull per journal")
    parser.add_argument("--min-year", type=int, default=2015, help="Only papers published this year or later")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for journal sampling (reproducibility)")
    parser.add_argument("--mailto", default=None, help="Contact email for OpenAlex's polite pool (optional)")
    parser.add_argument(
        "--output", default=None,
        help="Output path (default: benchmark/datasets/dataset_<timestamp>.json)",
    )
    args = parser.parse_args()

    output_path = Path(args.output) if args.output else DATASET_DIR / f"dataset_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"

    build_dataset(args.num_journals, args.per_journal, args.min_year, args.seed, args.mailto, output_path)


if __name__ == "__main__":
    main()
