"""Participant requests versus team-lead instructions (agent3_submit_repair_v1 withheld the Submit action because an
engineer's request was labelled THREAD_INSTRUCTION). RECORDED tests read that run unchanged; PREPARED tests script the
judge (labelled); normalization and checks are DETERMINISTIC."""
import json

import pytest

from threadsense.agents.advisor_checks import claim_issues, normalize, statements
from threadsense.agents.advisor_contracts import AdvisorDraft
from threadsense.agents.advisor_evidence import model_view
from threadsense.agents.advisor_pilot import DRAFT_RULES, GROUNDING_RULES, REVISION_RULES, ReplayClient, _json_text
from threadsense.handoff_inputs import ROOT
from tests.test_agent3_advisor import (  # noqa: F401 - fixtures reused
    Fake, codes, draft_for, retriever, run, supported, view,
)

RUN = ROOT/'data/experiments/agent3_submit_repair_v1'
ENGINEER = ['m:C_RP_GENERAL:1790873502.000226', 'm:C_RP_GENERAL:1790905427.000226']  # U016, ENGINEER
TEAM_LEAD = 'm:C_RP_GENERAL:1790873555.000339'  # U001, TEAM_LEAD
QA = 'm:C_RP_GENERAL:1790873462.000113'  # U008, QA_TUTOR


@pytest.fixture(scope='module')
def recorded():
    result = json.loads(next((RUN/'topics').glob('*.json')).read_text(encoding='utf-8'))['result']
    raw = json.loads(_json_text(next(c['raw'] for c in result['model_calls'] if c['stage'] == 'draft')))
    return result, raw, result['evidence_ledger']


def with_claim(raw, **claim):
    """The recorded draft with claim c5 replaced (kind, text, evidence, attributions as given)."""
    old = next(c for c in raw['claims'] if c['claim_id'] == 'c5')
    return AdvisorDraft.model_validate({**raw, 'claims': [{**old, **claim} if c['claim_id'] == 'c5' else c for c in raw['claims']]})


def c5(draft):
    return next(c for c in draft.claims if c.claim_id == 'c5')


def rejected(draft, ledger):
    return [i['code'] for i in claim_issues(draft, ledger) if i['statement_id'] == 'claim:c5']


def test_recorded_claim_has_only_a_wrong_category(recorded):
    """RECORDED. The rejected claim names the engineer correctly and attributes both cited messages to that engineer;
    only its kind says THREAD_INSTRUCTION, which needs a team lead's own message."""
    result, raw, ledger = recorded
    claim = next(c for c in raw['claims'] if c['claim_id'] == 'c5')
    assert claim['kind'] == 'THREAD_INSTRUCTION' and claim['text'].startswith('An engineer requests')
    assert claim['evidence_ids'] == ENGINEER and {(a['user_id'], a['relation']) for a in claim['attributions']} == {('U016', 'AUTHOR')}
    assert {ledger[e]['author_role'] for e in ENGINEER} == {'ENGINEER'}
    verdict = next(s for s in result['grounding']['statements'] if s['statement_id'] == 'claim:c5')['verdict']
    assert verdict == 'REJECTED_THREAD_INSTRUCTION_WITHOUT_TEAM_LEAD'


def test_engineer_request_is_relabelled_before_grounding_with_text_and_links_unchanged(recorded):
    """RECORDED + DETERMINISTIC. Category-only mismatch: relabelled INCIDENT_FACT before checks, recorded, the text,
    evidence and attributions unchanged; the task references stay linked to the engineer's own messages."""
    _, raw, ledger = recorded
    draft = AdvisorDraft.model_validate(raw)
    fixed, notes = normalize(draft, ledger)
    assert c5(fixed).kind == 'INCIDENT_FACT' and c5(fixed).text == c5(draft).text
    assert c5(fixed).evidence_ids == ENGINEER and c5(fixed).attributions == c5(draft).attributions
    [note] = [n for n in notes if n['statement_id'] == 'claim:c5']
    assert (note['code'], note['from'], note['to']) == ('REQUEST_KIND_CORRECTED', 'THREAD_INSTRUCTION', 'INCIDENT_FACT')
    assert rejected(fixed, ledger) == []
    assert 'RP-3412' in ledger[ENGINEER[0]]['excerpt'] and 'RP-5337' in ledger[ENGINEER[1]]['excerpt']
    stmt = next(s for s in statements(fixed, ledger) if s['statement_id'] == 'claim:c5')
    assert stmt['kind'] == 'CLAIM_INCIDENT_FACT' and stmt['evidence_ids'] == ENGINEER


