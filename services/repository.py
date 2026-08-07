import json
import sqlite3
from pathlib import Path
from dataclasses import asdict

import pandas as pd

from models.journal import Journal

DATA_DIR = Path(__file__).parent.parent / "data"
DB_PATH = DATA_DIR / "journal_intelligence.db"


def get_connection():
    """
    Create a connection to the SQLite database.
    """
    return sqlite3.connect(DB_PATH)


# SQLite caps how many "?" placeholders a single statement can have
# (SQLITE_MAX_VARIABLE_NUMBER -- 999 on many builds). An unfiltered
# search matches every journal (~55k), so a single IN (...) over all
# of them raises "too many SQL variables" -- chunking keeps every
# batch well under any build's limit.
_SQL_IN_CHUNK_SIZE = 500


def _chunked(items, size):
    for start in range(0, len(items), size):
        yield items[start:start + size]


def _fetch_sources(conn, journal_ids):
    """
    Batch-fetch confirmed indexing sources for a set of journal ids,
    with any per-source metadata (Scopus/WoS quartile, SJR, H-index;
    SINTA accreditation). Returns {journal_id: [detail_dict, ...]}.
    """

    journal_ids = list(journal_ids)

    if not journal_ids:
        return {}

    details_by_id = {}

    for chunk in _chunked(journal_ids, _SQL_IN_CHUNK_SIZE):
        placeholders = ",".join("?" for _ in chunk)

        rows = conn.execute(
            f"SELECT journal_id, source, quartile, sjr, h_index, accreditation "
            f"FROM journal_sources WHERE journal_id IN ({placeholders})",
            chunk,
        ).fetchall()

        for journal_id, source, quartile, sjr, h_index, accreditation in rows:
            details_by_id.setdefault(journal_id, []).append({
                "source": source,
                "quartile": quartile,
                "sjr": sjr,
                "h_index": h_index,
                "accreditation": accreditation,
            })

    return details_by_id


def _fetch_enrichment(conn, journal_ids):
    """
    Batch-fetch metadata enrichment (docs/ENRICHMENT.md) for a set of
    journal ids. Returns {journal_id: {provider: data, ...}, ...} --
    display-only, never read by services/recommender.py.
    """

    journal_ids = list(journal_ids)

    if not journal_ids:
        return {}

    enrichment_by_id = {}

    for chunk in _chunked(journal_ids, _SQL_IN_CHUNK_SIZE):
        placeholders = ",".join("?" for _ in chunk)

        rows = conn.execute(
            f"SELECT journal_id, provider, data FROM journal_enrichment WHERE journal_id IN ({placeholders})",
            chunk,
        ).fetchall()

        for journal_id, provider, data in rows:
            enrichment_by_id.setdefault(journal_id, {})[provider] = json.loads(data)

    return enrichment_by_id


def _rows_to_journals(dataframe, conn=None):
    """
    Convert a pandas DataFrame into Journal objects, attaching each
    journal's confirmed indexing sources from journal_sources and its
    metadata enrichment from journal_enrichment.
    """

    if dataframe.empty:
        return []

    owns_connection = conn is None
    if owns_connection:
        conn = get_connection()

    journal_ids = dataframe["id"].tolist()
    sources_by_id = _fetch_sources(conn, journal_ids)
    enrichment_by_id = _fetch_enrichment(conn, journal_ids)

    journals = [
        Journal.from_row(
            row,
            source_details=sources_by_id.get(row["id"], []),
            enrichment=enrichment_by_id.get(row["id"], {}),
        )
        for _, row in dataframe.iterrows()
    ]

    if owns_connection:
        conn.close()

    return journals


def get_all_journals():
    """Retrieve all journals."""

    conn = get_connection()

    query = """
    SELECT *
    FROM journals
    """

    dataframe = pd.read_sql_query(query, conn)

    result = _rows_to_journals(dataframe, conn=conn)

    conn.close()

    return result


def search_by_title(title):
    """Search journals by title."""

    conn = get_connection()

    query = """
    SELECT *
    FROM journals
    WHERE title LIKE ?
    """

    dataframe = pd.read_sql_query(
        query,
        conn,
        params=[f"%{title}%"]
    )

    result = _rows_to_journals(dataframe, conn=conn)

    conn.close()

    return result


def search_journals(**filters):
    """Search journals using any combination of filters."""

    conn = get_connection()

    query = "SELECT * FROM journals"

    conditions = []
    params = []

    for column, value in filters.items():
        conditions.append(f"{column} LIKE ?")
        params.append(f"%{value}%")

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    dataframe = pd.read_sql_query(
        query,
        conn,
        params=params
    )

    result = _rows_to_journals(dataframe, conn=conn)

    conn.close()

    return result


