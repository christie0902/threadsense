"""Policy wording in copyable drafts (prompts v16), offline, on the frozen v15 tie-decision result.

Uses the frozen evidence ledger and draft from data/experiments/agent3_writing_eval_v15_v1 (read only) and the real
deterministic checks, statement builder, final-grounding path and authorization. The semantic verdicts are PREPARED
(tests.test_agent3_advisor.supported), never model output: these tests show what the code enforces on its own, that
the judge receives the exact displayed wording with its premises, and what each judgment does to the card. They say
nothing about how a model would judge. The drafts below are hand-written EXAMPLES.
"""
import glob
import json

import pytest

from threadsense.agents import advisor_pilot as pilot
from threadsense.agents.advice_inputs import load_effective_view
from threadsense.agents.advisor_checks import (
    _action_text, action_issues, authorize, build_severity, statements, structural_issues)
from threadsense.agents.advisor_contracts import AdvisorDraft, Claim, GroundingJudgment
from threadsense.handoff_inputs import ROOT
from threadsense.severity_rubric import load_rubric
from tests.test_agent3_advisor import supported

RUN = ROOT/'data/experiments/agent3_writing_eval_v15_v1'
FAQ = 'k:response-preference-faq@1.1:4683724f'  # "Cosmetic phrasing alone usually does not ... a tie can be appropriate"
INSTRUCTIONS = 'k:response-preference-instructions@1.1:176ce67d'  # "Choose a tie when ... does not justify a preference."
QA_TUTOR = 'm:C_RP_QA:1790866050.000113'  # A QA tutor's own reasoning about one pair.
PREMISES = ['c1', 'c2', 'c3', 'c7', 'c8']
AS_OF = '2026-10-02T12:00:00Z'  # The frozen run's cutoff.

# The hand-written candidate under prompts v16 (EXAMPLE; not model output, not judged by a model).
CANDIDATE_INSTRUCTION = ('Collect the disputed batch-15 pairs, their prompt constraints and both written QA rationales from '
                         'the three tie threads, then hold a short calibration review against the current tie guideline '
                         'before considering any change to the tie threshold.')
CANDIDATE_DRAFT = ('For each tie in batch 15 that QA marked wrong, including RP-9595, please post in this thread:\n'
                   '- the pair,\n- any prompt constraints that affect the choice,\n- both written QA rationales.\n\n'
                   'We will first check whether the pairs are actually comparable, then calibrate. When you write a '
                   'rationale, use the current tie guideline: choose a tie when neither response has a meaningful quality '
                   'advantage; cosmetic phrasing alone does not justify a preference; when you prefer a response on a '
                   'small difference, explain its benefit to the user.')


@pytest.fixture(scope='module')
def frozen():
    path = next(p for p in glob.glob(str(RUN/'topics'/'*.json')) if 'f944891544b06f79' in p)
    result = json.loads(open(path, encoding='utf-8').read())['result']
    packet = pilot.topic_packet(load_effective_view(pilot.HANDOFF), result['scenario'])
    return AdvisorDraft.model_validate(result['drafts']['final']), result['evidence_ledger'], packet


def variant(draft, draft_text, premises, extra_claims=(), instruction=None):
    action = draft.proposed_action.model_copy(update={
        'draft_text': draft_text, 'support_claim_ids': premises, 'instruction': instruction or draft.proposed_action.instruction,
        'context_claim_ids': [c for c in draft.proposed_action.context_claim_ids if c not in premises]})
    return draft.model_copy(update={'claims': list(draft.claims) + list(extra_claims), 'proposed_action': action})


class Call:
    """The final-grounding call with a PREPARED judgment in place of the model."""
    client = type('Prepared', (), {'replay': False})()

    def __init__(self, prepare):
        self.prepare, self.payload = prepare, None

    def __call__(self, stage, payload, schema, reserve=0):
        self.payload = payload
        return GroundingJudgment.model_validate(self.prepare(payload))


def card_action(frozen, draft, prepare):
    """Run the real checks and final-grounding path with a prepared verdict; return (displayed action, call, structural)."""
    _, ledger, packet = frozen
    rubric = load_rubric(None)
    severity, issues = build_severity(draft.severity, ledger, packet, rubric)
    stmts = statements(draft, ledger, severity=severity)
    structural, actions = structural_issues(draft, ledger, set(packet['member_ids'])), action_issues(draft, ledger)
    call = Call(prepare)
    grounding = pilot._final_grounding(call, draft, ledger, pilot._topic(packet, AS_OF), stmts,
                                       structural, actions)
    final = authorize(draft, grounding, ledger, packet, severity=severity, severity_issues=issues, rubric=rubric)
    return final['action'], call, structural


