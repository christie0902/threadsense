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


def test_real_chunks_fit_the_tokenizer_without_truncation(real):
    from threadsense.retrieval.config import FIXTURE_CUTOFF, FIXTURE_ROOT, KNOWLEDGE_ROOT
    from threadsense.retrieval.corpus import collect
    from tests.retrieval_doubles import check_chunks
    retriever = real[1]
    model = retriever.encoder.model
    tokenizer, limit = model.tokenizer, model.max_seq_length
    assert limit == real[0]['embedding']['max_tokens'] == 256
    assert retriever.encoder.count('') == 2  # [CLS] and [SEP] are counted.
    for chunk in retriever.chunks.values():
        ids = tokenizer(chunk['indexed_text'], add_special_tokens=True, truncation=False)['input_ids']
        assert len(ids) == chunk['token_count'] <= limit, chunk['chunk_id']
        # What the model actually embeds after its own truncation is the whole chunk.
        assert tokenizer(chunk['indexed_text'], truncation=True, max_length=limit)['input_ids'] == ids
    documents, _ = collect(KNOWLEDGE_ROOT, FIXTURE_ROOT, FIXTURE_CUTOFF)
    by_document = {}
    for chunk in sorted(retriever.chunks.values(), key=lambda c: c['chunk_index']):
        by_document.setdefault((chunk['document_id'], chunk['version_id']), []).append(chunk)
    assert len(by_document) == len(documents) == real[0]['documents']
    for document in documents:
        check_chunks(document, by_document[(document['document_id'], document['version_id'])], limit)


def test_stored_real_vectors_match_an_independent_encoding(real):
    from sentence_transformers import SentenceTransformer
    from tests.retrieval_doubles import check_stored, read_chroma
    manifest, retriever = real
    stored = read_chroma(retriever.index_dir/'chroma')
    chunks = list(retriever.chunks.values())
    check_stored(chunks, stored, 384)
    # One per collection plus split, superseded and table-bearing chunks.
    picks = {next(c['chunk_id'] for c in chunks if c['collection'] == name) for name in ('guidelines', 'faq', 'decisions')}
    picks |= {next(c['chunk_id'] for c in chunks if c['chunk_count'] > 2 and c['collection'] == 'decisions'),
              next(c['chunk_id'] for c in chunks if c['supersession']['chunk_superseded_by']),
              next(c['chunk_id'] for c in chunks if '| --- |' in c['text'])}
    model = SentenceTransformer(EMBEDDING['model'], revision=EMBEDDING['revision'], device='cpu', local_files_only=True)
    fresh = model.encode([retriever.chunks[k]['indexed_text'] for k in sorted(picks)], normalize_embeddings=True)
    for key, vector in zip(sorted(picks), fresh):
        saved = stored[key][1]
        assert max(abs(a - float(b)) for a, b in zip(saved, vector)) < 1e-5, key
        assert sum(a * float(b) for a, b in zip(saved, vector)) > 0.99999, key


def test_real_faq_chunks_keep_questions_with_answers(real):
    question = '### Q: Do fake phone numbers or emails in a story require QN?'
    faq = [c for c in real[1].chunks.values() if c['metadata']['authoring_document_id'] == 'safety-classification-faq']
    answer = [c for c in faq if 'SC-PII-2026-09-10' in c['text']]
    assert answer and all(question in c['text'].split('\n') for c in answer)
