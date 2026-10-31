"""ToT v3 selection mechanics (PREPARED judgments: the Fake client returns scripted draft, comparison and grounding
responses). These show how the controller selects, transfers and validates candidates; they say nothing about live
model quality. Evidence comes from each payload; no topic is named in the logic under test."""
import pytest

from tests.test_agent3_advisor import (  # noqa: F401 - fixtures reused
    Fake, codes, draft_for, retriever, run, supported, view,
)

SCENARIO = 'audio_playback'  # Any pilot topic with current guidance and prior decisions in its evidence.


def members(payload):
    """Member messages in a draft payload (member_evidence) or a comparison payload (evidence)."""
    items = payload.get('member_evidence') or [i for i in payload['evidence'] if i.get('origin') == 'member_message']
    return [i['evidence_id'] for i in items]


def choice_draft(payload, action_type='POST_ALIGNMENT', competing=('POST_ALIGNMENT', 'NO_ACTION'), **extra):
    """An operational incumbent plus a stated action choice (the ACTION_CHOICE trigger), confident, no open question."""
    base = draft_for(payload)
    action = {**base['proposed_action'], 'action_type': action_type, 'instruction': 'Post the current handling.',
              'draft_text': 'Reminder: report the task ID and browser state.'}
    return {**base, 'proposed_action': action, 'action_choice': {
        'competing_actions': list(competing), 'evidence_ids': members(payload)[:1],
        'tradeoff': 'The threads were partly answered in place; it is unclear whether a reminder adds anything.'}, **extra}


def candidate(cid, action_type, evidence_ids, text, need_ids=None, **extra):
    c = {'candidate_id': cid, 'action_type': action_type, 'draft_text': text, 'evidence_ids': evidence_ids,
         'evidence_support': 'STRONG', 'applicability': 'CURRENT', 'severity_fit': 'FITS', 'rationale': 'It fits the evidence.',
         'need_strength': 'STRONG' if action_type != 'NO_ACTION' else 'NONE', 'temporal_scope': 'CONSISTENT',
         'proportionality': 'FITS', 'unresolved_assumptions': []}
    if action_type != 'NO_ACTION':
        c['intervention_need'] = {'kind': 'OPERATIONAL_PROBLEM', 'statement': 'The reports describe a current failure.',
                                  'evidence_ids': need_ids or evidence_ids}
    return {**c, **extra}


def comparison(payload, preferred, others, decision=None, close=False):
    """The incumbent copied verbatim from the payload, plus the other candidates."""
    inc = payload['incumbent']
    guide = next(i['evidence_id'] for i in payload['evidence'] if i.get('use') == 'CURRENT_GUIDANCE')
    incumbent = candidate('INC', inc['action_type'], [guide], inc['draft_text'], need_ids=members(payload)[:1],
                          instruction=inc.get('instruction'), incumbent=True)
    return {'candidates': [incumbent] + others, 'preferred_candidate_id': preferred, 'close_call': close,
            'decision': decision or ('CLOSE_CALL' if close else 'KEEP_INCUMBENT' if preferred == 'INC' else 'REPLACE_INCUMBENT'),
            'rationale': 'Compared on need, premises, scope and proportionality.'}


def guide_of(payload):
    return next(i['evidence_id'] for i in payload['evidence'] if i.get('use') == 'CURRENT_GUIDANCE')


def statement(result, sid):
    return next((s for s in result['grounding']['statements'] if s['statement_id'] == sid), None)


