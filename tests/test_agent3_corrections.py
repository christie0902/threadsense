"""Milestone 4 correction pass: regressions replaying recorded live-v1 and acceptance-run failures, and the workflow
changes since v3.

Recorded failures come from tests/fixtures/agent3_live_v1_failures.json (exact gpt-4o-mini output, with the
raw-response SHA-256). DETERMINISTIC tests are guaranteed by code; MOCKED SEMANTIC tests depend on a prepared
grounding verdict and say nothing about real model behaviour.
"""
import json

import pytest
from pydantic import ValidationError

from threadsense.agents.advisor_checks import (
    build_severity, claim_issues, coverage_issues, dependencies, grounding_result, rejected_statements, sendable,
    statements, structural_issues, temporal_check,
)
from threadsense.agents.advisor_contracts import AdvisorDraft, GroundingJudgment, SeverityProposal
from threadsense.agents.advisor_evidence import member_messages
from threadsense.agents.advisor_pilot import grounding_payload, topic_packet
from threadsense.handoff_inputs import ROOT, read_json
from tests.test_agent3_advisor import with_need
from tests.test_agent3_advisor import (  # noqa: F401 - fixtures reused
    RUBRIC, SCEN, Fake, codes, draft_for, make_draft, open_q, retriever, run, safety_tools, supported, view,
)

FAIL = read_json(ROOT/'tests/fixtures/agent3_live_v1_failures.json')['cases']


def members(view, scenario):
    packet = topic_packet(view, SCEN[scenario])
    return packet, {i['evidence_id']: i for i in member_messages(packet['members'])}


# ---- Replayed live-v1 failures ------------------------------------------------------------------------

def test_recorded_misquote_rejects_only_that_claim(retriever, view):
    """DETERMINISTIC rejection and routing; MOCKED SEMANTIC verdicts for the rest. Recorded PII draft: a paraphrase
    presented as verbatim and a Slack message cited as guidance are rejected and never sent; the two recorded incident
    facts still reach the judge and the card (in v1 one bad quote voided the whole draft). Marked as a paraphrase, the
    same words go to the judge instead. The recorded incident facts name their authors (correctly): since v5 card prose
    uses roles, so as recorded they are rejected as names; with roles they go to the judge."""
    packet, ledger = members(view, 'fictional_pii')
    ledger.update(safety_tools(retriever).ledger)
    case = FAIL['quotation']
    assert case['claim']['evidence_ids'][0] in ledger, 'precondition: the cited FAQ chunk is in the ledger'
    recorded = make_draft(claims=case['other_claims'])
    assert {(i['statement_id'], i['code']) for i in structural_issues(recorded, ledger, set(packet['member_ids']))} == {
        ('claim:incident_fact_1', 'PERSONAL_NAME_IN_PROSE'), ('claim:incident_fact_2', 'PERSONAL_NAME_IN_PROSE')}
    roles = [{**c, 'text': c['text'].replace('Nico', 'A tutor').replace('Sofia', 'Another tutor')} for c in case['other_claims']]
    draft = make_draft(claims=[*roles, case['claim'], FAIL['guidance_from_slack']['claim']])
    structural = structural_issues(draft, ledger, set(packet['member_ids']))
    assert {(i['statement_id'], i['code']) for i in structural} == {
        ('claim:guidance_1', 'QUOTE_NOT_VERBATIM'), ('claim:guidance_2', 'GUIDANCE_WITHOUT_CURRENT_SOURCE')}
    stmts = statements(draft, ledger)
    sent = {s['statement_id'] for s in sendable(stmts, rejected_statements(draft, stmts, structural))}
    assert sent == {'claim:incident_fact_1', 'claim:incident_fact_2', 'summary'}
    judgment = GroundingJudgment(verdicts=[{'statement_id': s, 'verdict': 'SUPPORTED', 'rationale': 'Stated.'} for s in sent])
    result = grounding_result(draft, ledger, stmts, structural=structural, judgment=judgment, ran=True)
    verdicts = {s['statement_id']: s['verdict'] for s in result['statements']}
    assert verdicts['claim:incident_fact_1'] == verdicts['claim:incident_fact_2'] == 'SUPPORTED'
    assert verdicts['claim:guidance_1'] == 'REJECTED_QUOTE_NOT_VERBATIM' and result['status'] == 'FAILED'
    paraphrase = make_draft(claims=[{**case['claim'], 'quote_kind': 'PARAPHRASE'}])
    assert structural_issues(paraphrase, ledger, set(packet['member_ids'])) == []
    assert 'Paraphrase: "Verified fictional placeholders alone do not require QN."' in statements(paraphrase, ledger)[0]['text']


def test_recorded_misattributed_reporter_is_dropped_not_fatal(view):
    """DETERMINISTIC. Recorded repeated-ending severity: U017 cited with U013's message is dropped and recorded, not
    fatal. The recording has a second defect: its HIGH[3] signal text is not the rubric's, which still (correctly)
    leaves severity UNASSESSED. With the rubric text, HIGH stands with the two correctly attributed reporters."""
    packet, ledger = members(view, 'repeated_ending')
    recorded = FAIL['attribution']['severity']
    notes = []
    severity, issues = build_severity(SeverityProposal.model_validate(recorded), ledger, packet, RUBRIC, notes=notes)
    assert issues == ['Signal HIGH[3] does not match the rubric text.'] and severity.assessment_status == 'UNASSESSED'
    assert notes == ['Affected reporter U017 dropped: the cited message is by U013.']
    exact = [{**s, 'signal_text': RUBRIC['levels'][s['level']]['required_signals'][s['signal_index']]} for s in recorded['signals']]
    severity, issues = build_severity(SeverityProposal.model_validate({**recorded, 'signals': exact}), ledger, packet, RUBRIC)
    assert issues == [] and severity.assessment_status == 'ASSESSED' and severity.level == 'HIGH'
    assert severity.occurrence.affected_reporters.ids == ['U007', 'U018']


def test_recorded_names_are_checked_against_message_authors(view):
    """DETERMINISTIC. Display names come from the canonical user directory. The recorded JSON-vs-prose claims name
    Yuki (U019) and Leo (U007), who wrote the cited messages: the relation holds, and they are rejected only as names
    (card prose uses roles). Naming someone who wrote none of the cited messages is an attribution error."""
    _, ledger = members(view, 'json_vs_prose')
    claims = FAIL['named_people']['claims']
    assert ledger[claims[0]['evidence_ids'][0]]['author_name'] == 'Yuki'
    assert {i['code'] for i in claim_issues(make_draft(claims=claims), ledger)} == {'PERSONAL_NAME_IN_PROSE'}
    swapped = make_draft(claims=[{**claims[0], 'text': claims[0]['text'].replace('Yuki', 'Leo')}])
    assert [i['code'] for i in claim_issues(swapped, ledger)] == ['NAME_RELATION_INVALID']


