"""Question uncertainty and effective research input; no live semantic claims."""
import json
from copy import deepcopy

import pytest

# Historical semantic-contract regressions; active taxonomy has separate coverage.
pytestmark = pytest.mark.usefixtures("legacy_agent2_v6")

from threadsense.legacy.agent2.topic_consolidation_v6 import build_request, parse_response, export_result
from threadsense.agents.topic_effective import load_effective_output, research_handoff
from threadsense.legacy.agent2.topic_evidence import evidence_catalog
from threadsense.agents.topic_requests import COMPARISON_MODEL, provider_schema
from threadsense.handoff_inputs import ROOT, read_json, file_hash
from threadsense.terminology import get_terms
from tests.agent2_inventory_fixtures import GIDS, payload
from tests.agent2_structured_fixtures import reviewed_draft

RUN = ROOT/'data/processed/agent2_contrastive_v5_3'


def test_saved_audio_answered_quarantine_question_remains_researchable_with_guidance_and_flags():
    before = file_hash(RUN/'consolidations.json')
    view = load_effective_output(RUN)
    row = next(r for r in view['records'] if r['candidate_group_id'] == GIDS[1])
    handoff = row['research_handoff']
    q = next(q for q in handoff['questions'] if q['original_question']['evidence_id'] == 'E014')
    assert 'should I QN' in q['original_question']['text']
    assert q['model_resolution']['status'] == 'ANSWERED' and q['research_required']
    assert q['model_resolution']['resolution_confidence'] is None
    assert q['model_resolution']['uncertainty_note'] is None
    assert q['effective_content_review_status'] == 'DISPUTED'
    assert any('Report the playback incident' in g['text'] for g in q['relevant_guidance'])
    assert sum(o.get('origin') == 'agent1' for o in handoff['review_obligations']) == 2
    assert any(o.get('assessment', {}).get('level') == 'HIGH' for o in handoff['review_obligations'])
    assert handoff['members'] == row['members'] and handoff['nonblocking']
    assert len(handoff['questions']) == sum(i['kind'] == 'QUESTION' for t in row['topics'] for i in t['inventory'])
    assert file_hash(RUN/'consolidations.json') == before


def test_saved_context_as_answer_is_effectively_provisional_and_original_is_inspectable():
    row = next(r for r in load_effective_output(RUN)['records'] if r['candidate_group_id'] == 'cluster_f944891544b06f79')
    topic = row['research_handoff']['topics'][0]
    assert not topic['supported_answers']
    context = next(i for i in topic['inventory'] if i['evidence_id'] == 'E002')
    assert context['kind'] == 'ANSWER' and context['answer_status'] == 'TENTATIVE'
    assert context['reliability'] == 'PROVISIONAL'  # Preserve raw mistake, never promote it.
    assert row['content_review_obligations']
    assert all(q['model_resolution']['resolution_confidence'] is None for q in row['research_handoff']['questions'])


def test_v6_wire_fields_are_required_and_policy_reaches_model(monkeypatch):
    monkeypatch.setenv('THREADSENSE_AGENT2_REASONING_EFFORT', 'low')
    request = build_request(payload(GIDS[0]), get_terms(), COMPARISON_MODEL)
    q = provider_schema()['$defs']['QuestionState']
    assert set(q['required']) == {'status', 'answer_item_ids', 'resolution_confidence', 'uncertainty_note'}
    system = request['messages'][0]['content']
    for phrase in ('uncalibrated self-assessment', 'most plausible supported', 'that label must not hide',
                   'Unsupported', 'question\'s own member conversation'):
        assert phrase.lower() in system.lower()
    assert not {'temperature', 'top_p', 'logprobs'} & request.keys()
    assert request['reasoning_effort'] == 'low' and request['max_completion_tokens'] == 8192
    assert all(x not in json.dumps(request) for x in ('review_supplement', 'source_review_findings', 'expected_verdict'))


@pytest.mark.parametrize('mutation', ['missing', 'out_of_range', 'invalid_id', 'cross_member'])
def test_question_uncertainty_is_strict_and_source_bound(mutation):
    p = payload(GIDS[1]); draft = reviewed_draft(GIDS[1])
    qitem = next(i for t in draft['topics'] for i in t['inventory'] if i['kind'] == 'QUESTION')
    q = qitem['question']
    if mutation == 'missing':
        q.pop('resolution_confidence')
    elif mutation == 'out_of_range':
        q['resolution_confidence'] = 1.1
    else:
        _, catalog = evidence_catalog(p)
        eid = 'MISSING' if mutation == 'invalid_id' else next(e for e in catalog if catalog[e]['member_id'] != catalog[qitem['evidence_id']]['member_id'])
        q['uncertainty_note'] = {'text': 'Synthetic unresolved scope.', 'evidence_ids': [eid]}
    with pytest.raises(ValueError):
        parse_response(p, json.dumps(draft))


def test_high_confidence_does_not_clear_dispute_and_answered_note_remains_visible():
    row = deepcopy(next(r for r in load_effective_output(RUN)['records'] if r['candidate_group_id'] == GIDS[1]))
    q = next(i for t in row['topics'] for i in t['inventory'] if i['evidence_id'] == 'E014' and i['kind'] == 'QUESTION')
    # Synthetic score in a copy ONLY; never attach a fabricated score to saved output.
    q['question'].update(resolution_confidence=.99, uncertainty_note={'text': 'Synthetic remaining handling choice.', 'evidence_ids': ['E014']})
    handoff = research_handoff(row)
    projected = next(q for q in handoff['questions'] if q['original_question']['evidence_id'] == 'E014')
    assert projected['model_resolution']['resolution_confidence'] == .99
    assert projected['effective_content_review_status'] == 'DISPUTED' and projected['research_required']
    assert handoff['review_obligations'] == row['review_obligations']
    assert handoff['topics'] == row['topics']  # Severity and raw status unchanged.


def test_old_response_requires_explicit_replay_and_does_not_invent_confidence():
    d = RUN/'records'/GIDS[1]; p = read_json(d/'input.json'); raw = (d/'analysis.raw.txt').read_text(encoding='utf-8')
    with pytest.raises(ValueError, match='resolution_confidence'):
        parse_response(p, raw)
    historical = parse_response(p, raw, response_schema_version=5)
    assert all('resolution_confidence' not in i.question.model_dump() for t in historical.topics for i in t.inventory if i.question)


def test_failed_group_research_handoff_retains_sources_and_obligations():
    row = export_result(payload(GIDS[1]), state='FAILED', error='Synthetic recoverable failure')
    row.update(review_obligations=deepcopy(row['inherited_review_obligations']), effective_content_review_status='NO_APPLICABLE_CONTENT_FINDING')
    handoff = research_handoff(row)
    assert handoff['questions'] == [] and len(handoff['review_obligations']) == 2
    assert handoff['members'] == row['members'] and handoff['processing_state'] == 'FAILED'
    assert not handoff['semantic_question_coverage_guaranteed']
