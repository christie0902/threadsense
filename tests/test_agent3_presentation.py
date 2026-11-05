"""Two presentation levels (draft v11, AdviceCard v4): a short summary, independently judged detail sentences, and an
explicit next-step state. Offline: no model calls.

PREPARED = tests/fixtures/agent3_presentation_prepared_responses.json (recorded live drafts with hand-written detail
sentences and hand-set verdicts; not model output). RECORDED = saved runs under data/experiments, read only.
"""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest

from threadsense.agents import advisor_pilot as pilot, flag_impact as fi
from threadsense.agents.advice_contracts import AdviceCardV4, validate_card
from threadsense.agents.advisor_checks import (
    detail_parts, next_step_state, no_action_reason, presentation_issues, shown_details, shown_summary, statements,
)
from threadsense.agents.advisor_contracts import AdvisorDraft
from threadsense.agents.flag_provenance import _element
from threadsense.dashboard.app import create_app
from threadsense.dashboard.decisions import DecisionStore
from threadsense.dashboard.runs import Catalog
from threadsense.routing import ROOT

PREPARED = json.loads((ROOT/'tests/fixtures/agent3_presentation_prepared_responses.json').read_text(encoding='utf-8'))
SUBMIT, TIES, GREETINGS = 'gap:routed_440e64c7fbdcc49f', 'topic:cluster_f944891544b06f79/topic_1', 'topic:cluster_be4e3bac742eccb3/topic_1'
PREPARED_RUN = ROOT/'data/experiments/agent3_presentation_prepared_v1'
LEGACY_RUN = ROOT/'data/experiments/agent3_flag_impact_live_v1'  # Committed live run with v3 cards.


def draft(work_id, **changes):
    raw = deepcopy(PREPARED['responses'][work_id]['draft'])
    raw.update(changes)
    return AdvisorDraft.model_validate(raw)


def ledger_for(d):
    return {e: {} for c in d.claims for e in c.evidence_ids}


def oks(verdicts):
    return lambda sid: verdicts.get(sid, 'SUPPORTED') == 'SUPPORTED'


# ---- Draft v11 contract -------------------------------------------------------------------------------------------

def test_detail_sentences_need_v11_and_valid_references():
    d = draft(SUBMIT)
    assert d.contract_version == 'agent3-advisor-draft-v11' and len(d.detail_sentences) == 6
    raw = PREPARED['responses'][SUBMIT]['draft']
    with pytest.raises(ValidationError, match='need draft v11'):
        AdvisorDraft.model_validate({**raw, 'contract_version': 'agent3-advisor-draft-v10'})
    bad = deepcopy(raw)
    bad['detail_sentences'][0]['depends_on'] = [2]
    with pytest.raises(ValidationError, match='earlier detail sentences'):
        AdvisorDraft.model_validate(bad)
    bad = deepcopy(raw)
    bad['detail_sentences'][0]['summary_depends_on'] = [5]
    with pytest.raises(ValidationError, match='summary sentences in this draft'):
        AdvisorDraft.model_validate(bad)
    bad = deepcopy(raw)
    bad['detail_sentences'][0]['support_claim_ids'] = ['c99']
    with pytest.raises(ValidationError, match='condense claims'):
        AdvisorDraft.model_validate(bad)


# ---- Statements, attribution and dependencies ---------------------------------------------------------------------

def test_detail_statements_carry_claim_evidence_attributions_and_dependencies():
    d = draft(SUBMIT)
    stmts = {s['statement_id']: s for s in statements(d, ledger_for(d))}
    claims = {c.claim_id: c for c in d.claims}
    d1 = stmts['detail:d1']
    assert d1['kind'] == 'DETAIL' and d1['blocking'] is False and d1['text'] == d.detail_sentences[0].text
    assert d1['evidence_ids'] == list(dict.fromkeys(e for c in ('c1', 'c5') for e in claims[c].evidence_ids))
    assert {(a['user_id'], a['evidence_id']) for a in d1['attributions']} == {
        (a.user_id, a.evidence_id) for c in ('c1', 'c5') for a in claims[c].attributions}
    assert stmts['detail:d5']['depends_on'] == ['detail:d4']
    assert all(stmts[f'summary:s{n}']['blocking'] for n in (1, 2))  # Summary rules unchanged.