def test_reported_symptoms_stay_distinct_from_verified_causes(view):
    """DETERMINISTIC. The recorded "repeats in the exported audio" is acceptable as a members' report, but as a CAUSE
    citing only tutor messages it is rejected; a team lead's message can be cited for a cause, and whether it verifies
    the cause is then a semantic judgment."""
    _, ledger = members(view, 'repeated_ending')
    claim = FAIL['reported_symptom']['claim']
    assert claim_issues(make_draft(claims=[claim]), ledger) == []
    assert [i['code'] for i in claim_issues(make_draft(claims=[{**claim, 'kind': 'CAUSE'}]), ledger)] == ['CAUSE_WITHOUT_VERIFICATION']
    lead = next(k for k, i in ledger.items() if i['author_role'] == 'TEAM_LEAD')
    assert claim_issues(make_draft(claims=[{**claim, 'kind': 'CAUSE', 'evidence_ids': [lead]}]), ledger) == []


def test_recorded_partial_thread_resolution_is_judged_against_the_whole_thread(retriever, view):
    """DETERMINISTIC judge context; MOCKED SEMANTIC verdict. The recorded audio resolution cites 2 of 4 messages; the
    judge still receives the whole thread, including the uncited team lead reply, and a PARTIALLY_SUPPORTED verdict
    leaves that member UNKNOWN."""
    resolution = FAIL['partial_thread_resolution']['resolution']
    lead_reply = 'm:C_AUDIO_GENERAL:1790934431.000339'
    assert lead_reply not in resolution['evidence_ids']
    sent = []
    sid = f"resolution:{resolution['member_id']}"
    result = run('audio_playback', Fake(draft=lambda p: draft_for(p, resolution=[resolution]),
                                        grounding=lambda p: sent.append(p) or supported(p, **{sid: 'PARTIALLY_SUPPORTED'})),
                 retriever, view)
    thread = {m['evidence_id'] for m in sent[0]['member_threads'] if m['member_id'] == resolution['member_id']}
    assert lead_reply in thread and len(thread) == 4
    assert result['resolution']['members'][resolution['member_id']] == 'UNKNOWN'


# ---- Workflow corrections ----------------------------------------------------------------------------

def test_open_confirmation_needs_a_specific_question_and_actions_survive_review(retriever, view):
    """DETERMINISTIC contract and routing; MOCKED SEMANTIC verdicts. OPEN needs a specific question and the evidence
    leaving it open; a NEEDS_REVIEW card still carries a supported action. Review reasons come from the final validated
    results: an open question the final grounding did not support is not an OPEN_CONFIRMATION reason (it stays in the
    diagnostics as a withheld statement)."""
    with pytest.raises(ValidationError, match='specific unresolved question'):
        make_draft(open_confirmation='OPEN')
    with pytest.raises(ValidationError, match='specific unresolved question'):
        make_draft(open_confirmation='OPEN', open_question='Which rule applies?')
    result = run('json_vs_prose', Fake(draft=lambda p: draft_for(p, **open_q(p)), grounding=supported), retriever, view)
    card = result['card']
    assert card['card_line'] == 'NEEDS_REVIEW' and card['recommended_action']['action_type'] == 'POST_ALIGNMENT'
    [reason] = [r for r in card['needs_review_reasons'] if r['code'] == 'OPEN_CONFIRMATION']
    assert reason['detail'] == 'Which rule wins when the two current sources disagree?'
    rejected = run('json_vs_prose', Fake(draft=lambda p: draft_for(p, **open_q(p)),
                                         grounding=lambda p: supported(p, open_question='UNSUPPORTED')), retriever, view)
    assert 'OPEN_CONFIRMATION' not in codes(rejected) and rejected['card']['checks']['open_confirmation'] == 'NONE'
    assert not any(n.startswith('Open question') for n in rejected['card']['review_notes'])
    assert 'INHERITED_FLAG' in codes(rejected)  # Legitimate reasons stay.
    assert any(d['statement_id'] == 'open_question' for d in rejected['diagnostics'] if d['code'] == 'WITHHELD_STATEMENT')
    assert 'Open question: Which rule wins when the two current sources disagree?' in card['review_notes']


def test_coverage_is_assessed_and_missing_support_drives_targeted_research(retriever, view):
    """DETERMINISTIC coverage checks and follow-up execution; MOCKED SEMANTIC gap detection. Every need must be
    assessed; COVERED needs evidence of that kind; MISSING without a follow-up is reported. A MISSING prior decision
    with a history follow-up runs one targeted search and a revision; nothing is searched for needs marked covered."""
    _, ledger = members(view, 'audio_playback')
    message = next(iter(ledger))
    assert coverage_issues(make_draft(), ledger) == [f'{n}: not assessed' for n in
                                                     ('CURRENT_GUIDANCE', 'ANNOUNCEMENTS', 'PRIOR_DECISIONS', 'MEMBER_QUESTIONS')]
    wrong = make_draft(coverage=[{'need': 'CURRENT_GUIDANCE', 'status': 'COVERED', 'evidence_ids': [message], 'note': 'x'},
                                 {'need': 'PRIOR_DECISIONS', 'status': 'MISSING', 'note': 'Earlier workaround outcome?'}])
    assert {'CURRENT_GUIDANCE: marked COVERED without evidence of that kind',
            'PRIOR_DECISIONS: missing and not researched'} <= set(coverage_issues(wrong, ledger))

    def missing(payload):
        coverage = [c for c in draft_for(payload)['coverage'] if c['need'] != 'PRIOR_DECISIONS'] + [
            {'need': 'PRIOR_DECISIONS', 'status': 'MISSING', 'note': 'Members recall an earlier workaround.', 'gap_id': 'g1'}]
        return draft_for(payload, coverage=coverage, gaps=[{'gap_id': 'g1', 'need': 'PRIOR_DECISION_OUTCOME',
                                                             'description': 'Outcome of the earlier workaround.',
                                                             'follow_up': {'query': 'previous playback workaround trial outcome',
                                                                           'source_types': ['decision', 'announcement'],
                                                                           'version_mode': 'history'}}])
    client = Fake(draft=missing, revision=missing, grounding=supported)
    result = run('audio_playback', client, retriever, view)
    assert [t['purpose'] for t in result['retrieval_trace'][1:]] == ['gap:PRIOR_DECISION_OUTCOME']
    assert result['retrieval_trace'][-1]['version_mode'] == 'history' and client.stages_called() == ['draft', 'revision', 'grounding']
    assert 'PRIOR_DECISIONS: missing; still missing after the revision used the follow-up evidence' in result['coverage_issues']
    assert any(r['detail'].startswith('Evidence coverage incomplete') for r in result['card']['needs_review_reasons'])