def insufficient(payload):
    out = supported(payload)
    out['action_sufficiency'] = {'verdict': 'INSUFFICIENT', 'essential_statement_ids': [],
                                 'rationale': 'PREPARED: the draft states the guidance more strongly than its source.'}
    return out


def sent_action(call):
    return next(s for s in call.payload['statements'] if s['statement_id'] == 'action')


def test_the_judge_receives_the_exact_displayed_draft_with_its_premises(frozen):
    draft = variant(frozen[0], CANDIDATE_DRAFT, PREMISES + ['c9'], instruction=CANDIDATE_INSTRUCTION)
    action, call, _ = card_action(frozen, draft, supported)
    sent = sent_action(call)
    assert sent['text'] == _action_text(draft.proposed_action, frozen[1]) and CANDIDATE_DRAFT in sent['text']
    assert [p['statement_id'] for p in sent['premises']] == [f'claim:{c}' for c in PREMISES + ['c9']]
    assert action is not None and action.draft_text == CANDIDATE_DRAFT and action.instruction == CANDIDATE_INSTRUCTION


def test_candidate_passes_every_deterministic_check(frozen):
    draft = variant(frozen[0], CANDIDATE_DRAFT, PREMISES + ['c9'], instruction=CANDIDATE_INSTRUCTION)
    _, _, structural = card_action(frozen, draft, supported)
    assert structural == []
    assert action_issues(draft, frozen[1]) == []


def test_qualified_guideline_overstated_as_mandatory_is_withheld_by_the_judgment_not_by_code(frozen):
    """The FAQ hedges ("usually", "can be appropriate"); the draft turns it into a rule. The code passes it (DETERMINISTIC:
    citations, roles and claim kinds are valid); only the PREPARED INSUFFICIENT judgment withholds the action."""
    faq = Claim(claim_id='cF', kind='GUIDANCE', evidence_ids=[FAQ],
                text='The current FAQ says cosmetic phrasing alone usually does not offer a meaningful benefit to the user, '
                     'and that a tie can be appropriate when no such benefit is explained.')
    overstated = ('Please post each disputed pair with both rationales. Cosmetic phrasing never justifies a preference, '
                  'and a tie is required whenever no benefit is explained.')
    draft = variant(frozen[0], overstated, PREMISES + ['cF'], [faq])
    shown, call, structural = card_action(frozen, draft, supported)
    assert structural == [] and shown is not None  # Nothing deterministic catches the overstatement.
    assert overstated in sent_action(call)['text']  # The judge sees the exact wording next to the hedged premise.
    withheld, _, _ = card_action(frozen, draft, insufficient)
    assert withheld is None


def test_mandatory_guideline_paraphrased_accurately_is_shown(frozen):
    accurate = ('Please post each disputed pair with both rationales. The current tie guideline says to choose a tie when '
                'neither response has a meaningful quality advantage, and that cosmetic phrasing alone does not justify a '
                'preference.')
    draft = variant(frozen[0], accurate, PREMISES + ['c9'])
    shown, _, structural = card_action(frozen, draft, supported)
    assert structural == [] and shown.draft_text == accurate


def test_participant_suggestion_attributed_passes_and_presented_as_policy_fails(frozen):
    draft_c4 = next(c for c in frozen[0].claims if c.claim_id == 'c4')  # INCIDENT_FACT with an AUTHOR attribution.
    assert draft_c4.kind == 'INCIDENT_FACT' and draft_c4.evidence_ids == [QA_TUTOR]
    attributed = ('Please post each disputed pair with both rationales. In the first thread, a QA tutor suggested a '
                  'calibration check rather than a policy rewrite for the two disputed tasks.')
    shown, _, structural = card_action(frozen, variant(frozen[0], attributed, PREMISES + ['c4']), supported)
    assert structural == [] and shown.draft_text == attributed

    # DETERMINISTIC: the same reasoning labelled as guidance while citing only the QA tutor's message is rejected
    # before the judge, and the action that relies on it is withheld even under a PREPARED "sufficient" verdict.
    as_rule = Claim(claim_id='cP', kind='GUIDANCE', evidence_ids=[QA_TUTOR],
                    text='Choose a tie when neither response has a meaningful quality advantage, and use the same criterion '
                         'for comparable pairs.')
    policy = 'Please post each disputed pair with both rationales. Rule for comparable pairs: treat them all as ties.'
    draft = variant(frozen[0], policy, PREMISES + ['cP'], [as_rule])
    rejected, call, structural = card_action(frozen, draft, lambda p: supported(p, essential=['claim:cP']))
    assert any(i['code'] == 'GUIDANCE_WITHOUT_CURRENT_SOURCE' and i['claim_id'] == 'cP' for i in structural)
    assert next(p for p in sent_action(call)['premises'] if p['statement_id'] == 'claim:cP')['status'].startswith('REJECTED')
    assert rejected is None

    # SEMANTIC (PREPARED): the rule stated in the draft text with only the attributed fact as premise passes the code
    # and is withheld only by the judgment.
    stated = 'Please post each disputed pair with both rationales. Rule for comparable pairs: treat them all as ties.'
    draft = variant(frozen[0], stated, PREMISES + ['c4'])
    passed, _, structural = card_action(frozen, draft, supported)
    assert structural == [] and passed is not None
    withheld, _, _ = card_action(frozen, draft, insufficient)
    assert withheld is None


