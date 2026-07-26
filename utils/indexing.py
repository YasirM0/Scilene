"""
Shared, Streamlit-free formatting for a journal's confirmed indexing
sources. Used by both the search page (for the on-screen chips) and the
export reports (services/reports.py), so the two never drift apart.
"""


def format_source_chip(detail):
    """
    e.g. 'Scopus (Q1)', 'SINTA 2', or plain 'DOAJ' / 'Web of Science'.

    Quartile is only ever shown on the Scopus entry, not repeated on
    Web of Science — both come from the same underlying SCImago row in
    this database, so showing it twice would just be the same number
    twice, not new information.
    """
    source = detail["source"]
    if source == "SINTA" and detail.get("accreditation"):
        return detail["accreditation"]
    if source == "Scopus" and detail.get("quartile"):
        return f"Scopus ({detail['quartile']})"
    return source


def format_index_summary(source_details, separator=", "):
    if not source_details:
        return "Not listed"
    return separator.join(format_source_chip(d) for d in source_details)