def test_selected_tot_candidate_becomes_the_action_without_clearing_flags(retriever, view):
    """MOCKED SEMANTIC selection and verdicts; DETERMINISTIC adoption rules. With no draft action, the model's clearly
    preferred valid candidate becomes the proposed action and is judged by the final grounding like any action; the
    open-confirmation and inherited flags stay. A close call or a candidate with an applicability issue is not adopted."""
    def open_draft(payload):
        return draft_for(payload, proposed_action=None, **open_q(payload))

    def tot(close=False, members_only=False):
        def response(payload):
            guide = payload['draft']['claims'][-1 if not members_only else 0]['evidence_ids']
            return {'candidates': [
                {'candidate_id': 'A', 'action_type': 'POST_ALIGNMENT', 'draft_text': 'Post the current scoring guidance.',
                 'evidence_ids': guide, 'evidence_support': 'STRONG', 'applicability': 'CURRENT', 'severity_fit': 'FITS',
                 'rationale': 'Current guidance answers the question.'},
                {'candidate_id': 'B', 'action_type': 'NO_ACTION', 'draft_text': 'Wait.', 'evidence_ids': guide,
                 'evidence_support': 'PARTIAL', 'applicability': 'CURRENT', 'severity_fit': 'FITS', 'rationale': 'r'}],
                'preferred_candidate_id': 'A', 'close_call': close, 'rationale': 'A is clearly better.'}
        return response
    sent = []
    client = Fake(draft=open_draft, tot=tot(), grounding=lambda p: sent.append(p) or supported(p))
    result = run('json_vs_prose', client, retriever, view)
    assert client.stages_called() == ['draft', 'tot', 'grounding'] and result['action_source'] == 'TOT'
    assert 'action' in {s['statement_id'] for s in sent[0]['statements']}  # Judged before reaching the card.
    assert result['card']['recommended_action']['action_type'] == 'POST_ALIGNMENT'
    assert {'OPEN_CONFIRMATION', 'INHERITED_FLAG'} <= set(codes(result))
    close = run('json_vs_prose', Fake(draft=open_draft, tot=tot(close=True), grounding=supported), retriever, view)
    assert close['action_source'] is None and close['card']['recommended_action'] is None
    # Claims CURRENT applicability while citing only member messages: APPLICABILITY_OVERSTATED, not adopted.
    flagged = run('json_vs_prose', Fake(draft=open_draft, tot=tot(members_only=True), grounding=supported),
                  retriever, view)
    assert flagged['card']['recommended_action'] is None and flagged['action_notes'][0].startswith('ToT candidate A not adopted')


# ---- Action sufficiency (MOCKED SEMANTIC judgments, DETERMINISTIC validation) -----------------------------

def premise_draft(payload):
    """An action resting on a current FAQ/guideline premise (c2) and a tutor message mislabelled as guidance (c3)."""
    base = draft_for(payload)
    tutor = next(i['evidence_id'] for i in payload['member_evidence'] if i['author_role'] in ('TUTOR', 'QA_TUTOR'))
    claims = base['claims'] + [{'claim_id': 'c3', 'kind': 'GUIDANCE', 'text': 'A tutor says to score format separately.',
                                'evidence_ids': [tutor]}]
    return draft_for(payload, claims=claims, proposed_action={'action_type': 'POST_ALIGNMENT', 'support_claim_ids': ['c2', 'c3'],
                                                              'draft_text': 'Post the current scoring guidance.'})


def test_optional_rejected_premise_leaves_a_sufficiently_supported_action(retriever, view):
    """MOCKED SEMANTIC sufficiency; DETERMINISTIC validation. c3 is rejected (tutor text is not guidance) and shown to
    the judge as REJECTED, c2 as pending the judge's own verdict (never as final); the judge names only c2 as essential, c2 passed, so the action stands (before this pass any
    rejected premise dropped the action)."""
    sent = []
    result = run('json_vs_prose', Fake(draft=premise_draft, grounding=lambda p: sent.append(p) or supported(
        p, essential=['claim:c2'])), retriever, view)
    action = next(s for s in sent[0]['statements'] if s['kind'] == 'ACTION')
    assert {p['statement_id']: p['status'] for p in action['premises']} == {
        'claim:c2': 'PENDING_YOUR_VERDICT', 'claim:c3': 'REJECTED_GUIDANCE_WITHOUT_CURRENT_SOURCE'}
    verdicts = {s['statement_id']: s['verdict'] for s in result['grounding']['statements']}
    assert verdicts['claim:c3'] == 'REJECTED_GUIDANCE_WITHOUT_CURRENT_SOURCE' and verdicts['action'] == 'SUPPORTED'
    assert result['card']['recommended_action']['action_type'] == 'POST_ALIGNMENT'
    action = result['card']['recommended_action']
    assert action['essential_premise_ids'] == ['claim:c2'] and 'claim:' not in json.dumps({k: action[k] for k in (
        'label', 'instruction', 'rationale', 'draft_text', 'scope_note')})


@pytest.mark.parametrize('sufficiency, expected', [
    ({'verdict': 'SUFFICIENT', 'essential_statement_ids': ['claim:c2', 'claim:c3']}, 'ESSENTIAL_PREMISE_NOT_PASSED'),
    ({'verdict': 'INSUFFICIENT', 'essential_statement_ids': ['claim:c3']}, 'INSUFFICIENT_PREMISES'),
    ({'verdict': 'SUFFICIENT', 'essential_statement_ids': ['claim:c1']}, 'ESSENTIAL_ID_NOT_A_PREMISE'),
    ({'verdict': 'SUFFICIENT', 'essential_statement_ids': []}, 'NO_ESSENTIAL_PREMISE_NAMED'),
])
def test_rejected_essential_premise_blocks_the_action(retriever, view, sufficiency, expected):
    """MOCKED SEMANTIC sufficiency; DETERMINISTIC validation of the judge's premise IDs against what passed. An
    essential premise that was rejected, an INSUFFICIENT judgment, an essential ID that is not a premise of this action,
    or no essential premise at all: the action never reaches the card."""
    result = run('json_vs_prose', Fake(draft=premise_draft, grounding=lambda p: {
        **supported(p), 'action_sufficiency': {**sufficiency, 'rationale': 'r'}}), retriever, view)
    assert {s['statement_id']: s['verdict'] for s in result['grounding']['statements']}['action'] == expected
    assert result['card']['recommended_action'] is None


def test_team_lead_instruction_labelled_guidance_is_relabelled_and_judged_in_scope(retriever, view):
    """DETERMINISTIC relabel; MOCKED SEMANTIC verdict. A GUIDANCE label on a team lead's in-thread instruction (the
    comparison-run failure) becomes THREAD_INSTRUCTION, recorded, and is judged; tutor text labelled guidance still fails."""
    def draft(payload):
        lead = next(i['evidence_id'] for i in payload['member_evidence'] if i['author_role'] == 'TEAM_LEAD')
        return draft_for(payload, claims=draft_for(payload)['claims'] + [
            {'claim_id': 'c5', 'kind': 'GUIDANCE', 'text': 'The team lead asks for the exact formatting instruction.',
             'evidence_ids': [lead]}])
    sent = []
    result = run('json_vs_prose', Fake(draft=draft, grounding=lambda p: sent.append(p) or supported(p)), retriever, view)
    [note] = [d for d in result['diagnostics'] if d['code'] == 'ROLE_LABEL_CORRECTED']
    assert note['statement_id'] == 'claim:c5' and note['to'] == 'THREAD_INSTRUCTION'
    assert {s['statement_id']: s['kind'] for s in sent[0]['statements']}['claim:c5'] == 'CLAIM_THREAD_INSTRUCTION'
    assert {s['statement_id']: s['verdict'] for s in result['grounding']['statements']}['claim:c5'] == 'SUPPORTED'
    tutor = run('json_vs_prose', Fake(draft=premise_draft, grounding=supported), retriever, view)
    assert not [d for d in tutor['diagnostics'] if d['code'] == 'ROLE_LABEL_CORRECTED']


# ---- Severity and recurrence ---------------------------------------------------------------------------

LEAD_IMPACT = 'm:C_AUDIO_GENERAL:1790920220.000113'  # "This affected task cannot be evaluated while the player fails to load."
ROOTS = ['m:C_AUDIO_GENERAL:1790882197.000111', 'm:C_AUDIO_GENERAL:1790896012.001900']


