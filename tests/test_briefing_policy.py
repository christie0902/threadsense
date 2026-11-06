"""briefing-routing-v2 on the cached full live run: briefing relevance kept apart from recommendation availability.
Offline: saved topic results only; no model call."""
from copy import deepcopy
import json
from pathlib import Path
import shutil

from fastapi.testclient import TestClient
import pytest

from threadsense.agents import briefing_policy as policy
from threadsense.agents.advice_contracts import AdviceCardV5
from threadsense.dashboard.app import create_app
from threadsense.dashboard.decisions import DecisionStore
from threadsense.dashboard.runs import Catalog, Run
from threadsense.routing import ROOT

PARENT = ROOT/'data/experiments/threadsense_full_v1/stages/agent3/overnight_run'
DERIVED = ROOT/'data/experiments/threadsense_full_v1_briefing_v2'
RAW_LABELS = json.loads((ROOT/'data/evaluation/briefing_relevance_labels_v2.json').read_text(encoding='utf-8'))
LABELS = policy.load_labels(RAW_LABELS)
CUTOFF = '2026-10-02T12:00:00Z'  # the parent run's saved briefing cutoff
pytestmark = pytest.mark.skipif(not PARENT.is_dir(), reason='full live run not present')


def topic(name):
    for path in sorted((PARENT/'topics').glob('*.json')):
        data = json.loads(path.read_text(encoding='utf-8'))
        if data['result']['card']['topic_name'] == name:
            return data['result']['card'], data['result']
    raise KeyError(name)


def route(name, **kw):
    card, result = topic(name)
    data, changes = policy.apply(card, result, labels=kw.pop('labels', LABELS), cutoff=kw.pop('cutoff', CUTOFF), **kw)
    return AdviceCardV5.model_validate(data).model_dump(mode='json'), changes


def codes(card):
    return sorted({r['code'] for r in card['needs_review_reasons']})


# --- The screenshot cases: observations that had no supported no-action reason --------------------------------

@pytest.mark.parametrize('name, status', [
    ('Regional vocabulary fit for target audience', 'NO_INTERVENTION_PROPOSED'),
    ('QA threshold consistency across review teams', 'NO_INTERVENTION_PROPOSED'),
    ('Citation support verification', 'NO_INTERVENTION_PROPOSED'),
    ('Repeated ending phrase in generated answer', 'NO_INTERVENTION_PROPOSED'),
    ('Korean language QA edge cases', 'RECOMMENDATION_WITHHELD')])
def test_an_observation_without_a_supported_no_action_reason_returns_to_review(name, status):
    before, _ = topic(name)
    assert (before['card_line'], before['next_step']['status']) == ('OBSERVATION', status)
    card, changes = route(name)
    assert card['card_line'] == 'NEEDS_REVIEW' and card['next_step'] == before['next_step']
    assert {'NO_INTERVENTION_PROPOSED': 'NO_ACTION_NOT_SUPPORTED', 'RECOMMENDATION_WITHHELD': 'RECOMMENDATION_WITHHELD'}[status] in codes(card)
    assert card['outstanding_step'] and card['briefing']['status'] == 'IN_BRIEFING'
    assert changes[0] == {'field': 'card_line', 'before': 'OBSERVATION', 'after': 'NEEDS_REVIEW',
                          'reason': f'Next step {status}: an observation needs a supported no-action reason.'}


def test_waiting_for_audience_details_comes_from_supported_statements_only():
    card, result = topic('Regional vocabulary fit for target audience')
    routed, _ = route('Regional vocabulary fit for target audience')
    step = routed['outstanding_step']
    assert step['kind'] == 'WAITING_ON_REQUESTED_STEP' and step['label'] == 'Pending follow-up'
    statements = {s['statement_id']: s for s in result['grounding']['statements']}
    for sid, text in zip(step['statement_ids'], step['details']):
        assert statements[sid]['verdict'] == 'SUPPORTED' and statements[sid]['text'].endswith(text)
    assert 'confirm the audience' in step['details'][0]
    assert 'OPEN_FOLLOW_UP' in codes(routed)


# --- Briefing relevance --------------------------------------------------------------------------------------

