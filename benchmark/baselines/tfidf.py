"""
TF-IDF / keyword-search baseline (#112, docs/BENCHMARK.md).

A deliberately separate, standalone implementation -- it does NOT
import services/recommender.py or services/repository.py. The whole
point of a baseline is to be a genuinely independent point of
comparison; wiring it through the app's own search machinery would
make "beats the baseline" a meaningless claim.

Pure Python, no numpy/sklearn: a corpus of ~55k short documents
(journal title + subjects + keywords) is small enough that a plain
inverted index is fast, and it keeps this benchmark tool from adding a
new dependency to the shipped app (requirements.txt) for something
only this optional, offline tool needs.

Classic TF-IDF with cosine similarity via an inverted index:
  - idf(t) = ln((N + 1) / (df(t) + 1)) + 1          (smoothed, sklearn's formula)
  - each document's TF-IDF vector is L2-normalized once, at index time
  - a query is scored by summing query_weight * doc_weight over terms
    the query and a candidate document share -- equivalent to cosine
    similarity since both sides are pre-normalized.
"""

import math
import re
from collections import defaultdict

_TOKEN_RE = re.compile(r"[a-zA-Z]{2,}")


def tokenize(text):
    if not text:
        return []
    return _TOKEN_RE.findall(text.lower())


class TFIDFIndex:
    """
    Build once from the full journal corpus, then call `search()` per
    benchmark record. Building is O(corpus size); each search is
    O(query terms), not O(corpus size), via the inverted index.
    """

    def __init__(self, documents):
        """
        `documents`: {doc_id: text}. Builds document frequencies, IDF,
        L2-normalized per-document TF-IDF vectors, and an inverted
        index (term -> [(doc_id, weight), ...]) for fast scoring.
        """
        self.doc_count = len(documents)
        doc_freq = defaultdict(int)
        doc_tokens = {}

        for doc_id, text in documents.items():
            tokens = tokenize(text)
            doc_tokens[doc_id] = tokens
            for term in set(tokens):
                doc_freq[term] += 1

        self.idf = {
            term: math.log((self.doc_count + 1) / (df + 1)) + 1
            for term, df in doc_freq.items()
        }

        self.inverted_index = defaultdict(list)

        for doc_id, tokens in doc_tokens.items():
            term_counts = defaultdict(int)
            for term in tokens:
                term_counts[term] += 1

            weights = {
                term: count * self.idf[term]
                for term, count in term_counts.items()
            }
            norm = math.sqrt(sum(w * w for w in weights.values())) or 1.0

            for term, weight in weights.items():
                self.inverted_index[term].append((doc_id, weight / norm))

    def search(self, query_text, top_n=20):
        """Returns [(doc_id, score), ...] sorted by score descending."""
        term_counts = defaultdict(int)
        for term in tokenize(query_text):
            term_counts[term] += 1

        query_weights = {
            term: count * self.idf[term]
            for term, count in term_counts.items()
            if term in self.idf
        }
        norm = math.sqrt(sum(w * w for w in query_weights.values())) or 1.0

        scores = defaultdict(float)
        for term, q_weight in query_weights.items():
            q_weight /= norm
            for doc_id, doc_weight in self.inverted_index.get(term, []):
                scores[doc_id] += q_weight * doc_weight

        ranked = sorted(scores.items(), key=lambda pair: pair[1], reverse=True)
        return ranked[:top_n]


def build_journal_corpus(conn):
    """
    {journal_id: "title subjects keywords"} for every journal --
    matches the fields services.repository.search_candidates() itself
    matches against (title, subjects, keywords), so the baseline is
    working from the same information, not a richer or poorer corpus.
    """
    rows = conn.execute("SELECT id, title, subjects, keywords FROM journals").fetchall()
    return {
        journal_id: " ".join(part for part in (title, subjects, keywords) if part)
        for journal_id, title, subjects, keywords in rows
    }
