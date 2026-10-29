"""Deterministic test-double encoder (hashed bag-of-words vectors, word-count tokens) and a
chunk-integrity checker shared by the structural and real-tokenizer tests.

The encoder is for structural tests only. It is never used to claim retrieval quality.
"""
from hashlib import sha256
import math
import re

from threadsense.knowledge_markdown import sections
from threadsense.retrieval.config import CHUNKING_VERSION, EMBEDDING
from threadsense.routing import digest

PART = re.compile(r'^(## .*) \(part (\d+)/\d+\)$')
STATES = ('authoring_record_kind', 'decision_status', 'execution_status', 'outcome_status')


def body_words(chunks):
    """Chunk bodies in order with split bookkeeping undone: part markers removed, repeated headings dropped."""
    words = []
    for chunk in chunks:
        for line in chunk['text'].split('\n'):
            part = PART.match(line)
            if not (part and int(part.group(2)) > 1):
                words += (part.group(1) if part else line).split()
    return words


def check_chunks(document, chunks, limit):
    """Every source word once and in order; resolvable citations; scoped sections, states and supersession."""
    expected, title = document['text'].split(), document['text'].lstrip().split('\n', 1)[0]
    got = body_words(chunks)
    if got != expected:  # Only a title-only preamble may be dropped, because the header repeats it.
        assert title.startswith('# ') and got == expected[len(title.split()):], document['document_id']
        assert all(c['indexed_text'].startswith(title[2:].strip()) for c in chunks)
    headings = {h for h, _ in sections(document['text']) if h} | {'Preamble'}
    supersession = document['metadata']['source_metadata'].get('supersession') or {'superseded_by': []}
    for index, chunk in enumerate(chunks):
        assert chunk['token_count'] <= limit and chunk['chunk_index'] == index and chunk['chunk_count'] == len(chunks)
        assert chunk['chunk_id'] == 'chunk_' + digest([CHUNKING_VERSION, document['document_id'], document['version_id'], index])[:32]
        header = chunk['indexed_text'][:-len(chunk['text'])]
        assert chunk['indexed_text'].endswith('\n\n' + chunk['text']) and header.rstrip('\n')
        citation = chunk['citation']
        assert (citation['document_id'], citation['version_id']) == (document['document_id'], document['version_id'])
        assert citation['sections'] == chunk['sections'] and set(chunk['sections']) <= headings
        assert all(f'## {s}' in chunk['text'] for s in chunk['sections'] if s != 'Preamble')
        authoring = document['metadata']['source_metadata'].get('authoring') or {}
        assert citation['authoring'] == (f"{authoring['document_id']}@{authoring['version']}" if authoring.get('document_id') else None)
        meta = chunk['metadata']
        if chunk['collection'] == 'decisions':
            assert all(f": {meta[k]}" in header for k in STATES if meta[k]), (document['document_id'], index)
        scoped = [r for r in supersession['superseded_by'] if r['granularity'] == 'document' or r.get('section') in chunk['sections']]
        assert chunk['supersession']['chunk_superseded_by'] == scoped


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


_READ = '''
import json, sys, chromadb
from chromadb.config import Settings
client = chromadb.PersistentClient(path=sys.argv[1], settings=Settings(anonymized_telemetry=False))
out = {}
for name in sys.argv[2:]:
    got = client.get_collection(name).get(include=['embeddings', 'documents', 'metadatas'])
    for key, vector, text, meta in zip(got['ids'], got['embeddings'], got['documents'], got['metadatas']):
        out[key] = [name, [float(x) for x in vector], text, meta]
sys.stdout.write(json.dumps(out))
'''


def read_chroma(path):
    """Everything Chroma persisted, read by a new process so nothing comes from the builder's client cache."""
    import json
    import subprocess
    import sys
    from threadsense.retrieval.config import COLLECTION_NAMES
    done = subprocess.run([sys.executable, '-c', _READ, str(path), *COLLECTION_NAMES], capture_output=True, text=True, check=True)
    return json.loads(done.stdout)


def check_stored(chunks, stored, dimension):
    """IDs, collection, indexed text and Chroma metadata match the sidecar; vectors are finite and unit length."""
    assert set(stored) == {c['chunk_id'] for c in chunks}
    for c in chunks:
        name, vector, text, meta = stored[c['chunk_id']]
        assert name == c['collection'] and text == c['indexed_text']
        assert meta == {'chunk_id': c['chunk_id'], 'document_id': c['document_id'], 'version_id': c['version_id'], 'collection': name}
        assert len(vector) == dimension and all(math.isfinite(x) for x in vector)
        assert abs(math.sqrt(sum(x * x for x in vector)) - 1.0) < 1e-4, c['chunk_id']
