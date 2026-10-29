"""Structural retrieval tests: test-double encoder, real local Chroma in temporary directories."""
from copy import deepcopy
import json
from pathlib import Path
import shutil

import pytest

from threadsense.retrieval.bm25 import BM25, tokenize
from threadsense.retrieval.chunking import chunk_document
from threadsense.retrieval.config import FIXTURE_CUTOFF, FIXTURE_ROOT, KNOWLEDGE_ROOT
from threadsense.retrieval.corpus import collect
from threadsense.retrieval.index import RetrievalIndexError, build_index, plan
from threadsense.retrieval.search import Retriever, mmr, rrf
from threadsense.retrieval.versions import VersionIndex
from tests.retrieval_doubles import HashEncoder

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope='module')
def built(tmp_path_factory):
    index = tmp_path_factory.mktemp('index')/'retrieval'
    manifest = build_index(index, encoder=HashEncoder())
    return index, manifest


@pytest.fixture(scope='module')
def retriever(built):
    return Retriever(built[0], encoder=HashEncoder())


def labels(response):
    return [(r['metadata']['authoring_document_id'] or r['metadata']['thread_id'], r['sections']) for r in response['results']]


def sources_snapshot():
    roots = [KNOWLEDGE_ROOT, FIXTURE_ROOT]
    return {p: p.stat().st_mtime_ns for root in roots for p in root.rglob('*') if p.is_file()}


def test_corpus_counts_are_derived_and_current_day_announcements_come_from_extraction():
    documents, report = collect(KNOWLEDGE_ROOT, FIXTURE_ROOT, FIXTURE_CUTOFF)
    receipt = report['current_day_announcements']
    assert report['knowledge_documents'] == report['shared_iterator_documents']
    assert report['documents'] == report['knowledge_documents'] + receipt['extracted'] - len(report['duplicates_removed'])
    assert receipt['announcement_threads'] == receipt['extracted'] and not receipt['extraction_failures']
    current = [d for d in documents if d['origin'] == 'current_day_extraction']
    assert all(d['metadata']['extraction_window']['cutoff'].startswith('2026-10-02T12:00:00') for d in current)
    # Historical archive posts are authored knowledge, not current-day announcements.
    archive = [d for d in documents if d['origin'] == 'knowledge_store' and d['metadata']['source']['system'] == 'slack']
    assert archive and all(d['metadata']['created_at'] < '2026-10-01' for d in archive)
    flagged = [d for d in current if (d['metadata']['inherited_agent1'] or {}).get('agent1_record', {}).get('review_required')]
    assert flagged, 'inherited Agent 1 review metadata should travel with extracted announcements'


def test_chunks_fit_limit_never_truncate_and_keep_decision_context():
    documents, _ = collect(KNOWLEDGE_ROOT, FIXTURE_ROOT, FIXTURE_CUTOFF)
    encoder = HashEncoder(max_tokens=80)
    for document in documents:
        chunks = chunk_document(document, encoder.count, encoder.max_tokens)
        assert all(c['token_count'] <= 80 for c in chunks)
        words = ' '.join(document['text'].split()).split()
        # A title-only preamble lives in each chunk's header, so check the indexed text.
        joined = ' '.join(' '.join(c['indexed_text'] for c in chunks).split())
        assert all(w in joined for w in words), document['document_id']
        if chunks[0]['collection'] == 'decisions' and len(chunks) > 1 and chunks[0]['metadata']['decision_status']:
            assert all(f"decision status: {chunks[0]['metadata']['decision_status']}" in c['indexed_text'] for c in chunks)
    guide = next(d for d in documents if d['metadata']['source_metadata'].get('authoring', {}).get('document_id') == 'audio-multimodal-instructions')
    sections = [c['sections'] for c in chunk_document(guide, encoder.count, 256)]
    assert ['Playback and unavailable content'] in sections and all(len(s) == 1 for s in sections)


def test_chunk_ids_are_deterministic_and_path_independent(tmp_path):
    copy = tmp_path/'elsewhere/knowledge'
    shutil.copytree(KNOWLEDGE_ROOT, copy, ignore=shutil.ignore_patterns('__pycache__'))
    first, *_ = plan(HashEncoder())
    moved, *_ = plan(HashEncoder(), knowledge_root=copy)
    assert [c['chunk_id'] for c in first] == [c['chunk_id'] for c in moved]
    assert [c['chunk_id'] for c in first] == [c['chunk_id'] for c in plan(HashEncoder())[0]]


