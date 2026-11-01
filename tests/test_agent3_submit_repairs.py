"""Repairs from agent3_summary_eval_v1 (Submit): revision payload size, record authorship, action destinations and
independent summary sentences. RECORDED tests read that run unchanged; PREPARED tests script the judge (labelled);
everything else is DETERMINISTIC."""
import json

import pytest

from threadsense.agents.advisor_checks import relation_holds, shown_summary, statements
from threadsense.agents.advisor_contracts import AdvisorDraft
from threadsense.agents.advisor_evidence import Budget, ResearchTools, authorship, model_view
from threadsense.agents.advisor_pilot import (
    DRAFT_RULES, GROUNDING_RULES, REVISION_RULES, STYLE_EXAMPLES, WRITING_GUIDE, _json_text, sent_schema,
)
from threadsense.handoff_inputs import ROOT
from tests.test_agent3_advisor import (  # noqa: F401 - fixtures reused
    Fake, codes, draft_for, retriever, run, sent_payload, supported, view,
)

RUN = ROOT/'data/experiments/agent3_summary_eval_v1'
SUBMIT = 'gap:routed_440e64c7fbdcc49f'
HANDOFF = 'k:rp-submit-engineering-handoff@1.0:d84c905d'
RECORDED_BLOCKED_TOKENS = 24405  # agent3_summary_eval_v1: "InputLimitExceeded: 24405 input tokens > 24000; not sent"


@pytest.fixture(scope='module')
def recorded():
    path = next(p for p in (RUN/'topics').glob('*.json') if json.loads(p.read_text(encoding='utf-8'))['work_item']['work_id'] == SUBMIT)
    result = json.loads(path.read_text(encoding='utf-8'))['result']
    raw = json.loads(_json_text(next(c['raw'] for c in result['model_calls'] if c['stage'] == 'draft')))
    return result, raw


# --- 1. Revision payload --------------------------------------------------------------------------------------------

