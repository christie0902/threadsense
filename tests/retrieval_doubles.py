"""Deterministic test-double encoder: hashed bag-of-words vectors, word-count tokens.

Structural tests only. It is never used to claim retrieval quality.
"""
from hashlib import sha256
import math
import re

from threadsense.retrieval.config import EMBEDDING


class HashEncoder:
    allow_download = False

    def __init__(self, dimension=64, max_tokens=120):
        self.dimension, self.max_tokens = dimension, max_tokens

    def count(self, text):
        return len(text.split()) + 2

    def encode(self, texts):
        vectors = []
        for text in texts:
            v = [0.0] * self.dimension
            for word in re.findall(r'\w+', text.lower()):
                v[int(sha256(word.encode()).hexdigest(), 16) % self.dimension] += 1.0
            norm = math.sqrt(sum(x * x for x in v)) or 1.0
            vectors.append([x / norm for x in v])
        return vectors

    def identity(self):
        return {**EMBEDDING, 'dimension': self.dimension, 'max_tokens': self.max_tokens}
