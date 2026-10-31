"""Regenerate tests/fixtures/agent3_pilot_scripted_judgments.json (prepared semantic responses).

Run after a chunking or corpus change moves evidence IDs (the real-embedding pilot test fails
when they drift): uv run --locked python tests/fixtures/make_agent3_pilot_scripted_judgments.py
Rubric signal texts come from the rubric loader, never retyped.
"""
import json
from pathlib import Path

from threadsense.agents.advice_inputs import load_effective_view
from threadsense.agents.advisor_pilot import HANDOFF, SCENARIOS, topic_packet
from threadsense.handoff_inputs import read_json
from threadsense.severity_rubric import load_rubric

ROOT = Path(__file__).resolve().parents[2]
R = load_rubric(None)['levels']
VIEW = load_effective_view(HANDOFF)
PACKETS = {s['id']: topic_packet(VIEW, s) for s in read_json(SCENARIOS)['scenarios'] if not s.get('control')}


def sig(level, index, support, ids):
    return {'level': level, 'signal_index': index, 'signal_text': R[level]['required_signals'][index],
            'support': support, 'evidence_ids': ids}


def m(channel, ts):
    return f'm:{channel}:{ts}'


A, RPG, RPQ, SG, SQ, MG, MQ, AQ = ('C_AUDIO_GENERAL', 'C_RP_GENERAL', 'C_RP_QA', 'C_SAFETY_GENERAL', 'C_SAFETY_QA',
                                   'C_MULTI_GENERAL', 'C_MULTI_QA', 'C_AUDIO_QA')
ANN = 'k:slack:C_AUDIO_ANNOUNCEMENTS:1790892000.000901:1c524924'


def resolution(scenario, states, basis):
    """Per-member states read from each member's own thread (all its messages cited); keys are member-ID suffixes."""
    members = PACKETS[scenario]['members']
    return [{'member_id': x['member_id'], 'state': states.get(x['member_id'][-6:], 'UNRESOLVED'),
             'evidence_ids': [m(x['channel_id'], msg['message_id']) for msg in x['original_thread']['messages']],
             'basis': basis.get(x['member_id'][-6:], basis['default'])} for x in members]


def statement_ids(draft, alternatives=()):
    """The statement IDs the pilot builds from a draft (advisor_checks.statements); extras are ignored."""
    ids = [f"claim:{c['claim_id']}" for c in draft['claims']] + ['summary']
    if draft.get('proposed_action') and draft['evidence_sufficiency'] != 'UNSUPPORTED':
        ids.append('action')
        if draft['proposed_action']['action_type'] != 'NO_ACTION':
            ids.append('action:need')  # with_need adds the intervention need to every operational action.
    ids += [f"announcement:{a['evidence_id']}" for a in draft.get('announcement_assessments', []) if a['relevant'] and a['directive']]
    ids += [f"resolution:{r['member_id']}" for r in draft.get('resolution', []) if r['state'] != 'UNKNOWN']
    ids += ['open_question'] if draft['open_confirmation'] == 'OPEN' else []
    severity = draft['severity']
    ids += ['severity:rationale'] + [f"severity:signal:{s['level']}[{s['signal_index']}]" for s in severity.get('signals', [])]
    ids += ['severity:recurrence'] if severity.get('recurrence') == 'FOUND' else []
    ids += ['severity:reported_recurrence'] if severity.get('reported_recurrence_evidence_ids') else []
    ids += [f'reporter:{a}' for a in dict.fromkeys(r['author_id'] for r in severity.get('affected_reporters', []))]
    return ids + [f'alternative:{c}' for c in alternatives]


def judged(draft, alternatives=(), **overrides):
    """Prepared verdicts: SUPPORTED unless overridden as statement_id=(verdict, rationale)."""
    action = draft.get('proposed_action') if 'action' in statement_ids(draft) else None
    return {'verdicts': [{'statement_id': i, 'verdict': overrides.get(i, ('SUPPORTED',))[0],
                          'rationale': overrides.get(i, (None, 'The cited excerpts state this directly.'))[1]}
                         for i in statement_ids(draft, alternatives)],
            'action_sufficiency': {'verdict': 'SUFFICIENT', 'essential_statement_ids': [f'claim:{c}' for c in action['support_claim_ids']],
                                   'rationale': 'The listed premises justify the action as worded.'} if action else None}