def search_by_keywords(keywords):
    """
    Search journals matching any keyword in the title,
    subjects, or keywords fields.
    """

    # Remove empty keywords
    keywords = [
        keyword.strip()
        for keyword in keywords
        if keyword.strip()
    ]

    # If no keywords were provided, return all journals
    if not keywords:
        return get_all_journals()

    conn = get_connection()

    conditions = []
    params = []

    for keyword in keywords:

        conditions.extend([
            "title LIKE ?",
            "subjects LIKE ?",
            "keywords LIKE ?",
        ])

        params.extend([
            f"%{keyword}%",
            f"%{keyword}%",
            f"%{keyword}%"
        ])

    query = f"""
    SELECT DISTINCT *
    FROM journals
    WHERE {" OR ".join(conditions)}
    """

    dataframe = pd.read_sql_query(
        query,
        conn,
        params=params,
    )

    result = _rows_to_journals(dataframe, conn=conn)

    conn.close()

    return result


def keyword_document_frequency(keyword):
    """
    How many journals in the WHOLE database contain this keyword in
    title/subjects/keywords, regardless of the current search's other
    filters. Used by the recommender to down-weight ubiquitous words
    (e.g. "policy" appearing in thousands of journals) relative to
    distinctive ones, without needing a hardcoded list of "generic"
    words — this measures actual corpus frequency instead of guessing.
    """
    conn = get_connection()
    count = conn.execute(
        "SELECT COUNT(*) FROM journals WHERE title LIKE ? OR subjects LIKE ? OR keywords LIKE ?",
        [f"%{keyword}%"] * 3,
    ).fetchone()[0]
    conn.close()
    return count


def search_candidates(keywords, language=None, free_only=False, indexing=None,
                       quartiles=None, sinta_levels=None, max_review_weeks=None):
    """
    Search journals matching any keyword in the title, subjects, or
    keywords fields, optionally narrowed by language, free-only,
    confirmed indexing source(s), Scopus/WoS quartile(s), SINTA
    accreditation level(s), and/or a maximum typical review time.

    quartiles:
        Optional list (e.g. ["Q1", "Q2"]). Matches a journal if ANY of
        its confirmed sources (Scopus and/or WoS) carries one of these
        quartiles.

    sinta_levels:
        Optional list (e.g. ["SINTA 1", "SINTA 2"]). Matches a journal
        if its SINTA accreditation is one of these.

    (language/free_only/indexing documented above.)

    Note: budget (max APC) filtering is NOT done here — see recommender.
    """

    keywords = [
        keyword.strip()
        for keyword in keywords
        if keyword.strip()
    ]

    conn = get_connection()

    conditions = []
    params = []

    if keywords:
        keyword_conditions = []
        for keyword in keywords:
            keyword_conditions.append(
                "(title LIKE ? OR subjects LIKE ? OR keywords LIKE ?)"
            )
            params.extend([f"%{keyword}%"] * 3)
        conditions.append("(" + " OR ".join(keyword_conditions) + ")")

    if language:
        conditions.append("languages LIKE ?")
        params.append(f"%{language}%")

    if free_only:
        conditions.append("apc = 'No'")

    if indexing:
        placeholders = ",".join("?" for _ in indexing)
        conditions.append(
            f"id IN (SELECT journal_id FROM journal_sources WHERE source IN ({placeholders}))"
        )
        params.extend(indexing)

    if quartiles:
        placeholders = ",".join("?" for _ in quartiles)
        conditions.append(
            f"id IN (SELECT journal_id FROM journal_sources WHERE quartile IN ({placeholders}))"
        )
        params.extend(quartiles)

    if sinta_levels:
        placeholders = ",".join("?" for _ in sinta_levels)
        conditions.append(
            f"id IN (SELECT journal_id FROM journal_sources WHERE accreditation IN ({placeholders}))"
        )
        params.extend(sinta_levels)

    if max_review_weeks is not None:
        conditions.append("review_weeks IS NOT NULL AND review_weeks <= ?")
        params.append(max_review_weeks)

    query = "SELECT DISTINCT * FROM journals"

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    dataframe = pd.read_sql_query(query, conn, params=params)

    result = _rows_to_journals(dataframe, conn=conn)

    conn.close()

    return result


