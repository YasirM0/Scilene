DROP TABLE IF EXISTS journal_aliases;
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

    -- Semicolon-separated curated index terms (#73/#74), from
    -- data/processed/*_complete.csv's "index_terms" column -- the real
    -- replacement for the OpenAlex-topics proxy scripts/build_semantic_index.py
    -- used before this existed. Same "first source to set it wins" rule
    -- as other core metadata (DOAJ imports first): not concatenated
    -- across sources, to avoid mixing two different enrichment passes'
    -- terms for one journal.
    index_terms TEXT,

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
    source TEXT,

    -- Publication type (#128) -- e.g. "Journal", "Book Series", "Trade
    -- Journal". Only the Elsevier Source List's "Source Type" column
    -- currently populates this (importers/elsevier.py); NULL for
    -- journals Elsevier hasn't matched, resolved to a display default
    -- at presentation time (utils/publication_types.py), never
    -- fabricated here.
    publication_type TEXT
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

    -- Elsevier Source List (#98, source = 'Scopus' rows only). `active`
    -- is NULL for every non-Elsevier-tagged row (unknown, not "false")
    -- -- only importers/elsevier.py ever sets it, to 1 or 0. `coverage`
    -- and `article_language` are display-only, never read by
    -- services/recommender.py; `active` DOES affect default visibility
    -- (web/search_presentation.py's filter_visible_results, reusing
    -- the existing "Show weaker recommendations" toggle -- no separate
    -- filter, per the issue).
    active INTEGER,
    coverage TEXT,
    source_record_id TEXT,
    article_language TEXT,

    -- The period from Elsevier's own "Added to List <period>" column
    -- header (e.g. "June 2026"), stored as plain text ONLY for rows
    -- that column flags "Added" -- resolved to a real, dated sentence
    -- at import time ("Indexed in Scopus since June 2026"), never a
    -- relative one ("Recently indexed") that would go stale (#98).
    added_to_list TEXT,

    PRIMARY KEY (journal_id, source),
    FOREIGN KEY (journal_id) REFERENCES journals(id)
);

CREATE INDEX idx_journals_issn_print ON journals(issn_print);
CREATE INDEX idx_journals_issn_online ON journals(issn_online);
CREATE INDEX idx_journals_title ON journals(title);
CREATE INDEX idx_journals_country ON journals(country);
CREATE INDEX idx_journal_sources_journal_id ON journal_sources(journal_id);
CREATE INDEX idx_journal_sources_source ON journal_sources(source);
CREATE INDEX idx_journal_sources_source_record_id ON journal_sources(source_record_id);

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

-- Alternate/historical titles for a journal (#100) -- translated
-- titles, former names, "continued as" successors, related titles.
-- Purely additive: a journal with no known aliases just has zero rows
-- here, nothing else in the schema changes shape. alias_type keeps
-- provenance (e.g. "Formerly known as", "English title") instead of
-- treating every alias the same, per the issue's acceptance criteria.
CREATE TABLE journal_aliases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    journal_id INTEGER NOT NULL,
    alias TEXT NOT NULL,
    alias_type TEXT NOT NULL,
    source TEXT NOT NULL,

    FOREIGN KEY (journal_id) REFERENCES journals(id)
);

CREATE UNIQUE INDEX idx_journal_aliases_unique ON journal_aliases(journal_id, alias, source);
CREATE INDEX idx_journal_aliases_journal_id ON journal_aliases(journal_id);
CREATE INDEX idx_journal_aliases_alias ON journal_aliases(alias);