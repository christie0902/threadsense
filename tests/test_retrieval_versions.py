"""Version-aware eligibility on synthetic revisions (temporary corpora, test-double encoder)."""
from pathlib import Path
import shutil

import pytest

from threadsense.retrieval.config import KNOWLEDGE_ROOT
from threadsense.retrieval.index import build_index
from threadsense.retrieval.search import Retriever
from tests.retrieval_doubles import HashEncoder

AUDIO = 'instructions/audio_multimodal_instructions.md'
LEGACY = 'Legacy step: press the purple reload lever twice before reporting a stuck player.'
PROJECT = 'audio_multimodal'


def revision(root, name, *, version, effective, status='approved', extra='', source=AUDIO):
    text = (KNOWLEDGE_ROOT/source).read_text(encoding='utf-8')
    for old, new in ((f"version: '1.3'", f"version: '{version}'"),
                     ("effective_at: '2026-09-15T13:00:00Z'", f"effective_at: '{effective}'"),
                     ('status: approved', f'status: {status}')):
        assert old in text
        text = text.replace(old, new, 1)
    path = root/'instructions/history'/name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.replace('## Playback and unavailable content\n', f'## Playback and unavailable content\n{extra}\n', 1)
                    if extra else text, encoding='utf-8')


def corpus(tmp_path, *revisions):
    root = tmp_path/'knowledge'
    shutil.copytree(KNOWLEDGE_ROOT, root, ignore=shutil.ignore_patterns('__pycache__'))
    for args, kwargs in revisions:
        revision(root, *args, **kwargs)
    index = tmp_path/'index'
    build_index(index, encoder=HashEncoder(), knowledge_root=root)
    return Retriever(index, encoder=HashEncoder())


def audio_versions(results):
    return [(r['metadata']['authoring_version'], r['version']['state']) for r in results
            if r['metadata']['authoring_document_id'] == 'audio-multimodal-instructions']


@pytest.fixture(scope='module')
def revised(tmp_path_factory):
    # 1.12 is numerically and lexically "larger" but older; 1.4 is future-effective; 1.5 is a draft.
    return corpus(tmp_path_factory.mktemp('revised'),
                  (('audio_v1.12.md',), {'version': '1.12', 'effective': '2026-09-01T13:00:00Z', 'extra': LEGACY}),
                  (('audio_v1.4.md',), {'version': '1.4', 'effective': '2026-10-15T13:00:00Z', 'extra': LEGACY}),
                  (('audio_v1.5.md',), {'version': '1.5', 'effective': '2026-09-20T13:00:00Z', 'status': 'draft', 'extra': LEGACY}))


def test_older_revision_that_matches_better_does_not_compete_in_current_mode(revised):
    response = revised.search('purple reload lever twice', PROJECT, top_k=20, use_mmr=False)
    assert audio_versions(response['results']) and set(audio_versions(response['results'])) == {('1.3', 'CURRENT')}
    withheld = {(w['citation']['authoring'], w['state']) for w in response['withheld_by_version']}
    assert ('audio-multimodal-instructions@1.12', 'SUPERSEDED_REVISION') in withheld
    assert ('audio-multimodal-instructions@1.5', 'NOT_APPROVED') in withheld
    current = next(r for r in response['results'] if r['metadata']['authoring_version'] == '1.3')
    others = {o['authoring_version']: o['state'] for o in current['version']['other_revisions']}
    assert others == {'1.12': 'SUPERSEDED_REVISION', '1.4': 'NOT_YET_EFFECTIVE', '1.5': 'NOT_APPROVED'}


def test_history_mode_keeps_every_revision_marked(revised):
    response = revised.search('purple reload lever twice', PROJECT, top_k=60, candidate_k=200, use_mmr=False, version_mode='history')
    states = dict(audio_versions(response['results']))
    assert states['1.12'] == 'SUPERSEDED_REVISION' and states['1.3'] == 'CURRENT'
    assert states['1.5'] == 'NOT_APPROVED' and states['1.4'] == 'NOT_YET_EFFECTIVE'
    older = next(r for r in response['results'] if r['metadata']['authoring_version'] == '1.12')
    assert older['citation']['authoring'] == 'audio-multimodal-instructions@1.12' and LEGACY in older['text']
    assert response['withheld_by_version'] == []


