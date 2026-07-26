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


def _fetch_sources(conn, journal_ids):
    """
    Batch-fetch confirmed indexing sources for a set of journal ids,
    with any per-source metadata (Scopus/WoS quartile, SJR, H-index;
    SINTA accreditation). Returns {journal_id: [detail_dict, ...]}.
    """

    journal_ids = list(journal_ids)

    if not journal_ids:
        return {}

    placeholders = ",".join("?" for _ in journal_ids)

    rows = conn.execute(
        f"SELECT journal_id, source, quartile, sjr, h_index, accreditation "
        f"FROM journal_sources WHERE journal_id IN ({placeholders})",
        journal_ids,
    ).fetchall()

    details_by_id = {}
    for journal_id, source, quartile, sjr, h_index, accreditation in rows:
        details_by_id.setdefault(journal_id, []).append({
            "source": source,
            "quartile": quartile,
            "sjr": sjr,
            "h_index": h_index,
            "accreditation": accreditation,
        })

    return details_by_id


def _rows_to_journals(dataframe, conn=None):
    """
    Convert a pandas DataFrame into Journal objects, attaching each
    journal's confirmed indexing sources from journal_sources.
    """

    if dataframe.empty:
        return []

    owns_connection = conn is None
    if owns_connection:
        conn = get_connection()

    sources_by_id = _fetch_sources(conn, dataframe["id"].tolist())

    journals = [
        Journal.from_row(row, source_details=sources_by_id.get(row["id"], []))
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
        if column.name not in ("id", "source_details")
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