def test_summary_dependency_is_an_id_of_the_summary_level():
    raw = deepcopy(PREPARED['responses'][SUBMIT]['draft'])
    raw['detail_sentences'][0]['summary_depends_on'] = [2]
    parts = detail_parts(AdvisorDraft.model_validate(raw))
    assert parts[0]['depends_on'] == ['summary:s2']


@pytest.mark.parametrize('verdicts, summary, details', [
    ({}, 2, [1, 2, 3, 4, 5, 6]),
    ({'detail:d4': 'UNSUPPORTED'}, 2, [1, 2, 3, 6]),                 # d5 depends on d4: withheld with it
    ({'claim:c9': 'UNSUPPORTED'}, 2, [1, 2, 3, 4, 5]),               # a condensed claim withheld: its sentence too
    ({'detail:d2': 'PARTIALLY_SUPPORTED'}, 2, [1, 3, 4, 5, 6]),      # unrelated sentences stay
    ({'detail:d1': 'PENDING', 'detail:d3': 'NOT_JUDGED'}, 2, [2, 4, 5, 6]),  # unjudged is never shown
])
def test_each_level_shows_only_supported_sentences_with_their_dependencies(verdicts, summary, details):
    d = draft(SUBMIT)
    text, _ = shown_summary(d, oks(verdicts))
    shown, held = shown_details(d, oks(verdicts))
    assert text == ' '.join(s.text for s in d.summary_sentences[:summary])
    assert shown == [d.detail_sentences[n - 1].text for n in details]
    if 'detail:d4' in verdicts:
        assert held == [('detail:d5', 'depends on withheld detail:d4')]


def test_a_detail_sentence_referring_to_a_withheld_summary_sentence_is_withheld():
    raw = deepcopy(PREPARED['responses'][SUBMIT]['draft'])
    raw['detail_sentences'][0]['summary_depends_on'] = [2]
    d = AdvisorDraft.model_validate(raw)
    shown, held = shown_details(d, oks({'summary:s2': 'UNSUPPORTED'}))
    assert d.detail_sentences[0].text not in shown and held[0] == ('detail:d1', 'depends on withheld summary:s2')


def test_detail_and_no_action_text_get_the_display_checks():
    d = draft(TIES)
    raw_ids = lambda issues: {i['statement_id'] for i in issues if i['code'] == 'RAW_ID_IN_PROSE'}  # noqa: E731
    assert not raw_ids(presentation_issues(d, ledger_for(d))) & {'detail:d1', 'action:no_action'}
    raw = deepcopy(PREPARED['responses'][TIES]['draft'])
    raw['detail_sentences'][0]['text'] = 'See member_4ae1700632c4a55ae1a24a4d for the tie.'
    raw['proposed_action']['rationale'] = 'Nothing to do (NO_ACTION).'
    assert {'detail:d1', 'action:no_action'} <= raw_ids(presentation_issues(AdvisorDraft.model_validate(raw), ledger_for(d)))


# ---- NO_ACTION versus withheld or unavailable ---------------------------------------------------------------------

def test_no_action_reason_is_one_non_blocking_statement():
    d = draft(TIES)
    reason = no_action_reason(d)
    assert reason and reason[0] == d.proposed_action.rationale
    s = next(s for s in statements(d, ledger_for(d)) if s['statement_id'] == 'action:no_action')
    assert (s['kind'], s['blocking']) == ('NO_ACTION_RATIONALE', False) and s['evidence_ids']
    assert not any(s['statement_id'] == 'action' for s in statements(d, ledger_for(d)))  # Bare NO_ACTION: no action text.
    unsupported = draft(TIES, evidence_sufficiency='UNSUPPORTED')
    assert no_action_reason(unsupported) is None