def severity_draft(payload, *, recurrence_ids, support='The team lead states the task cannot be evaluated.', level='HIGH',
                   signal=('HIGH', 0)):
    return draft_for(payload, severity={
        'level': level, 'rationale': 'Affected tasks cannot be evaluated; this has happened before.',
        'signals': [{'level': signal[0], 'signal_index': signal[1], 'support': support, 'evidence_ids': [LEAD_IMPACT],
                     'signal_text': RUBRIC['levels'][signal[0]]['required_signals'][signal[1]]}],
        'affected_reporters': [{'author_id': 'U019', 'evidence_id': ROOTS[0]}, {'author_id': 'U018', 'evidence_id': ROOTS[1]}],
        'recurrence': 'FOUND', 'recurrence_evidence_ids': recurrence_ids(payload)})


def test_current_impact_severity_survives_unverified_historical_recurrence(retriever, view):
    """DETERMINISTIC reclassification and rebinding; MOCKED SEMANTIC verdicts. Members' "happening again" messages cited
    as history become reported recurrence (not corroborated); a cited record the judge rejects is removed. The HIGH
    level rests on its independent current-impact signal, and both affected reporters stay counted."""
    members = run('audio_playback', Fake(draft=lambda p: severity_draft(p, recurrence_ids=lambda q: [ROOTS[0]]),
                                         grounding=supported), retriever, view)
    assert any(d['code'] == 'RECURRENCE_RECLASSIFIED' for d in members['diagnostics'])
    severity = members['card']['severity']
    assert severity['level'] == 'HIGH' and severity['assessment_status'] == 'ASSESSED'
    assert severity['occurrence']['historical_recurrence']['status'] == 'NOT_CHECKED'
    assert severity['occurrence']['affected_reporters']['ids'] == ['U019', 'U018']
    assert 'severity:reported_recurrence' in {s['statement_id'] for s in members['grounding']['statements']}

    def record(payload):
        return [next(i['evidence_id'] for i in payload['retrieved_evidence'] if i['use'] != 'CURRENT_GUIDANCE')]
    rejected = run('audio_playback', Fake(draft=lambda p: severity_draft(p, recurrence_ids=record), grounding=lambda p: supported(
        p, **{'severity:recurrence': 'UNSUPPORTED', 'severity:rationale': 'PARTIALLY_SUPPORTED'})), retriever, view)
    severity = rejected['card']['severity']
    assert severity['level'] == 'HIGH' and severity['assessment_status'] == 'ASSESSED'
    assert severity['occurrence']['historical_recurrence']['status'] == 'NOT_CHECKED'
    assert severity['occurrence']['affected_reporters']['ids'] == ['U019', 'U018']
    assert severity['rationale'].startswith('Supported rubric signals: signal:HIGH[0]')  # Unsupported history removed.


def test_severity_justified_only_by_rejected_recurrence_is_not_defaulted(retriever, view):
    """MOCKED SEMANTIC verdicts; DETERMINISTIC rebinding. A MEDIUM whose only signal argued from history ("this happened
    in the last batch") and whose rationale rests on it: both are judged unsupported, so severity is UNASSESSED. It is
    not lowered or defaulted to LOW or MEDIUM."""
    result = run('audio_playback', Fake(draft=lambda p: severity_draft(
        p, recurrence_ids=lambda q: [ROOTS[0]], level='MEDIUM', signal=('MEDIUM', 0),
        support='The same confusion happened in the last batch.'), grounding=lambda p: supported(
        p, **{'severity:signal:MEDIUM[0]': 'UNSUPPORTED', 'severity:rationale': 'UNSUPPORTED'})), retriever, view)
    severity = result['card']['severity']
    assert severity['assessment_status'] == 'UNASSESSED' and severity['level'] == 'UNKNOWN'
    assert any('no rubric signal passed' in i for i in result['severity']['issues'])


# ---- Milestone 4 closeout: roles in card prose, attribution, dependency order, ToT fallback, agreeing sources ------

ACC = read_json(ROOT/'tests/fixtures/agent3_acceptance_v1_cases.json')['cases']
LEAD_IN_OMAR_THREAD = 'm:C_RP_GENERAL:1790933024.000339'  # Alex (U001, team lead) replying in Omar's (U018) thread.


def v5(value, model):
    """A recorded v4 output under the last contract its content satisfies (version label only; content unchanged):
    recorded drafts predate the v7 intervention need, as in replay."""
    from threadsense.agents.advisor_pilot import LEGACY_LABELS
    label = LEGACY_LABELS.get(model.__name__) or model.model_fields['contract_version'].default
    return model.model_validate({**value, 'contract_version': label})


def test_observed_false_name_rejections_are_valid_relations_and_roles_pass(view):
    """DETERMINISTIC. The three acceptance-run claims rejected as NAME_NOT_IN_CITED_EVIDENCE named the owner of the cited
    message's thread ("In Omar's thread, Alex asks ...") or, in a negation, the thread starter. Checked by canonical ID
    the relations hold, so the only remaining issue is presentation: card prose uses roles. Written with roles and
    canonical-ID attributions, the same claim passes."""
    for case in ACC['false_name_rejections']['claims']:
        _, ledger = members(view, case['scenario'])
        issues = claim_issues(make_draft(claims=[case['claim']]), ledger)
        assert issues and {i['code'] for i in issues} == {'PERSONAL_NAME_IN_PROSE'}, (case['scenario'], issues)
    _, ledger = members(view, 'json_vs_prose')
    recorded = ACC['false_name_rejections']['claims'][0]['claim']
    roles = {**recorded, 'text': "In a tutor's thread, the team lead asks for the exact formatting instruction so QA can "
                                 'verify whether it was mandatory. This applies to that thread, not as project guidance.',
             'attributions': [{'user_id': 'U018', 'relation': 'THREAD_STARTER', 'evidence_id': LEAD_IN_OMAR_THREAD},
                              {'user_id': 'U001', 'relation': 'AUTHOR', 'evidence_id': LEAD_IN_OMAR_THREAD}]}
    draft = make_draft(claims=[roles])
    assert claim_issues(draft, ledger) == []
    [statement] = [s for s in statements(draft, ledger) if s['statement_id'] == f"claim:{recorded['claim_id']}"]
    assert [(a['user_id'], a['role'], a['relation']) for a in statement['attributions']] == [
        ('U018', 'TUTOR', 'THREAD_STARTER'), ('U001', 'TEAM_LEAD', 'AUTHOR')]  # What the judge assesses.