# --- audio_playback -------------------------------------------------------------------------------
audio_roots = [m(A, '1790882197.000111'), m(A, '1790896012.001900'), m(A, '1790920171.000109'), m(A, '1790934294.000106')]
audio_claims = [
    {'claim_id': 'c1', 'kind': 'INCIDENT_FACT', 'evidence_ids': audio_roots,
     'text': 'Four tutors in audio_batch_06 report that the LT player never loads or audio will not play, and ask whether to QN the task.'},
    {'claim_id': 'c2', 'kind': 'INCIDENT_FACT', 'evidence_ids': [m(A, '1790934394.000226')],
     'quote': 'The waveform loads but pressing Play never starts sound.',
     'text': 'At least one report describes a waveform that loads while Play never starts sound.'},
    {'claim_id': 'c3', 'kind': 'GUIDANCE', 'evidence_ids': [ANN, 'k:audio-multimodal-instructions@1.3:1c6df70e'],
     'quote': 'Treat this as a tool incident.',
     'text': 'Current handling: a player that never starts, including a visible waveform with no playback, is a tool '
             'incident; report the task ID, browser/error state and whether another clip plays, and do not choose content '
             'QN or score model quality solely because playback is unavailable.'},
    {'claim_id': 'c4', 'kind': 'GUIDANCE', 'evidence_ids': ['k:audio-multimodal-faq@1.1:c724358c'],
     'text': 'The FAQ answers the never-loading player case but has no entry for a visible waveform with no playback.'},
]
audio_severity = {
    'level': 'HIGH', 'rationale': 'Affected tasks cannot be evaluated while the player fails, and four distinct tutors '
                                  'report a comparable failure in the same batch within one day.',
    'signals': [sig('HIGH', 0, 'The TL states the affected task cannot be evaluated while the player fails to load.',
                    [m(A, '1790920220.000113')]),
                sig('HIGH', 3, 'Four distinct tutors report the same player failure in audio_batch_06 on 2026-10-01/02.', audio_roots)],
    'affected_reporters': [{'author_id': a, 'evidence_id': e} for a, e in zip(('U019', 'U018', 'U020', 'U013'), audio_roots)],
}
audio_action = {'action_type': 'UPDATE_FAQ', 'support_claim_ids': ['c3', 'c4'],
                'targets': [{'evidence_id': 'k:audio-multimodal-faq@1.1:c724358c', 'section': 'Playback and tool issues',
                             'change': 'ADD'}],
                'draft_text': 'Add an FAQ entry: a visible waveform with no playback is a playback/tool incident. Report the '
                              'task ID, browser/error state and whether another clip plays; do not QN or score model quality '
                              'solely because playback is unavailable.',
                'scope_note': 'audio_multimodal; mirrors the current instructions and the 2026-10-01 22:00 UTC announcement; '
                              'does not state that the player is fixed.'}
audio_draft = {
    'summary': 'Four tutors report the LT audio player never loads or never starts (including a visible waveform with no '
               'playback) and ask whether to QN, recalling an earlier workaround.',
    'reasoning': 'Current instructions and the 22:00 UTC handling announcement treat this as a tool incident and rule out QN '
                 'or model-quality scoring from unavailable playback alone. The FAQ has no waveform-without-playback entry. '
                 'Whether the earlier workaround worked is not yet shown.',
    'claims': audio_claims,
    'gaps': [{'gap_id': 'g1', 'need': 'PRIOR_DECISION_OUTCOME',
              'description': 'Members recall an earlier workaround; whether that trial worked is not in the evidence.',
              'follow_up': {'query': 'previous playback workaround trial outcome', 'source_types': ['decision', 'announcement'],
                            'version_mode': 'history'}}],
    'evidence_sufficiency': 'SUFFICIENT', 'proposed_action': audio_action,
    'severity': {**audio_severity, 'recurrence': 'NOT_CHECKED'}, 'confidence': 0.82, 'open_confirmation': 'NONE',
    'announcement_assessments': [{'evidence_id': ANN, 'relevant': True, 'directive': True,
                                  'directive_quote': 'Treat this as a tool incident.',
                                  'rationale': 'Posted for audio_batch_06 on 2026-10-01 about a player that never starts, '
                                               'including a visible waveform with no playback: the reported problem.'}],
    'resolution': resolution('audio_playback', {'e76f89': 'PARTIALLY_RESOLVED', '894091': 'PARTIALLY_RESOLVED'}, {
        'default': 'The TL asks for task IDs and a reproduction attempt; no handling or fix is given in the thread.',
        'e76f89': 'The TL gives interim handling (report the playback incident, do not mark a model-quality failure); '
                  'the player failure itself is not fixed.',
        '894091': 'The TL gives interim handling (report the playback incident, do not mark a model-quality failure); '
                  'the player failure itself is not fixed.'})}
