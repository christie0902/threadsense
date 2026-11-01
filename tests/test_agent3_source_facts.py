"""Descriptive source claims, governing guidance and action dependencies (agent3_request_kind_v1 withheld the Submit
action: an accurate description of an example-collection announcement was filed as GUIDANCE, voided because the
announcement does not govern the topic's handling, and the action's scope note leaned on it). RECORDED tests read
saved runs unchanged; PREPARED tests script the judge (labelled); everything else is DETERMINISTIC."""
import json

import pytest

from threadsense.agents.advisor_checks import _effective, claim_issues, normalize, statements
from threadsense.agents.advisor_contracts import AdvisorDraft, StatementVerdict  # noqa: F401
from threadsense.agents.advisor_pilot import DRAFT_RULES, GROUNDING_RULES, REVISION_RULES, WRITING_GUIDE, _json_text
from threadsense.handoff_inputs import ROOT
from tests.test_agent3_advisor import (  # noqa: F401 - fixtures reused
    Fake, codes, draft_for, retriever, run, supported, view,
)

RUN = ROOT/'data/experiments/agent3_request_kind_v1'
ANNOUNCEMENT = 'k:slack:C_RP_ANNOUNCEMENTS:1790888971.000030:7db831c7'
ENGINEER = ['m:C_RP_GENERAL:1790873502.000226', 'm:C_RP_GENERAL:1790905427.000226']


@pytest.fixture(scope='module')
def recorded():
    result = json.loads(next((RUN/'topics').glob('*.json')).read_text(encoding='utf-8'))['result']
    raw = json.loads(_json_text(next(c['raw'] for c in result['model_calls'] if c['stage'] == 'revision')))
    return result, raw, result['evidence_ledger']


def claim(raw, cid):
    return next(c for c in raw['claims'] if c['claim_id'] == cid)


def draft_with(raw, **changes):
    return AdvisorDraft.model_validate({**raw, 'contract_version': 'agent3-advisor-draft-v10', **changes})


def test_recorded_c11_only_describes_the_announcement(recorded):
    """RECORDED. c11 says what the announcement asks (examples in its thread) and denies that it names an intake route;
    it was filed as GUIDANCE, voided because the announcement does not govern the topic's handling. The judge left it
    out of the essential premises; the action was still insufficient because its scope note leaned on it."""
    result, raw, ledger = recorded
    c11 = claim(raw, 'c11')
    assert c11['kind'] == 'GUIDANCE' and c11['evidence_ids'] == [ANNOUNCEMENT]
    assert 'keep examples in its thread' in c11['text'] and 'does not name that thread as an engineering intake route' in c11['text']
    assert 'Please keep examples in this thread' in ledger[ANNOUNCEMENT]['excerpt']
    verdicts = {s['statement_id']: s['verdict'] for s in result['grounding']['statements']}
    assert verdicts['claim:c11'] == 'ANNOUNCEMENT_NOT_VERIFIED' and verdicts[f'announcement:{ANNOUNCEMENT}'] == 'UNSUPPORTED'
    action = raw['proposed_action']
    assert 'c11' in action['support_claim_ids'] and 'announcement thread is for example collection' in action['scope_note']
    sufficiency = result['grounding']['action_sufficiency']
    assert 'claim:c11' not in sufficiency['essential_statement_ids'] and sufficiency['verdict'] == 'INSUFFICIENT'


def test_accurate_description_is_descriptive_evidence_not_governing_guidance(recorded):
    """The same text as a SOURCE_FACT passes the structural checks and is not voided by the announcement's failed
    applicability; as GUIDANCE it still is (authority checks unchanged)."""
    _, raw, ledger = recorded
    as_fact = draft_with(raw, claims=[{**c, 'kind': 'SOURCE_FACT'} if c['claim_id'] == 'c11' else c for c in raw['claims']])
    assert [i for i in claim_issues(as_fact, ledger) if i['statement_id'] == 'claim:c11'] == []
    verdicts = {'claim:c11': 'SUPPORTED', f'announcement:{ANNOUNCEMENT}': 'UNSUPPORTED'}
    assert _effective(as_fact, ledger, verdicts)['claim:c11'] == 'SUPPORTED'
    as_guidance = draft_with(raw)
    assert _effective(as_guidance, ledger, verdicts)['claim:c11'] == 'ANNOUNCEMENT_NOT_VERIFIED'
    stmt = next(s for s in statements(as_fact, ledger) if s['statement_id'] == 'claim:c11')
    assert stmt['kind'] == 'CLAIM_SOURCE_FACT' and stmt['evidence_ids'] == [ANNOUNCEMENT]