@pytest.mark.parametrize('text, attributions, expected', [
    # Yuki (U019) posted in Omar's thread but did not write the cited message: participation supports only a
    # participation claim.
    ('Yuki asks for the exact formatting instruction.', [], ['NAME_RELATION_INVALID']),
    ('Yuki participated in the thread.', [], ['PERSONAL_NAME_IN_PROSE']),
    ('A QA tutor asks for the exact formatting instruction.', [('U019', 'AUTHOR')],
     ['ROLE_NOT_IN_CITED_EVIDENCE', 'ATTRIBUTION_INVALID']),
    ('The team lead asks for the exact formatting instruction.', [('U001', 'THREAD_STARTER')], ['ATTRIBUTION_INVALID']),
    ('A tutor in the thread took part.', [('U007', 'PARTICIPANT')], ['ATTRIBUTION_INVALID']),
    ('A QA tutor took part in the thread.', [('U019', 'PARTICIPANT')], []),
    ('A tutor reports the comparison problem.', [], ['ROLE_NOT_IN_CITED_EVIDENCE']),
    ('Three team leads report the comparison problem.', [], ['PLURAL_NOT_SUPPORTED_BY_DISTINCT_AUTHORS']),
    ('The team lead asks for the exact formatting instruction.', [('U001', 'AUTHOR')], []),
])
def test_attribution_is_checked_by_canonical_id_and_role(view, text, attributions, expected):
    """DETERMINISTIC. AUTHOR wrote the cited message, THREAD_STARTER started its thread, PARTICIPANT posted in it (only
    for a participation claim); role wording must match a cited author's role; plural wording needs that many distinct
    cited authors (one team lead message cannot support "three team leads report")."""
    _, ledger = members(view, 'json_vs_prose')
    claim = {'claim_id': 'c1', 'kind': 'INCIDENT_FACT', 'text': text, 'evidence_ids': [LEAD_IN_OMAR_THREAD],
             'attributions': [{'user_id': u, 'relation': r, 'evidence_id': LEAD_IN_OMAR_THREAD} for u, r in attributions]}
    issues = claim_issues(make_draft(claims=[claim]), ledger)
    assert [i['code'] for i in issues] == expected, issues
    if attributions and attributions[0] == ('U019', 'AUTHOR'):
        assert issues[-1]['detail'].endswith('(only PARTICIPANT).')


def test_names_in_summary_and_action_prose_are_withheld_but_quotes_are_untouched(view):
    """DETERMINISTIC. Every statement that can reach the card gets the same checks; quoted source text is never checked
    or changed."""
    _, ledger = members(view, 'json_vs_prose')
    claim = {'claim_id': 'c1', 'kind': 'INCIDENT_FACT', 'text': 'The team lead asks for the exact instruction.',
             'evidence_ids': [LEAD_IN_OMAR_THREAD], 'quote': 'Please paste the exact formatting instruction;',
             'quote_kind': 'VERBATIM'}
    draft = make_draft(claims=[claim], summary='Alex asks for the instruction.', proposed_action={
        'action_type': 'POST_ALIGNMENT', 'draft_text': 'Reply to Omar with the "Alex" quote rule.', 'support_claim_ids': ['c1']})
    codes_by = {(i['statement_id'], i['code']) for i in structural_issues(draft, ledger, set())}
    assert codes_by == {('summary', 'PERSONAL_NAME_IN_PROSE'), ('action', 'PERSONAL_NAME_IN_PROSE')}
    assert 'Verbatim quote: "Please paste the exact formatting instruction;"' in statements(draft, ledger)[0]['text']


def submit_case(view):
    case = ACC['submit_dependency']
    packet, ledger = members(view, 'submit_failure')
    ledger.update(case['retrieved_evidence'])
    draft = v5(case['draft'], AdvisorDraft)
    structural = structural_issues(draft, ledger, set(packet['member_ids']))
    return case, ledger, draft, structural, statements(draft, ledger)


def test_submit_dependency_inconsistency_is_caught_and_premises_are_shown_provisional(view):
    """DETERMINISTIC validation of the RECORDED Sol judgment. The judge named C13 essential while judging UNSUPPORTED the
    announcement C13 rests on (it saw C13 as SENT). Announcement applicability is applied first, so C13's final status is
    ANNOUNCEMENT_NOT_VERIFIED, and the action fails as ESSENTIAL_PREMISE_VOIDED_BY_DEPENDENCY. The judge is now shown
    C13 as pending its own verdict, with the announcement it depends on; no premise is presented as final."""
    case, ledger, draft, structural, stmts = submit_case(view)
    judgment = v5(case['judgment'], GroundingJudgment)
    assert 'claim:C13' in judgment.action_sufficiency.essential_statement_ids
    result = grounding_result(draft, ledger, stmts, structural=structural, judgment=judgment, ran=True)
    verdicts = {s['statement_id']: s for s in result['statements']}
    assert (verdicts['claim:C13']['model_verdict'], verdicts['claim:C13']['verdict']) == ('SUPPORTED', 'ANNOUNCEMENT_NOT_VERIFIED')
    assert verdicts['action']['verdict'] == 'ESSENTIAL_PREMISE_VOIDED_BY_DEPENDENCY'
    rejected = rejected_statements(draft, stmts, structural)
    payload = grounding_payload(stmts, ledger, {}, rejected, dependencies(draft, ledger))
    premises = {p['statement_id']: p for p in next(s for s in payload['statements'] if s['kind'] == 'ACTION')['premises']}
    announcement = 'announcement:k:slack:C_RP_ANNOUNCEMENTS:1790888971.000030:7db831c7'
    assert premises['claim:C13'] == {'statement_id': 'claim:C13', 'status': 'PENDING_YOUR_VERDICT', 'depends_on': [announcement]}
    assert not any(p['status'] == 'SENT' for p in premises.values())
    # The recorded claims name their authors (correctly); as v5 prose they are rejected and shown as REJECTED.
    assert premises['claim:C1']['status'] == 'REJECTED_PERSONAL_NAME_IN_PROSE'


def fallback_draft(payload):
    """A draft action resting on c2 (current guidance) and on c3, a named claim that is rejected as a name."""
    named = next(i for i in payload['member_evidence'] if i['author_id'] == 'U018')
    base = draft_for(payload, **open_q(payload))
    claims = base['claims'] + [{'claim_id': 'c3', 'kind': 'INCIDENT_FACT', 'text': 'Omar reports that audio will not play.',
                                'evidence_ids': [named['evidence_id']]}]
    return with_need({**base, 'claims': claims, 'proposed_action': {'action_type': 'POST_ALIGNMENT', 'support_claim_ids': ['c2', 'c3'],
                                                                    'draft_text': 'Post the current playback handling.'}},
                     [named['evidence_id']])


def fallback_tot(text='Post the current playback handling in the reporting threads.', close=False):
    def response(payload):
        guide = payload['draft']['claims'][1]['evidence_ids']
        return {'candidates': [
            {'candidate_id': 'A', 'action_type': 'POST_ALIGNMENT', 'draft_text': text, 'evidence_ids': guide,
             'evidence_support': 'STRONG', 'applicability': 'CURRENT', 'severity_fit': 'FITS', 'rationale': 'Current guidance applies.'},
            {'candidate_id': 'B', 'action_type': 'NO_ACTION', 'draft_text': 'Wait for the team lead.', 'evidence_ids': guide,
             'evidence_support': 'PARTIAL', 'applicability': 'CURRENT', 'severity_fit': 'FITS', 'rationale': 'r'}],
            'preferred_candidate_id': 'A', 'close_call': close, 'rationale': 'A is clearly better.'}
    return response