def test_changed_classification_needs_a_new_judgment(recorded):
    """RECORDED. Same text as the recorded claim but a new kind: replay has no verdict to reuse for it."""
    result, raw, ledger = recorded
    fixed, _ = normalize(AdvisorDraft.model_validate(raw), ledger)
    stmt = next(s for s in statements(fixed, ledger) if s['statement_id'] == 'claim:c5')
    client = ReplayClient(RUN)
    client.grounding_inputs_same = True  # isolate the statement-level binding
    payload = {'scenario_id': result['scenario']['id'], 'statements': [stmt],
               'member_threads': [{'evidence_id': e} for e in ledger if e.startswith('m:')],
               'retrieved_sources': [{'evidence_id': e} for e in ledger if not e.startswith('m:')]}
    assert client._judgment(payload, client.recorded[payload['scenario_id']])['verdicts'] == []
    assert client.reuse_log[-1]['reason'] == 'content changed'


def test_team_lead_instruction_keeps_its_classification(recorded):
    _, raw, ledger = recorded
    draft = with_claim(raw, kind='THREAD_INSTRUCTION', evidence_ids=[TEAM_LEAD],
                       text='In that thread, the team lead asks for the task ID, required-field state and exact button behavior.',
                       attributions=[{'user_id': 'U001', 'relation': 'AUTHOR', 'evidence_id': TEAM_LEAD}])
    fixed, notes = normalize(draft, ledger)
    assert c5(fixed).kind == 'THREAD_INSTRUCTION' and not [n for n in notes if n['statement_id'] == 'claim:c5']
    assert rejected(fixed, ledger) == []


def test_qa_request_is_a_reported_request_never_policy(recorded):
    """A QA tutor's request labelled THREAD_INSTRUCTION becomes a reported request; labelled GUIDANCE it is not turned
    into anything and still fails (thread messages without a team lead are not guidance)."""
    _, raw, ledger = recorded
    claim = dict(evidence_ids=[QA], text='A QA tutor asks whether any required rating fields are unset.',
                 attributions=[{'user_id': 'U008', 'relation': 'AUTHOR', 'evidence_id': QA}])
    fixed, _ = normalize(with_claim(raw, kind='THREAD_INSTRUCTION', **claim), ledger)
    assert c5(fixed).kind == 'INCIDENT_FACT' and rejected(fixed, ledger) == []
    guidance, notes = normalize(with_claim(raw, kind='GUIDANCE', **claim), ledger)
    assert c5(guidance).kind == 'GUIDANCE' and 'GUIDANCE_WITHOUT_CURRENT_SOURCE' in rejected(guidance, ledger)
    assert not [n for n in notes if n['statement_id'] == 'claim:c5']


@pytest.mark.parametrize('text, attributions, evidence', [
    # The prose names the wrong actor.
    ('The team lead requests the LT error state and time for tasks RP-3412 and RP-5337.',
     [{'user_id': 'U016', 'relation': 'AUTHOR', 'evidence_id': ENGINEER[0]}, {'user_id': 'U016', 'relation': 'AUTHOR', 'evidence_id': ENGINEER[1]}],
     ENGINEER),
    # The prose asserts authority.
    ('An engineer instructs tutors to capture the LT error state and time for tasks RP-3412 and RP-5337.',
     [{'user_id': 'U016', 'relation': 'AUTHOR', 'evidence_id': ENGINEER[0]}, {'user_id': 'U016', 'relation': 'AUTHOR', 'evidence_id': ENGINEER[1]}],
     ENGINEER),
    # The attribution names someone who did not write the cited message.
    ('An engineer requests the LT error state and time for task RP-3412.',
     [{'user_id': 'U005', 'relation': 'AUTHOR', 'evidence_id': ENGINEER[0]}], ENGINEER[:1]),
    # No requester is named at all (ambiguous).
    ('The LT error state and time for task RP-3412 should be captured.',
     [{'user_id': 'U016', 'relation': 'AUTHOR', 'evidence_id': ENGINEER[0]}], ENGINEER[:1]),
])
def test_wrong_actor_authority_or_ambiguity_is_not_normalized_and_still_fails(recorded, text, attributions, evidence):
    _, raw, ledger = recorded
    fixed, notes = normalize(with_claim(raw, kind='THREAD_INSTRUCTION', text=text, attributions=attributions,
                                        evidence_ids=evidence), ledger)
    assert c5(fixed).kind == 'THREAD_INSTRUCTION' and not [n for n in notes if n['statement_id'] == 'claim:c5']
    assert 'THREAD_INSTRUCTION_WITHOUT_TEAM_LEAD' in rejected(fixed, ledger)