def test_source_facts_cite_retrieved_sources_and_keep_their_dates(recorded):
    _, raw, ledger = recorded
    member = draft_with(raw, claims=[{**c, 'kind': 'SOURCE_FACT'} if c['claim_id'] == 'c6' else c for c in raw['claims']])
    assert 'SOURCE_FACT_NEEDS_RETRIEVED_SOURCE' in [i['code'] for i in claim_issues(member, ledger) if i['statement_id'] == 'claim:c6']
    history = {**ledger, 'k:old': {**ledger[ANNOUNCEMENT], 'evidence_id': 'k:old', 'use': 'HISTORY_ONLY'}}
    stale = draft_with(raw, claims=raw['claims'] + [{'claim_id': 'c99', 'kind': 'SOURCE_FACT', 'evidence_ids': ['k:old'],
                                                     'text': 'The old note currently asks for examples in its thread.'}])
    assert 'SOURCE_FACT_PRESENTS_HISTORY_AS_CURRENT' in [i['code'] for i in claim_issues(stale, history) if i['statement_id'] == 'claim:c99']


def test_rejected_guidance_is_not_reclassified_automatically(recorded):
    """No normalization turns a voided GUIDANCE claim into a harmless fact; the classification is the draft's."""
    _, raw, ledger = recorded
    fixed, notes = normalize(draft_with(raw), ledger)
    assert claim(json.loads(fixed.model_dump_json()), 'c11')['kind'] == 'GUIDANCE'
    assert not [n for n in notes if n['statement_id'] == 'claim:c11']


def test_engineer_request_classification_is_unchanged(recorded):
    result, raw, ledger = recorded
    c6 = claim(raw, 'c6')
    assert c6['kind'] == 'INCIDENT_FACT' and c6['evidence_ids'] == ENGINEER and c6['text'].startswith('An engineer asks')
    fixed, notes = normalize(draft_with(raw), ledger)
    assert claim(json.loads(fixed.model_dump_json()), 'c6')['kind'] == 'INCIDENT_FACT' and not [
        n for n in notes if n['statement_id'] == 'claim:c6']
    assert {s['statement_id']: s['verdict'] for s in result['grounding']['statements']}['claim:c6'] == 'SUPPORTED'


# --- Action dependencies (DETERMINISTIC routing over PREPARED verdicts) ---------------------------------------------

def sufficient(essential):
    from threadsense.agents.advisor_contracts import ActionSufficiency
    return ActionSufficiency(verdict='SUFFICIENT', essential_statement_ids=essential, rationale='Prepared.')


def test_context_claims_feed_the_rationale_not_the_action_premises(recorded):
    _, raw, ledger = recorded
    action = {**raw['proposed_action'], 'support_claim_ids': ['c1', 'c2', 'c3', 'c4', 'c5', 'c6'], 'context_claim_ids': ['c11'],
              'scope_note': None,
              'rationale': 'The batch announcement only asks for examples in its thread, so the report goes to engineering directly.'}
    draft = draft_with(raw, proposed_action=action,
                       claims=[{**c, 'kind': 'SOURCE_FACT'} if c['claim_id'] == 'c11' else c for c in raw['claims']])
    stmts = {s['statement_id']: s for s in statements(draft, ledger)}
    assert 'claim:c11' not in stmts['action']['premises'] and ANNOUNCEMENT not in stmts['action']['evidence_ids']
    assert ANNOUNCEMENT in stmts['action:rationale']['evidence_ids']
    with pytest.raises(ValueError):
        AdvisorDraft.model_validate({**raw, 'contract_version': 'agent3-advisor-draft-v10',
                                     'proposed_action': {**action, 'context_claim_ids': ['c1']}})
    with pytest.raises(ValueError):  # Context claims need draft v10.
        AdvisorDraft.model_validate({**raw, 'contract_version': 'agent3-advisor-draft-v9', 'proposed_action': action})


def test_essential_routing_premise_resting_on_a_non_governing_announcement_withholds_the_action(recorded):
    """A destination premise filed as GUIDANCE on the example-collection announcement: when the announcement is not
    verified as governing that use, the premise is voided and the action falls (also when the judge called it
    sufficient), as in agent3_acceptance_v1 (submit_failure: ESSENTIAL_PREMISE_NOT_PASSED)."""
    _, raw, ledger = recorded
    draft = draft_with(raw)
    verdicts = {f'claim:c{i}': 'SUPPORTED' for i in range(1, 12)} | {'action': 'SUPPORTED', f'announcement:{ANNOUNCEMENT}': 'UNSUPPORTED'}
    out = _effective(draft, ledger, verdicts, sufficient(['claim:c1', 'claim:c11']))
    assert out['action'] == 'ESSENTIAL_PREMISE_VOIDED_BY_DEPENDENCY'
    applicable = _effective(draft, ledger, {**verdicts, f'announcement:{ANNOUNCEMENT}': 'SUPPORTED'}, sufficient(['claim:c1', 'claim:c11']))
    assert applicable['action'] == 'SUPPORTED'  # a genuinely applicable directive supports its destination
    acceptance = json.loads((ROOT/'data/experiments/agent3_acceptance_v1/results/submit_failure.json').read_text(encoding='utf-8'))
    assert {s['statement_id']: s['verdict'] for s in acceptance['grounding']['statements']}['action'] == 'ESSENTIAL_PREMISE_NOT_PASSED'