def test_valid_tot_candidate_replaces_a_withheld_draft_action(retriever, view):
    """MOCKED SEMANTIC verdicts; DETERMINISTIC selection. The judge names the rejected c3 essential, so the draft action
    is withheld. The preferred ToT candidate was judged as its own statement (SUPPORTED) with its own sufficiency over
    its premises (c2, final SUPPORTED): it becomes the card action with its exact text. The card stays NEEDS_REVIEW and
    keeps every review reason and inherited obligation."""
    sent = []
    result = run('audio_playback', Fake(draft=fallback_draft, tot=fallback_tot(), grounding=lambda p: sent.append(p) or supported(
        p, essential=['claim:c2', 'claim:c3'])), retriever, view)
    alternative = next(s for s in sent[0]['statements'] if s['statement_id'] == 'alternative:A')
    assert alternative['premises'] == [{'statement_id': 'claim:c2', 'status': 'PENDING_YOUR_VERDICT'}]
    verdicts = {s['statement_id']: s['verdict'] for s in result['grounding']['statements']}
    assert verdicts['claim:c3'] == 'REJECTED_PERSONAL_NAME_IN_PROSE' and verdicts['action'] == 'ESSENTIAL_PREMISE_NOT_PASSED'
    card = result['card']
    assert result['action_source'] == 'TOT_FALLBACK'
    assert card['recommended_action']['draft_text'] == 'Post the current playback handling in the reporting threads.'
    assert card['recommended_action']['source'] == 'TOT_FALLBACK' and card['recommended_action']['essential_premise_ids'] == ['claim:c2']
    assert any('reviewed alternative' in n for n in card['review_notes'])
    assert card['card_line'] == 'NEEDS_REVIEW' and {'GROUNDING_FAILURE', 'OPEN_CONFIRMATION', 'INHERITED_FLAG'} <= set(codes(result))
    assert result['coverage']['uncarried_obligations'] == []


@pytest.mark.parametrize('tot, grounding, reason', [
    (fallback_tot(), {'alternative:A': 'PARTIALLY_SUPPORTED'}, 'text judged PARTIALLY_SUPPORTED'),
    (fallback_tot(), {'essential': ['claim:c3']}, 'sufficiency check ESSENTIAL_ID_NOT_A_PREMISE'),
    (fallback_tot(text='Ask Omar to post the playback handling.'), {}, "issues ['NAME_RELATION_INVALID']"),
    (fallback_tot(close=True), {}, 'close call'),
])
def test_tot_fallback_needs_the_same_checks_as_the_draft_action(retriever, view, tot, grounding, reason):
    """MOCKED SEMANTIC verdicts; DETERMINISTIC selection. No fallback when the candidate's exact text was not SUPPORTED,
    its essential premises fail validation, its prose fails the presentation checks, or the comparison was a close
    call. The reason is recorded; nothing is rewritten."""
    def judge(payload):
        value = supported(payload, essential=['claim:c2', 'claim:c3'],
                          **{k: v for k, v in grounding.items() if k != 'essential'})
        if 'essential' in grounding:
            value['alternative_sufficiency'] = [{**a, 'essential_statement_ids': grounding['essential']}
                                                for a in value['alternative_sufficiency']]
        return value
    result = run('audio_playback', Fake(draft=fallback_draft, tot=tot, grounding=judge), retriever, view)
    assert result['card']['recommended_action'] is None and result['action_source'] == 'DRAFT'
    assert any(n.startswith('No ToT fallback') and reason in n for n in result['action_notes']), result['action_notes']


def pii_conflict(handling=None, **item_changes):
    case = ACC['pii_superseded_section']
    ledger = {k: {**v, **item_changes.get(k, {})} for k, v in case['retrieved_evidence'].items()}
    return make_draft(source_conflicts=case['source_conflicts']), ledger, set(case['established_handling'] if handling is None
                                                                              else handling)


@pytest.mark.parametrize('agreement, status, code', [
    ('SUPPORTED', 'RESOLVED_BY_RECORDED_SUPERSESSION', 'SUPERSEDED_SOURCE_EXPLAINS_CONFLICT'),
    ('UNSUPPORTED', 'DETECTED', 'CURRENT_SOURCE_AGREEMENT_NOT_ESTABLISHED'),
    ('PENDING', 'DETECTED', 'CURRENT_SOURCE_AGREEMENT_PENDING'),
    (None, 'DETECTED', 'CURRENT_SOURCE_AGREEMENT_NOT_YET_JUDGED'),
])
def test_several_agreeing_current_sources_explain_a_superseded_section(agreement, status, code):
    """DETERMINISTIC rule; the agreement is a semantic judgment (here prepared). Recorded PII conflict: the superseded
    help-page section against the current FAQ and the verified clarification that replaced it. With two current
    sources the record alone does not settle it: a non-blocking SOURCE_AGREEMENT statement goes to the final grounding,
    and only its SUPPORTED verdict resolves the conflict. The second recorded conflict (a status note against current
    sources, no superseded material) stays DETECTED: a real disagreement remains reviewable."""
    draft, ledger, handling = pii_conflict()
    agreements = [s for s in statements(draft, ledger, handling=handling) if s['kind'] == 'SOURCE_AGREEMENT']
    assert [(s['statement_id'], s['blocking']) for s in agreements] == [('temporal:conflict[0]', False)]
    result = temporal_check(draft, ledger, handling, None if agreement is None else {'temporal:conflict[0]': agreement})
    first, second = result['findings']
    assert (first['status'], first['code']) == (status, code)
    assert (second['status'], second['code']) == ('DETECTED', 'UNEXPLAINED_SOURCE_CONFLICT')


def test_uncertain_applicability_keeps_a_superseded_conflict_reviewable():
    """DETERMINISTIC. Even with agreement judged SUPPORTED, an unverified supersession on a current source, or a
    replacing announcement not verified for this topic, leaves the conflict DETECTED."""
    faq = 'k:safety-classification-faq@1.1:6025b955'
    item = ACC['pii_superseded_section']['retrieved_evidence'][faq]
    draft, ledger, handling = pii_conflict(**{faq: {'applicability': {**item['applicability'], 'unverified_supersession': ['x']}}})
    assert temporal_check(draft, ledger, handling, {'temporal:conflict[0]': 'SUPPORTED'})['findings'][0]['code'] == \
        'UNEXPLAINED_SOURCE_CONFLICT'
    draft, ledger, handling = pii_conflict(handling=[])
    assert temporal_check(draft, ledger, handling, {'temporal:conflict[0]': 'SUPPORTED'})['findings'][0]['code'] == \
        'UNEXPLAINED_SOURCE_CONFLICT'


def test_card_lists_related_threads_with_labels_and_permalink_or_thread_id(retriever, view):
    """DETERMINISTIC. Each member thread appears with a short label (channel, date, starter's role, opening words
    quoted from the source) and its stored permalink; the fixtures store none, so the thread ID is shown."""
    from threadsense.agents.advisor_checks import related_thread
    result = run('json_vs_prose', Fake(draft=draft_for, grounding=supported), retriever, view)
    card = result['card']
    assert card['contract_version'] == 'agent3-advice-card-v3'
    threads = card['related_threads']
    assert [t['thread_id'] for t in threads] == [m['thread_id'] for m in topic_packet(view, SCEN['json_vs_prose'])['members']]
    assert all(t['permalink'] is None and t['display_reference'] == t['thread_id'] and t['label'].startswith('#')
               and ', started by a' in t['label'] for t in threads)
    packet = topic_packet(view, SCEN['json_vs_prose'])
    member = packet['members'][0]
    linked = {**member, 'original_thread': {**member['original_thread'], 'permalink': 'https://example.slack.com/archives/x/p1'}}
    ref = related_thread(linked, packet)
    assert ref.display_reference == ref.permalink == 'https://example.slack.com/archives/x/p1'