@pytest.mark.parametrize('name', ['Language-day greetings', 'Social greetings and well-wishes'])
def test_pure_greetings_leave_the_brief_but_keep_their_card(name):
    card, changes = route(name)
    assert card['briefing']['status'] == 'EXCLUDED_SOCIAL' and card['card_line'] == 'OBSERVATION'
    assert card['lineage']['member_ids'] and card['summary'] == topic(name)[0]['summary']
    assert changes[-1]['field'] == 'briefing.status' and changes[-1]['after'] == 'EXCLUDED_SOCIAL'


@pytest.mark.parametrize('name, relevance', [('Work environment and background noise', 'MIXED'),
                                             ('Queue coverage and closure reminders', 'ROUTINE_NOTICE')])
def test_a_useful_observation_with_na_severity_stays_in_the_brief(name, relevance):
    card, _ = route(name)
    assert card['severity']['level'] == 'N/A'
    assert (card['card_line'], card['briefing']['status'], card['briefing']['relevance']) == ('OBSERVATION', 'IN_BRIEFING', relevance)
    assert card['next_step']['status'] == 'NO_ACTION_NEEDED' and card['outstanding_step'] is None


def test_unlabelled_relevance_never_hides_a_card():
    card, _ = route('Language-day greetings', labels={})
    assert card['briefing'] == {'status': 'IN_BRIEFING', 'relevance': 'UNLABELLED', 'label_id': None, 'label_source': None,
                                'kept_because': [], 'basis': None, 'evidence_statement_ids': []}


def test_a_label_on_changed_messages_is_void():
    card, result = topic('Language-day greetings')
    result = deepcopy(result)
    next(e for e in result['evidence_ledger'].values() if e.get('origin') == 'member_message')['excerpt'] += ' Also the queue is down.'
    data, _ = policy.apply(card, result, labels=LABELS)
    assert data['briefing']['status'] == 'IN_BRIEFING' and data['briefing']['relevance'] == 'UNLABELLED'
    assert 'no longer matches the saved messages' in data['briefing']['kept_because'][0]


def test_excluded_content_with_an_outstanding_obligation_stays_in_the_brief():
    card, result = topic('Social greetings and well-wishes')
    data, changes = policy.apply(card, result, labels=LABELS, queue_member_ids=card['lineage']['member_ids'])
    assert data['briefing']['status'] == 'IN_BRIEFING' and data['briefing']['relevance'] == 'SOCIAL_ONLY'
    assert data['briefing']['kept_because'] == ['a member has a Model Review Queue item']
    assert 'not applied' in changes[-1]['reason']
    flagged = deepcopy(card)
    flagged['inherited_flags'] = [{'origin': 'agent1', 'kind': 'inherited_agent1_review', 'candidate_group_id': 'g',
                                   'member_ids': card['lineage']['member_ids']}]
    flagged['needs_review_reasons'] = [{'code': 'INHERITED_FLAG', 'detail': 'open', 'obligation_ids': [], 'evidence': []}]
    flagged['card_line'] = 'NEEDS_REVIEW'
    data, _ = policy.apply(flagged, result, labels=LABELS)
    assert data['briefing']['status'] == 'IN_BRIEFING' and data['card_line'] == 'NEEDS_REVIEW'


# --- Next-step evidence ---------------------------------------------------------------------------------------

def test_unanswered_question_versus_substantively_answered_question():
    unanswered, _ = route('Repeated ending phrase in generated answer')
    answered, _ = route('Tie threshold for near-identical responses')
    assert unanswered['card_line'] == 'NEEDS_REVIEW' and unanswered['outstanding_step']['kind'] == 'THREAD_STILL_OPEN'
    assert unanswered['briefing']['status'] == 'IN_BRIEFING'
    # Answered in both threads, consistent with current guidance: a resolved routine exchange goes to history.
    assert (answered['card_line'], answered['outstanding_step'], answered['briefing']['status']) == ('OBSERVATION', None, 'HISTORY_ROUTINE')
    assert answered['resolution_status'] == 'RESOLVED_IN_THREAD'


def test_a_supported_monitoring_decision_keeps_its_line_and_states_what_is_open():
    card, _ = route('Audio-transcript mismatch clarification')
    assert card['next_step']['status'] == 'NO_ACTION_NEEDED' and card['card_line'] == 'NEEDS_REVIEW'
    assert codes(card) == ['INHERITED_FLAG'] and card['outstanding_step']['kind'] == 'MONITORING'


