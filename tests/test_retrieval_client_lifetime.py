"""Chroma client lifetime (DETERMINISTIC). A Retriever reads the stored embeddings once and releases its Chroma client
before its constructor returns or raises, so no cached Chroma system outlives an open. A system left cached for a path
was reused by the next open of that path in the same process, which intermittently failed with "Error creating hnsw
segment reader: Nothing found on disk" (tests/repro_chroma_reopen.py second_open: 3/40 and 6/120 cycles failed
before this change, always on the second open)."""
import json
import os
import shutil

import pytest

from threadsense.agents.advisor_evidence import StaleIndexError, open_retriever
from threadsense.retrieval.index import KNOWLEDGE_ROOT, RetrievalIndexError, build_index
from threadsense.retrieval.search import Retriever
from tests.retrieval_doubles import HashEncoder


def cached(index):
    from chromadb.api.shared_system_client import SharedSystemClient
    target = os.path.normcase(os.path.abspath(index/'chroma'))
    return [k for k in SharedSystemClient._identifier_to_system if os.path.normcase(os.path.abspath(k)) == target]


@pytest.fixture
def index(tmp_path):
    path = tmp_path/'index'
    build_index(path, encoder=HashEncoder())
    assert cached(path) == []  # build_index already closes its own client
    return path


def test_open_leaves_no_cached_system_and_reopening_reads_fresh(index):
    first = Retriever(index, encoder=HashEncoder())
    assert cached(index) == []
    second = Retriever(index, encoder=HashEncoder())  # the sequence that failed: a second open while the first is alive
    assert cached(index) == [] and second.vectors.keys() == first.vectors.keys()
    first.client.close()  # callers' close stays a safe no-op


def test_failed_open_after_reading_chroma_leaves_no_cached_system(index):
    manifest = json.loads((index/'manifest.json').read_text(encoding='utf-8'))
    manifest['collection_chunks'] = {**manifest['collection_chunks'], 'faq': manifest['collection_chunks']['faq'] + 1}
    (index/'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    with pytest.raises(RetrievalIndexError, match='differ from the manifest'):
        Retriever(index, encoder=HashEncoder())
    assert cached(index) == []


def test_stale_index_refusal_leaves_no_cached_system(tmp_path):
    knowledge, index = tmp_path/'knowledge', tmp_path/'index'
    shutil.copytree(KNOWLEDGE_ROOT, knowledge, ignore=shutil.ignore_patterns('__pycache__'))
    build_index(index, encoder=HashEncoder(), knowledge_root=knowledge)
    opened = open_retriever(index, encoder=HashEncoder(), knowledge_root=knowledge)
    faq = knowledge/'faq/audio_multimodal_faq.md'
    faq.write_text(faq.read_text(encoding='utf-8') + '\nAn added sentence.\n', encoding='utf-8')
    with pytest.raises(StaleIndexError):
        open_retriever(index, encoder=HashEncoder(), knowledge_root=knowledge)
    assert cached(index) == [] and opened.vectors
