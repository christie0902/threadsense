"""ToT candidate linkage and mechanical selection rules (PREPARED judgments; DETERMINISTIC controller). These check how
candidate identity carries from the comparison to the card, and that the selection boundary is explicit: replacement
needs the comparison's REPLACE_INCUMBENT decision, a close call never names a preferred candidate, and the withheld
incumbent cannot come back through the fallback under its second verdict. They say nothing about live model quality."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from threadsense.agents import advisor_tot
from threadsense.agents.advisor_contracts import ActionProposal
from tests.test_agent3_advisor import Fake, retriever, run, supported, view  # noqa: F401 - fixtures reused
from tests.test_agent3_corrections import fallback_draft
from tests.test_agent3_tot_v3 import SCENARIO, candidate, choice_draft, comparison, guide_of, members

ROOT = Path(__file__).resolve().parents[1]
NSFW = ROOT/'data/experiments/threadsense_full_v1/stages/agent3/overnight_run/topics/topic__cluster_44314b0d10532bdb__topic_1.json'


def kept_incumbent(payload):
    """v3: the draft's action verbatim as the preferred incumbent (KEEP_INCUMBENT), plus an observation candidate."""
    guide = payload['draft']['claims'][1]['evidence_ids']
    inc = payload['incumbent']
    return {'candidates': [candidate('INC', inc['action_type'], guide, inc['draft_text'], incumbent=True,
                                     need_ids=inc['intervention_need']['evidence_ids']),
                           candidate('WAIT', 'NO_ACTION', guide, 'Wait for the team lead.')],
            'preferred_candidate_id': 'INC', 'close_call': False, 'decision': 'KEEP_INCUMBENT',
            'rationale': 'The draft action fits.'}


def test_a_withheld_incumbent_does_not_return_through_the_fallback(retriever, view):
    """The kept incumbent is also judged as alternative:INC (the same text). When the action is withheld (its essential
    premise c3 was rejected) the fallback must not re-admit that same text from its second verdict."""
    result = run('audio_playback', Fake(draft=fallback_draft, tot=kept_incumbent,
                                        grounding=lambda p: supported(p, essential=['claim:c2', 'claim:c3'])), retriever, view)
    verdicts = {s['statement_id']: s['verdict'] for s in result['grounding']['statements']}
    assert verdicts['action'] == 'ESSENTIAL_PREMISE_NOT_PASSED' and verdicts['alternative:INC'] == 'SUPPORTED'
    assert result['card']['recommended_action'] is None and result['action_source'] == 'DRAFT'
    assert any(n.startswith('No ToT fallback: preferred candidate INC is the incumbent') for n in result['action_notes'])
    assert result['tot']['card_action'] == {'candidate_id': None, 'basis': 'NO_CARD_ACTION'}


def test_a_v3_comparison_without_a_decision_keeps_the_incumbent(retriever, view):
    """v3 asks for an explicit decision; a preferred candidate alone (decision missing) does not replace the action."""
    def tot(payload):
        value = comparison(payload, 'B', [candidate('B', 'NO_ACTION', [guide_of(payload)] + members(payload)[:1], 'Keep observing.')])
        return {**value, 'decision': None}
    result = run(SCENARIO, Fake(draft=choice_draft, tot=tot, grounding=supported), retriever, view)
    assert result['action_source'] == 'DRAFT' and 'selected_candidate_id' not in result['tot']
    assert result['card']['recommended_action']['draft_text'] == 'Reminder: report the task ID and browser state.'
    assert result['action_notes'] == ['ToT stated no decision (comparison v3 requires one); the draft action is kept.']
    assert result['tot']['card_action'] == {'candidate_id': 'INC', 'basis': 'INCUMBENT'}


def test_a_replace_decision_that_names_the_incumbent_keeps_it_and_says_why(retriever, view):
    def tot(payload):
        return comparison(payload, 'INC', [candidate('B', 'NO_ACTION', [guide_of(payload)], 'Keep observing.')],
                          decision='REPLACE_INCUMBENT')
    result = run(SCENARIO, Fake(draft=choice_draft, tot=tot, grounding=supported), retriever, view)
    assert result['action_source'] == 'DRAFT'
    assert result['action_notes'] == ['ToT decision REPLACE_INCUMBENT names no other candidate; the draft action is kept.']


