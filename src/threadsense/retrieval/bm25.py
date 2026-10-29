"""Okapi BM25 over the same chunk texts that are embedded. Pure Python, deterministic."""
from collections import Counter
import math
import re

# Small function-word list only; domain terms (QN, LT, JSON, tie) are never removed.
STOPWORDS = frozenset('''a an and are as at be but by for from has have if in into is it its of on or
that the their then there these this to was were will with'''.split())


def tokenize(text):
    return [t for t in re.findall(r'\w+', text.lower()) if t not in STOPWORDS]


class BM25:
    """Corpus statistics come from every indexed chunk, so filters never change IDF."""

    def __init__(self, texts, *, k1=1.5, b=0.75):
        self.k1, self.b = k1, b
        self.terms = {key: Counter(tokenize(text)) for key, text in texts.items()}
        self.lengths = {key: sum(c.values()) for key, c in self.terms.items()}
        self.average = sum(self.lengths.values()) / max(len(self.lengths), 1)
        df = Counter(term for counts in self.terms.values() for term in counts)
        n = len(self.terms)
        self.idf = {term: math.log(1 + (n - f + 0.5) / (f + 0.5)) for term, f in df.items()}

    def scores(self, query, keys):
        """Positive scores for the given eligible keys only."""
        query_terms = tokenize(query)
        result = {}
        for key in keys:
            counts, length = self.terms[key], self.lengths[key]
            score = 0.0
            for term in query_terms:
                tf = counts.get(term, 0)
                if tf:
                    score += self.idf[term] * tf * (self.k1 + 1) / (tf + self.k1 * (1 - self.b + self.b * length / self.average))
            if score > 0:
                result[key] = score
        return result