def test_counts_in_prose_citing_no_member_message_use_the_topic_reporters(view):
    """DETERMINISTIC. An announcement rationale saying "these three reporters" cites only the announcement; the count is
    checked against the topic's distinct thread starters (three in JSON vs prose), not against zero cited authors."""
    from threadsense.agents.advisor_checks import prose_issues
    _, ledger = members(view, 'json_vs_prose')
    assert prose_issues('It does not say what these three reporters tried.', [], ledger) == []
    assert [c for c, _ in prose_issues('It does not say what these five reporters tried.', [], ledger)] == [
        'PLURAL_NOT_SUPPORTED_BY_DISTINCT_AUTHORS']


# ---- Team lead-facing card text and state (pilot v6) ------------------------------------------------------------

OBSERVED_SUMMARY = ('A QA tutor and three tutors report LT playback failures. [m:C_AUDIO_GENERAL:1790882197.000111; '
                    'k:audio-multimodal-instructions@1.3:1c6df70e]')  # The closeout-run audio summary's citation tail.


@pytest.mark.parametrize('text, expected', [
    (OBSERVED_SUMMARY, ['RAW_ID_IN_PROSE']),
    ('Post the reminder. Essential premises: the FAQ entry.', ['RAW_ID_IN_PROSE']),
    ('Use POST_ALIGNMENT for this batch.', ['RAW_ID_IN_PROSE']),
    ('A tutor reports that the "player shows a frozen grey waveform forever" in batch 06.', ['QUOTE_NOT_IN_SOURCE']),
    ('Post a reminder for batch 06 (task AUDIO-6012); report a technical issue rather than "QN".', []),
])
def test_display_text_carries_no_internal_ids_and_quotes_match_sources(view, text, expected):
    """DETERMINISTIC. Team lead-facing text has no evidence/claim/user IDs, enum names or premise lists (task references
    and short quoted terms are fine); a quoted passage of five or more words must be verbatim in a cited source."""
    from threadsense.agents.advisor_checks import display_issues
    _, ledger = members(view, 'audio_playback')
    assert [code for code, _ in display_issues(text, list(ledger.values())[:3])] == expected


def test_source_quotation_is_matched_exactly_and_exempt_from_role_rules(view):
    """DETERMINISTIC. A verbatim quotation of a member message passes exact-source matching; the same words altered
    fail it. A name inside a quotation is source text and is not checked or rewritten; outside quotes it is."""
    from threadsense.agents.advisor_checks import display_issues, prose_issues
    _, ledger = members(view, 'json_vs_prose')
    item = ledger[LEAD_IN_OMAR_THREAD]
    quote = 'Please paste the exact formatting instruction;'
    assert quote in item['excerpt']
    assert display_issues(f'The team lead asks: "{quote}"', [item]) == []
    assert [c for c, _ in display_issues('The team lead asks: "Please paste the full formatting instruction;"', [item])] == [
        'QUOTE_NOT_IN_SOURCE']
    assert prose_issues('The team lead asks: "Omar, please paste it."', [item], ledger) == []
    assert [c for c, _ in prose_issues('The team lead asks Omar to paste it.', [item], ledger)] == ['PERSONAL_NAME_IN_PROSE']


def readable_draft(payload):
    base = draft_for(payload)
    return {**base, 'summary': 'A tutor asks how to weigh format against accuracy. Current guidance covers it.',
            'review_note': 'Confirm that the reminder goes to batch 15 only.',
            'proposed_action': {**base['proposed_action'], 'instruction': 'Post a reminder in the batch channel that '
                                'format and accuracy are scored separately.', 'rationale': 'The current guidance already '
                                'answers the question; one reminder gives everyone the same rule.',
                                'draft_text': 'Reminder: score format and accuracy separately.'}}


def test_card_answers_what_happened_what_to_do_why_and_what_needs_review(retriever, view):
    """MOCKED SEMANTIC verdicts; DETERMINISTIC assembly. The card shows the summary, the action's familiar label, one
    instruction, the rationale and the copyable draft separately, and plain review notes; enums, premise IDs and
    statement IDs stay in structured fields. The judge sees exactly the displayed action text and rationale."""
    from threadsense.agents.advisor_checks import card_ids, card_names
    sent = []
    result = run('json_vs_prose', Fake(draft=readable_draft, grounding=lambda p: sent.append(p) or supported(p)), retriever, view)
    card, action = result['card'], result['card']['recommended_action']
    assert (action['label'], action['action_type']) == ('Post a reminder', 'POST_ALIGNMENT')
    assert action['instruction'].startswith('Post a reminder in the batch channel') and action['rationale'].startswith('The current')
    shown = {s['statement_id']: s['text'] for s in sent[0]['statements']}
    assert shown['action'] == ('Post a reminder. Instruction: Post a reminder in the batch channel that format and accuracy '
                               'are scored separately. Draft to copy: Reminder: score format and accuracy separately.')
    assert shown['action:rationale'].endswith('one reminder gives everyone the same rule.')
    assert card['review_notes'][0] == 'Confirm that the reminder goes to batch 15 only.'
    assert card_ids(card) == [] and card_names(card) == []
    assert 'claim:' not in card['reasoning'] and 'member_' not in card['reasoning'] and 'UNRESOLVED' not in card['reasoning']
    withheld = run('json_vs_prose', Fake(draft=readable_draft, grounding=lambda p: supported(
        p, **{'action:rationale': 'PARTIALLY_SUPPORTED'})), retriever, view)
    assert withheld['card']['recommended_action']['rationale'] is None  # The action stands; its unsupported "why" is withheld.
    assert withheld['card']['recommended_action']['instruction'] == action['instruction']


def test_blocked_revision_is_distinguished_from_evidence_not_found(retriever, view):
    """DETERMINISTIC state; MOCKED SEMANTIC gap detection. A follow-up that retrieved records whose revision was refused
    (over the input limit) is reported as found but not incorporated, not as missing evidence; the error text stays in
    the structured reason."""
    from threadsense.agents.advisor_pilot import InputLimitExceeded

    def missing(payload):
        coverage = [c for c in draft_for(payload)['coverage'] if c['need'] != 'PRIOR_DECISIONS'] + [
            {'need': 'PRIOR_DECISIONS', 'status': 'MISSING', 'note': 'Members recall an earlier workaround.', 'gap_id': 'g1'}]
        return draft_for(payload, coverage=coverage, gaps=[{
            'gap_id': 'g1', 'need': 'PRIOR_DECISION_OUTCOME', 'description': 'Outcome of the earlier workaround.',
            'follow_up': {'query': 'previous playback workaround trial outcome', 'source_types': ['decision', 'announcement'],
                          'version_mode': 'history'}}])
    blocked = run('audio_playback', Fake(draft=missing, revision=InputLimitExceeded('24310 input tokens > 24000; not sent'),
                                         grounding=supported), retriever, view)
    assert blocked['follow_ups'][0]['new_evidence_ids'], 'precondition: the follow-up retrieved new records'
    [issue] = blocked['coverage_issues']
    assert issue.endswith('were not incorporated (revision FAILED (RESOURCE))')
    notes = blocked['card']['review_notes']
    assert any('relevant records were found but not used, because the revision step did not run' in n for n in notes)
    assert any(n.startswith('The revision step did not complete (a request limit was reached)') for n in notes)
    assert not any('InputLimitExceeded' in n for n in notes)
    assert any('InputLimitExceeded' in r['detail'] for r in blocked['card']['needs_review_reasons'])