def test_a_rejected_no_action_explanation_is_never_an_observation():
    card, result = topic('Language-day greetings')
    card, result = deepcopy(card), deepcopy(result)
    next(s for s in result['grounding']['statements'] if s['statement_id'] == 'action:no_action')['verdict'] = \
        'REJECTED_SOURCE_FACT_NEEDS_RETRIEVED_SOURCE'
    card['next_step'] = {'status': 'NO_INTERVENTION_PROPOSED', 'rationale': None,
                         'explanation': 'The advisor chose not to propose an intervention. Its reason is not shown.'}
    data, _ = policy.apply(card, result, labels=LABELS)
    routed = AdviceCardV5.model_validate(data)
    assert routed.card_line == 'NEEDS_REVIEW' and routed.briefing.status == 'IN_BRIEFING'
    assert routed.outstanding_step.kind == 'NO_ACTION_CHOICE_NEEDS_REVIEW' and routed.outstanding_step.text_source == 'FIXED_EXPLANATION'
    assert 'it has review reasons' in routed.briefing.kept_because


def test_a_withheld_operational_recommendation_stays_in_review_without_a_new_action():
    before, _ = topic('Conflicting QN guidance sources')
    card, _ = route('Conflicting QN guidance sources')
    assert card['next_step']['status'] == 'RECOMMENDATION_WITHHELD' and card['recommended_action'] is None
    assert {'RECOMMENDATION_WITHHELD', 'GROUNDING_FAILURE'} <= set(codes(card))
    assert card['next_step'] == before['next_step']


def test_v5_refuses_the_contradictions_the_screenshots_showed():
    card, _ = route('Korean language QA edge cases')
    for broken in (
            {**card, 'card_line': 'OBSERVATION', 'needs_review_reasons': []},
            {**card, 'needs_review_reasons': [r for r in card['needs_review_reasons'] if r['code'] != 'RECOMMENDATION_WITHHELD']},
            {**card, 'outstanding_step': None},
            {**card, 'briefing': {**card['briefing'], 'status': 'EXCLUDED_SOCIAL', 'relevance': 'SOCIAL_ONLY'}}):
        with pytest.raises(ValueError):
            AdviceCardV5.model_validate(broken)


def test_legacy_records_with_insufficient_evidence():
    card, result = topic('Repeated ending phrase in generated answer')
    with pytest.raises(ValueError):
        policy.apply({**card, 'contract_version': 'agent3-advice-card-v3'}, result, labels=LABELS)
    stale = deepcopy(result)
    for s in stale['grounding']['statements']:
        if s['kind'] == 'RESOLUTION':
            s['text'] += ' (edited)'
    data, _ = policy.apply(card, stale, labels=LABELS)  # a judged text that is not the basis is not reused
    assert data['outstanding_step']['kind'] == 'NO_ACTION_CHOICE_NEEDS_REVIEW'
    assert data['outstanding_step']['text_source'] == 'FIXED_EXPLANATION'


def test_the_original_run_flags_its_unsupported_observations():
    run = Run(PARENT)
    flagged = {run.cards[c]['topic_name'] for c in run.cards if run.presentation(c)['unsupported_observation']}
    assert flagged == {'Regional vocabulary fit for target audience', 'QA threshold consistency across review teams',
                       'Citation support verification', 'Repeated ending phrase in generated answer', 'Korean language QA edge cases'}


# --- The derived run ------------------------------------------------------------------------------------------

@pytest.mark.skipif(not DERIVED.is_dir(), reason='derived run not written')
def test_the_derived_run_keeps_every_input_and_obligation():
    parent, derived = Run(PARENT), Run(DERIVED)
    p_members = sorted(m for c in parent.cards.values() for m in c['lineage']['member_ids'])
    d_members = sorted(m for c in derived.cards.values() for m in c['lineage']['member_ids'])
    assert p_members == d_members and len(d_members) == 177
    assert [i.item_id for i in parent.queue.values()] == [i.item_id for i in derived.queue.values()]
    assert [i.source_obligation for i in parent.queue.values()] == [i.source_obligation for i in derived.queue.values()]
    assert not set(parent.cards) & set(derived.cards)
    briefing = derived.brief['briefing']
    assert briefing['in_briefing'] + len(briefing['not_in_briefing']) == len(derived.cards) == 81
    assert derived.brief['counts']['members_on_cards'] == 177 and derived.brief['accounting']['status'] == 'COMPLETE'
    for card in derived.cards.values():
        original = parent.cards[card['derivation']['parent_card_id']]
        for field in ('summary', 'details', 'recommended_action', 'reasoning', 'next_step', 'severity', 'supporting_sources'):
            assert card[field] == original[field]