def test_a_replacement_links_the_card_action_to_the_selected_candidate(retriever, view):
    text = 'Playback fails for several tasks; please investigate.'

    def tot(payload):
        return comparison(payload, 'B', [candidate('B', 'ESCALATE_ENGINEERING', [guide_of(payload)] + members(payload)[:1], text,
                                                   need_ids=members(payload)[:1])])
    result = run(SCENARIO, Fake(draft=choice_draft, tot=tot, grounding=supported), retriever, view)
    assert result['action_source'] == 'TOT' and result['card']['recommended_action']['draft_text'] == text
    assert result['tot']['card_action'] == {'candidate_id': 'B', 'basis': 'SELECTED'}
    displaced = next(c for c in result['tot']['candidates'] if c['candidate_id'] == 'INC')
    assert displaced['grounding'] == 'SUPPORTED'  # The displaced incumbent keeps its own ID and verdict.


def test_a_close_call_never_reports_a_preferred_candidate():
    """finalize (new runs) and the dashboard label (saved runs, including legacy records that kept a preferred ID)."""
    from threadsense.dashboard.runs import Run
    tot = {'status': 'COMPARED', 'close_call': True, 'decision': None, 'model_preferred_candidate_id': 'A',
           'candidates': [{'candidate_id': 'A', 'action_type': 'POST_ALIGNMENT', 'valid': True, 'issues': []},
                          {'candidate_id': 'B', 'action_type': 'NO_ACTION', 'valid': True, 'issues': []}]}
    grounding = {'statements': [{'statement_id': 'alternative:A', 'verdict': 'SUPPORTED'},
                                {'statement_id': 'alternative:B', 'verdict': 'SUPPORTED'}]}
    final = advisor_tot.finalize(tot, grounding)
    assert final['preferred_candidate_id'] is None and final['presentation'] == 'SURFACE_GROUNDED_ALTERNATIVES'
    saved = {**final, 'preferred_candidate_id': 'A',  # as recorded before this rule
             'candidates': [{**final['candidates'][0], 'draft_text': 'Post it.'}],
             'choice_after_grounding': {'status': 'RESOLVED_BY_GROUNDING', 'viable': []}}
    sid = 'alternative:A'
    stub = SimpleNamespace(topics={'c': {'result': {'tot': saved, 'grounding': {
        'statements': [{'statement_id': sid, 'verdict': 'SUPPORTED'}],
        'alternative_sufficiency': {sid: {'check': 'SUPPORTED', 'verdict': 'SUFFICIENT'}}}}}},
        cards={'c': {'recommended_action': {'draft_text': 'Something else.', 'action_type': 'NO_ACTION'}}})
    [shown] = Run.alternatives(stub, 'c')
    assert shown['candidate_id'] == 'A' and not shown['preferred_by_comparison']


@pytest.mark.parametrize('tot, source, expected', [
    ({'status': 'NOT_TRIGGERED'}, 'DRAFT', None),
    ({'status': 'COMPARED', 'selected_candidate_id': 'B', 'candidates': []}, 'TOT', {'candidate_id': 'B', 'basis': 'SELECTED'}),
    ({'status': 'COMPARED', 'model_preferred_candidate_id': 'C', 'candidates': []}, 'TOT_FALLBACK',
     {'candidate_id': 'C', 'basis': 'FALLBACK'}),
    ({'status': 'COMPARED', 'candidates': [{'candidate_id': 'I', 'incumbent': True, 'action_type': 'POST_ALIGNMENT',
                                            'draft_text': 'Post it. '}]}, 'DRAFT', {'candidate_id': 'I', 'basis': 'INCUMBENT'}),
    ({'status': 'COMPARED', 'candidates': [{'candidate_id': 'I', 'incumbent': True, 'action_type': 'POST_ALIGNMENT',
                                            'draft_text': 'Post a different text.'}]}, 'DRAFT',
     {'candidate_id': None, 'basis': 'NOT_A_CANDIDATE'}),
])
def test_card_action_candidate_is_derived_from_saved_fields(tot, source, expected):
    action = ActionProposal(action_type='POST_ALIGNMENT', draft_text='Post it.')
    assert advisor_tot.card_action_candidate(tot, action, source) == expected


@pytest.mark.skipif(not NSFW.is_file(), reason='live full run not present')
def test_the_live_close_call_links_its_card_action_to_the_incumbent_candidate():
    """Saved before this field existed: the dashboard derives the link from the saved incumbent flag and exact text."""
    from threadsense.dashboard.runs import Run
    record = json.loads(NSFW.read_text(encoding='utf-8'))
    card_id = record['result']['card']['card_id']
    assert 'card_action' not in record['result']['tot']
    stub = SimpleNamespace(topics={card_id: record}, cards={card_id: record['result']['card']})
    assert Run.action_candidate(stub, card_id) == {'candidate_id': 'focused_discussion', 'basis': 'INCUMBENT'}
    shown = Run.alternatives(stub, card_id)
    assert [a['candidate_id'] for a in shown] == ['written_clarification_request'] and shown[0]['closely_matched']
