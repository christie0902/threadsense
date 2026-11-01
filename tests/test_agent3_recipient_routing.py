"""One recipient/route rule for drafting and grounding (prompts v14). agent3_source_fact_v1 withheld "report the current
submission failures to engineering" because the v13 grounding rules required a premise establishing a route for any
destination, while the draft rules allowed an unspecified one. RECORDED tests read that run unchanged; PREPARED tests
script the judge (labelled); everything else is DETERMINISTIC."""
import json

import pytest

from threadsense.agents.advisor_pilot import (
    DRAFT_RULES, GROUNDING_RULES, PROMPT_VERSION, REVISION_RULES, ROUTING_RULE, grounding_inputs, prompt_fingerprints,
)
from threadsense.handoff_inputs import ROOT
from tests.test_agent3_advisor import (  # noqa: F401 - fixtures reused
    Fake, draft_for, retriever, run, supported, view,
)

RUN = ROOT/'data/experiments/agent3_source_fact_v1'
ENGINEER = ['m:C_RP_GENERAL:1790873502.000226', 'm:C_RP_GENERAL:1790905427.000226']
V13_ROUTE_REQUIREMENT = 'A destination the action names (a thread, channel, person or queue it goes to or through) needs a premise establishing that route'


def test_recorded_rejection_required_an_intake_route_for_the_recipient():
    """RECORDED. Under v13 every premise was SUPPORTED and essential, yet the action was insufficient because nothing
    established "a route for sending these four current reports to engineering"; the action named no concrete route."""
    result = json.loads(next((RUN/'topics').glob('*.json')).read_text(encoding='utf-8'))['result']
    sufficiency = result['grounding']['action_sufficiency']
    assert sufficiency['verdict'] == 'INSUFFICIENT' and 'not a route for sending' in sufficiency['rationale']
    verdicts = {s['statement_id']: s['verdict'] for s in result['grounding']['statements']}
    assert all(verdicts[p] == 'SUPPORTED' for p in sufficiency['essential_statement_ids'])
    assert result['card']['recommended_action'] is None
    manifest = json.loads((RUN/'run_manifest.json').read_text(encoding='utf-8'))
    assert manifest['fingerprints']['prompts']['prompt_version'] == 'agent3-advisor-prompts-v13'
    # Replay cannot reuse those verdicts: the grounding rules changed.
    assert grounding_inputs(manifest['fingerprints']['prompts']) != grounding_inputs(prompt_fingerprints())


def test_one_rule_in_drafting_and_grounding_and_the_contradiction_is_gone():
    assert PROMPT_VERSION == 'agent3-advisor-prompts-v14'
    for rules in (DRAFT_RULES, REVISION_RULES, GROUNDING_RULES):
        assert rules.count(ROUTING_RULE) == 1 and V13_ROUTE_REQUIREMENT not in rules
    assert 'evidence of an established intake route is not required' in ROUTING_RULE
    assert 'mentioning the recipient justifies nothing by itself' in ROUTING_RULE
    assert 'designated, official or mandatory, is a claim of its own and needs a premise' in ROUTING_RULE
    assert 'never on whether an intake route is on record' in GROUNDING_RULES


