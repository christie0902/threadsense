"""Integration: real local all-MiniLM-L6-v2 embeddings and persistent Chroma, offline.

Skipped (with the reason) when the pinned model is not in the local cache.
Reports measured quality; it does not require hybrid retrieval to win every case.
"""
import pytest

from threadsense.retrieval.config import EMBEDDING


@pytest.fixture(scope='module')
def real(tmp_path_factory):
    try:
        from threadsense.retrieval.embeddings import SentenceEncoder
        encoder = SentenceEncoder()
    except OSError as error:
        pytest.skip(f'Pinned embedding model not cached locally: {error}')
    from threadsense.retrieval.index import build_index
    from threadsense.retrieval.search import Retriever
    index = tmp_path_factory.mktemp('real')/'retrieval'
    manifest = build_index(index, encoder=encoder)
    return manifest, Retriever(index, encoder=encoder)


def test_real_index_records_embedding_identity(real):
    manifest, retriever = real
    assert manifest['embedding']['model'] == EMBEDDING['model'] and manifest['embedding']['revision'] == EMBEDDING['revision']
    assert manifest['embedding']['dimension'] == 384 and manifest['max_chunk_tokens'] <= manifest['embedding']['max_tokens']
    result = retriever.search('waveform loads but play never starts', 'audio_multimodal')['results'][0]
    assert -1.0 <= result['scores']['dense_cosine'] <= 1.0 and result['scores']['bm25_rank'] is not None


def test_real_evaluation_runs_and_respects_date_exclusions(real):
    from threadsense.retrieval.evaluate import evaluate
    report = evaluate(real[1])
    for name, summary in report['summary'].items():
        assert summary['must_exclude_violations'] == 0, name
        assert summary['answerable_cases'] == 9
    unsupported = next(c for c in report['cases'] if c['id'] == 'unsupported_payroll')
    assert unsupported['answerable'] is False and unsupported['variants']['hybrid_rrf_mmr']['recall'] is None