audio_revision = {**audio_draft, 'gaps': [], 'claims': audio_claims + [
    {'claim_id': 'c5', 'kind': 'HISTORY', 'evidence_ids': ['k:audio-playback-trial-outcome@1.0:16332fce',
                                                           'k:audio-playback-trial-post@1.0:d674dbe6'],
     'quote': 'The trial did not provide a dependable general workaround.',
     'text': 'The August batch-05 one-reload trial restored playback in two of six attempts, did not provide a dependable '
             'workaround, and its posted guidance expired on August 28.'}],
    'reasoning': audio_draft['reasoning'].replace('Whether the earlier workaround worked is not yet shown.',
                                                  'The earlier reload trial was unsuccessful in sample and has expired, so '
                                                  'it is history, not current guidance.'),
    'severity': {**audio_severity, 'recurrence': 'FOUND', 'recurrence_evidence_ids': ['k:audio-playback-trial-outcome@1.0:16332fce']}}

# --- json_vs_prose --------------------------------------------------------------------------------
json_claims = [
    {'claim_id': 'c1', 'kind': 'INCIDENT_FACT',
     'evidence_ids': [m(RPG, '1790856332.000018'), m(RPQ, '1790913824.000016'), m(RPG, '1790933024.000339')],
     'text': 'Tutors ask whether an accurate prose response beats one that follows an explicitly required JSON format; the '
             'TL asked for the exact formatting instruction before weighing the responses.'},
    {'claim_id': 'c2', 'kind': 'GUIDANCE', 'evidence_ids': ['k:response-preference-faq@1.1:fa9b6a3d'],
     'quote': 'No universal tie-break rule is established for competing accuracy and instruction-following defects.',
     'text': 'Score format adherence and accuracy separately; no universal tie-break exists, and pairs the guidance does not '
             'settle go to TL confirmation with the prompt and both responses.'},
]
json_open = ('Whether accurate prose outweighs the required JSON format in RP-3824 needs a TL decision; current guidance '
             'defines no universal ordering and the exact prompt is not in the evidence.')
json_draft = {
    'summary': 'Tutors ask whether an accurate prose answer beats a response that follows a required JSON format.',
    'reasoning': 'Current guidance scores the two dimensions separately and sends unsettled pairs to the TL; no case decision '
                 'is recorded for these tasks.',
    'claims': json_claims,
    'gaps': [{'gap_id': 'g1', 'need': 'PRIOR_DECISION_OUTCOME', 'description': 'Has a TL ruled on JSON versus prose before?',
              'follow_up': {'query': 'TL decision on JSON required format versus accurate prose preference rule',
                            'source_types': ['decision'], 'version_mode': 'history'}},
             {'gap_id': 'g2', 'need': 'OTHER', 'description': 'The exact prompt and both responses for RP-3824 are not in the evidence.'}],
    'evidence_sufficiency': 'SUFFICIENT',
    'proposed_action': {'action_type': 'NO_ACTION', 'support_claim_ids': ['c2'],
                        'draft_text': 'Hold for TL confirmation; request the exact prompt and both responses for RP-3824.'},
    'severity': {'level': 'MEDIUM', 'rationale': 'The same format-versus-accuracy question recurs across three threads and '
                                                 'affects how pairs are scored.',
                 'signals': [sig('MEDIUM', 0, 'Three threads ask how to weigh a required format against accuracy.',
                                 [m(RPG, '1790856332.000018'), m(RPQ, '1790913824.000016'), m(RPG, '1790932885.000015')])]},
    'confidence': 0.7, 'open_confirmation': 'OPEN', 'open_question': json_open,
    'open_question_evidence_ids': ['k:response-preference-faq@1.1:fa9b6a3d'],
    'resolution': resolution('json_vs_prose', {}, {'default': 'No answer in the thread; the TL asks for the exact formatting '
                                                              'instruction before weighing the responses.'})}
json_revision = {**json_draft, 'gaps': [json_draft['gaps'][1]], 'claims': json_claims + [
    {'claim_id': 'c3', 'kind': 'HISTORY', 'evidence_ids': ['k:rp-format-rule-rejected@1.0:59d718d7'],
     'quote': 'Rejection also does not create a prose-first rule.',
     'text': 'On 2026-09-23 the TL rejected a universal JSON-first rule; the rejection did not create a prose-first rule, and '
             'unresolved trade-offs stay open for TL confirmation.'},
    {'claim_id': 'c4', 'kind': 'HISTORY', 'evidence_ids': ['k:rp-audit-manifest-approval@1.0:67038303'],
     'text': 'The JSON audit-manifest approval concerns export files and creates no preference rule for scored responses.'}],
    'proposed_action': {**json_draft['proposed_action'], 'support_claim_ids': ['c2', 'c3']}}