def test_stored_text_is_never_cut(retriever, view):
    """DETERMINISTIC. Inherited Agent 1 review text and the related threads' opening messages are stored complete; a label
    quotes the opening message's first sentence only when it is short and complete."""
    from threadsense.agents.advisor_checks import thread_label
    result = run('audio_playback', Fake(draft=draft_for, grounding=supported), retriever, view)
    packet = topic_packet(view, SCEN['audio_playback'])
    reasons = [o['agent1_record'].get('review_reason') for o in packet['record'].get('inherited_review_obligations', [])
               if o['member_id'] in packet['member_ids'] and o['agent1_record'].get('review_reason')]
    assert sorted(f['detail'] for f in result['card']['inherited_flags'] if f['origin'] == 'agent1') == sorted(reasons)
    for thread, member in zip(result['card']['related_threads'], packet['members']):
        root = next(m for m in member['original_thread']['messages'] if m['message_id'] == member['thread_id'])
        assert thread['opening_text'] == root['text'] and '…' not in thread['label']
    long = {'thread_id': '1.000001', 'channel_id': 'C', 'channel_name': 'c', 'created_at': '2026-10-01T00:00:00Z',
            'messages': [{'message_id': '1.000001', 'author_role': 'TUTOR', 'text': 'word ' * 40 + 'end. Next.'}]}
    assert thread_label(long) == '#c, 2026-10-01, started by a tutor'
    short = {**long, 'messages': [{**long['messages'][0], 'text': 'Player never loads, should I QN? I thought so.'}]}
    assert thread_label(short) == '#c, 2026-10-01, started by a tutor: "Player never loads, should I QN?"'


def test_rules_are_sent_once_and_prompt_version_is_recorded():
    """DETERMINISTIC. The task text carries the rules once (the JSON body no longer repeats them); the draft and revision
    rules include the writing guide and the two STYLE ONLY examples; the prompt version is fingerprinted; the input
    cap is 24,000 tokens."""
    from threadsense.agents.advisor_contracts import AdvisorDraft
    from threadsense.agents.advisor_pilot import (
        DRAFT_RULES, INPUT_TOKEN_LIMIT, REVISION_RULES, STYLE_EXAMPLES, WRITING_GUIDE, live_settings, prompt_fingerprints,
        task_description,
    )
    text = task_description({'rules': DRAFT_RULES, 'topic': {}}, AdvisorDraft)
    assert text.count(DRAFT_RULES) == 1 and '"rules"' not in text
    assert WRITING_GUIDE in DRAFT_RULES and STYLE_EXAMPLES in REVISION_RULES
    assert 'STYLE ONLY, NOT EVIDENCE' in STYLE_EXAMPLES and 'never copy their facts' in STYLE_EXAMPLES
    fingerprints = prompt_fingerprints()
    assert fingerprints['prompt_version'] == 'agent3-advisor-prompts-v7' and fingerprints['style_examples']
    assert INPUT_TOKEN_LIMIT == 24_000 and live_settings('openai/gpt-6.1-sol')['input_token_limit'] == 24_000


# ---- Readability run (pilot v6): recorded false rejections -----------------------------------------------------

READ = ACC['readability_false_rejections']


def test_recorded_possessive_plural_counts_thread_starters(view):
    """DETERMINISTIC. Recorded audio claim and HIGH[0] support: "In two tutors' threads, the team lead says ..." cites
    two team lead replies in threads started by two tutors. A possessive plural is about the threads' starters, so it
    passes; "three tutors' threads" over the same two threads still fails, and so does "two team leads say"."""
    from threadsense.agents.advisor_checks import prose_issues
    _, ledger = members(view, 'audio_playback')
    case = READ['possessive_plural']
    assert claim_issues(make_draft(claims=[case['claim']]), ledger) == []
    items = [ledger[e] for e in case['signal']['evidence_ids']]
    assert prose_issues(case['signal']['support'], items, ledger) == []
    assert [c for c, _ in prose_issues("In three tutors' threads, the team lead says it.", items, ledger)] == [
        'PLURAL_NOT_SUPPORTED_BY_DISTINCT_AUTHORS']
    assert [c for c, _ in prose_issues('Two team leads say the task cannot be evaluated.', items, ledger)] == [
        'PLURAL_NOT_SUPPORTED_BY_DISTINCT_AUTHORS']


def test_approving_authority_does_not_establish_authorship(retriever, view):
    """DETERMINISTIC. Recorded Submit history claim attributes the September 28 handoff record to the team lead (U001)
    as AUTHOR. The record names U001 as its approving authority, not its author, so the attribution is rejected (the
    readability-run fix had accepted it; corrected in Milestone 5). A Slack announcement record's actor is the posting
    message's author, so AUTHOR holds there."""
    _, ledger = members(view, 'submit_failure')
    case = READ['record_author']
    ledger.update(case['retrieved_evidence'])
    [issue] = claim_issues(make_draft(claims=[case['claim']]), ledger)
    assert issue['code'] == 'ATTRIBUTION_INVALID' and 'approving authority, which does not establish authorship' in issue['detail']
    from threadsense.agents.advisor_checks import relation_holds
    slack = next(i for i in safety_tools(retriever).ledger.values() if (i['citation'].get('source') or {}).get('system') == 'slack'
                 and i['authority'].get('actor'))
    assert relation_holds(slack['authority']['actor'], 'AUTHOR', slack, ledger)
    assert not relation_holds(slack['authority']['actor'], 'THREAD_STARTER', slack, ledger)


@pytest.mark.parametrize('text, expected', [
    ('The team lead wrote: "Keep it."', ['QUOTE_NOT_IN_SOURCE']),
    ('The team lead wrote "Please paste the exact formatting instruction;"', []),
    ('The FAQ calls it "fine".', ['QUOTE_NOT_IN_SOURCE']),
    ('Mark it as "QN" only if needed.', []),
])
def test_explicitly_attributed_quotations_are_matched_regardless_of_length(view, text, expected):
    """DETERMINISTIC. A quotation presented as someone's or something's words must match a cited source even when it is
    short; an unattributed short term in quotes is not a source quotation."""
    from threadsense.agents.advisor_checks import display_issues
    _, ledger = members(view, 'json_vs_prose')
    assert [c for c, _ in display_issues(text, [ledger[LEAD_IN_OMAR_THREAD]])] == expected


def test_grounding_sees_the_open_review_flags_a_review_note_relies_on(retriever, view):
    """DETERMINISTIC payload; the verdict is semantic. The recorded audio review note says upstream review flags remain
    open; the judge rejected it because the flags were not in its context. The grounding payload now carries every
    open upstream obligation for the topic's threads."""
    sent = []
    note = READ['review_note']['text']
    result = run('audio_playback', Fake(draft=lambda p: draft_for(p, review_note=note),
                                        grounding=lambda p: sent.append(p) or supported(p)), retriever, view)
    flags = sent[0]['open_review_flags']
    assert len(flags) == len(result['card']['inherited_flags']) == 2
    assert all(f['origin'] == 'agent1' and f['detail'] for f in flags)
    assert 'review_note' in {s['statement_id'] for s in sent[0]['statements']}
    assert result['card']['review_notes'][0] == note