def count_journals():
    """
    Return the number of journals stored in the database.
    """

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM journals
        """
    )

    count = cursor.fetchone()[0]

    conn.close()

    return count


def count_by_source():
    """
    Return {source: count} for every confirmed indexing source, e.g.
    {"DOAJ": 23077, "Scopus": 32191, "Web of Science": 17815, "SINTA": 11768}.

    A small, read-only aggregate for display purposes (e.g. homepage
    statistics) — not a general query-builder.
    """

    conn = get_connection()

    rows = conn.execute(
        """
        SELECT source, COUNT(DISTINCT journal_id)
        FROM journal_sources
        GROUP BY source
        """
    ).fetchall()

    conn.close()

    return dict(rows)


def count_by_enrichment_provider():
    """
    Return {provider: count} for every metadata enrichment provider,
    e.g. {"road": 27500, "erihplus": 8963}. Same shape/purpose as
    count_by_source(), kept as a separate function/query since this
    reads journal_enrichment, not journal_sources -- see
    docs/ENRICHMENT.md.
    """

    conn = get_connection()

    rows = conn.execute(
        """
        SELECT provider, COUNT(DISTINCT journal_id)
        FROM journal_enrichment
        GROUP BY provider
        """
    ).fetchall()

    conn.close()

    return dict(rows)


def insert_minimal_journal(conn, title, publisher=None, country=None, website=None,
                            issn_print=None, issn_online=None, source=None):
    """
    Create a new journal row from a non-DOAJ source (Scopus/WoS/SINTA)
    when no existing journal matches it. Used by the import pipeline —
    takes an already-open connection so callers can batch many inserts
    in one transaction.
    """

    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO journals (title, publisher, country, website,
                               issn_print, issn_online, source)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (title, publisher, country, website, issn_print, issn_online, source),
    )

    return cursor.lastrowid


def tag_source(conn, journal_id, source, metadata=None):
    """
    Confirm a journal in a given source, with any source-specific
    metadata (quartile/sjr/h_index for Scopus/WoS, accreditation for
    SINTA). Upserts: re-running an import updates the metadata for an
    already-tagged journal rather than duplicating the row.
    """

    metadata = metadata or {}

    conn.execute(
        """
        INSERT INTO journal_sources (journal_id, source, quartile, sjr, h_index, accreditation)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(journal_id, source) DO UPDATE SET
            quartile = excluded.quartile,
            sjr = excluded.sjr,
            h_index = excluded.h_index,
            accreditation = excluded.accreditation
        """,
        (
            journal_id,
            source,
            metadata.get("quartile"),
            metadata.get("sjr"),
            metadata.get("h_index"),
            metadata.get("accreditation"),
        ),
    )


def tag_enrichment(conn, journal_id, provider, data, fetched_at=None):
    """
    Attach a metadata enrichment provider's data to a journal that
    already exists. Upserts, same as tag_source. `data` is stored as a
    JSON blob -- see docs/ENRICHMENT.md for why (provider-specific,
    display-only shape, never queried or filtered on).

    Never creates a journal row -- callers (importers/enrichment/)
    only call this for a journal_id already resolved by matching
    against `journals`, exactly like tag_source.
    """

    conn.execute(
        """
        INSERT INTO journal_enrichment (journal_id, provider, fetched_at, data)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(journal_id, provider) DO UPDATE SET
            fetched_at = excluded.fetched_at,
            data = excluded.data
        """,
        (journal_id, provider, fetched_at, json.dumps(data)),
    )


def insert_journals(journals):
    """
    Insert Journal objects into the database, along with their confirmed
    indexing sources into journal_sources.
    """

    conn = get_connection()
    cursor = conn.cursor()

    journal_columns = [
        column.name
        for column in Journal.__dataclass_fields__.values()
        if column.name not in ("id", "source_details", "enrichment")
    ]

    placeholders = ", ".join("?" for _ in journal_columns)
    columns_sql = ", ".join(journal_columns)

    for journal in journals:

        row = asdict(journal)
        values = [row[column] for column in journal_columns]

        cursor.execute(
            f"INSERT INTO journals ({columns_sql}) VALUES ({placeholders})",
            values,
        )

        journal_id = cursor.lastrowid

        # A journal's confirmed sources are its `sources` list if set,
        # otherwise its single `source` value (backward compatible with
        # importers that haven't been updated to set `sources`).
        sources = journal.sources or ([journal.source] if journal.source else [])

        for source in sources:
            cursor.execute(
                "INSERT OR IGNORE INTO journal_sources (journal_id, source) VALUES (?, ?)",
                (journal_id, source),
            )

    conn.commit()
    conn.close()