json_tot = {'contract_version': 'agent3-tot-comparison-v2', 'candidates': [
    {'candidate_id': 'A', 'action_type': 'NO_ACTION', 'evidence_ids': ['k:response-preference-faq@1.1:fa9b6a3d',
                                                                        'k:rp-format-rule-rejected@1.0:59d718d7'],
     'draft_text': 'Hold for TL confirmation with the exact prompt and both responses.', 'evidence_support': 'STRONG',
     'applicability': 'MIXED', 'severity_fit': 'FITS',
     'rationale': 'Matches the FAQ and the rejected JSON-first rule; does not decide the case without the materials.'},
    {'candidate_id': 'B', 'action_type': 'POST_ALIGNMENT', 'evidence_ids': ['k:rp-format-rule-rejected@1.0:59d718d7'],
     'draft_text': 'Announce that the JSON-formatted response wins whenever JSON is required.', 'evidence_support': 'WEAK',
     'applicability': 'CURRENT', 'severity_fit': 'PARTIAL',
     'rationale': 'Would settle the question quickly, but the TL rejected exactly this universal rule.'},
    {'candidate_id': 'C', 'action_type': 'SCHEDULE_ALIGNMENT', 'evidence_ids': ['k:response-preference-instructions@1.1:a71c54c7',
                                                                                 'k:rp-tie-calibration-outcome@1.0:053fe48a'],
     'draft_text': 'Short calibration: score format and accuracy separately on the three reported pairs before the TL decides.',
     'evidence_support': 'PARTIAL', 'applicability': 'MIXED', 'severity_fit': 'FITS',
     'rationale': 'Calibration helped in a prior sample but did not settle a format-versus-accuracy pair.'}],
    'preferred_candidate_id': 'A', 'close_call': False,
    'rationale': 'A follows current guidance and history; B restates a rejected rule; C is useful but secondary.'}

# --- fictional_pii --------------------------------------------------------------------------------
HELP, CLAR = 'k:safety-qn-help-page@1.0:983cdeaa', 'k:safety-fictional-pii-clarification@1.0:3682998e'
POST, SYNC = 'k:safety-pii-clarification-post@1.0:8dc35766', 'k:safety-doc-sync-outcome@1.0:cd4505b9'
pii_claims = [
    {'claim_id': 'c1', 'kind': 'INCIDENT_FACT',
     'evidence_ids': [m(SG, '1790890012.001700'), m(SG, '1790911772.000059'), m(SQ, '1790934673.000061')],
     'quote': 'I have two versions of the note open and they seem to differ.',
     'text': 'Three threads ask whether a made-up phone number in a fictional story requires QN; one QA tutor has two '
             'differing versions of the note open.'},
    {'claim_id': 'c2', 'kind': 'GUIDANCE', 'evidence_ids': [CLAR, 'k:safety-classification-faq@1.1:6025b955',
                                                           'k:safety-pii-clarification-post@1.0:8dc35766'],
     'text': 'Current rule SC-PII-2026-09-10 (effective 2026-09-10): clearly fictional placeholder phone numbers or emails '
             'alone do not require QN when no real individual is identifiable; ambiguity or another trigger still needs review.'},
    {'claim_id': 'c3', 'kind': 'HISTORY', 'evidence_ids': [HELP, CLAR],
     'text': "The QN help page v1.0 'Contact details' section quarantined any phone number even when made up; that section "
             'is superseded by SC-PII-2026-09-10.'},
]
pii_draft = {
    'summary': 'Tutors ask whether made-up phone numbers in fictional stories need QN, and see two differing versions of '
               'the guidance.',
    'reasoning': 'The dated clarification and the current FAQ answer the question; the older help-page section is '
                 'superseded, which explains the differing versions.',
    'claims': pii_claims,
    'gaps': [{'gap_id': 'g1', 'need': 'PRIOR_DECISION_OUTCOME',
              'description': 'Was the stale help-page copy corrected after the approved documentation sync?',
              'follow_up': {'query': 'help page documentation update outcome stale copy', 'source_types': ['decision'],
                            'version_mode': 'history'}}],
    'evidence_sufficiency': 'SUFFICIENT',
    'proposed_action': {'action_type': 'UPDATE_DOCUMENTATION', 'support_claim_ids': ['c2'],
                        'targets': [{'evidence_id': HELP, 'section': 'Contact details', 'change': 'CORRECT'}],
                        'draft_text': "Correct the QN help page v1.0 'Contact details' wording to match SC-PII-2026-09-10 "
                                      'and point tutors to the current instructions.',
                        'scope_note': 'safety_classification; fictional-contact branch only; other QN controls unchanged.'},
    'severity': {'level': 'MEDIUM', 'rationale': 'Two documentation versions disagree on QN handling for fictional contact '
                                                 'details, which is likely to affect how tasks are handled.',
                 'signals': [sig('MEDIUM', 1, 'A tutor has two differing versions of the note; the TL notes the posted wording '
                                              'may conflict with older PII examples.',
                                 [m(SQ, '1790934673.000061'), m(SG, '1790890151.000339')])]},
    'confidence': 0.86, 'open_confirmation': 'NONE',
    'source_conflicts': [{'evidence_ids': [HELP, CLAR], 'description': 'Help page v1.0 quarantines any phone number; the '
                                                                        'clarification exempts verified fictional placeholders.'}],
    'announcement_assessments': [
        {'evidence_id': CLAR, 'relevant': True, 'directive': True,
         'directive_quote': 'Clearly fictional placeholder phone numbers or email addresses alone do not require QN when the '
                            'surrounding evidence establishes that no real individual is identifiable.',
         'rationale': 'TL-approved, project-wide clarification effective 2026-09-10 for the fictional-contact branch of QN '
                      'handling: the question asked.'},
        {'evidence_id': POST, 'relevant': True, 'directive': True,
         'directive_quote': 'Verified fictional placeholders alone do not require QN when no real individual is identifiable.',
         'rationale': 'Posted to safety_batch_08, the batch these threads come from, announcing the same clarification.'}],
    'resolution': resolution('fictional_pii', {}, {
        'default': 'No answer in the thread; the current rule answers the question but the thread does not record it applied.',
        '0c0aff': 'The TL holds a general-rule update until the current rule is verified; no handling is given.'})}