def escalation(payload, *, instruction, route_claim=None):
    base = draft_for(payload)
    by = {i['evidence_id']: i for i in payload['member_evidence']}
    reporters = [i['evidence_id'] for i in payload['member_evidence'] if i['author_id'] == i['thread_starter_id']][:2]
    engineer = [e for e in ENGINEER if e in by]
    claims = [{'claim_id': 'c1', 'kind': 'INCIDENT_FACT', 'text': 'Two members report that Submit does not work.', 'evidence_ids': reporters},
              {'claim_id': 'c2', 'kind': 'INCIDENT_FACT', 'evidence_ids': engineer,
               'text': 'An engineer asks for the LT error state and time on tasks RP-3412 and RP-5337.',
               'attributions': [{'user_id': by[e]['author_id'], 'relation': 'AUTHOR', 'evidence_id': e} for e in engineer]}]
    premises = ['c1', 'c2']
    if route_claim:
        claims.append({'claim_id': 'c3', 'kind': 'INCIDENT_FACT', 'text': route_claim, 'evidence_ids': [reporters[0]]})
        premises.append('c3')
    return {**base, 'contract_version': 'agent3-advisor-draft-v10', 'claims': claims, 'proposed_action': {
        'action_type': 'ESCALATE_ENGINEERING', 'instruction': instruction,
        'draft_text': 'Submit does not work on RP-3412 and RP-5337; error states and times follow.',
        'support_claim_ids': premises, 'intervention_need': {
            'kind': 'OPERATIONAL_PROBLEM', 'statement': 'Members cannot submit their tasks.', 'evidence_ids': reporters}}}


def test_rendered_draft_and_grounding_requests_carry_the_rule(retriever, view):
    """DETERMINISTIC. The exact task text both calls receive contains the same rule once."""
    instruction = 'Report the Submit failures to engineering with the error states the engineer asked for.'
    client = Fake(draft=lambda p: escalation(p, instruction=instruction), grounding=supported)
    run('submit_failure', client, retriever, view)
    sent = dict(client.calls)
    for stage in ('draft', 'grounding'):
        rules = sent[stage].split('\n\nInput JSON:\n', 1)[0]
        assert rules.count(ROUTING_RULE) == 1 and V13_ROUTE_REQUIREMENT not in sent[stage]


def test_supported_incident_yields_a_displayed_engineering_escalation(retriever, view):
    """PREPARED judge applying v14 (recipient justified by the incident evidence; no route named). Shown exactly."""
    instruction = 'Report the Submit failures to engineering with the error states the engineer asked for.'
    client = Fake(draft=lambda p: escalation(p, instruction=instruction), grounding=supported)
    action = run('submit_failure', client, retriever, view)['card']['recommended_action']
    assert action['action_type'] == 'ESCALATE_ENGINEERING' and action['instruction'] == instruction


@pytest.mark.parametrize('kind', ['claim', 'action'])
def test_unsupported_official_intake_route_is_still_rejected(retriever, view, kind):
    """PREPARED judge applying v14: the action asserts that a named channel is the official intake route. Either the
    route premise is UNSUPPORTED (and essential) or the action itself is judged insufficient for the route; the whole
    action is withheld and the route wording never reaches the card."""
    instruction = 'Post the Submit failures in #rp-general, the official engineering intake channel.'
    route = 'The #rp-general channel is the official engineering intake route.'

    def judge(p):
        if kind == 'claim':
            return supported(p, essential=['claim:c1', 'claim:c2', 'claim:c3'], **{'claim:c3': 'UNSUPPORTED'})
        out = supported(p, action='PARTIALLY_SUPPORTED')
        out['action_sufficiency'] = {**out['action_sufficiency'], 'verdict': 'INSUFFICIENT',
                                     'rationale': 'Nothing establishes #rp-general as an official intake route.'}
        return out
    result = run('submit_failure', Fake(draft=lambda p: escalation(p, instruction=instruction,
                                                                   route_claim=route if kind == 'claim' else None),
                                        grounding=judge), retriever, view)
    card = json.dumps(result['card'])
    assert result['card']['recommended_action'] is None and 'official engineering intake' not in card


def test_mentioning_engineering_is_not_approved_without_the_judge(retriever, view):
    """PREPARED judge: an escalation the judge finds unsupported by the incident evidence is withheld; nothing in the
    advisor passes an action because it names engineering."""
    instruction = 'Report the Submit failures to engineering with the error states the engineer asked for.'
    client = Fake(draft=lambda p: escalation(p, instruction=instruction), grounding=lambda p: supported(p, action='UNSUPPORTED'))
    assert run('submit_failure', client, retriever, view)['card']['recommended_action'] is None