@pytest.mark.skipif(not DERIVED.is_dir(), reason='derived run not written')
def test_a_decision_on_a_parent_card_does_not_apply_to_its_derived_card(tmp_path):
    roots = tmp_path/'parent', tmp_path/'derived'
    shutil.copytree(PARENT, roots[0]/'overnight_run')
    shutil.copytree(DERIVED, roots[1]/DERIVED.name)
    client = TestClient(create_app(catalog=Catalog(roots), store=DecisionStore(tmp_path/'d.sqlite3'), session_actor='U006'))
    parent_card = next(c for c in client.get('/api/runs/overnight_run/brief').json()['cards']
                       if c['card']['topic_name'] == 'Unfindable or non-existent references')['card']
    saved = client.post(f"/api/runs/overnight_run/cards/{parent_card['card_id']}/decisions",
                        json={'kind': 'DISMISS', 'actor_id': 'U006', 'note': 'test'},
                        headers={'Idempotency-Key': 'test-key-0001'})
    assert saved.status_code in (200, 201), saved.text
    brief = client.get(f'/api/runs/{DERIVED.name}/brief').json()
    derived = next(c for c in brief['cards'] if c['card']['derivation']['parent_card_id'] == parent_card['card_id'])
    assert derived['card']['card_id'] != parent_card['card_id'] and not derived['resolved']
    assert client.get(f'/api/runs/{DERIVED.name}/decisions').json()['decisions'] == []


# --- v2 relevance: routine administration, time-bound notices, reviewed briefing value -------------------------

def test_an_open_routine_admin_question_goes_to_history_with_its_open_status_kept():
    before, _ = topic('Team avatar asset location')
    card, changes = route('Team avatar asset location')
    assert card['briefing']['status'] == 'HISTORY_ROUTINE' and card['briefing']['relevance'] == 'ROUTINE_ADMIN'
    assert 'Administrative question' in card['briefing']['basis'] and card['briefing']['kept_because'] == []
    assert card['resolution_status'] == before['resolution_status'] == 'PARTIALLY_RESOLVED'
    assert card['outstanding_step']['kind'] == 'MONITORING' and card['lineage'] == before['lineage']
    assert card['next_step'] == before['next_step'] and card['summary'] == before['summary']
    moved = next(c for c in changes if c['field'] == 'briefing.status')
    assert 'stays PARTIALLY_RESOLVED and its open step is kept' in moved['reason']


def test_v1_labels_kept_the_open_admin_question_in_the_brief():
    raw = json.loads((ROOT/'data/evaluation/briefing_relevance_labels_v1.json').read_text(encoding='utf-8'))
    card, _ = route('Team avatar asset location', labels=policy.load_labels(raw))
    assert card['briefing']['status'] == 'IN_BRIEFING' and card['briefing']['kept_because'] == ['it has an outstanding step']


def test_routine_admin_with_a_review_obligation_or_unsupported_next_step_stays():
    card, result = topic('Team avatar asset location')
    data, _ = policy.apply(card, result, labels=LABELS, cutoff=CUTOFF, queue_member_ids=card['lineage']['member_ids'])
    assert data['briefing']['status'] == 'IN_BRIEFING' and data['briefing']['kept_because'] == ['a member has a Model Review Queue item']
    unproven = {**card, 'recommended_action': None,
                'next_step': {'status': 'NO_INTERVENTION_PROPOSED', 'rationale': None, 'explanation': 'Its reason is not shown.'}}
    data, _ = policy.apply(unproven, result, labels=LABELS, cutoff=CUTOFF)
    routed = AdviceCardV5.model_validate(data)
    assert routed.briefing.status == 'IN_BRIEFING' and routed.card_line == 'NEEDS_REVIEW'
    assert {'it has review reasons', 'it has an outstanding step', 'it has no supported no-action reason'} <= set(routed.briefing.kept_because)