def test_v16_changes_only_the_writing_guidance(frozen):
    manifest = json.loads((RUN/'run_manifest.json').read_text(encoding='utf-8'))
    assert pilot.PROMPT_VERSION == 'agent3-advisor-prompts-v18'
    # v16 and v17 kept the grounding inputs; v18 adds the DETAIL and NO_ACTION_RATIONALE kinds, so this run's recorded
    # verdicts are no longer reused in replay.
    assert pilot.grounding_inputs(manifest['fingerprints']['prompts']) != pilot.grounding_inputs(pilot.prompt_fingerprints())
    for phrase in ("team lead's own voice", 'at the strength and scope of the governing source',
                   'is not stated as a rule unless a current guideline', 'Keep requests apart by who made them',
                   'without commenting on its absence', 'including severity.rationale', 'in the supplied batch context'):
        assert phrase in pilot.WRITING_GUIDE and phrase not in pilot.GROUNDING_RULES


# Submit regression EXAMPLE (hand-written on the frozen v15 Submit draft): the symptom bullets are kept verbatim; only
# the diagnostic paragraph (engineer's task-specific request kept apart from the team lead's four-thread request) and
# the scope note (no comment on an unnamed intake route) change.
SUBMIT_DIAGNOSTICS = ('In all four threads, the team lead asked for the task ID, required-field state and exact button '
                      'behavior; these are still outstanding. Separately, an engineer asked for the LT error state and time '
                      'on RP-3412 and RP-5337. Submission status remains unverified. Please assess these reports without '
                      'assuming a shared cause.')
SUBMIT_SCOPE = ('Collect details under the current submission-incident instructions; a selected label is not a completed '
                'submission until LT confirms it. Similar button behavior alone does not link these reports to the earlier '
                'incident.')


def test_submit_regression_example_keeps_the_grouped_format_and_passes_deterministic_checks():
    path = next(p for p in glob.glob(str(RUN/'topics'/'*.json')) if 'routed_440e64c7fbdcc49f' in p)
    result = json.loads(open(path, encoding='utf-8').read())['result']
    draft = AdvisorDraft.model_validate(result['drafts']['final'])
    ledger, packet = result['evidence_ledger'], pilot.topic_packet(load_effective_view(pilot.HANDOFF), result['scenario'])
    old = draft.proposed_action.draft_text
    bullets = old[:old.index('The requested diagnostic set')]
    new_text = bullets + SUBMIT_DIAGNOSTICS
    action = draft.proposed_action.model_copy(update={'draft_text': new_text, 'scope_note': SUBMIT_SCOPE})
    candidate = draft.model_copy(update={'proposed_action': action})
    assert 'RP-1577' in new_text and 'RP-3325' in new_text and 'not supplied' in new_text  # Task IDs and gaps kept.
    assert 'intake route' not in new_text + SUBMIT_SCOPE and 'intake route' in draft.proposed_action.scope_note
    assert structural_issues(candidate, ledger, set(packet['member_ids'])) == [] and action_issues(candidate, ledger) == []
    severity, _ = build_severity(candidate.severity, ledger, packet, load_rubric(None))
    sent = next(s for s in statements(candidate, ledger, severity=severity) if s['statement_id'] == 'action')
    assert sent['text'] == _action_text(action, ledger) and SUBMIT_DIAGNOSTICS in sent['text'] and SUBMIT_SCOPE in sent['text']