@pytest.mark.parametrize('incumbent, preferred_type, text', [
    ('POST_ALIGNMENT', 'NO_ACTION', 'Keep observing; the threads were answered in place.'),          # observation preferred
    ('ESCALATE_ENGINEERING', 'POST_ALIGNMENT', 'Reminder: report the task ID, browser state and whether another clip plays.'),
    ('POST_ALIGNMENT', 'ESCALATE_ENGINEERING', 'Playback fails for several tasks; please investigate.'),  # escalation preferred
])
def test_clearly_preferred_candidate_replaces_a_valid_incumbent_before_grounding(retriever, view, incumbent, preferred_type, text):
    sent = []

    def tot(payload):
        return comparison(payload, 'B', [candidate('B', preferred_type, [guide_of(payload)] + members(payload)[:1], text,
                                                   need_ids=members(payload)[:1])])
    client = Fake(draft=lambda p: choice_draft(p, action_type=incumbent, competing=(incumbent, preferred_type)),
                  tot=tot, grounding=lambda p: sent.append(p) or supported(p))
    result = run(SCENARIO, client, retriever, view)
    assert client.stages_called() == ['draft', 'tot', 'grounding']  # One comparison; the grounding call stays last.
    assert result['tot']['triggers'] == ['ACTION_CHOICE'] and result['action_source'] == 'TOT'
    action = statement(result, 'action')
    assert action['verdict'] == 'SUPPORTED' and text in action['text']  # The exact selected text was judged.
    alternatives = [s['statement_id'] for s in sent[0]['statements'] if s['kind'] == 'ALTERNATIVE']
    assert alternatives == ['alternative:INC']  # The displaced incumbent is judged; the selection is not judged twice.
    assert statement(result, 'tot:action_choice')['verdict'] == 'SUPPORTED'
    card = result['card']
    if preferred_type == 'NO_ACTION':
        assert card['recommended_action'] in (None, {}) or card['recommended_action']['action_type'] == 'NO_ACTION'
        assert statement(result, 'action:need') is None  # NO_ACTION states no intervention need.
    else:
        assert card['recommended_action']['action_type'] == preferred_type and card['recommended_action']['draft_text'] == text
        assert statement(result, 'action:need')['verdict'] == 'SUPPORTED'
    # Selection never clears review obligations: routing still follows the review reasons.
    assert ('INHERITED_FLAG' in codes(result)) == bool(card['inherited_flags'])
    assert card['card_line'] == ('NEEDS_REVIEW' if codes(result) else 'RECOMMENDED_ACTION' if card['recommended_action']
                                 and card['recommended_action']['action_type'] != 'NO_ACTION' else 'OBSERVATION')


def test_incumbent_is_retained_when_preferred(retriever, view):
    client = Fake(draft=choice_draft, tot=lambda p: comparison(p, 'INC', [candidate('B', 'NO_ACTION', [guide_of(p)], 'Observe.')]),
                  grounding=supported)
    result = run(SCENARIO, client, retriever, view)
    assert result['action_source'] == 'DRAFT' and 'kept the draft action' in result['action_notes'][0]
    assert result['card']['recommended_action']['draft_text'] == 'Reminder: report the task ID and browser state.'


def test_close_call_keeps_the_incumbent_and_leaves_alternatives_reviewable(retriever, view):
    client = Fake(draft=choice_draft, tot=lambda p: comparison(p, None, [candidate('B', 'NO_ACTION', [guide_of(p)], 'Observe.')],
                                                               close=True), grounding=supported)
    result = run(SCENARIO, client, retriever, view)
    assert result['action_source'] == 'DRAFT' and result['action_notes'][0].startswith('Close call')
    assert statement(result, 'alternative:INC')['verdict'] == 'SUPPORTED' and statement(result, 'alternative:B')
    assert result['tot']['presentation'] == 'SURFACE_GROUNDED_ALTERNATIVES'


def test_historical_only_support_cannot_become_the_current_action(retriever, view):
    def tot(payload):
        history = next(i['evidence_id'] for i in payload['evidence'] if i.get('use') in ('PRIOR_DECISION', 'HISTORY_ONLY'))
        return comparison(payload, 'B', [candidate('B', 'POST_ALIGNMENT', [history], 'Re-run the earlier trial.',
                                                   need_ids=members(payload)[:1], applicability='HISTORICAL_ONLY')])
    client = Fake(draft=lambda p: choice_draft(p, action_type='ESCALATE_ENGINEERING', competing=('ESCALATE_ENGINEERING', 'POST_ALIGNMENT')),
                  tot=tot, grounding=supported)
    result = run(SCENARIO, client, retriever, view)
    b = next(c for c in result['tot']['candidates'] if c['candidate_id'] == 'B')
    assert 'HISTORICAL_ONLY_SUPPORT' in b['issues'] and result['action_source'] == 'DRAFT'
    assert 'not adopted' in result['action_notes'][0] and result['card']['recommended_action']['action_type'] == 'ESCALATE_ENGINEERING'


def test_a_rewritten_incumbent_is_flagged_not_trusted(retriever, view):
    def tot(payload):
        value = comparison(payload, 'INC', [candidate('B', 'NO_ACTION', [guide_of(payload)], 'Observe.')])
        value['candidates'][0]['draft_text'] = 'A quietly improved reminder.'
        return value
    result = run(SCENARIO, Fake(draft=choice_draft, tot=tot, grounding=supported), retriever, view)
    inc = next(c for c in result['tot']['candidates'] if c['candidate_id'] == 'INC')
    assert 'INCUMBENT_NOT_VERBATIM' in inc['issues']
    assert result['card']['recommended_action']['draft_text'] == 'Reminder: report the task ID and browser state.'