def test_an_unsupported_audit_statement_voids_the_exclusion():
    card, result = topic('Team avatar asset location')
    result = deepcopy(result)
    next(s for s in result['grounding']['statements'] if s['statement_id'] == 'claim:c3')['verdict'] = 'REJECTED_UNSUPPORTED'
    data, _ = policy.apply(card, result, labels=LABELS, cutoff=CUTOFF)
    assert data['briefing']['status'] == 'IN_BRIEFING'
    assert data['briefing']['kept_because'] == ['audit evidence claim:c3 is not a SUPPORTED statement']


def test_queue_notices_are_checked_against_the_saved_cutoff():
    card, changes = route('Queue coverage and closure reminders')
    kept = card['briefing']['kept_because']
    assert card['briefing']['status'] == 'IN_BRIEFING' and len(kept) == 2
    # No timezone is recorded: the closure can still be open at 12:30Z (posted from UTC+05:30); coverage is for a later day.
    assert 'member_809df2faae873ed0419f1574: latest end 2026-10-02T12:30:00Z' in kept[0]
    assert 'member_211e8a1284a7577600ae8ad4: latest end 2026-10-04T01:00:00Z' in kept[1]
    assert card['resolution_status'] == 'UNKNOWN'


def test_expired_notices_go_to_history_without_being_marked_complete():
    before, _ = topic('Queue coverage and closure reminders')
    card, _ = route('Queue coverage and closure reminders', cutoff='2026-10-04T01:00:00Z')
    assert card['briefing']['status'] == 'HISTORY_ROUTINE' and card['briefing']['kept_because'] == []
    assert card['resolution_status'] == before['resolution_status'] == 'UNKNOWN' and card['outstanding_step'] is None
    partly, _ = route('Queue coverage and closure reminders', cutoff='2026-10-03T00:00:00Z')
    assert partly['briefing']['status'] == 'IN_BRIEFING' and len(partly['briefing']['kept_because']) == 1
    unknown, _ = route('Queue coverage and closure reminders', cutoff=None)
    assert unknown['briefing']['kept_because'] == ['the briefing cutoff is unknown']


def test_reviewed_answered_cards_record_their_briefing_value():
    suggestive, _ = route('Suggestive vs explicit content boundary')
    assert suggestive['briefing']['status'] == 'IN_BRIEFING' and suggestive['briefing']['relevance'] == 'PROJECT'
    assert 'claim:c5' in suggestive['briefing']['evidence_statement_ids'] and 'guidance gap' in suggestive['briefing']['basis']
    assert suggestive['recommended_action'] == topic('Suggestive vs explicit content boundary')[0]['recommended_action']
    tie, _ = route('Tie threshold for near-identical responses')
    assert tie['briefing']['status'] == 'HISTORY_ROUTINE' and {'claim:c6', 'claim:c7'} <= set(tie['briefing']['evidence_statement_ids'])
    sibling, _ = route('QA inconsistency on tie judgments')
    assert sibling['briefing']['status'] == 'IN_BRIEFING' and sibling['card_line'] == 'NEEDS_REVIEW'


def test_every_audit_label_cites_only_supported_statements():
    reviewed = [l for l in RAW_LABELS['labels'] if l['audit'] == 'REVIEWED_2026-11-06']
    assert len(reviewed) == 4 and 'no automatic relevance classification' in RAW_LABELS['method']
    for label in reviewed:
        _, result = topic(label['topic_name'])
        assert policy.evidence_check(label, result) == [], label['topic_name']


def test_only_routine_admin_may_leave_the_briefing_with_an_open_thread():
    card, _ = route('Team avatar asset location')
    AdviceCardV5.model_validate(card)
    for broken in ({**card, 'briefing': {**card['briefing'], 'relevance': 'ROUTINE_NO_FINDING'}},
                   {**card, 'outstanding_step': {**card['outstanding_step'], 'kind': 'THREAD_STILL_OPEN'}}):
        with pytest.raises(ValueError):
            AdviceCardV5.model_validate(broken)


# --- Original and derived runs share a logical run ID but nothing else -----------------------------------------