def test_failed_optional_premise_alone_does_not_block_a_sufficient_action(recorded):
    _, raw, ledger = recorded
    verdicts = {f'claim:c{i}': 'SUPPORTED' for i in range(1, 12)} | {'action': 'SUPPORTED', f'announcement:{ANNOUNCEMENT}': 'UNSUPPORTED'}
    out = _effective(draft_with(raw), ledger, verdicts, sufficient(['claim:c1', 'claim:c5', 'claim:c6']))
    assert out['claim:c11'] == 'ANNOUNCEMENT_NOT_VERIFIED' and out['action'] == 'SUPPORTED'


def test_rules_state_the_distinctions():
    for rules in (DRAFT_RULES, REVISION_RULES):
        assert 'write a SOURCE_FACT claim citing it' in rules and 'An announcement governs only what it directs' in rules
        assert 'go in context_claim_ids' in rules
    assert 'only conditions and limits the action depends on' in WRITING_GUIDE
    assert 'CLAIM_SOURCE_FACT is SUPPORTED if the cited source says it' in GROUNDING_RULES
    assert 'governs only what it directs' in GROUNDING_RULES
    assert 'a listed premise the text does not rely on is not essential' in GROUNDING_RULES


# --- End to end (PREPARED judge; the advisor's own routing and display) ----------------------------------------------

def escalation(payload, *, instruction, rationale, context=True):
    base = draft_for(payload)
    by = {i['evidence_id']: i for i in payload['member_evidence']}
    reporters = [i['evidence_id'] for i in payload['member_evidence'] if i['author_id'] == i['thread_starter_id']][:2]
    engineer = [e for e in ENGINEER if e in by]
    guide = next(i['evidence_id'] for i in payload['retrieved_evidence'] if i['use'] == 'PRIOR_DECISION')
    claims = [{'claim_id': 'c1', 'kind': 'INCIDENT_FACT', 'text': 'Two members report a Submit problem.', 'evidence_ids': reporters},
              {'claim_id': 'c2', 'kind': 'INCIDENT_FACT', 'evidence_ids': engineer,
               'text': 'An engineer asks for the LT error state and time on tasks RP-3412 and RP-5337.',
               'attributions': [{'user_id': by[e]['author_id'], 'relation': 'AUTHOR', 'evidence_id': e} for e in engineer]},
              {'claim_id': 'c3', 'kind': 'SOURCE_FACT', 'evidence_ids': [guide],
               'text': 'An earlier record describes a similar Submit report.'}]
    return {**base, 'contract_version': 'agent3-advisor-draft-v10', 'claims': claims, 'proposed_action': {
        'action_type': 'ESCALATE_ENGINEERING', 'instruction': instruction, 'rationale': rationale,
        'draft_text': 'Submit problems on RP-3412 and RP-5337 need investigation.', 'support_claim_ids': ['c1', 'c2'],
        'context_claim_ids': ['c3'] if context else [], 'intervention_need': {
            'kind': 'OPERATIONAL_PROBLEM', 'statement': 'Submissions remain unverified.', 'evidence_ids': reporters}}}


INSTRUCTION = 'Report the submission problems to engineering with the LT error state and time the engineer asked for.'


def test_escalation_from_incident_facts_and_requests_survives_a_failed_optional_note(retriever, view):
    """PREPARED judge: the rationale (explanatory context) is UNSUPPORTED. The action, supported by incident facts and
    the engineer's request, is shown with its exact judged wording; the rationale is withheld."""
    rationale = 'An earlier record shows engineering already fixed this, so they can check quickly.'
    client = Fake(draft=lambda p: escalation(p, instruction=INSTRUCTION, rationale=rationale),
                  grounding=lambda p: supported(p, **{'action:rationale': 'UNSUPPORTED'}))
    result = run('submit_failure', client, retriever, view)
    action = result['card']['recommended_action']
    assert action['instruction'] == INSTRUCTION and action['rationale'] is None
    assert action['draft_text'] == 'Submit problems on RP-3412 and RP-5337 need investigation.'
    assert rationale not in json.dumps(result['card'])


def test_unsupported_destination_still_withholds_the_whole_action(retriever, view):
    instruction = 'Send the error states through the announcement\'s example thread as the engineering intake.'

    def judge(p):
        out = supported(p, action='PARTIALLY_SUPPORTED')
        out['action_sufficiency'] = {**out['action_sufficiency'], 'verdict': 'INSUFFICIENT',
                                     'rationale': 'Nothing establishes that thread as an intake route.'}
        return out
    result = run('submit_failure', Fake(draft=lambda p: escalation(p, instruction=instruction, rationale='Faster.'),
                                        grounding=judge), retriever, view)
    assert result['card']['recommended_action'] is None and 'example thread' not in json.dumps(result['card'])
