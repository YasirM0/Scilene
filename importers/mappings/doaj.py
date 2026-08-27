"""
Column mappings for the DOAJ journal CSV.
"""

DOAJ_COLUMNS = {
    # Basic journal information
    "title": "Journal title",
    "website": "Journal URL",
    "doaj_url": "URL in DOAJ",

    # Identifiers
    "issn_print": "Journal ISSN (print version)",
    "issn_online": "Journal EISSN (online version)",

    # Publisher
    "publisher": "Publisher",
    "country": "Country of publisher",

    # Classification
    "subjects": "Subjects",
    "keywords": "Keywords",
    "languages": "Languages in which the journal accepts manuscripts",
    "index_terms": "index_terms",

    # Publishing model
    "apc": "APC",
    "apc_amount": "APC amount",
    "waiver_policy": "Journal waiver policy (for developing country authors etc)",

    # Review
    "review_process": "Review process",
    "review_weeks": "Average number of weeks between article submission and publication",

    # Metadata
    "license": "Journal license",
    #"added_date": "Added on Date",
    #"updated_date": "Last updated Date",
    "article_count": "Number of Article Records",
}