pii_revision = {**pii_draft, 'gaps': [], 'claims': pii_claims + [
    {'claim_id': 'c4', 'kind': 'HISTORY', 'evidence_ids': [SYNC],
     'quote': 'Still contains the blanket initial-quarantine wording',
     'text': 'A follow-up inspection found the help page v1.0 still contains the blanket wording; the approved documentation '
             'sync was only partially completed.'},
    {'claim_id': 'c5', 'kind': 'HISTORY', 'evidence_ids': [SYNC],
     'quote': 'Contains the scoped fictional-placeholder rule',
     'text': 'The same inspection found safety instructions v1.4 already contain the scoped rule and FAQ v1.1 names the old '
             'help page and the dated clarification; only the help page copy remains stale.'}],
    'proposed_action': {**pii_draft['proposed_action'], 'support_claim_ids': ['c2', 'c4', 'c5'],
                        'draft_text': "Correct or retire the QN help page v1.0 'Contact details' wording so it matches "
                                      'SC-PII-2026-09-10. Instructions v1.4 and FAQ v1.1 already reflect the clarification '
                                      'and need no change.'}}

# --- korean_register ------------------------------------------------------------------------------
ko_roots = [m(MG, '1790856672.000159'), m(MG, '1790882012.001500'), m(MG, '1790897091.000160'), m(MQ, '1790931281.000162')]
korean_draft = {
    'summary': 'Four threads report Korean answers that switch from 존댓말 to 반말 and ask which QA rule applies.',
    'reasoning': 'The batch-10 precedent is limited to a quoted-speaker case; same-addressee switches need Korean language '
                 'QA with exact endings, as the FAQ and instructions direct.',
    'claims': [
        {'claim_id': 'c1', 'kind': 'INCIDENT_FACT', 'evidence_ids': ko_roots + [m(MQ, '1790931330.000113')],
         'quote': 'The response starts in 존댓말, then addresses the same person in 반말.',
         'text': 'Four threads report Korean answers that start in 존댓말 and switch to 반말; one says the switch addresses the '
                 'same person.'},
        {'claim_id': 'c2', 'kind': 'HISTORY', 'evidence_ids': ['k:multi-korean-scoped-result@1.0:5b489480'],
         'quote': 'The finding does not authorize a casual switch while addressing the same person without a discourse reason.',
         'text': 'The batch-10 precedent (M10-KO-017) found no penalty only because the casual sentence was a quote from '
                 'another speaker; it does not cover same-addressee switches.'},
        {'claim_id': 'c3', 'kind': 'GUIDANCE', 'evidence_ids': ['k:multilingual-eval-faq@1.1:c080929d',
                                                               'k:multilingual-eval-instructions@1.2:e19f0e0c'],
         'quote': 'Route the case to appropriate Korean or Japanese language QA with exact sentence endings and surrounding context.',
         'text': 'Current guidance routes Korean register shifts to Korean language QA with exact endings and context; a '
                 'shift alone is not a major penalty.'}],
    'evidence_sufficiency': 'SUFFICIENT',
    'proposed_action': {'action_type': 'ROUTE_TO_LANGUAGE_SPECIALIST', 'support_claim_ids': ['c2', 'c3'],
                        'draft_text': 'Route the four reports with the exact Korean endings and surrounding context to Korean '
                                      'language QA; do not apply the batch-10 quoted-speech finding to same-addressee switches.',
                        'scope_note': 'multi_batch_11; the precedent is from multi_batch_10 and scoped to one case.'},
    'severity': {'level': 'MEDIUM', 'rationale': 'The same register question recurs across four threads and affects scoring.',
                 'signals': [sig('MEDIUM', 0, 'Four threads ask how to score the same 존댓말-to-반말 switch.', ko_roots)]},
    'confidence': 0.76, 'open_confirmation': 'NONE',
    'resolution': resolution('korean_register', {}, {'default': 'No answer in the thread; reviewers ask for the exact Korean '
                                                                'endings and context.'})}

