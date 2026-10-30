"""Build the persistent Chroma index and its provenance sidecar. Queries never call this.

Layout under the index directory:
  chroma/          persistent Chroma (guidelines, faq, decisions)
  chunks.json      every chunk: text, citation, filter projection, supersession
  documents.json   full normalized metadata per document version
  manifest.json    fingerprints, embedding identity, chunking/retrieval config, counts
"""
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path

from threadsense.retrieval.chunking import chunk_document
from threadsense.retrieval.config import (
    CHUNKING_VERSION, COLLECTION_NAMES, DEFAULTS, DENSE_SEARCH, FIXTURE_CUTOFF, FIXTURE_ROOT, HNSW, INDEX_DIR, KNOWLEDGE_ROOT,
)
from threadsense.retrieval.corpus import collect
from threadsense.routing import ROOT, digest

INDEX_FORMAT = 'threadsense-retrieval-index-v1'


class RetrievalIndexError(RuntimeError):
    """Missing, incompatible or stale index; rebuild explicitly."""


def chroma_client(path):
    import chromadb
    from chromadb.config import Settings
    return chromadb.PersistentClient(path=str(path), settings=Settings(anonymized_telemetry=False))


_VERIFY = '''
import sys, chromadb
from chromadb.config import Settings
client = chromadb.PersistentClient(path=sys.argv[1], settings=Settings(anonymized_telemetry=False))
for pair in sys.argv[2:]:
    name, expected = pair.split('=')
    got = client.get_collection(name).get(include=['embeddings'])
    if len(got['ids']) != int(expected) or any(len(v) == 0 for v in got['embeddings']):
        raise SystemExit(f'{name}: read {len(got["ids"])} embeddings, expected {expected}')
'''


def verify_readable(path, counts):
    """Every stored embedding must be readable from a fresh process before the manifest is published."""
    import subprocess
    import sys
    pairs = [f'{name}={count}' for name, count in counts.items()]
    done = subprocess.run([sys.executable, '-c', _VERIFY, str(path), *pairs], capture_output=True, text=True)
    if done.returncode:
        raise RetrievalIndexError('Persisted Chroma index is not readable from a new process: '
                                  + done.stderr.strip().splitlines()[-1][:300])


def _write(path, payload):
    body = (json.dumps(payload, ensure_ascii=False, indent=1, sort_keys=True) + '\n').encode('utf-8')
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_bytes(body)
    os.replace(tmp, path)
    return sha256(body).hexdigest()


def _rel(path):
    path = Path(path).resolve()
    return path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else path.as_posix()


def plan(encoder, *, knowledge_root=KNOWLEDGE_ROOT, fixture_root=FIXTURE_ROOT, cutoff=FIXTURE_CUTOFF, canonical_members=None,
         decision_root=None):
    """Normalize and chunk without touching any index. Returns chunks, documents and fingerprints.

    decision_root (optional): exported TL decisions; absent, the fingerprint is the same as before it existed.
    """
    documents, corpus = collect(Path(knowledge_root), Path(fixture_root), cutoff, canonical_members,
                                Path(decision_root) if decision_root else None)
    chunks = [c for d in sorted(documents, key=lambda d: (d['document_id'], d['version_id']))
              for c in chunk_document(d, encoder.count, encoder.max_tokens)]
    ids = [c['chunk_id'] for c in chunks]
    if len(ids) != len(set(ids)):
        raise RetrievalIndexError('Duplicate chunk IDs.')
    core = {'index_format': INDEX_FORMAT, 'chunking_version': CHUNKING_VERSION, 'embedding': encoder.identity(),
            'hnsw': HNSW, 'dense_search': DENSE_SEARCH, 'retrieval_defaults': DEFAULTS, 'cutoff': cutoff,
            'knowledge_root': _rel(knowledge_root), 'fixture_root': _rel(fixture_root),
            'corpus_fingerprint': corpus['corpus_fingerprint'],
            'chunk_fingerprint': digest([[c['chunk_id'], sha256(c['indexed_text'].encode('utf-8')).hexdigest()] for c in chunks])}
    if decision_root:
        core['decision_root'] = _rel(decision_root)
    return chunks, documents, corpus, core


def build_index(index_dir=INDEX_DIR, *, encoder, rebuild=False, **sources):
    index_dir = Path(index_dir)
    chunks, documents, corpus, core = plan(encoder, **sources)
    fingerprint = digest(core)
    manifest_path = index_dir/'manifest.json'
    if manifest_path.is_file():
        old = json.loads(manifest_path.read_text(encoding='utf-8'))
        if old.get('build_fingerprint') == fingerprint:
            return {**old, 'status': 'UP_TO_DATE'}
        if not rebuild:
            raise RetrievalIndexError('Index exists with a different corpus/configuration; rerun with --rebuild.')
    elif index_dir.exists() and any(index_dir.iterdir()) and not rebuild:
        raise RetrievalIndexError('Index directory has no manifest (incomplete build); rerun with --rebuild.')
    index_dir.mkdir(parents=True, exist_ok=True)
    if manifest_path.exists():
        manifest_path.unlink()  # No manifest while collections change: queries refuse a half-built index.
    client = chroma_client(index_dir/'chroma')
    existing = {c.name if hasattr(c, 'name') else c for c in client.list_collections()}
    vectors = dict(zip([c['chunk_id'] for c in chunks], encoder.encode([c['indexed_text'] for c in chunks])))
    counts = {}
    for name in COLLECTION_NAMES:
        if name in existing:
            client.delete_collection(name)  # Replaced wholesale, so repeat builds never accumulate chunks.
        collection = client.create_collection(name, metadata=dict(HNSW), embedding_function=None)
        members = [c for c in chunks if c['collection'] == name]
        if members:
            collection.add(ids=[c['chunk_id'] for c in members], embeddings=[vectors[c['chunk_id']] for c in members],
                           documents=[c['indexed_text'] for c in members],
                           metadatas=[{'chunk_id': c['chunk_id'], 'document_id': c['document_id'],
                                       'version_id': c['version_id'], 'collection': name} for c in members])
        counts[name] = len(collection.get(include=[])['ids'])
        if counts[name] != len(members):
            raise RetrievalIndexError(f'{name}: stored {counts[name]} chunks, expected {len(members)}.')
    # Release the build's Chroma system: `del` keeps it cached per path, and a later in-process open would
    # reuse it and intermittently fail ("Nothing found on disk"; reproduced in ~5% of build->open cycles).
    client.close()
    verify_readable(index_dir/'chroma', counts)
    chunks_sha = _write(index_dir/'chunks.json', chunks)
    documents_sha = _write(index_dir/'documents.json', {f"{d['document_id']}@{d['version_id']}": d for d in documents})
    manifest = {**core, 'build_fingerprint': fingerprint, 'built_at': datetime.now(timezone.utc).isoformat(),
                'model_download_allowed': encoder.allow_download if hasattr(encoder, 'allow_download') else False,
                'documents': len(documents), 'chunks': len(chunks), 'collection_chunks': counts,
                'collection_documents': dict(Counter(c['collection'] for c in chunks if c['chunk_index'] == 0)),
                'split_documents': sum(1 for c in chunks if c['chunk_index'] == 1),
                'max_chunk_tokens': max((c['token_count'] for c in chunks), default=0),
                'corpus': corpus, 'chunks_sha256': chunks_sha, 'documents_sha256': documents_sha}
    _write(manifest_path, manifest)
    return {**manifest, 'status': 'BUILT'}
