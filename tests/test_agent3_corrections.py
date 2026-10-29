"""Milestone 4 correction pass: regressions replaying recorded live-v1 failures, and the v3 workflow changes.

Recorded failures come from tests/fixtures/agent3_live_v1_failures.json (exact gpt-4o-mini output, with the
raw-response SHA-256). DETERMINISTIC tests are guaranteed by code; MOCKED SEMANTIC tests depend on a prepared
grounding verdict and say nothing about real model behaviour.
"""
import pytest
from pydantic import ValidationError

from threadsense.agents.advisor_checks import (
    build_severity, claim_issues, coverage_issues, grounding_result, rejected_statements, sendable, statements,
    structural_issues,
)
from threadsense.agents.advisor_contracts import GroundingJudgment, SeverityProposal
from threadsense.agents.advisor_evidence import member_messages
from threadsense.agents.advisor_pilot import topic_packet
from threadsense.handoff_inputs import ROOT, read_json
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
    same words go to the judge instead."""
    packet, ledger = members(view, 'fictional_pii')
    ledger.update(safety_tools(retriever).ledger)
    case = FAIL['quotation']
    assert case['claim']['evidence_ids'][0] in ledger, 'precondition: the cited FAQ chunk is in the ledger'
    draft = make_draft(claims=[*case['other_claims'], case['claim'], FAIL['guidance_from_slack']['claim']])
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
    Yuki (U019) and Leo (U007), who wrote the cited messages, so they pass; naming someone who wrote none of the
    cited messages is rejected."""
    _, ledger = members(view, 'json_vs_prose')
    claims = FAIL['named_people']['claims']
    assert ledger[claims[0]['evidence_ids'][0]]['author_name'] == 'Yuki'
    assert claim_issues(make_draft(claims=claims), ledger) == []
    swapped = make_draft(claims=[{**claims[0], 'text': claims[0]['text'].replace('Yuki', 'Leo')}])
    assert [i['code'] for i in claim_issues(swapped, ledger)] == ['NAME_NOT_IN_CITED_EVIDENCE']


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
    leaving it open; a NEEDS_REVIEW card still carries a supported action; an unsupported open question keeps its flag
    (never cleared) but says it was not supported."""
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
    [reason] = [r for r in rejected['card']['needs_review_reasons'] if r['code'] == 'OPEN_CONFIRMATION']
    assert reason['detail'].endswith('not supported by the evidence; see diagnostics)')
    assert rejected['card']['checks']['open_confirmation'] == 'OPEN'


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
    assert 'PRIOR_DECISIONS: missing (follow-up requested)' in result['coverage_issues']
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