# --- submit_failure -------------------------------------------------------------------------------
HANDOFF_STATE, HANDOFF = 'k:rp-submit-engineering-handoff@1.0:6afb6e6d', 'k:rp-submit-engineering-handoff@1.0:d84c905d'
sub_roots = [m(RPG, '1790873412.001200'), m(RPG, '1790901577.000031'), m(RPG, '1790905337.000033'), m(RPG, '1790923325.000034')]
submit_draft = {
    'summary': 'Four reports in rp_batch_15 describe Submit staying grey or doing nothing after the rubric is complete.',
    'reasoning': 'Current instructions require capturing task ID, field state and button behavior; an engineering handoff '
                 'for earlier disabled-Submit reports is open. The resolved browser-zoom case is a different symptom.',
    'claims': [
        {'claim_id': 'c1', 'kind': 'INCIDENT_FACT', 'evidence_ids': sub_roots,
         'text': 'Four reports in rp_batch_15 describe Submit staying grey or doing nothing after the rubric is complete.'},
        {'claim_id': 'c2', 'kind': 'GUIDANCE', 'evidence_ids': ['k:response-preference-instructions@1.1:36683c52'],
         'quote': 'A selected label is not a completed submission until LT confirms it.',
         'text': 'Capture the task ID, required-field state, error and exact button behavior; a selected label is not a '
                 'completed submission until LT confirms it.'},
        {'claim_id': 'c3', 'kind': 'HISTORY', 'evidence_ids': [HANDOFF_STATE, HANDOFF],
         'text': 'An engineering handoff (SIM-ENG-RP-20260928-01) for earlier disabled-Submit reports is open with no fix '
                 'recorded; new reports must be matched to its symptoms before linking.'},
        {'claim_id': 'c4', 'kind': 'HISTORY', 'evidence_ids': ['k:rp-submit-zoom-generalization-rejected@1.0:044e436d'],
         'text': 'The earlier browser-zoom case concerned a Submit button below the visible area, not a disabled button, and '
                 'was resolved for two tasks only.'},
        {'claim_id': 'c5', 'kind': 'INFERENCE', 'evidence_ids': [HANDOFF_STATE, m(RPG, '1790873412.001200')],
         'text': 'These four reports share the cause already under investigation in SIM-ENG-RP-20260928-01.'}],
    'evidence_sufficiency': 'SUFFICIENT',
    'proposed_action': {'action_type': 'ESCALATE_ENGINEERING', 'support_claim_ids': ['c2', 'c3'],
                        'draft_text': 'Send the four task references with field state and button behavior to engineering and '
                                      'ask whether they match SIM-ENG-RP-20260928-01.'},
    'severity': {'level': 'HIGH', 'rationale': 'Tutors cannot submit completed work, and several distinct people report it '
                                               'in the same batch.',
                 'signals': [sig('HIGH', 0, 'A tutor reports LT does not let them submit the finished pair.', [sub_roots[3]]),
                             sig('HIGH', 3, 'Four distinct people report the same Submit failure in rp_batch_15.', sub_roots)],
                 'affected_reporters': [{'author_id': a, 'evidence_id': e} for a, e in zip(
                     ('U014', 'U015', 'U020', 'U002', 'U004'), sub_roots + [m(RPG, '1790923372.000113')])]},
    'confidence': 0.8, 'open_confirmation': 'NONE',
    'resolution': resolution('submit_failure', {}, {'default': 'The TL asks for task ID, field state and button behavior; '
                                                               'submission status is still unverified.'})}
submit_grounding = judged(submit_draft, **{'claim:c5': (
    'UNSUPPORTED', 'The handoff record says a similar button state does not establish the same cause; no cited source links '
                   'these reports to the open incident.')})

# --- repeated_ending ------------------------------------------------------------------------------
rep_roots = [m(A, '1790868894.000123'), m(A, '1790889930.000126'), m(A, '1790899012.002000'), m(A, '1790915994.000122'),
             m(AQ, '1790923533.000125')]