def test_operational_candidate_without_a_need_is_not_selected(retriever, view):
    def tot(payload):
        b = candidate('B', 'ESCALATE_ENGINEERING', [guide_of(payload)], 'Escalate now.')
        del b['intervention_need']
        return comparison(payload, 'B', [b])
    result = run(SCENARIO, Fake(draft=choice_draft, tot=tot, grounding=supported), retriever, view)
    assert result['action_source'] == 'DRAFT' and 'NO_INTERVENTION_NEED_STATED' in result['action_notes'][0]


def test_selected_action_unjudged_is_never_shown(retriever, view):
    """No unjudged substitution: if the grounding omits the selected action's verdict, nothing is shown, and the
    fallback does not resend the same candidate."""
    def tot(payload):
        return comparison(payload, 'B', [candidate('B', 'ESCALATE_ENGINEERING', [guide_of(payload)] + members(payload)[:1],
                                                   'Please investigate the playback failures.', need_ids=members(payload)[:1])])
    def judge(payload):
        value = supported(payload)
        return {**value, 'verdicts': [v for v in value['verdicts'] if v['statement_id'] != 'action']}
    result = run(SCENARIO, Fake(draft=choice_draft, tot=tot, grounding=judge), retriever, view)
    assert statement(result, 'action')['verdict'] == 'NOT_JUDGED' and result['card']['recommended_action'] is None
    assert any('already the action' in n for n in result['action_notes'])


@pytest.mark.parametrize('change', [
    {},                                                                                   # nothing to compare
    {'action_choice': None},
    {'action_choice': {'competing_actions': ['POST_ALIGNMENT', 'POST_ALIGNMENT'], 'tradeoff': 't', 'evidence_ids': ['m:x']}},
])
def test_straightforward_paths_bypass_tot(retriever, view, change):
    """No trigger: no comparison call. Inherited flags alone, or an action choice naming one action type, never trigger."""
    def draft(payload):
        base = choice_draft(payload)
        if not change:
            return {k: v for k, v in base.items() if k != 'action_choice'}
        if change.get('action_choice') and change['action_choice']['competing_actions'][0] == 'POST_ALIGNMENT':
            return base  # Built below through validation instead.
        return {**base, **change}
    if change.get('action_choice'):
        from pydantic import ValidationError
        from threadsense.agents.advisor_contracts import ActionChoice
        with pytest.raises(ValidationError, match='two different action types'):
            ActionChoice.model_validate(change['action_choice'])
        return
    client = Fake(draft=draft, grounding=supported)
    result = run(SCENARIO, client, retriever, view)
    assert client.stages_called() == ['draft', 'grounding'] and result['tot']['status'] == 'NOT_TRIGGERED'


def test_choice_citing_unknown_evidence_does_not_trigger(retriever, view):
    def draft(payload):
        base = choice_draft(payload)
        return {**base, 'action_choice': {**base['action_choice'], 'evidence_ids': ['m:C_UNKNOWN:1.1']}}
    client = Fake(draft=draft, grounding=supported)
    assert run(SCENARIO, client, retriever, view)['tot']['status'] == 'NOT_TRIGGERED'


def test_comparison_never_consumes_the_reserved_grounding_call(retriever, view):
    from threadsense.agents.advisor_evidence import Budget
    client = Fake(draft=choice_draft, tot=lambda p: comparison(p, 'INC', []), grounding=supported)
    result = run(SCENARIO, client, retriever, view, budget=Budget({'model_calls_per_topic': 2, 'retrieval_calls_per_topic': 6}))
    assert client.stages_called() == ['draft', 'grounding'] and result['tot']['status'] == 'UNAVAILABLE'
    assert statement(result, 'action')['verdict'] == 'SUPPORTED'


def test_recorded_v2_comparisons_keep_adopt_only_behaviour(retriever, view):
    """A v2 comparison cannot displace an operational draft action (replay keeps the original behaviour)."""
    def tot(payload):
        value = comparison(payload, 'B', [candidate('B', 'ESCALATE_ENGINEERING', [guide_of(payload)], 'Escalate.',
                                                    need_ids=members(payload)[:1])])
        return {**value, 'contract_version': 'agent3-tot-comparison-v2', 'decision': None,
                'candidates': [{k: v for k, v in c.items() if k in ('candidate_id', 'action_type', 'draft_text', 'evidence_ids',
                                                                     'evidence_support', 'applicability', 'severity_fit', 'rationale',
                                                                     'instruction')} for c in value['candidates']]}
    result = run(SCENARIO, Fake(draft=choice_draft, tot=tot, grounding=supported), retriever, view)
    assert result['action_source'] == 'DRAFT' and result['card']['recommended_action']['action_type'] == 'POST_ALIGNMENT'
