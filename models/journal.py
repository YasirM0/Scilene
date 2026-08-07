"""
Journal domain model.
"""

from dataclasses import dataclass, field


@dataclass(slots=True)
class Journal:
    """
    Internal representation of a journal.

    All importers convert external data into this model before
    it is validated and stored in the database.

    `source_details` holds one entry per confirmed index (DOAJ, Scopus,
    Web of Science, SINTA, ...), each with whatever metadata is specific
    to that source (Scopus/WoS quartile & SJR, SINTA accreditation, ...).
    `.sources` is a convenience property returning just the source names.
    """

    id: int | None = None

    title: str = ""

    publisher: str | None = None
    country: str | None = None

    website: str | None = None
    doaj_url: str | None = None

    issn_print: str | None = None
    issn_online: str | None = None

    subjects: str | None = None
    keywords: str | None = None
    languages: str | None = None

    apc: str | None = None
    apc_amount: str | None = None
    waiver_policy: str | None = None

    review_process: str | None = None
    review_weeks: int | None = None

    license: str | None = None

    article_count: int | None = None

    source: str | None = None
    # Full detail per confirmed source, e.g.
    # [{"source": "Scopus", "quartile": "Q1", "sjr": 1.2, "h_index": 40, "accreditation": None}, ...]
    source_details: list[dict] = field(default_factory=list)

    # Display-only metadata enrichment (docs/ENRICHMENT.md), keyed by
    # provider name, e.g. {"road": {...}, "erihplus": {...}}. Like
    # source_details, this is populated separately by the repository
    # layer (journal_enrichment, not a `journals` column) and must be
    # excluded anywhere Journal fields are mapped 1:1 onto `journals`
    # columns -- see insert_journals().
    enrichment: dict = field(default_factory=dict)

    @property
    def sources(self):
        """Plain list of confirmed source names, e.g. ["DOAJ", "Scopus"]."""
        return [detail["source"] for detail in self.source_details]

    @staticmethod
    def _clean(value):
        """
        pandas represents SQL NULL as NaN for some columns depending on
        the query shape, not just None. NaN is truthy in Python (`nan or
        ""` returns `nan`, not `""`), which breaks any `field or default`
        pattern downstream — so it's normalized to None right here, once,
        rather than requiring every caller to remember to check for it.
        """
        if isinstance(value, float) and value != value:  # NaN != NaN
            return None
        return value

    @classmethod
    def from_row(cls, row, source_details=None, enrichment=None):
        """
        Create a Journal from a database row.

        `source_details` (optional) is the list of confirmed indexing
        sources (with metadata) for this journal, looked up separately
        from journal_sources. Falls back to a single-entry list built
        from row["source"] if not provided.

        `enrichment` (optional) is the {provider: data} dict looked up
        separately from journal_enrichment. Defaults to {} (no
        enrichment data), never fabricated from anything on the row.
        """

        clean = cls._clean

        if source_details is None:
            source_details = (
                [{"source": clean(row["source"]), "quartile": None, "sjr": None,
                  "h_index": None, "accreditation": None}]
                if clean(row["source"]) else []
            )

        return cls(
            id=row["id"],
            title=clean(row["title"]),
            publisher=clean(row["publisher"]),
            country=clean(row["country"]),
            website=clean(row["website"]),
            doaj_url=clean(row["doaj_url"]),
            issn_print=clean(row["issn_print"]),
            issn_online=clean(row["issn_online"]),
            subjects=clean(row["subjects"]),
            keywords=clean(row["keywords"]),
            languages=clean(row["languages"]),
            apc=clean(row["apc"]),
            apc_amount=clean(row["apc_amount"]),
            waiver_policy=clean(row["waiver_policy"]),
            review_process=clean(row["review_process"]),
            review_weeks=clean(row["review_weeks"]),
            license=clean(row["license"]),
            article_count=clean(row["article_count"]),
            source=clean(row["source"]),
            source_details=source_details,
            enrichment=enrichment or {},
        )