@pytest.fixture(scope='module')
def measured():
    """The blocked revision request rebuilt from the recorded draft with the run's own snapshot and settings, captured at
    the HTTP transport (never sent) and counted with RequestGuard's rule. Needs the active real-embedding index."""
    if not (ROOT/'.index/retrieval/manifest.json').is_file():
        pytest.skip('Active retrieval index not built (scripts/build_retrieval_index.py).')
    import importlib.util
    spec = importlib.util.spec_from_file_location('measure_revision_request', ROOT/'scripts/measure_revision_request.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.measure(RUN, SUBMIT)


def test_recorded_revision_request_fits_under_the_unchanged_cap(measured, recorded):
    """RECORDED. The same revision (same draft, follow-ups and evidence) that was refused at 24,405 tokens now fits the
    unchanged 24,000 limit; the limit was not raised and nothing was cut from the evidence."""
    result, _ = recorded
    refused = next(c for c in result['model_calls'] if c['stage'] == 'revision')
    assert str(RECORDED_BLOCKED_TOKENS) in refused['error'] and measured['input_token_limit'] == 24000
    assert measured['revision_requested'] and measured['fits'] and measured['input_tokens'] < RECORDED_BLOCKED_TOKENS
    assert measured['headroom'] >= 2000


def test_revision_request_keeps_every_source_text_identity_and_obligation(measured, recorded):
    """RECORDED. Every evidence item of the recorded ledger travels with its exact text, identity and recorded states; the
    upstream review flags are still in the request; source text is not truncated."""
    result, _ = recorded
    sent = sent_payload(measured['body']['messages'][1]['content'])
    items = {i['evidence_id']: i for i in sent['member_evidence'] + sent['retrieved_evidence']}
    assert set(result['evidence_ledger']) <= set(items)
    for eid, old in result['evidence_ledger'].items():
        new = items[eid]
        assert old['excerpt'] in new['excerpt'] or new['excerpt'].endswith(old['excerpt'].split('\n', 1)[-1])
        if old['origin'] == 'retrieved_source':
            assert new['citation'].get('authoring') == old['citation']['authoring'] and new['use'] == old['use']
            assert {k: v for k, v in old['recorded_states'].items() if v is not None} == new.get('recorded_states', {})
            assert new['scope']['project_id'] == old['scope']['project_id']
        else:
            assert (new['author_id'], new['author_role'], new['thread_id']) == (old['author_id'], old['author_role'], old['thread_id'])
    assert all(i.get('agent1_review_required') is not None for i in sent['agent1_interpretations'])
    assert sent['previous_draft']['claims'] and sent['follow_ups']


def test_revision_keeps_every_rule_and_the_writing_guide_without_the_style_examples():
    """DETERMINISTIC. The revision drops only the STYLE ONLY examples; schemas lose only generated titles."""
    assert WRITING_GUIDE in REVISION_RULES and STYLE_EXAMPLES not in REVISION_RULES and STYLE_EXAMPLES in DRAFT_RULES
    assert DRAFT_RULES.replace(f' {STYLE_EXAMPLES}', '') in REVISION_RULES
    schema = sent_schema(AdvisorDraft)
    text = json.dumps(schema)
    assert '"title": "' not in text.replace('"title": {', '')
    full = AdvisorDraft.model_json_schema()
    assert schema['required'] == full['required'] and set(schema['properties']) == set(full['properties'])
    assert set(schema['$defs']) == set(full['$defs'])


# --- 2. Authorship versus authority ---------------------------------------------------------------------------------

def handoff_item(retriever):
    tools = ResearchTools(retriever, project='response_preference', batch='rp_batch_15', as_of=retriever.manifest['cutoff'],
                          budget=Budget({}), top_k=20)
    tools.search('Submit button disabled engineering handoff', purpose='test', source_types=['decision'], version_mode='history')
    return tools.ledger[HANDOFF], tools.ledger


def test_handoff_record_names_its_approver_and_no_author(retriever):
    """DETERMINISTIC (the recorded ambiguity). The earlier engineering handoff is a manual record whose authority actor
    (the team lead) approved and recorded it; it names no author. The model sees both facts apart."""
    item, _ = handoff_item(retriever)
    shown = model_view(item)
    assert shown['authority']['actor'] == 'U001' and shown['authority']['actor_relation'] == 'RECORD_AUTHORITY'
    assert shown['authorship'] == {'verified': False, 'basis': 'NO_AUTHOR_RECORDED'}
    assert 'Alex approved an engineering handoff' in shown['excerpt']  # approval stays in the source text


def test_author_attribution_rule_is_not_broadened(retriever):
    """DETERMINISTIC. AUTHOR still holds only for a Slack record's message author: the approver of a manual record is
    not its author (the claim from the recorded run stays rejected), and a Slack record's author is."""
    item, ledger = handoff_item(retriever)
    assert not relation_holds('U001', 'AUTHOR', item, ledger)
    slack = {'origin': 'retrieved_source', 'citation': {'source': {'system': 'slack'}}, 'authority': {'actor': 'U001'}}
    assert relation_holds('U001', 'AUTHOR', slack, {}) and authorship(slack['citation'], 'U001')['verified']
    assert authorship({'source': {'system': 'manual'}}, 'U001') == {'author_id': None, 'verified': False, 'basis': 'NO_AUTHOR_RECORDED'}


def test_rules_tell_draft_and_judge_that_approval_is_not_authorship():
    for rules in (DRAFT_RULES, REVISION_RULES):
        assert 'the earlier handoff records' in rules and 'only when its authorship is verified' in rules
    assert 'is not its author' in GROUNDING_RULES


# --- 3. Action destinations -----------------------------------------------------------------------------------------

def test_rules_separate_the_recommendation_from_its_destination():
    """v14 states this as one shared recipient/route rule (tests/test_agent3_recipient_routing.py)."""
    for rules in (DRAFT_RULES, REVISION_RULES, GROUNDING_RULES):
        assert 'is a claim of its own and needs a premise whose evidence establishes it' in rules
        assert 'does not make that thread an intake route' in rules and 'leave it unspecified' in rules
    assert 'leaves the concrete route unspecified is not PARTIALLY_SUPPORTED, UNSUPPORTED or insufficient' in GROUNDING_RULES


def escalation_draft(instruction):
    def draft(payload):
        base = draft_for(payload)
        reporters = [i['evidence_id'] for i in payload['member_evidence'] if i['author_id'] == i['thread_starter_id']][:2]
        return {**base, 'claims': [{'claim_id': 'c1', 'kind': 'INCIDENT_FACT', 'text': 'Two members report a Submit problem.',
                                    'evidence_ids': reporters}],
                'proposed_action': {'action_type': 'ESCALATE_ENGINEERING', 'instruction': instruction,
                                    'draft_text': 'Submit problems need investigation; task references follow.',
                                    'support_claim_ids': ['c1'], 'intervention_need': {
                                        'kind': 'OPERATIONAL_PROBLEM', 'statement': 'Submissions remain unverified.',
                                        'evidence_ids': reporters}}}
    return draft


def test_action_with_an_unsupported_destination_is_withheld_whole_never_trimmed(retriever, view):
    """PREPARED judge (as recorded: the action PARTIALLY_SUPPORTED, insufficient for its routing). The action is withheld
    as generated; no shortened or destination-free version appears after grounding."""
    instruction = 'Collect the diagnostics in the existing example thread and send engineering a consolidated update.'

    def judge(p):
        out = supported(p, action='PARTIALLY_SUPPORTED')
        out['action_sufficiency'] = {**out['action_sufficiency'], 'verdict': 'INSUFFICIENT',
                                     'rationale': 'Nothing establishes the example thread as an intake route.'}
        return out
    result = run('submit_failure', Fake(draft=escalation_draft(instruction), grounding=judge), retriever, view)
    card = result['card']
    assert card['recommended_action'] is None and 'example thread' not in json.dumps(card)


def test_action_without_a_named_destination_is_shown_exactly_as_generated(retriever, view):
    instruction = 'Report the submission problems to engineering with the task IDs and exact button behavior.'
    result = run('submit_failure', Fake(draft=escalation_draft(instruction), grounding=supported), retriever, view)
    action = result['card']['recommended_action']
    assert action['action_type'] == 'ESCALATE_ENGINEERING' and action['instruction'] == instruction


# --- 4. Independent summary sentences -------------------------------------------------------------------------------

def test_current_handling_survives_when_the_history_sentence_is_withheld(recorded):
    """RECORDED claims, DETERMINISTIC selection. The recorded second sentence joined the team lead's request (claim c5,
    SUPPORTED) with the earlier handoff (claim c7, rejected for its AUTHOR attribution), so both were lost. Written as
    separate sentences (as the v11 guide asks), the supported one is shown and the history sentence is withheld because
    its claim is, even if the judge accepted its wording."""
    result, raw = recorded
    verdicts = {s['statement_id']: s['verdict'] for s in result['grounding']['statements']}
    assert verdicts['claim:c5'] == 'SUPPORTED' and verdicts['claim:c7'] == 'REJECTED_ATTRIBUTION_INVALID'
    first = raw['summary_sentences'][0]['text']
    asked = 'The team lead asked each of the four threads for the task ID, required-field state and exact button behavior.'
    history = 'An earlier handoff for similar reports in this batch records no confirmed cause or repair.'
    draft = AdvisorDraft.model_validate({**raw, 'summary_sentences': [
        raw['summary_sentences'][0], {'text': asked, 'support_claim_ids': ['c5']},
        {'text': history, 'support_claim_ids': ['c7']}]})
    sentence_ok = {'summary:s1': True, 'summary:s2': True, 'summary:s3': True}
    ok = lambda sid: sentence_ok[sid] if sid in sentence_ok else verdicts.get(sid) == 'SUPPORTED'  # noqa: E731
    text, held = shown_summary(draft, ok)
    assert text == f'{first} {asked}' and held == [('summary:s3', 'depends on withheld claim:c7')]
    assert [s['statement_id'] for s in statements(draft, result['evidence_ledger']) if s['kind'] == 'SUMMARY'] == [
        'summary:s1', 'summary:s2', 'summary:s3']


def test_guide_separates_facts_with_different_evidence_and_allows_three_sentences():
    assert 'up to 3 when needed' in WRITING_GUIDE and 'rather than joining unrelated facts' in WRITING_GUIDE
    assert AdvisorDraft.model_fields['summary_sentences'].metadata[0].max_length == 3