@pytest.mark.parametrize('card_action, proposed, verdicts, kw, status', [
    ({'action_type': 'POST_ALIGNMENT', 'rationale': 'Why.'}, {'action_type': 'POST_ALIGNMENT'}, {}, {}, 'ACTION_RECOMMENDED'),
    ({'action_type': 'NO_ACTION', 'rationale': None}, {'action_type': 'NO_ACTION'}, {'action': 'SUPPORTED'}, {}, 'NO_ACTION_NEEDED'),
    (None, {'action_type': 'NO_ACTION', 'rationale': 'R.'}, {'action:no_action': 'SUPPORTED'},
     {'no_action_rationale': 'R.'}, 'NO_ACTION_NEEDED'),
    (None, {'action_type': 'NO_ACTION', 'rationale': 'R.'}, {'action:no_action': 'PARTIALLY_SUPPORTED'}, {},
     'NO_INTERVENTION_PROPOSED'),
    (None, {'action_type': 'NO_ACTION', 'rationale': 'R.'}, {}, {}, 'NO_INTERVENTION_PROPOSED'),  # legacy: never judged
    (None, {'action_type': 'ESCALATE_ENGINEERING'}, {'action': 'NO_INTERVENTION_NEED'}, {}, 'RECOMMENDATION_WITHHELD'),
    (None, {'action_type': 'POST_ALIGNMENT'}, {'action': 'INSUFFICIENT_PREMISES'}, {}, 'RECOMMENDATION_WITHHELD'),
    (None, {'action_type': 'UPDATE_FAQ'}, {}, {'evidence_sufficiency': 'UNSUPPORTED'}, 'RECOMMENDATION_WITHHELD'),
    (None, None, {}, {}, 'NO_RECOMMENDATION_AVAILABLE'),
    (None, None, {}, {'has_draft': False}, 'NO_RECOMMENDATION_AVAILABLE'),
    (None, {'action_type': 'NO_ACTION'}, {}, {'saved': False}, 'NO_RECOMMENDATION_AVAILABLE'),
])
def test_next_step_state_comes_from_structured_results_only(card_action, proposed, verdicts, kw, status):
    state = next_step_state(card_action, proposed, verdicts, **{'has_draft': True, **kw})
    assert state['status'] == status
    if status in ('NO_INTERVENTION_PROPOSED', 'RECOMMENDATION_WITHHELD', 'NO_RECOMMENDATION_AVAILABLE'):
        assert state['rationale'] is None and state['explanation']
    if status == 'NO_INTERVENTION_PROPOSED':
        assert "not a confirmed decision" in state['explanation']


def test_an_absent_action_is_never_read_as_no_action_needed():
    for verdicts in ({}, {'action:no_action': 'UNSUPPORTED'}, {'action': 'PENDING'}):
        assert next_step_state(None, {'action_type': 'NO_ACTION', 'rationale': 'x'}, verdicts,
                               has_draft=True)['status'] != 'NO_ACTION_NEEDED'


def test_card_v4_ties_the_next_step_to_the_action_it_shows():
    card = next(c for c in json.loads((PREPARED_RUN/'cards.json').read_text(encoding='utf-8'))
                if c['next_step']['status'] == 'ACTION_RECOMMENDED')
    AdviceCardV4.model_validate(card)
    for status in ('NO_ACTION_NEEDED', 'NO_INTERVENTION_PROPOSED', 'RECOMMENDATION_WITHHELD'):
        with pytest.raises(ValidationError, match='ACTION_RECOMMENDED exactly when'):
            AdviceCardV4.model_validate({**card, 'next_step': {'status': status, 'rationale': None, 'explanation': 'x'}})
    with pytest.raises(ValidationError, match='shows no action'):
        AdviceCardV4.model_validate({**card, 'card_line': 'NEEDS_REVIEW', 'recommended_action': None,
                                     'needs_review_reasons': card['needs_review_reasons'] or [
                                         {'code': 'OTHER', 'detail': 'x'}],
                                     'next_step': {'status': 'RECOMMENDATION_WITHHELD', 'rationale': 'Model text.',
                                                   'explanation': 'x'}})


# ---- The prepared run end to end (PREPARED, SCRIPTED_MOCK) ---------------------------------------------------------