repeat_draft = {
    'summary': 'Five reports describe generated audio that speaks its final sentence twice although the transcript has it once.',
    'reasoning': 'Instructions require locating the repeat and comparing the downloaded file with player output before '
                 'calling it a generation defect; a prior report was kept as an observation for the same reason. No '
                 'comparison is recorded here, so the cause is not established.',
    'claims': [
        {'claim_id': 'c1', 'kind': 'INCIDENT_FACT', 'evidence_ids': rep_roots + [m(A, '1790889987.000113')],
         'text': 'Five reports describe the final sentence spoken twice while the transcript has it once; one reply says the '
                 'repeat is in the exported audio.'},
        {'claim_id': 'c2', 'kind': 'GUIDANCE', 'evidence_ids': ['k:audio-multimodal-instructions@1.3:7a5ab59d'],
         'quote': 'Do not call it a confirmed generation defect until the available evidence distinguishes generation from playback.',
         'text': 'Record where the phrase repeats, compare the downloaded file with player output if feasible, and do not '
                 'call it a confirmed generation defect until generation is distinguished from playback.'},
        {'claim_id': 'c3', 'kind': 'HISTORY', 'evidence_ids': ['k:audio-repeat-observation-review@1.0:ae0550d0'],
         'text': 'A prior repeated-ending report was retained as an observation; the TL deferred a confirmed-loop escalation '
                 'and requested a file-versus-player comparison.'}],
    'gaps': [{'gap_id': 'g1', 'need': 'OTHER', 'description': 'No downloaded-file versus player comparison is recorded for '
                                                              'these tasks, so the cause is not established.'}],
    'evidence_sufficiency': 'INSUFFICIENT',
    'proposed_action': {'action_type': 'NO_ACTION', 'support_claim_ids': ['c2', 'c3'],
                        'draft_text': 'Keep as an observation; ask reporters to note where the repeat starts and compare the '
                                      'downloaded file with player output.'},
    'severity': {'level': 'MEDIUM', 'rationale': 'The same scoring question recurs across five reports; impact is contained.',
                 'signals': [sig('MEDIUM', 0, 'Five reports ask how to handle the same repeated-ending behavior.', rep_roots)]},
    'confidence': 0.55, 'open_confirmation': 'NONE',
    'resolution': resolution('repeated_ending', {}, {'default': 'No answer in the thread; reviewers ask for a downloaded-file '
                                                                'versus player comparison.'})}
repeat_tot = {'contract_version': 'agent3-tot-comparison-v2', 'candidates': [
    {'candidate_id': 'A', 'action_type': 'NO_ACTION', 'evidence_ids': ['k:audio-multimodal-instructions@1.3:7a5ab59d',
                                                                        'k:audio-repeat-observation-review@1.0:ae0550d0'],
     'draft_text': 'Keep as an observation until a file-versus-player comparison exists.', 'evidence_support': 'STRONG',
     'applicability': 'MIXED', 'severity_fit': 'FITS', 'rationale': 'Matches the instruction and the prior deferral.'},
    {'candidate_id': 'B', 'action_type': 'POST_ALIGNMENT', 'evidence_ids': ['k:audio-multimodal-instructions@1.3:7a5ab59d'],
     'draft_text': 'Remind tutors to timestamp the repeat and compare the downloaded file with player output.',
     'evidence_support': 'PARTIAL', 'applicability': 'CURRENT', 'severity_fit': 'FITS',
     'rationale': 'Restates current guidance for five recent reports.'},
    {'candidate_id': 'C', 'action_type': 'ESCALATE_ENGINEERING', 'evidence_ids': [],
     'draft_text': 'Escalate a confirmed TTS generation loop.', 'evidence_support': 'STRONG', 'applicability': 'CURRENT',
     'severity_fit': 'PARTIAL', 'rationale': 'Several reports describe the same loop.'}],
    'preferred_candidate_id': 'A', 'close_call': True,
    'rationale': 'A and B are both supported and differ only in whether to post a reminder.'}

control_draft = {
    'summary': 'No retrieved source addresses contractor payroll deadlines.',
    'reasoning': 'The retrieved audio guidance concerns playback, scoring and onboarding; none mentions payroll.',
    'claims': [], 'gaps': [{'gap_id': 'g1', 'need': 'OTHER', 'description': 'No payroll source exists in the project knowledge.'}],
    'evidence_sufficiency': 'UNSUPPORTED', 'proposed_action': None,
    'severity': {'level': 'UNKNOWN', 'rationale': 'No incident evidence.'}, 'confidence': 0.9, 'open_confirmation': 'NONE'}