def test_bm25_rrf_and_mmr_mechanics():
    bm25 = BM25({'a': 'quarantine QN rule', 'b': 'tie calibration', 'c': 'QN QN QN'})
    assert tokenize('The QN and the LT') == ['qn', 'lt']
    assert set(bm25.scores('QN', ['a', 'b', 'c'])) == {'a', 'c'} and bm25.scores('QN', ['b']) == {}
    fused = rrf([['x', 'y'], ['y', 'z']], 60)
    assert fused['y'] == pytest.approx(1 / 62 + 1 / 61) and fused['x'] == pytest.approx(1 / 61)
    vectors = {'x': [1, 0], 'y': [1, 0], 'z': [0, 1]}
    assert mmr(['x', 'y', 'z'], {'x': 1, 'y': 0.9, 'z': 0.5}, vectors, top_k=3, lam=1.0)[0] == ['x', 'y', 'z']
    assert mmr(['x', 'y', 'z'], {'x': 1, 'y': 0.9, 'z': 0.5}, vectors, top_k=2, lam=0.5)[0] == ['x', 'z']
    assert mmr(['y', 'x'], {'x': 1, 'y': 1}, {'x': [1, 0], 'y': [0, 1]}, top_k=2, lam=0.65)[0] == ['y', 'x']


def test_build_is_idempotent_and_detects_stale_or_tampered_indexes(built, tmp_path):
    index, manifest = built
    assert manifest['status'] == 'BUILT' and manifest['chunks'] == sum(manifest['collection_chunks'].values())
    before = {p: p.stat().st_mtime_ns for p in index.rglob('*') if p.is_file()}
    assert build_index(index, encoder=HashEncoder())['status'] == 'UP_TO_DATE'
    assert {p: p.stat().st_mtime_ns for p in index.rglob('*') if p.is_file()} == before
    copy = tmp_path/'index'
    shutil.copytree(index, copy)
    with pytest.raises(RetrievalIndexError, match='--rebuild'):
        build_index(copy, encoder=HashEncoder(max_tokens=100))
    rebuilt = build_index(copy, encoder=HashEncoder(max_tokens=100), rebuild=True)
    assert rebuilt['status'] == 'BUILT' and sum(rebuilt['collection_chunks'].values()) == rebuilt['chunks']
    again = build_index(copy, encoder=HashEncoder(max_tokens=100), rebuild=True)
    assert again['status'] == 'UP_TO_DATE' and again['collection_chunks'] == rebuilt['collection_chunks']
    (copy/'chunks.json').write_text('[]', encoding='utf-8')
    with pytest.raises(RetrievalIndexError, match='chunks.json'):
        Retriever(copy, encoder=HashEncoder())
    (copy/'manifest.json').unlink()
    with pytest.raises(RetrievalIndexError, match='No complete index'):
        Retriever(copy, encoder=HashEncoder())