def prepared_cards():
    return {c['lineage'].get('topic_id') or 'gap:' + c['lineage']['candidate_group_id']: c
            for c in json.loads((PREPARED_RUN/'cards.json').read_text(encoding='utf-8'))}


def test_prepared_run_keeps_review_status_and_states_the_next_step():
    cards = prepared_cards()
    submit, ties, greet = cards['gap:routed_440e64c7fbdcc49f'], cards['cluster_f944891544b06f79/topic_1'], cards[
        'cluster_be4e3bac742eccb3/topic_1']
    # Submit: a withheld detail sentence is not a review reason; the card keeps severity and inherited flags.
    assert {r['code'] for r in submit['needs_review_reasons']} == {'HIGH_SEVERITY', 'INHERITED_FLAG'}
    assert submit['checks']['grounding'] == 'PASSED' and len(submit['details']) == 4
    assert {f['kind'] for f in submit['inherited_flags']} == {'inherited_agent1_review', 'projection_gap'}
    # Cosmetic ties: a supported NO_ACTION reason, while the failed severity assessment still requires review.
    assert ties['next_step']['status'] == 'NO_ACTION_NEEDED' and ties['card_line'] == 'NEEDS_REVIEW'
    assert {r['code'] for r in ties['needs_review_reasons']} == {'GROUNDING_FAILURE', 'OTHER'}
    assert ties['severity']['assessment_status'] == 'UNASSESSED'
    assert greet['card_line'] == 'OBSERVATION' and greet['next_step']['status'] == 'NO_ACTION_NEEDED' and greet['details'] == []
    brief = json.loads((PREPARED_RUN/'morning_brief.json').read_text(encoding='utf-8'))
    assert brief['accounting']['status'] == 'COMPLETE' and brief['counts']['review_queue_items'] == 52


def test_withheld_detail_sentences_are_listed_for_review_not_shown():
    topic = json.loads((PREPARED_RUN/'topics/gap__routed_440e64c7fbdcc49f.json').read_text(encoding='utf-8'))['result']
    held = {d['statement_id']: d for d in topic['diagnostics'] if d.get('code') == 'WITHHELD_STATEMENT'}
    assert held['detail:d4']['verdict'] == 'UNSUPPORTED' and held['detail:d5']['withheld_because'] == 'depends on withheld detail:d4'
    card = prepared_cards()['gap:routed_440e64c7fbdcc49f']
    assert held['detail:d4']['text'] not in card['details'] and held['detail:d5']['text'] not in card['details']
    run = Catalog([PREPARED_RUN.parent]).get(PREPARED_RUN.name)
    view = run.review(card['card_id'])
    assert {w['statement_id'] for w in view['withheld']} >= {'detail:d4', 'detail:d5'}
    assert next(w for w in view['withheld'] if w['statement_id'] == 'detail:d4')['field'] == 'What happened, sentence 4'


# ---- Flag catalogues and bindings ---------------------------------------------------------------------------------

def test_new_statements_enter_the_flag_catalogue_and_dependency_elements():
    d = draft(SUBMIT)
    stmts = statements(d, ledger_for(d))
    members = ['member_92cea4511885f2a7a0f35d94']
    catalogue = fi.catalogue(stmts, members, [])
    assert {'detail:d1', 'detail:d6', 'summary:s1'} <= set(catalogue)
    assert _element('detail:d3') == 'SUMMARY' and _element('action:no_action') == 'ACTION_RATIONALE'
    assert _element('action:rationale') == 'ACTION_RATIONALE' and _element('action') == 'ACTION'


def test_card_text_binding_covers_v4_fields_and_keeps_v3_digests():
    card = prepared_cards()['gap:routed_440e64c7fbdcc49f']
    v3_like = {k: v for k, v in card.items() if k not in ('details', 'next_step')}
    assert fi.card_text(card) != fi.card_text(v3_like)
    assert fi.card_text({**card, 'details': card['details'][:1]}) != fi.card_text(card)


def test_flag_impact_stays_off_by_default():
    import inspect
    assert inspect.signature(pilot.advise).parameters['flag_impact'].default is False


# ---- Legacy cards and frozen runs ---------------------------------------------------------------------------------