def test_future_effective_revision_waits_for_its_date(revised):
    now = revised.search('purple reload lever', PROJECT, top_k=40, use_mmr=False)
    assert 'FUTURE_EFFECTIVE_REVISION' in {d['kind'] for d in now['version_diagnostics']}
    later = revised.select(PROJECT, as_of='2026-10-20T00:00:00Z')
    versions = {revised.chunks[k]['metadata']['authoring_version'] for k in later['eligible']
                if revised.chunks[k]['metadata']['authoring_document_id'] == 'audio-multimodal-instructions'}
    assert versions == {'1.4'}


def test_tied_or_undated_ordering_is_reported_not_resolved(tmp_path):
    retriever = corpus(tmp_path, (('audio_tie.md',), {'version': '1.3b', 'effective': '2026-09-15T13:00:00Z', 'extra': LEGACY}))
    response = retriever.search('purple reload lever', PROJECT, top_k=40, candidate_k=200, use_mmr=False)
    assert {state for _, state in audio_versions(response['results'])} == {'UNRESOLVED'}
    assert {v for v, _ in audio_versions(response['results'])} == {'1.3', '1.3b'}
    diagnostic = next(d for d in response['version_diagnostics'] if d['kind'] == 'TIED_REVISION_DATES')
    assert {r['authoring_version'] for r in diagnostic['revisions']} == {'1.3', '1.3b'}
    assert all(r['version']['applicability'] == 'UNRESOLVED' for r in response['results']
               if r['metadata']['authoring_document_id'] == 'audio-multimodal-instructions')


def test_conflicting_contents_for_one_authoring_version_still_fail_the_build(tmp_path):
    root = tmp_path/'knowledge'
    shutil.copytree(KNOWLEDGE_ROOT, root, ignore=shutil.ignore_patterns('__pycache__'))
    revision(root, 'audio_conflict.md', version='1.3', effective='2026-09-15T13:00:00Z', extra=LEGACY)
    with pytest.raises(ValueError, match='audio-multimodal-instructions@1.3'):
        build_index(tmp_path/'index', encoder=HashEncoder(), knowledge_root=root)


@pytest.fixture(scope='module')
def real_corpus(tmp_path_factory):
    index = tmp_path_factory.mktemp('plain')/'index'
    build_index(index, encoder=HashEncoder())
    return Retriever(index, encoder=HashEncoder())


def test_section_only_supersession(real_corpus):
    help_page = {k: c for k, c in real_corpus.chunks.items() if c['metadata']['authoring_document_id'] == 'safety-qn-help-page'}
    current = real_corpus.select('safety_classification')
    kept = {tuple(help_page[k]['sections']) for k in current['eligible'] if k in help_page}
    assert kept == {('Other safety concerns',)}
    [withheld] = [w for w in current['withheld'] if w['citation']['authoring'] == 'safety-qn-help-page@1.0']
    assert withheld['state'] == 'SECTION_SUPERSEDED' and withheld['sections'] == ['Contact details']
    assert withheld['section_superseded_by'][0]['superseding']['authoring'] == 'safety-fictional-pii-clarification@1.0'
    clarification = next(v for k, v in current['eligible'].items()
                         if real_corpus.chunks[k]['metadata']['authoring_document_id'] == 'safety-fictional-pii-clarification')
    assert clarification['version']['supersedes'][0]['section'] == 'Contact details'
    history = real_corpus.select('safety_classification', version_mode='history')['eligible']
    marked = {tuple(help_page[k]['sections']): history[k]['version']['applicability'] for k in history if k in help_page}
    assert marked == {('Contact details',): 'SECTION_SUPERSEDED', ('Other safety concerns',): 'CURRENT'}


def test_supersession_before_the_replacement_is_effective_is_not_applied(real_corpus):
    early = real_corpus.select('safety_classification', as_of='2026-09-05T00:00:00Z')
    sections = {tuple(real_corpus.chunks[k]['sections']) for k in early['eligible']
                if real_corpus.chunks[k]['metadata']['authoring_document_id'] == 'safety-qn-help-page'}
    assert ('Contact details',) in sections
    assert any(d['kind'] == 'UNVERIFIED_SUPERSESSION' and d['reason'] == 'SUPERSEDING_SOURCE_NOT_YET_EFFECTIVE'
               for d in early['diagnostics'])


def test_eligibility_precedes_both_ranking_paths(revised):
    for mode in ('dense', 'bm25', 'hybrid'):
        response = revised.search('purple reload lever twice', PROJECT, mode=mode, top_k=200, candidate_k=200, use_mmr=False)
        assert all(r['metadata']['authoring_version'] != '1.12' for r in response['results'])
