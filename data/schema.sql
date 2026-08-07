DROP TABLE IF EXISTS journal_enrichment;
DROP TABLE IF EXISTS journal_sources;
DROP TABLE IF EXISTS journals;

CREATE TABLE journals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    title TEXT NOT NULL,

    publisher TEXT,
    country TEXT,

    website TEXT,
    doaj_url TEXT,

    issn_print TEXT,
    issn_online TEXT,

    subjects TEXT,
    keywords TEXT,
    languages TEXT,

    apc TEXT,
    apc_amount REAL,
    waiver_policy TEXT,

    review_process TEXT,
    review_weeks INTEGER,

    license TEXT,

    article_count INTEGER,

    -- The source this row was first created from. A journal's FULL set
    -- of confirmed indexing sources lives in journal_sources below, not
    -- here — this column is historical/informational only.
    source TEXT
);

-- A journal may be confirmed in more than one index (DOAJ, Scopus,
-- Web of Science, SINTA, ...). One row per (journal, source) pair, so
-- a journal in three indexes has three rows here and still only ONE
-- row in `journals`. Metadata that's specific to a given source (e.g.
-- Scopus quartile, SINTA accreditation) lives on that source's row and
-- is simply NULL for sources it doesn't apply to.
CREATE TABLE journal_sources (
    journal_id INTEGER NOT NULL,
    source TEXT NOT NULL,

    -- Scopus / Web of Science (via SCImago)
    quartile TEXT,
    sjr REAL,
    h_index INTEGER,

    -- SINTA
    accreditation TEXT,

    PRIMARY KEY (journal_id, source),
    FOREIGN KEY (journal_id) REFERENCES journals(id)
);

CREATE INDEX idx_journals_issn_print ON journals(issn_print);
CREATE INDEX idx_journals_issn_online ON journals(issn_online);
CREATE INDEX idx_journals_title ON journals(title);
CREATE INDEX idx_journals_country ON journals(country);
CREATE INDEX idx_journal_sources_journal_id ON journal_sources(journal_id);
CREATE INDEX idx_journal_sources_source ON journal_sources(source);

-- Metadata enrichment (docs/ENRICHMENT.md) -- structurally separate
-- from journal_sources on purpose: nothing in services/recommender.py
-- reads this table, so a bug here cannot affect search, filtering, or
-- ranking. `data` is a JSON blob (display-only, provider-specific
-- shape) rather than fixed columns, since providers' fields genuinely
-- differ and none of it needs to be queried or filtered on.
CREATE TABLE journal_enrichment (
    journal_id INTEGER NOT NULL,
    provider TEXT NOT NULL,
    fetched_at TEXT,
    data TEXT NOT NULL,

    PRIMARY KEY (journal_id, provider),
    FOREIGN KEY (journal_id) REFERENCES journals(id)
);

CREATE INDEX idx_journal_enrichment_journal_id ON journal_enrichment(journal_id);