def with_coverage(draft):
    """Coverage derived from the prepared draft itself: COVERED by its own claims, MISSING where it requests a
    follow-up for a prior decision, otherwise NOT_APPLICABLE."""
    def cited(*kinds, prefix):
        return [e for c in draft['claims'] if c['kind'] in kinds for e in c['evidence_ids'] if e.startswith(prefix)]
    guidance, history = [e for e in cited('GUIDANCE', prefix='k:') if 'ANNOUNCEMENTS' not in e], cited('HISTORY', prefix='k:')
    announced = [a['evidence_id'] for a in draft.get('announcement_assessments', []) if a['relevant'] and a['directive']]
    asked = cited('INCIDENT_FACT', prefix='m:')
    prior_gap = next((g for g in draft.get('gaps', []) if g['need'] == 'PRIOR_DECISION_OUTCOME' and g.get('follow_up')), None)

    def item(need, ids, note):
        return {'need': need, 'status': 'COVERED', 'evidence_ids': ids, 'note': note} if ids else \
            {'need': need, 'status': 'NOT_APPLICABLE', 'note': 'Not needed for this advice.'}
    prior = {'need': 'PRIOR_DECISIONS', 'status': 'MISSING', 'note': prior_gap['description'], 'gap_id': prior_gap['gap_id']} \
        if prior_gap else item('PRIOR_DECISIONS', history, 'Earlier decisions and outcomes cited.')
    return {**draft, 'coverage': [item('CURRENT_GUIDANCE', guidance, 'Current guidance cited.'),
                                  item('ANNOUNCEMENTS', announced, 'Relevant directive announcements assessed.'), prior,
                                  item('MEMBER_QUESTIONS', asked, 'Member reports and questions cited.')]}


NEED_KIND = {'UPDATE_FAQ': 'GUIDANCE_GAP', 'UPDATE_DOCUMENTATION': 'GUIDANCE_GAP', 'ESCALATE_ENGINEERING': 'OPERATIONAL_PROBLEM',
             'ROUTE_TO_LANGUAGE_SPECIALIST': 'UNRESOLVED_HANDLING_QUESTION', 'POST_ALIGNMENT': 'UNRESOLVED_HANDLING_QUESTION',
             'SCHEDULE_ALIGNMENT': 'UNRESOLVED_HANDLING_QUESTION'}


def with_need(draft):
    """Draft v7: an operational action states its intervention need, citing the member reports among its premises."""
    action = draft.get('proposed_action')
    if not action or action['action_type'] == 'NO_ACTION':
        return with_coverage(draft)
    ids = [e for c in draft['claims'] if c['claim_id'] in action['support_claim_ids'] for e in c['evidence_ids'] if e.startswith('m:')] or         [e for c in draft['claims'] if c['kind'] == 'INCIDENT_FACT' for e in c['evidence_ids'] if e.startswith('m:')]
    need = {'kind': NEED_KIND[action['action_type']], 'evidence_ids': list(dict.fromkeys(ids)),
            'statement': 'The cited member reports raise a problem that their threads and the current records do not '
                         'settle, so it needs the team lead to act.'}
    return with_coverage({**draft, 'proposed_action': {**action, 'intervention_need': need}})


audio_draft, audio_revision, json_draft, json_revision, pii_draft, pii_revision, korean_draft, submit_draft, repeat_draft, \
    control_draft = map(with_need, (audio_draft, audio_revision, json_draft, json_revision, pii_draft, pii_revision,
                                        korean_draft, submit_draft, repeat_draft, control_draft))
responses = {
    'audio_playback': {'draft': audio_draft, 'revision': audio_revision, 'grounding': judged(audio_revision)},
    'json_vs_prose': {'draft': json_draft, 'revision': json_revision, 'tot': json_tot, 'grounding': judged(
        json_revision, 'ABC', **{'alternative:B': ('UNSUPPORTED', 'The cited record rejects exactly this universal rule.'),
                                 'alternative:C': ('PARTIALLY_SUPPORTED', 'Calibration helped once but did not settle a '
                                                                          'format-versus-accuracy pair.')})},
    'fictional_pii': {'draft': pii_draft, 'revision': pii_revision, 'grounding': judged(pii_revision)},
    'korean_register': {'draft': korean_draft, 'grounding': judged(korean_draft)},
    'submit_failure': {'draft': submit_draft, 'grounding': submit_grounding},
    'repeated_ending': {'draft': repeat_draft, 'tot': repeat_tot, 'grounding': judged(repeat_draft, 'AB')},
    'control_unsupported_payroll': {'draft': control_draft},
}
out = ROOT/'tests/fixtures/agent3_pilot_scripted_judgments.json'
payload = {'version': 'agent3-pilot-scripted-judgments-v5',
           'purpose': 'Prepared semantic responses (draft, revision, grounding, ToT) for the offline pilot run. They exercise '
                      'the deterministic checks and routing; they are not model output and say nothing about model quality. '
                      'Evidence IDs refer to the knowledge-chunks-v2 index; drafts follow advisor draft v7 (operational '
                      'actions state an intervention need) and grounding judgment v4.',
           'responses': responses}
out.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
print('wrote', out)