@pytest.mark.skipif(not DERIVED.is_dir(), reason='derived run not written')
def test_original_and_derived_runs_stay_isolated_across_loading_evidence_and_writes(tmp_path):
    roots = tmp_path/'parent', tmp_path/'derived'
    shutil.copytree(PARENT, roots[0]/'overnight_run')
    shutil.copytree(DERIVED, roots[1]/DERIVED.name)
    client = TestClient(create_app(catalog=Catalog(roots), store=DecisionStore(tmp_path/'d.sqlite3'), session_actor='U006'))
    runs = {r['run_key']: r for r in client.get('/api/runs').json()['runs']}
    parent, derived = runs['overnight_run'], runs[DERIVED.name]
    assert parent['run_id'] == derived['run_id'] and parent['run_instance'] != derived['run_instance']
    assert parent['shares_run_id_with'] == [DERIVED.name] and derived['shares_run_id_with'] == ['overnight_run']

    # Loading: each run serves only its own cards; a card ID from one run is not found in the other.
    p_cards = {c['card']['card_id']: c for c in client.get('/api/runs/overnight_run/brief').json()['cards']}
    d_brief = client.get(f'/api/runs/{DERIVED.name}/brief').json()
    d_cards = {c['card']['card_id']: c for c in d_brief['cards']}
    assert not set(p_cards) & set(d_cards)
    parent_id = next(i for i, c in p_cards.items() if c['card']['topic_name'] == 'Korean language QA edge cases')
    derived_id = next(i for i, c in d_cards.items() if c['card']['derivation']['parent_card_id'] == parent_id)
    assert client.get(f'/api/runs/{DERIVED.name}/cards/{parent_id}').status_code == 404
    assert client.get(f'/api/runs/overnight_run/cards/{derived_id}').status_code == 404

    # Evidence links resolve inside the run that cites them: each run reads only its own saved ledger.
    detail = client.get(f'/api/runs/{DERIVED.name}/cards/{derived_id}').json()
    eid = next(e['evidence_id'] for e in d_cards[derived_id]['cited_evidence'] if not e.get('missing_from_ledger'))
    assert client.get(f'/api/runs/{DERIVED.name}/evidence/{eid}').status_code == 200 and detail['card']['card_id'] == derived_id
    for holder in [p for p in (roots[1]/DERIVED.name/'topics').glob('*.json') if eid in p.read_text(encoding='utf-8')]:
        holder.unlink()  # topics are not instance files, so the run instance is unchanged
    fresh = TestClient(create_app(catalog=Catalog(roots), store=DecisionStore(tmp_path/'d.sqlite3'), session_actor='U006'))
    assert fresh.get(f'/api/runs/{DERIVED.name}/evidence/{eid}').status_code == 404
    assert fresh.get(f'/api/runs/overnight_run/evidence/{eid}').status_code == 200
    shutil.rmtree(roots[1]/DERIVED.name)
    shutil.copytree(DERIVED, roots[1]/DERIVED.name)

    # Decision writes: a card decision posted against the other run's ID is refused and writes nothing.
    refused = client.post(f'/api/runs/{DERIVED.name}/cards/{parent_id}/decisions',
                          json={'kind': 'DISMISS', 'actor_id': 'U006', 'note': 'test'}, headers={'Idempotency-Key': 'iso-key-0001'})
    assert refused.status_code == 404
    saved = client.post(f'/api/runs/{DERIVED.name}/cards/{derived_id}/decisions',
                        json={'kind': 'DISMISS', 'actor_id': 'U006', 'note': 'test'}, headers={'Idempotency-Key': 'iso-key-0002'})
    assert saved.status_code in (200, 201), saved.text
    assert client.get('/api/runs/overnight_run/decisions').json()['decisions'] == []
    assert [d['card_id'] for d in client.get(f'/api/runs/{DERIVED.name}/decisions').json()['decisions']] == [derived_id]

    # Review queue items keep the same IDs in both runs; an action on one run's item never appears on the other.
    queue = lambda key: {i['item']['item_id']: i for i in client.get(f'/api/runs/{key}/review-queue').json()['items']}
    item_id = next(iter(queue('overnight_run')))
    derived_state = queue(DERIVED.name)[item_id]['review_state']
    acted = client.post(f'/api/runs/overnight_run/review-items/{item_id}/actions',
                        json={'action': 'DEFER', 'actor_id': 'U006', 'note': 'test'}, headers={'Idempotency-Key': 'iso-key-0003'})
    assert acted.status_code in (200, 201), acted.text
    assert queue('overnight_run')[item_id]['entries'] and not queue(DERIVED.name)[item_id]['entries']
    assert queue(DERIVED.name)[item_id]['review_state'] == derived_state