def test_incompatible_embedding_configuration_is_refused(built, tmp_path):
    copy = tmp_path/'index'
    shutil.copytree(built[0], copy)
    manifest = json.loads((copy/'manifest.json').read_text(encoding='utf-8'))
    manifest['embedding']['model'] = 'some/other-model'
    (copy/'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    with pytest.raises(RetrievalIndexError, match='embedding'):
        Retriever(copy, encoder=HashEncoder())


def test_filters_select_before_both_paths_and_isolate_projects(retriever):
    eligible = retriever.eligible('audio_multimodal')
    assert eligible and all(retriever.chunks[k]['metadata']['project_id'] == 'audio_multimodal' for k in eligible)
    response = retriever.search('playback waveform tool incident', 'audio_multimodal', top_k=50, use_mmr=False, candidate_k=5)
    assert response['dense_candidates'] == 5 and response['bm25_candidates'] <= 5
    assert {r['chunk_id'] for r in response['results']} <= set(eligible)
    assert all(r['metadata']['project_id'] == 'audio_multimodal' for r in response['results'])
    assert retriever.eligible('no_such_project') == {}


def test_shared_scope_requires_explicit_request(retriever):
    chunks = deepcopy(retriever.chunks)
    try:
        key = next(iter(retriever.chunks))
        retriever.chunks[key]['metadata'].update(scope='shared', project_id='cross_project')
        retriever.versions = VersionIndex(retriever.chunks)  # Lineages include scope.
        assert key not in retriever.eligible('audio_multimodal')
        assert key in retriever.eligible('audio_multimodal', include_shared=True)
    finally:
        retriever.chunks.clear()
        retriever.chunks.update(chunks)
        retriever.versions = VersionIndex(retriever.chunks)


def test_earlier_batches_stay_available_and_marked(retriever):
    project = retriever.search('Korean honorific register quoted speech', 'multilingual_eval', batch='multi_batch_11', top_k=30, use_mmr=False)
    relations = {r['metadata']['authoring_document_id']: r['batch_relation'] for r in project['results']}
    assert relations.get('multi-korean-scoped-result') == 'other_batch'
    assert relations.get('multilingual-eval-instructions') == 'project_wide'
    strict = retriever.eligible('multilingual_eval', batch='multi_batch_11', batch_scope='strict')
    assert all(retriever.chunks[k]['metadata']['batch_id'] in (None, 'multi_batch_11') for k in strict)
    assert len(strict) < len(retriever.eligible('multilingual_eval', batch='multi_batch_11'))


def test_as_of_uses_source_dates_and_keeps_undated_explicit(retriever):
    announcement = [k for k, c in retriever.chunks.items() if c['metadata']['thread_id'] == '1790892000.000901']
    assert announcement
    assert announcement[0] in retriever.eligible('audio_multimodal', as_of='2026-10-01T23:06:52Z')
    assert announcement[0] not in retriever.eligible('audio_multimodal', as_of='2026-10-01T21:59:59Z')
    trial = next(k for k, c in retriever.chunks.items() if c['metadata']['authoring_document_id'] == 'audio-playback-trial-approval')
    assert retriever.eligible('audio_multimodal', as_of='2026-10-02T12:00:00Z')[trial]['expired_as_of'] is True
    original = retriever.chunks[trial]['metadata']['source_date']
    try:
        retriever.chunks[trial]['metadata']['source_date'] = None
        assert retriever.eligible('audio_multimodal', as_of='2026-10-02T12:00:00Z')[trial]['date_status'] == 'MISSING_SOURCE_DATE'
        assert trial not in retriever.eligible('audio_multimodal', as_of='2026-10-02T12:00:00Z', include_undated=False)
    finally:
        retriever.chunks[trial]['metadata']['source_date'] = original


def test_rejected_deferred_and_superseded_material_is_kept_with_provenance(retriever):
    statuses = {retriever.chunks[k]['metadata']['decision_status'] for k in retriever.eligible('multilingual_eval')}
    assert {'tl_deferred', 'tl_approved'} <= statuses
    only = retriever.eligible('response_preference', statuses=['tl_rejected'])
    assert only and all(retriever.chunks[k]['metadata']['decision_status'] == 'tl_rejected' for k in only)
    response = retriever.search('quarantine any task containing a phone number', 'safety_classification',
                                top_k=200, candidate_k=200, use_mmr=False, version_mode='history')
    help_page = [r for r in response['results'] if r['metadata']['authoring_document_id'] == 'safety-qn-help-page']
    contact = next(r for r in help_page if 'Contact details' in r['sections'])
    other = next(r for r in help_page if 'Other safety concerns' in r['sections'])
    assert contact['supersession']['chunk_superseded_by'][0]['document_id'] == 'safety-fictional-pii-clarification'
    assert other['supersession']['chunk_superseded_by'] == []
    assert contact['metadata']['status'] == 'partially_superseded' and contact['citation']['authoring'] == 'safety-qn-help-page@1.0'
    assert contact['version']['applicability'] == 'SECTION_SUPERSEDED' and other['version']['applicability'] == 'CURRENT'
    result = response['results'][0]
    for key in ('document_id', 'version_id', 'chunk_id', 'citation', 'metadata', 'scores', 'rank'):
        assert key in result
    assert result['evidence_only'] and 'rrf_score' in result['scores'] and result['citation']['source']


def test_identical_evidence_collapses_only_with_matching_metadata(retriever):
    keys = sorted(retriever.eligible('response_preference', record_kinds=['advice_review']))
    first, second = keys[0], keys[1]
    saved = deepcopy(retriever.chunks[second])
    query = retriever.chunks[first]['text'][:200]
    try:
        # Same words, different date/authority/decision state: both stay as separate evidence.
        retriever.chunks[second]['text'] = retriever.chunks[first]['text']
        returned = {r['chunk_id'] for r in retriever.search(query, 'response_preference', top_k=60, candidate_k=200, use_mmr=False)['results']}
        assert {first, second} <= returned
        # Same words and same relevant metadata: one displayed result keeping both provenances.
        retriever.chunks[second]['metadata'] = deepcopy(retriever.chunks[first]['metadata'])
        response = retriever.search(query, 'response_preference', top_k=60, candidate_k=200, use_mmr=False)
        assert len({r['chunk_id'] for r in response['results']} & {first, second}) == 1
        shared = next(r for r in response['results'] if r['chunk_id'] in {first, second})
        [kept] = shared['duplicate_sources']
        assert kept['chunk_id'] in {first, second} and kept['citation'] and kept['metadata']['decision_status']
    finally:
        retriever.chunks[second] = saved
    approval = retriever.search('tie calibration approved follow-up outcome', 'response_preference', top_k=30, use_mmr=False)
    kinds = {r['metadata']['authoring_document_id'] for r in approval['results']}
    assert {'rp-tie-calibration-approval', 'rp-tie-calibration-outcome'} <= kinds


def test_queries_are_read_only(built):
    index = built[0]
    sources, files = sources_snapshot(), {p: p.read_bytes() for p in index.glob('*.json')}
    retriever = Retriever(index, encoder=HashEncoder())
    retriever.search('submit button disabled', 'response_preference')
    retriever.search('fictional phone number', 'safety_classification', as_of='2026-09-30T00:00:00Z')
    assert sources_snapshot() == sources
    assert {p: p.read_bytes() for p in index.glob('*.json')} == files
    assert retriever.staleness() == 'CURRENT'
