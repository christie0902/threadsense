"""Milestone 7 checks: absence statements, the recorded-link lookup (investigation only) and the scenario matrix."""
import json

import pytest

from threadsense.agents.advice_inputs import load_effective_view
from threadsense.agents.advisor_checks import _coverage_note, display_issues
from threadsense.agents.advisor_pilot import HANDOFF, PROMPT_VERSION, WRITING_GUIDE
from threadsense.retrieval.index import build_index
from threadsense.retrieval.related import related
from threadsense.retrieval.search import Retriever
from threadsense.routing import ROOT
from tests.retrieval_doubles import HashEncoder

MATRIX = json.loads((ROOT/'data/evaluation/agent3_demo_scenarios.json').read_text(encoding='utf-8'))


@pytest.mark.parametrize('text, flagged', [
    ('No later decision exists on the trial.', True),
    ('Such guidance does not exist.', True),
    ('The outcome is not in the knowledge store.', True),
    ('The records retrieved for this run do not show the trial outcome.', False),
    ('The task ID does not exist in the queue.', False),  # A reported fact, not a claim about the records.
])
def test_absence_statements_are_limited_to_what_the_run_retrieved(text, flagged):
    assert any(code == 'ABSENCE_OVERCLAIM' for code, _ in display_issues(text, [])) == flagged


def test_coverage_note_and_prompt_describe_this_runs_retrieval():
    note = _coverage_note('PRIOR_DECISIONS: found no new evidence')
    assert "this run's searches retrieved nothing further" in note and 'does not show no such record exists' in note
    assert PROMPT_VERSION == 'agent3-advisor-prompts-v7' and 'what this run retrieved' in WRITING_GUIDE


@pytest.fixture(scope='module')
def retriever(tmp_path_factory):
    index = tmp_path_factory.mktemp('related')/'index'
    build_index(index, encoder=HashEncoder())
    r = Retriever(index, encoder=HashEncoder())
    yield r
    r.client.close()


def test_related_lookup_adds_only_recorded_links_within_filters(retriever):
    filters = {'as_of': '2026-10-02T12:00:00Z', 'batch': 'audio_batch_06', 'version_mode': 'history',
               'document_types': ['decision']}
    search = retriever.search('approve a limited playback trial reload', 'audio_multimodal', top_k=1, **filters)
    assert [r['metadata']['authoring_document_id'] for r in search['results']] == ['audio-playback-trial-approval']
    added = related(retriever, search, 'audio_multimodal', limit=2, **filters)
    # The outcome record cites the approval (source_refs) and shares its event series; nothing else is linked.
    assert {(a['metadata']['authoring_document_id'], l['link']) for a in added['added'] for l in a['links']} == {
        ('audio-playback-trial-outcome', 'backward'), ('audio-playback-trial-outcome', 'series')}
    returned = {r['document_id'] for r in search['results']}
    assert len(added['added']) <= 2 and not returned & {a['document_id'] for a in added['added']}
    by_authoring = {r['metadata']['authoring_document_id']: r for r in search['results']}
    for a in added['added']:
        assert a['links']
        for link in a['links']:
            source = by_authoring[link['from']]['metadata']
            if link['link'] == 'series':
                assert a['metadata']['event_series_id'] == source['event_series_id']
            else:  # forward/backward: the recorded source_refs name the other document.
                refs = {r['document_id'] for r in retriever.document(a['document_id'], a['version_id'])['metadata']
                        ['source_metadata'].get('source_refs') or []}
                assert link['from'] in refs or link['link'] == 'forward'
    # The same filters apply: before the outcome record's effective date it cannot be added.
    early = {**filters, 'as_of': '2026-08-25T00:00:00Z'}
    search = retriever.search('approve a limited playback trial reload', 'audio_multimodal', top_k=1, **early)
    assert not any(a['metadata']['authoring_document_id'] == 'audio-playback-trial-outcome'
                   for a in related(retriever, search, 'audio_multimodal', limit=2, **early)['added'])


def test_scenario_matrix_matches_the_handoff():
    view = load_effective_view(HANDOFF)
    records = {r['candidate_group_id']: r for r in view['records']}
    cases = {s['demo_case'] for s in MATRIX['scenarios']}
    assert len(MATRIX['scenarios']) == 9 and len(cases) == 9
    for s in MATRIX['scenarios']:
        row = records[s['candidate_group_id']]
        members = (next(t for t in row['topics'] if t['topic_id'] == s['topic_id'])['member_ids'] if s['topic_id']
                   else row['unassigned_member_ids'])
        assert s['member_ids'] == members
        flagged = {o['member_id'] for o in row['inherited_review_obligations'] if o.get('member_id') in members}
        assert set(s['inherited_obligation_member_ids']) == flagged
        # Inherited flags are required review reasons; they are never removed to reach a Recommended Action.
        assert (s['required_review_reasons'] == ['INHERITED_FLAG']) == bool(flagged)
        assert s['acceptable_actions'] and s['expected_sources']