def tree_hash(root):
    h = sha256()
    for path in sorted(Path(root).rglob('*')):
        if path.is_file():
            h.update(path.relative_to(root).as_posix().encode() + b'\0' + path.read_bytes())
    return h.hexdigest()


def test_legacy_v3_cards_load_unchanged_with_a_derived_state():
    before = tree_hash(LEGACY_RUN)
    run = Catalog([LEGACY_RUN.parent]).get(LEGACY_RUN.name)
    for card_id, card in run.cards.items():
        assert card['contract_version'] == 'agent3-advice-card-v3' and 'next_step' not in card
        validate_card(card)
        view = run.presentation(card_id)
        assert view['next_step']['derived'] and view['details'] == {
            'source': 'SAVED_REASONING', 'sentences': [], 'findings': card['reasoning']}
        if card['recommended_action'] is None:
            assert view['next_step']['status'] != 'NO_ACTION_NEEDED'
    assert tree_hash(LEGACY_RUN) == before


def test_unknown_card_contracts_are_refused():
    card = next(iter(json.loads((PREPARED_RUN/'cards.json').read_text(encoding='utf-8'))))
    with pytest.raises(ValueError, match='Unsupported card contract'):
        validate_card({**card, 'contract_version': 'agent3-advice-card-v9'})


# ---- Prompts ------------------------------------------------------------------------------------------------------

def test_prompts_v18_define_each_field_once_and_judge_the_new_kinds():
    assert pilot.PROMPT_VERSION == 'agent3-advisor-prompts-v18'
    guide = pilot.WRITING_GUIDE
    for phrase in ('about 35-55 words', 'about 15-25 words', 'detail_sentences (the opened card', 'summary_depends_on',
                   'State a diagnostic request or a missing detail once'):
        assert phrase in guide
    assert 'why that helps and any explanatory context' not in guide  # Replaced, not appended.
    for phrase in ('A DETAIL sentence (statement_id detail:d1', 'NO_ACTION_RATIONALE is the advisor', 'SUMMARY, DETAIL, ACTION'):
        assert phrase in pilot.GROUNDING_RULES
    assert pilot.AdvisorDraft.model_fields['contract_version'].default == 'agent3-advisor-draft-v11'


# ---- Decisions on v4 cards ----------------------------------------------------------------------------------------

def test_decisions_on_v4_cards_save_and_render_the_approved_text(tmp_path):
    catalog = Catalog([PREPARED_RUN.parent])
    run = catalog.get(PREPARED_RUN.name)
    client = TestClient(create_app(catalog=catalog, store=DecisionStore(tmp_path/'store.sqlite3'), decision_origin='TEST',
                                   static_dir=tmp_path/'none'))
    brief = client.get(f'/api/runs/{run.key}/brief').json()
    assert all(c['presentation']['next_step']['derived'] is False for c in brief['cards'])
    rec = next(c['card'] for c in brief['cards'] if c['card']['card_line'] == 'RECOMMENDED_ACTION')
    reply = client.post(f"/api/runs/{run.key}/cards/{rec['card_id']}/decisions", json={'kind': 'APPROVE_ACTION', 'actor_id': 'U001'},
                        headers={'Idempotency-Key': 'test-v4-approve'})
    assert reply.status_code == 201, reply.text
    entry = reply.json()['entry']
    assert entry['text']['model_grounded_text'] == rec['recommended_action']['draft_text']
    assert entry['decision']['execution']['state'] == 'NOT_EXECUTED'
    review = next(c['card'] for c in brief['cards'] if c['card']['card_line'] == 'NEEDS_REVIEW')
    dismissed = client.post(f"/api/runs/{run.key}/cards/{review['card_id']}/decisions",
                            json={'kind': 'DISMISS', 'actor_id': 'U001', 'note': 'Checked.'}, headers={'Idempotency-Key': 'test-v4-dismiss'})
    assert dismissed.status_code == 201, dismissed.text
    assert client.get(f'/api/runs/{run.key}/decisions').json()['decisions'][0]['card_id'] in (rec['card_id'], review['card_id'])