def test_mixed_claim_citing_a_team_lead_keeps_the_existing_rule(recorded):
    _, raw, ledger = recorded
    fixed, notes = normalize(with_claim(raw, kind='THREAD_INSTRUCTION', evidence_ids=[ENGINEER[0], TEAM_LEAD],
                                        text='An engineer and the team lead ask for diagnostics on task RP-3412.',
                                        attributions=[{'user_id': 'U016', 'relation': 'AUTHOR', 'evidence_id': ENGINEER[0]},
                                                      {'user_id': 'U001', 'relation': 'AUTHOR', 'evidence_id': TEAM_LEAD}]), ledger)
    assert c5(fixed).kind == 'THREAD_INSTRUCTION' and not [n for n in notes if n['statement_id'] == 'claim:c5']


def test_member_messages_state_who_may_instruct_and_rules_explain_it(recorded):
    _, _, ledger = recorded
    assert model_view(ledger[TEAM_LEAD])['instruction_authority'] == 'THREAD_SCOPE'
    assert {model_view(ledger[e])['instruction_authority'] for e in ENGINEER + [QA]} == {'NONE'}
    for rules in (DRAFT_RULES, REVISION_RULES):
        assert 'is an INCIDENT_FACT naming who asked' in rules and 'a reported request with no authority' in rules
    assert 'A request by anyone but a team lead is a CLAIM_INCIDENT_FACT' in GROUNDING_RULES


# --- End to end (PREPARED judge) ------------------------------------------------------------------------------------

def request_draft(instruction, kind='THREAD_INSTRUCTION'):
    def draft(payload):
        base = draft_for(payload)
        by = {i['evidence_id']: i for i in payload['member_evidence']}
        engineer = [e for e in ENGINEER if e in by]
        reporters = [i['evidence_id'] for i in payload['member_evidence'] if i['author_id'] == i['thread_starter_id']][:2]
        assert len(engineer) == 2
        return {**base, 'claims': [
            {'claim_id': 'c1', 'kind': 'INCIDENT_FACT', 'text': 'Two members report a Submit problem.', 'evidence_ids': reporters},
            {'claim_id': 'c2', 'kind': kind, 'evidence_ids': engineer,
             'text': 'An engineer requests the LT error state and time for tasks RP-3412 and RP-5337.',
             'attributions': [{'user_id': by[e]['author_id'], 'relation': 'AUTHOR', 'evidence_id': e} for e in engineer]}],
            'proposed_action': {'action_type': 'ESCALATE_ENGINEERING', 'instruction': instruction,
                                'draft_text': 'Submit problems on RP-3412 and RP-5337 need investigation.',
                                'support_claim_ids': ['c1', 'c2'], 'intervention_need': {
                                    'kind': 'OPERATIONAL_PROBLEM', 'statement': 'Submissions remain unverified.',
                                    'evidence_ids': reporters}}}
    return draft


def test_engineer_request_supports_diagnostic_collection(retriever, view):
    """PREPARED judge. Mislabelled as an instruction, the engineer's request is relabelled before grounding, reaches the
    judge as a reported fact and, judged SUPPORTED with a sufficient action, supports the escalation shown as generated."""
    instruction = 'Report the submission problems to engineering with the LT error state and time the engineer asked for.'
    client = Fake(draft=request_draft(instruction), grounding=supported)
    result = run('submit_failure', client, retriever, view)
    assert result['card']['recommended_action']['instruction'] == instruction
    corrected = [d for d in result['diagnostics'] if d.get('code') == 'REQUEST_KIND_CORRECTED']
    assert [d['statement_id'] for d in corrected] == ['claim:c2']
    kinds = {s['statement_id']: s['kind'] for s in result['grounding']['statements']}
    assert kinds['claim:c2'] == 'CLAIM_INCIDENT_FACT' and 'GROUNDING_FAILURE' not in codes(result)


def test_unsupported_destination_still_fails_with_a_valid_request_premise(retriever, view):
    """PREPARED judge (insufficient for the named thread). A valid request premise does not rescue an unsupported
    destination; the action is withheld whole."""
    instruction = 'Collect the error states in the existing example thread and send engineering a consolidated update.'

    def judge(p):
        out = supported(p, action='PARTIALLY_SUPPORTED')
        out['action_sufficiency'] = {**out['action_sufficiency'], 'verdict': 'INSUFFICIENT',
                                     'rationale': 'Nothing establishes the example thread as an intake route.'}
        return out
    result = run('submit_failure', Fake(draft=request_draft(instruction), grounding=judge), retriever, view)
    assert result['card']['recommended_action'] is None and 'example thread' not in json.dumps(result['card'])
