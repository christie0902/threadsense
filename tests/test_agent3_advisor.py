"""Agent 3 Advisor pilot, offline. Test-double encoder index; the model is a scripted fake.

Docstrings mark each test DETERMINISTIC (no semantic judgment involved) or MOCKED SEMANTIC
(the outcome depends on a prepared draft/grounding/ToT response; real model behaviour is
not tested here).
"""
from copy import deepcopy
import json
import shutil

import pytest

from threadsense.agents.advice_inputs import load_effective_view
from pydantic import ValidationError

from threadsense.agents.advisor_checks import (
    action_issues, announcement_issues, build_severity, claim_issues, resolution_issues, temporal_check, topic_resolution,
)
from threadsense.agents.advisor_contracts import AdvisorDraft, SeverityProposal
from threadsense.agents.advisor_evidence import (
    Budget, ResearchTools, StaleIndexError, member_messages, open_retriever,
)
from threadsense.agents.advisor_pilot import (
    BUDGET, DRAFT_RULES, HANDOFF, SCENARIOS, _research_payload, advise, control, plan, run_pilot, task_description,
    topic_packet, write_outputs,
)
from threadsense.handoff_inputs import read_json
from threadsense.retrieval.config import KNOWLEDGE_ROOT
from threadsense.retrieval.index import build_index
from threadsense.retrieval.search import Retriever
from threadsense.severity_rubric import load_rubric
from tests.retrieval_doubles import HashEncoder

SCEN = {s['id']: s for s in read_json(SCENARIOS)['scenarios']}
RUBRIC = load_rubric(None)
ANNOUNCEMENT = '1790892000.000901'
REMINDER = '1790914912.000140'  # "Reminder to use headphones for the audio calibration exercise."


@pytest.fixture(scope='module')
def retriever(tmp_path_factory):
    index = tmp_path_factory.mktemp('advisor')/'index'
    build_index(index, encoder=HashEncoder())
    return Retriever(index, encoder=HashEncoder())


@pytest.fixture(scope='module')
def view():
    return load_effective_view(HANDOFF)


class Fake:
    """Scripted model. Records the exact task text a live CrewAI call would receive."""
    label = 'TEST_FAKE'

    def __init__(self, **stages):
        self.stages, self.calls = stages, []

    def complete(self, stage, payload, schema):
        self.calls.append((stage, task_description(payload, schema)))
        response = self.stages[stage]
        if isinstance(response, Exception):
            raise response
        value = response(payload) if callable(response) else response
        return value if isinstance(value, str) else json.dumps(value)

    def stages_called(self):
        return [stage for stage, _ in self.calls]


def sent_payload(description):
    """Invert task_description: the JSON object the model actually received."""
    return json.loads(description.split('Input JSON:\n', 1)[1].rsplit('\n\nReturn exactly one JSON object', 1)[0])


def first(payload, *uses):
    return next(i['evidence_id'] for i in payload['retrieved_evidence'] if i['use'] in uses)


def draft_for(payload, **overrides):
    """A plausible structurally valid draft built only from what the payload offers."""
    guide = next((i['evidence_id'] for i in payload['retrieved_evidence'] if i['use'] == 'CURRENT_GUIDANCE'), None)
    base = {'summary': 'A member reports the problem.', 'reasoning': 'Cited guidance applies.',
            'claims': [{'claim_id': 'c1', 'kind': 'INCIDENT_FACT', 'text': 'A member reports the issue.',
                        'evidence_ids': [payload['member_evidence'][0]['evidence_id']]}] +
                      ([{'claim_id': 'c2', 'kind': 'GUIDANCE', 'text': 'Current guidance covers it.', 'evidence_ids': [guide]}]
                       if guide else []),
            'evidence_sufficiency': 'SUFFICIENT',
            'proposed_action': {'action_type': 'POST_ALIGNMENT', 'draft_text': 'Post a reminder.', 'support_claim_ids': ['c2']}
            if guide else None,
            'severity': {'level': 'LOW', 'rationale': 'Contained.'}, 'confidence': 0.9, 'open_confirmation': 'NONE',
            'coverage': [{'need': n, 'status': 'NOT_APPLICABLE', 'note': 'Not needed for this test draft.'}
                         for n in ('CURRENT_GUIDANCE', 'ANNOUNCEMENTS', 'PRIOR_DECISIONS', 'MEMBER_QUESTIONS')]}
    return {**base, **overrides}


def open_q(payload, question='Which rule wins when the two current sources disagree?'):
    """Open-confirmation fields: a specific question plus the evidence that leaves it open."""
    return {'open_confirmation': 'OPEN', 'open_question': question,
            'open_question_evidence_ids': [payload['member_evidence'][0]['evidence_id']]}


def supported(payload, essential=None, **overrides):
    """Grounding judgment over the statements actually sent: SUPPORTED unless overridden by statement ID. For an action,
    a SUFFICIENT judgment naming `essential` premises (default: every premise that was sent)."""
    def passed(statement):
        return [p['statement_id'] for p in statement.get('premises', []) if not p['status'].startswith('REJECTED')]
    action = next((s for s in payload['statements'] if s['kind'] == 'ACTION'), None)
    return {'verdicts': [{'statement_id': s['statement_id'], 'verdict': overrides.get(s['statement_id'], 'SUPPORTED'),
                          'rationale': 'Stated.'} for s in payload['statements']],
            'action_sufficiency': {'verdict': 'SUFFICIENT', 'essential_statement_ids': passed(action) if essential is None
                                   else essential, 'rationale': 'The premises justify the action.'} if action else None,
            'alternative_sufficiency': [{'statement_id': s['statement_id'], 'verdict': 'SUFFICIENT',
                                         'essential_statement_ids': passed(s), 'rationale': 'The premises justify it.'}
                                        for s in payload['statements'] if s['kind'] == 'ALTERNATIVE' and passed(s)]}


def run(scenario_id, client, retriever, view, *, budget=None, **kw):
    return advise(SCEN[scenario_id], view=view, retriever=retriever, client=client, budget=budget or Budget(BUDGET),
                  rubric=RUBRIC, run_id='run_test', as_of=retriever.manifest['cutoff'], **kw)


def codes(result):
    return [r['code'] for r in result['card']['needs_review_reasons']]


def make_draft(**kw):
    return AdvisorDraft.model_validate({'summary': 's', 'reasoning': 'r', 'evidence_sufficiency': 'SUFFICIENT',
                                        'severity': {'level': 'LOW', 'rationale': 'x'}, 'confidence': 0.9,
                                        'open_confirmation': 'NONE', **kw})


# ---- Freshness, serialization, applicability (DETERMINISTIC) ---------------------------------------

def test_stale_or_incompatible_index_is_refused_once_before_research(tmp_path):
    """DETERMINISTIC. One staleness check at startup; none per query; stale/incompatible -> rebuild instructions."""
    knowledge, index = tmp_path/'knowledge', tmp_path/'index'
    shutil.copytree(KNOWLEDGE_ROOT, knowledge, ignore=shutil.ignore_patterns('__pycache__'))
    build_index(index, encoder=HashEncoder(), knowledge_root=knowledge)
    checks = []

    class Counting(Retriever):
        def staleness(self, **sources):
            checks.append(sources)
            return super().staleness(**sources)
    opened = open_retriever(index, encoder=HashEncoder(), retriever_class=Counting, knowledge_root=knowledge)
    tools = ResearchTools(opened, project='audio_multimodal', batch=None, as_of=opened.manifest['cutoff'], budget=Budget({}))
    for query in ('player never loads', 'repeated ending', 'clipping'):
        tools.search(query, purpose='test')
    assert len(checks) == 1
    faq = knowledge/'faq/audio_multimodal_faq.md'
    faq.write_text(faq.read_text(encoding='utf-8') + '\nAn added sentence.\n', encoding='utf-8')
    with pytest.raises(StaleIndexError, match='build_retrieval_index.py --rebuild'):
        open_retriever(index, encoder=HashEncoder(), knowledge_root=knowledge)
    manifest = json.loads((index/'manifest.json').read_text(encoding='utf-8'))
    (index/'manifest.json').write_text(json.dumps({**manifest, 'chunking_version': 'knowledge-chunks-v1'}), encoding='utf-8')
    with pytest.raises(StaleIndexError, match='--rebuild'):
        open_retriever(index, encoder=HashEncoder(), knowledge_root=knowledge)


def safety_tools(retriever):
    tools = ResearchTools(retriever, project='safety_classification', batch='safety_batch_08',
                          as_of=retriever.manifest['cutoff'], budget=Budget({}), top_k=40)
    tools.search('fictional phone number quarantine clarification', purpose='test')
    tools.search('quarantine any task containing a phone number contact details', purpose='test', version_mode='history')
    return tools


def test_model_receives_applicability_beside_each_excerpt(retriever):
    """DETERMINISTIC. Parsed from the exact task text: identity, applicability, replacement, dates, scope,
    authority and states travel with the excerpt; withheld sections are listed; history is not guidance."""
    tools = safety_tools(retriever)
    payload = _research_payload(DRAFT_RULES, {'project_id': 'safety_classification'}, tools.ledger, tools, RUBRIC, [])
    sent = sent_payload(task_description({**payload, 'output_schema': {}}, AdvisorDraft))
    old = next(i for i in sent['retrieved_evidence'] if i['citation']['authoring'] == 'safety-qn-help-page@1.0'
               and i['citation']['sections'] == ['Contact details'])
    assert old['use'] == 'HISTORY_ONLY' and old['applicability']['state'] == 'SECTION_SUPERSEDED'
    assert old['applicability']['replaced_by'][0]['replaced_by'] == 'safety-fictional-pii-clarification@1.0'
    status = old['excerpt'].split('\n', 1)[0]
    assert status.startswith('[HISTORICAL - NOT CURRENT GUIDANCE') and 'safety-fictional-pii-clarification@1.0' in status
    assert all(old['citation'][k] for k in ('document_id', 'version_id', 'chunk_id', 'authoring', 'title', 'source'))
    assert old['dates']['source_date'] and old['dates']['reference_time'] == retriever.manifest['cutoff']
    assert old['scope'] == {'project_id': 'safety_classification', 'batch_id': None, 'scope': 'project', 'batch_relation': 'project_wide'}
    assert set(old['authority']) == {'role', 'actor', 'approval_status', 'provenance'}
    assert old['recorded_states']['status'] == 'partially_superseded'
    clarification = next(i for i in sent['retrieved_evidence'] if i['citation']['authoring'] == 'safety-fictional-pii-clarification@1.0')
    assert clarification['use'] == 'ANNOUNCEMENT' and clarification['applicability']['supersedes'][0]['section'] == 'Contact details'
    assert clarification['excerpt'].startswith('[ANNOUNCEMENT posted') and clarification['authority']['approval_status']
    [withheld] = [w for w in sent['retrieval_notes']['withheld_by_version'] if w['authoring'] == 'safety-qn-help-page@1.0']
    assert withheld['sections'] == ['Contact details'] and withheld['replaced_by'][0]['replaced_by'] == 'safety-fictional-pii-clarification@1.0'
    draft = make_draft(claims=[{'claim_id': 'c1', 'kind': 'GUIDANCE', 'text': 'Quarantine any phone number.',
                                'evidence_ids': [old['evidence_id']]}])
    assert [i['code'] for i in claim_issues(draft, tools.ledger)] == ['GUIDANCE_WITHOUT_CURRENT_SOURCE',
                                                                      'HISTORICAL_SOURCE_AS_CURRENT_GUIDANCE']


def test_future_and_draft_revisions_leave_approved_guidance_current(tmp_path):
    """DETERMINISTIC. A future-effective 1.4 and a draft 1.5 do not displace or conflict with approved 1.3."""
    from tests.test_retrieval_versions import LEGACY, corpus
    revised = corpus(tmp_path, (('audio_v1.4.md',), {'version': '1.4', 'effective': '2026-10-15T13:00:00Z', 'extra': LEGACY}),
                     (('audio_v1.5.md',), {'version': '1.5', 'effective': '2026-09-20T13:00:00Z', 'status': 'draft', 'extra': LEGACY}))
    tools = ResearchTools(revised, project='audio_multimodal', batch=None, as_of=revised.manifest['cutoff'], budget=Budget({}), top_k=40)
    tools.search('purple reload lever twice playback unavailable', purpose='test', source_types=['guideline'])
    items = [i for i in tools.ledger.values() if i['citation']['authoring'].startswith('audio-multimodal-instructions')]
    assert {i['citation']['authoring'] for i in items} == {'audio-multimodal-instructions@1.3'}
    item = next(i for i in items if i['citation']['sections'] == ['Playback and unavailable content'])
    assert item['use'] == 'CURRENT_GUIDANCE'
    assert {o['authoring']: o['state'] for o in item['applicability']['other_revisions']} == {
        'audio-multimodal-instructions@1.4': 'NOT_YET_EFFECTIVE', 'audio-multimodal-instructions@1.5': 'NOT_APPROVED'}
    draft = make_draft(claims=[{'claim_id': 'c1', 'kind': 'GUIDANCE', 'text': 'Report a tool incident.',
                                'evidence_ids': [item['evidence_id']]}])
    assert claim_issues(draft, tools.ledger) == [] and temporal_check(draft, tools.ledger)['status'] == 'NONE_FOUND'


def test_history_mode_still_respects_the_as_of_cutoff(retriever):
    """DETERMINISTIC. History widens versions, never time: the 22:00 announcement is absent before 22:00."""
    def announcement_ids(as_of):
        tools = ResearchTools(retriever, project='audio_multimodal', batch='audio_batch_06', as_of=as_of, budget=Budget({}), top_k=50)
        tools.search('player never starts playback handling', purpose='test', source_types=['announcement'], version_mode='history')
        return {i['citation']['source'].get('thread_id') or i['evidence_id'] for i in tools.ledger.values()}
    assert not any(ANNOUNCEMENT in str(x) for x in announcement_ids('2026-10-01T21:59:59Z'))
    assert any(ANNOUNCEMENT in str(x) for x in announcement_ids(retriever.manifest['cutoff']))


# ---- Grounding (DETERMINISTIC structure; MOCKED SEMANTIC verdicts) ----------------------------------

def test_structural_failures_reject_only_their_statements(retriever, view):
    """DETERMINISTIC. Incident facts from retrieved sources, unknown IDs and non-verbatim quotes are rejected before any
    judgment and never sent; unaffected statements still go to the one semantic call."""
    def bad(payload):
        claims = draft_for(payload)['claims']
        claims[0]['evidence_ids'] = [first(payload, 'CURRENT_GUIDANCE')]  # Incident fact from guidance.
        return draft_for(payload, claims=claims + [
            {'claim_id': 'c3', 'kind': 'HISTORY', 'text': 'Invented.', 'evidence_ids': ['k:not-in-ledger@1:00000000']},
            {'claim_id': 'c4', 'kind': 'GUIDANCE', 'text': 'Quoted.', 'evidence_ids': [first(payload, 'CURRENT_GUIDANCE')],
             'quote': 'HISTORICAL - NOT CURRENT GUIDANCE'}])
    sent = []
    client = Fake(draft=bad, grounding=lambda p: sent.append(p) or supported(p))
    result = run('audio_playback', client, retriever, view)
    assert client.stages_called() == ['draft', 'grounding']
    assert result['grounding']['status'] == 'FAILED' and result['grounding']['basis'] == 'STRUCTURAL+SEMANTIC'
    assert {i['code'] for i in result['grounding']['structural_issues']} == {
        'INCIDENT_FACT_NEEDS_MEMBER_EVIDENCE', 'UNKNOWN_EVIDENCE', 'QUOTE_NOT_VERBATIM'}
    assert set(result['grounding']['rejected']) == {'claim:c1', 'claim:c3', 'claim:c4'}
    judged = {s['statement_id'] for s in sent[0]['statements']}
    assert not judged & {'claim:c1', 'claim:c3', 'claim:c4'} and {'claim:c2', 'summary', 'action'} <= judged
    assert result['card']['checks']['grounding'] == 'FAILED' and 'GROUNDING_FAILURE' in codes(result)


@pytest.mark.parametrize('judgment, expected', [
    (lambda p: supported(p), 'PASSED'),
    (lambda p: supported(p, **{'claim:c2': 'PARTIALLY_SUPPORTED'}), 'FAILED'),
    (lambda p: {'verdicts': supported(p)['verdicts'][:1]}, 'FAILED'),
    (lambda p: supported(p, action='UNSUPPORTED'), 'FAILED'),
    (lambda p: supported(p, summary='UNSUPPORTED'), 'FAILED'),
])
def test_citation_existence_alone_never_passes_grounding(retriever, view, judgment, expected):
    """MOCKED SEMANTIC. Structurally valid citations pass only with a SUPPORTED verdict on every blocking
    statement (claims, summary, action, severity); partial, missing or action-level failures all fail."""
    client = Fake(draft=draft_for, grounding=judgment)
    result = run('audio_playback', client, retriever, view)
    assert result['grounding']['structural_issues'] == [] and result['grounding']['status'] == expected
    assert result['card']['checks']['grounding'] == expected


def test_unavailable_grounding_is_not_run_never_passed(retriever, view):
    """DETERMINISTIC. A failed grounding call leaves NOT_RUN with GROUNDING_NOT_RUN; nothing is retried."""
    client = Fake(draft=draft_for, grounding=RuntimeError('provider down'))
    result = run('korean_register', client, retriever, view)
    assert client.stages_called() == ['draft', 'grounding']
    assert result['card']['checks']['grounding'] == 'NOT_RUN' and 'GROUNDING_NOT_RUN' in codes(result)
    assert result['card']['card_line'] == 'NEEDS_REVIEW'
    assert [c['status'] for c in result['model_calls']] == ['OK', 'FAILED']


# ---- Severity and separate judgments (DETERMINISTIC binding) -----------------------------------------

def test_severity_binds_to_member_evidence_and_rubric_text(view):
    """DETERMINISTIC. Signals need member evidence and exact rubric text; repliers are not affected reporters."""
    packet = topic_packet(view, SCEN['audio_playback'])
    ledger = {i['evidence_id']: i for i in member_messages(packet['members'])}
    ledger['k:guide'] = {'evidence_id': 'k:guide', 'origin': 'retrieved_source', 'use': 'CURRENT_GUIDANCE'}
    report, tl_reply = 'm:C_AUDIO_GENERAL:1790882197.000111', 'm:C_AUDIO_GENERAL:1790882343.000339'
    signal = RUBRIC['levels']['MEDIUM']['required_signals'][2]

    def proposal(**kw):
        return SeverityProposal.model_validate({'level': 'MEDIUM', 'rationale': 'Contained player failure.', **kw})
    good, issues = build_severity(proposal(
        signals=[{'level': 'MEDIUM', 'signal_index': 2, 'signal_text': signal, 'support': 's', 'evidence_ids': [report]}],
        affected_reporters=[{'author_id': 'U019', 'evidence_id': report}]), ledger, packet, RUBRIC)
    assert issues == [] and good.assessment_status == 'ASSESSED' and good.rubric_scope == 'SHARED_DEFAULT'
    reporters = good.occurrence.affected_reporters
    assert reporters.status == 'LOWER_BOUND' and reporters.ids == ['U019']
    assert good.occurrence.structural.distinct_participants > 1  # Participants are counted separately.
    for bad in (
            {'signals': [{'level': 'MEDIUM', 'signal_index': 2, 'signal_text': signal, 'support': 's', 'evidence_ids': ['k:guide']}]},
            {'signals': [{'level': 'MEDIUM', 'signal_index': 2, 'signal_text': 'paraphrased signal', 'support': 's', 'evidence_ids': [report]}]},
            {'level': 'HIGH'}):  # HIGH without a HIGH signal.
        severity, issues = build_severity(proposal(**bad), ledger, packet, RUBRIC)
        assert issues and severity.assessment_status == 'UNASSESSED' and severity.level == 'UNKNOWN', bad
    notes = []  # Someone else's message: that reporter is dropped and recorded; the assessment stands.
    kept, issues = build_severity(proposal(
        signals=[{'level': 'MEDIUM', 'signal_index': 2, 'signal_text': signal, 'support': 's', 'evidence_ids': [report]}],
        affected_reporters=[{'author_id': 'U006', 'evidence_id': report}, {'author_id': 'U019', 'evidence_id': report}]),
        ledger, packet, RUBRIC, notes=notes)
    assert issues == [] and kept.occurrence.affected_reporters.ids == ['U019']
    assert notes == ['Affected reporter U006 dropped: the cited message is by U019.']


def test_severity_confidence_resolution_and_grounding_stay_separate(retriever, view):
    """MOCKED SEMANTIC. Confident LOW-severity draft whose guidance claim fails grounding: each field keeps its own
    value; resolution is UNKNOWN because the draft gave no member-level evidence (Agent 1 labels are not used)."""
    client = Fake(draft=draft_for, grounding=lambda p: supported(p, **{'claim:c2': 'UNSUPPORTED'}))
    result = run('json_vs_prose', client, retriever, view)
    card = result['card']
    assert card['confidence'] == 0.9 and card['confidence_band'] == 'HIGH'
    assert card['severity']['level'] == 'LOW' and card['severity']['assessment_status'] == 'ASSESSED'
    assert card['checks']['grounding'] == 'FAILED' and card['resolution_status'] == 'UNKNOWN'
    assert {a['state'] for a in result['resolution']['agent1_attributed']} == {'UNRESOLVED'}
    assert 'LOW_CONFIDENCE' not in codes(result) and 'HIGH_SEVERITY' not in codes(result)


# ---- Bounded research and budgets (DETERMINISTIC enforcement) ----------------------------------------

def test_omitted_handling_announcement_is_recovered_by_targeted_follow_up(retriever, view):
    """MOCKED SEMANTIC gap detection; DETERMINISTIC retrieval. The first pass omits the 22:00 announcement;
    the draft names a CURRENT_HANDLING gap from what it was given, and one targeted retrieval recovers it."""
    def draft(payload):
        return draft_for(payload, evidence_sufficiency='INSUFFICIENT', claims=draft_for(payload)['claims'][:1],
                         proposed_action=None, gaps=[
            {'gap_id': 'g1', 'need': 'CURRENT_HANDLING', 'description': 'No current handling announcement in the evidence.',
             'follow_up': {'query': 'LT player never starts handling reminder tool incident', 'source_types': ['announcement']}}])

    def revision(payload):
        recovered = next(i['evidence_id'] for i in payload['retrieved_evidence'] if ANNOUNCEMENT in i['evidence_id'])
        claims = [{'claim_id': 'c1', 'kind': 'INCIDENT_FACT', 'text': 'A member reports the issue.',
                   'evidence_ids': [payload['member_evidence'][0]['evidence_id']]},
                  {'claim_id': 'c3', 'kind': 'GUIDANCE', 'text': 'Treat as a tool incident.',
                   'evidence_ids': [recovered], 'quote': 'Treat this as a tool incident.'}]
        return draft_for(payload, claims=claims, proposed_action={
            'action_type': 'POST_ALIGNMENT', 'draft_text': 'Remind tutors to report it as a tool incident.',
            'support_claim_ids': ['c3']}, announcement_assessments=[
            {'evidence_id': recovered, 'relevant': True, 'directive': True, 'directive_quote': 'Treat this as a tool incident.',
             'rationale': 'Batch 06 playback handling for the reported player failure.'}])
    client = Fake(draft=draft, revision=revision, grounding=supported)
    # A natural member-style question whose top five omit the announcement under this test encoder
    # (the real-embedding variant uses the question that omits it there).
    result = run('audio_playback', client, retriever, view, initial='Did the earlier reload trial restore playback?')
    initial, follow = result['retrieval_trace'][0], result['retrieval_trace'][1]
    assert not any(ANNOUNCEMENT in i for i in initial['result_ids']), 'precondition: the first pass omits it'
    assert client.calls and ANNOUNCEMENT not in client.calls[0][1]  # The draft never saw it.
    assert follow['purpose'] == 'gap:CURRENT_HANDLING' and any(ANNOUNCEMENT in i for i in follow['new_evidence_ids'])
    assert client.stages_called() == ['draft', 'revision', 'grounding'] and result['drafts']['revised']
    assert any(ANNOUNCEMENT in (s['note'] or '') and 'CURRENT_HANDLING' in s['note'] for s in result['card']['supporting_sources'])
    assert result['grounding']['status'] == 'PASSED'


def test_call_budgets_cap_follow_ups_revisions_and_runs(retriever, view):
    """DETERMINISTIC. Five requested follow-ups -> 3 run, 2 recorded as dropped; one revision even if it asks
    for more; per-topic and run-wide ceilings hold; a draft never starts without a grounding call reserved;
    exhausted topics still emit cards with members."""
    def greedy(payload):
        gaps = [{'gap_id': f'g{i}', 'need': 'OTHER', 'description': 'more', 'follow_up': {'query': f'query {i}', 'source_types': ['faq']}}
                for i in range(5)]
        return draft_for(payload, gaps=gaps)
    client = Fake(draft=greedy, revision=greedy, grounding=supported, tot=RuntimeError('unused'))
    budget = Budget({**BUDGET, 'model_calls_total': 4})
    result = run('audio_playback', client, retriever, view, budget=budget)
    assert [f['status'] for f in result['follow_ups']] == ['DONE'] * 3 + ['DROPPED_FOLLOW_UP_LIMIT'] * 2
    assert client.stages_called() == ['draft', 'revision', 'grounding']
    assert result['budget']['consumed'] == {'retrieval_calls': 4, 'model_calls': 3}
    second = run('korean_register', client, retriever, view, budget=budget)  # One run-wide call left: held for grounding.
    assert [(c['stage'], c['status']) for c in second['model_calls']] == [('draft', 'SKIPPED_RESERVED_FOR_GROUNDING')]
    assert second['card']['checks']['grounding'] == 'NOT_RUN' and second['drafts']['final'] is None
    budget.used['model_calls'] = 4  # Exhaust the run.
    third = run('fictional_pii', client, retriever, view, budget=budget)
    assert [c['status'] for c in third['model_calls']] == ['SKIPPED_BUDGET'] and third['drafts']['final'] is None
    card = third['card']
    assert card['card_line'] == 'NEEDS_REVIEW' and card['lineage']['member_ids'] == topic_packet(view, SCEN['fictional_pii'])['member_ids']
    assert {'LOW_CONFIDENCE', 'GROUNDING_NOT_RUN', 'INHERITED_FLAG', 'OTHER'} <= set(codes(third))
    # Retrieval: 1 + 3 follow-ups for the drafted topic; 1 each for the undrafted ones (+1 PII supersession check).
    assert budget.used == {'retrieval_calls': 4 + 1 + 2, 'model_calls': 4}
    tight = Budget({**BUDGET, 'retrieval_calls_per_topic': 2})
    capped = run('audio_playback', Fake(draft=greedy, revision=greedy, grounding=supported), retriever, view, budget=tight)
    assert [f['status'] for f in capped['follow_ups']] == ['DONE', 'SKIPPED_BUDGET', 'SKIPPED_BUDGET',
                                                           'DROPPED_FOLLOW_UP_LIMIT', 'DROPPED_FOLLOW_UP_LIMIT']


def test_invalid_model_output_is_recorded_not_retried(retriever, view):
    """DETERMINISTIC. Malformed JSON is one failed call; the card still carries every member and obligation."""
    client = Fake(draft='not json')
    result = run('submit_failure', client, retriever, view)
    assert client.stages_called() == ['draft'] and result['model_calls'][0]['status'] == 'FAILED'
    assert result['coverage']['uncarried_obligations'] == [] and result['card']['card_line'] == 'NEEDS_REVIEW'


# ---- Conditional ToT (MOCKED SEMANTIC candidates, DETERMINISTIC checks) ------------------------------

def tot_response(payload, preferred='C'):
    known = first({'retrieved_evidence': payload['evidence']}, 'CURRENT_GUIDANCE')
    return {'candidates': [
        {'candidate_id': 'A', 'action_type': 'NO_ACTION', 'draft_text': 'Wait for TL.', 'evidence_ids': [known],
         'evidence_support': 'STRONG', 'applicability': 'CURRENT', 'severity_fit': 'FITS', 'rationale': 'r'},
        {'candidate_id': 'C', 'action_type': 'ESCALATE_ENGINEERING', 'draft_text': 'Escalate.', 'evidence_ids': ['k:invented@9:00000000'],
         'evidence_support': 'STRONG', 'applicability': 'CURRENT', 'severity_fit': 'FITS', 'rationale': 'r'}],
        'preferred_candidate_id': preferred, 'close_call': False, 'rationale': 'C looks decisive.'}


def test_tot_runs_only_on_flagged_paths_and_never_clears_review(retriever, view):
    """MOCKED SEMANTIC. Ordinary confident path: no comparison. Open confirmation: one comparison whose invented
    evidence invalidates the model's preferred candidate; review reasons equal those without any comparison."""
    ordinary = Fake(draft=draft_for, grounding=supported, tot=RuntimeError('must not be called'))
    plain = run('korean_register', ordinary, retriever, view)
    assert plain['tot']['status'] == 'NOT_TRIGGERED' and 'tot' not in ordinary.stages_called()

    def open_draft(payload):
        return draft_for(payload, **open_q(payload))
    flagged = Fake(draft=open_draft, grounding=supported, tot=tot_response)
    result = run('json_vs_prose', flagged, retriever, view)
    assert flagged.stages_called().count('tot') == 1 and result['tot']['triggers'] == ['OPEN_CONFIRMATION']
    invented = next(c for c in result['tot']['candidates'] if c['candidate_id'] == 'C')
    assert not invented['valid'] and 'CITES_UNKNOWN_EVIDENCE' in invented['issues']
    assert result['tot']['model_preferred_candidate_id'] == 'C' and result['tot']['preferred_candidate_id'] is None
    assert invented['grounding'] == 'NOT_PRESENTED_INVALID' and result['tot']['grounded_candidate_ids'] == ['A']
    assert result['tot']['presentation'] == 'SURFACE_GROUNDED_ALTERNATIVES'
    assert flagged.stages_called() == ['draft', 'tot', 'grounding']  # The final grounding call comes last.
    unavailable = run('json_vs_prose', Fake(draft=open_draft, grounding=supported, tot=RuntimeError('down')), retriever, view)
    assert unavailable['tot']['status'] == 'UNAVAILABLE'
    strip = lambda r: [x for x in r['card']['needs_review_reasons'] if not x['detail'].startswith('tot:')]
    assert strip(result) == strip(unavailable) and 'OPEN_CONFIRMATION' in codes(result)
    assert result['card']['recommended_action'] == unavailable['card']['recommended_action']


def test_low_confidence_and_unexplained_conflict_trigger_tot(retriever, view):
    """MOCKED SEMANTIC conflict report; DETERMINISTIC temporal verdict. Two current sources in conflict are
    DETECTED (TEMPORAL_CONFLICT); a superseded section against its replacement is explained by the record."""
    def conflict(payload):
        current = [i['evidence_id'] for i in payload['retrieved_evidence'] if i['use'] in ('CURRENT_GUIDANCE', 'CURRENT_HANDLING')]
        return draft_for(payload, confidence=0.5, source_conflicts=[{'evidence_ids': current[:2], 'description': 'They disagree.'}])
    client = Fake(draft=conflict, grounding=supported, tot=tot_response)
    result = run('audio_playback', client, retriever, view)
    assert result['temporal']['status'] == 'DETECTED' and 'TEMPORAL_CONFLICT' in codes(result)
    assert result['tot']['triggers'] == ['TEMPORAL_CONFLICT', 'LOW_CONFIDENCE']
    tools = safety_tools(retriever)
    old = next(k for k, i in tools.ledger.items() if i['citation']['authoring'] == 'safety-qn-help-page@1.0'
               and i['citation']['sections'] == ['Contact details'])
    new = next(k for k, i in tools.ledger.items() if i['citation']['authoring'] == 'safety-fictional-pii-clarification@1.0')
    conflict = [{'evidence_ids': [old, new], 'description': 'Old vs new rule.'}]
    # The replacement is an announcement: recorded supersession explains the conflict only once it is established.
    assert temporal_check(make_draft(source_conflicts=conflict), tools.ledger)['status'] == 'DETECTED'
    quote = 'Clearly fictional placeholder phone numbers or email addresses alone do not require QN'
    explained = temporal_check(make_draft(source_conflicts=conflict, announcement_assessments=[
        {'evidence_id': new, 'relevant': True, 'directive': True, 'directive_quote': quote, 'rationale': 'Project-wide rule.'}]),
        tools.ledger)
    assert explained['status'] == 'NONE_FOUND' and explained['findings'][0]['status'] == 'RESOLVED_BY_RECORDED_SUPERSESSION'


# ---- Unsupported cases, obligations, scenario selection ----------------------------------------------

def test_unsupported_stays_visibly_unsupported(retriever, view):
    """MOCKED SEMANTIC. The payroll control gets results (nearest neighbours) but stays UNSUPPORTED with no card;
    a topic draft marked UNSUPPORTED cannot carry an operational action."""
    unsupported = {'summary': 'No source addresses this.', 'reasoning': 'Nothing relevant.', 'claims': [],
                   'evidence_sufficiency': 'UNSUPPORTED', 'severity': {'level': 'UNKNOWN', 'rationale': 'No evidence.'},
                   'confidence': 0.9, 'open_confirmation': 'NONE'}
    result = control(SCEN['control_unsupported_payroll'], retriever=retriever, client=Fake(draft=unsupported),
                     budget=Budget(BUDGET), rubric=RUBRIC, as_of=retriever.manifest['cutoff'])
    assert result['retrieved_results'] > 0 and result['control_outcome'] == 'UNSUPPORTED' and result['card'] is None
    topic = run('repeated_ending', Fake(draft=lambda p: draft_for(p, evidence_sufficiency='UNSUPPORTED'), grounding=supported),
                retriever, view)
    assert topic['card']['recommended_action'] is None and topic['card']['card_line'] == 'NEEDS_REVIEW'
    assert any(r['detail'].startswith('Evidence unsupported') for r in topic['card']['needs_review_reasons'])
    assert 'UNSUPPORTED_ACTION_NOT_CARRIED' in [d['code'] for d in topic['diagnostics']]


def test_projection_gap_and_inherited_obligations_survive(retriever, view):
    """DETERMINISTIC. The Submit group has no Agent 2 topic: the card covers its unassigned members, names the gap
    and keeps every Agent 1 obligation; review items link back to the card."""
    result = run('submit_failure', Fake(draft=draft_for, grounding=supported), retriever, view)
    card, record = result['card'], next(r for r in view['records'] if r['candidate_group_id'] == 'routed_440e64c7fbdcc49f')
    assert card['lineage']['topic_id'] is None and 'projection gap' in card['topic_name']
    assert sorted(card['lineage']['member_ids']) == sorted(record['unassigned_member_ids'])
    kinds = [f['kind'] for f in card['inherited_flags']]
    assert 'projection_gap' in kinds and kinds.count('inherited_agent1_review') == len(record['inherited_review_obligations'])
    assert result['coverage'] == {'group_members_outside_this_card': [], 'uncarried_obligations': []}
    assert all(card['card_id'] in i['related_card_ids'] for i in result['review_items'])
    assert card['card_line'] == 'NEEDS_REVIEW' and 'INHERITED_FLAG' in codes(result)


def test_unflagged_grounded_paths_reach_recommended_action_or_observation(retriever, view):
    """MOCKED SEMANTIC. Every real pilot topic carries upstream obligations, so this removes them from a copy of
    one record to exercise the other card lines: grounded operational action -> RECOMMENDED_ACTION; NO_ACTION ->
    OBSERVATION; the same draft with grounding NOT_RUN -> NEEDS_REVIEW."""
    record = next(r for r in view['records'] if r['candidate_group_id'] == SCEN['korean_register']['candidate_group_id'])
    unflagged = {**view, 'records': [{**record, 'inherited_review_obligations': [], 'agent2_review_obligations': [],
                                      'content_review_obligations': []}]}
    recommended = run('korean_register', Fake(draft=draft_for, grounding=supported), retriever, unflagged)
    assert recommended['card']['card_line'] == 'RECOMMENDED_ACTION' and recommended['card']['needs_review_reasons'] == []
    assert recommended['card']['supporting_sources'] and recommended['card']['checks']['grounding'] == 'PASSED'
    observe = run('korean_register', Fake(draft=lambda p: draft_for(p, proposed_action={'action_type': 'NO_ACTION',
                                                                                          'support_claim_ids': []}),
                                          grounding=supported), retriever, unflagged)
    assert observe['card']['card_line'] == 'OBSERVATION'
    unchecked = run('korean_register', Fake(draft=draft_for, grounding=RuntimeError('down')), retriever, unflagged)
    card = unchecked['card']
    assert card['card_line'] == 'NEEDS_REVIEW' and codes(unchecked) == ['GROUNDING_NOT_RUN', 'OTHER', 'OTHER']
    # Nothing ungrounded is shown as established: no action, withheld summary, provisional severity.
    assert card['recommended_action'] is None and card['summary'].startswith("The advisor's summary is not shown")
    assert card['severity']['assessment_status'] == 'UNASSESSED' and card['supporting_sources'] == []


def test_unavailable_topics_are_reported_not_repaired(retriever, view):
    """DETERMINISTIC. A topic name absent from the handoff is a visible diagnostic, not an invented topic."""
    spec = {'scenarios': [{**SCEN['audio_playback'], 'id': 'missing', 'topic_name': 'No such topic'}]}
    run_ = run_pilot(client=Fake(), retriever=retriever, view=view, scenarios=spec)
    assert run_['results'][0]['status'] == 'SCENARIO_UNAVAILABLE' and run_['results'][0]['card'] is None
    assert run_['manifest']['budget_consumed'] == {}


def test_plan_makes_no_model_calls_and_outputs_need_a_new_directory(retriever, view, tmp_path):
    """DETERMINISTIC. The default script path is zero-call; outputs never overwrite."""
    planned = plan(retriever=retriever, view=view)
    assert planned['model_calls'] == 0 and len(planned['scenarios']) == 7
    assert next(s for s in planned['scenarios'] if s['id'] == 'fictional_pii')['supersession_check_planned']
    spec = {'scenarios': [SCEN['korean_register']]}
    done = run_pilot(client=Fake(draft=draft_for, grounding=supported), retriever=retriever, view=view, scenarios=spec)
    out = write_outputs(tmp_path/'pilot', done)
    assert (out/'report.md').is_file() and json.loads((out/'cards.json').read_text(encoding='utf-8'))[0]['card_line']
    with pytest.raises(FileExistsError):
        write_outputs(tmp_path/'pilot', done)


# ---- Final grounding covers what the card says (MOCKED SEMANTIC verdicts, DETERMINISTIC authorization) ----

def by_member(payload):
    out = {}
    for item in payload['member_evidence']:
        out.setdefault(item['member_id'], []).append(item['evidence_id'])
    return out


def full_draft(payload, *, states=None, **overrides):
    """Every statement kind: claims, action, summary, a severity signal, two reporters and member resolution
    (default: the first member resolved in its thread, the rest unresolved)."""
    members, messages = payload['topic']['member_ids'], by_member(payload)
    states = states if states is not None else {m: 'RESOLVED_IN_THREAD' if k == 0 else 'UNRESOLVED' for k, m in enumerate(members)}
    report, second = 'm:C_AUDIO_GENERAL:1790882197.000111', 'm:C_AUDIO_GENERAL:1790896012.001900'
    signal = RUBRIC['levels']['MEDIUM']['required_signals'][2]
    return draft_for(payload, severity={
        'level': 'MEDIUM', 'rationale': 'Two tutors report the player failing.',
        'signals': [{'level': 'MEDIUM', 'signal_index': 2, 'signal_text': signal, 'support': 'Player fails.', 'evidence_ids': [report]}],
        'affected_reporters': [{'author_id': 'U019', 'evidence_id': report}, {'author_id': 'U018', 'evidence_id': second}]},
        resolution=[{'member_id': m, 'state': s, 'evidence_ids': messages[m], 'basis': 'From the thread.'} for m, s in states.items()],
        **overrides)


def test_final_grounding_covers_every_card_statement_and_is_the_last_call(retriever, view):
    """MOCKED SEMANTIC verdicts; DETERMINISTIC coverage and authorization. The one grounding call is the last model
    call and judges summary, claims, action, severity rationale/signal, each affected reporter and each member's
    resolution; the card shows only what it supported, so a withheld summary, reporter or resolution never appears
    as established. One resolved member never resolves the topic."""
    sent = []
    client = Fake(draft=full_draft, grounding=lambda p: sent.append(p) or supported(p))
    result = run('audio_playback', client, retriever, view)
    assert client.stages_called()[-1] == 'grounding'
    assert {'SUMMARY', 'ACTION', 'CLAIM_INCIDENT_FACT', 'CLAIM_GUIDANCE', 'SEVERITY_RATIONALE', 'SEVERITY_SIGNAL',
            'AFFECTED_REPORTER', 'RESOLUTION'} <= {s['kind'] for s in sent[0]['statements']}
    # The judge sees every member message and every retrieved source, not only what the draft cited.
    context = {e['evidence_id'] for e in sent[0]['member_threads'] + sent[0]['retrieved_sources']}
    assert context == set(result['evidence_ledger']) and context > {i for s in sent[0]['statements'] for i in s['evidence_ids']}
    card = result['card']
    assert result['grounding']['status'] == 'PASSED' and card['summary'] == 'A member reports the problem.'
    assert card['severity']['occurrence']['affected_reporters']['ids'] == ['U019', 'U018']
    assert card['resolution_status'] == 'MIXED' and '(an input, not evidence)' in card['reasoning']

    first_member = topic_packet(view, SCEN['audio_playback'])['member_ids'][0]
    partial = run('audio_playback', Fake(draft=full_draft, grounding=lambda p: supported(p, **{
        'summary': 'UNSUPPORTED', 'reporter:U018': 'UNSUPPORTED', f'resolution:{first_member}': 'PARTIALLY_SUPPORTED'})),
        retriever, view)
    card = partial['card']
    assert card['summary'].startswith("The advisor's summary is not shown") and 'A member reports the problem.' not in json.dumps(card)
    assert card['severity']['occurrence']['affected_reporters']['ids'] == ['U019']
    assert partial['resolution']['members'][first_member] == 'UNKNOWN' and card['resolution_status'] == 'UNKNOWN'
    withheld = {d['statement_id']: d for d in partial['diagnostics'] if d['code'] == 'WITHHELD_STATEMENT'}
    assert set(withheld) == {'summary', 'reporter:U018', f'resolution:{first_member}'}
    assert withheld['summary']['text'] == 'A member reports the problem.' and 'GROUNDING_FAILURE' in codes(partial)

    rationale = run('audio_playback', Fake(draft=full_draft, grounding=lambda p: supported(p, **{'severity:rationale': 'UNSUPPORTED'})),
                    retriever, view)
    # An unsupported rationale is replaced by the supported signal's own wording; the level stands on that signal.
    assert rationale['card']['severity']['assessment_status'] == 'ASSESSED'
    assert rationale['card']['severity']['rationale'].startswith('Supported rubric signals: signal:MEDIUM[2]')
    unsupported_signal = run('audio_playback', Fake(draft=full_draft, grounding=lambda p: supported(
        p, **{'severity:rationale': 'UNSUPPORTED', 'severity:signal:MEDIUM[2]': 'UNSUPPORTED'})), retriever, view)
    assert unsupported_signal['card']['severity']['assessment_status'] == 'UNASSESSED'
    only_one = run('audio_playback', Fake(draft=lambda p: full_draft(p, states={p['topic']['member_ids'][0]: 'RESOLVED_IN_THREAD'}),
                                          grounding=supported), retriever, view)
    assert only_one['card']['resolution_status'] == 'UNKNOWN'  # The other members have no supported state.


def test_tot_alternatives_need_their_own_grounding_verdict(retriever, view):
    """MOCKED SEMANTIC. Regression: a ToT candidate introduces an unsupported claim (a "confirmed generation loop")
    citing a real member message, so it passes the deterministic candidate checks. A judgment covering only the
    draft's statements cannot authorize it: unjudged or UNSUPPORTED, it is never preferred, never reaches the card,
    and is kept in diagnostics."""
    def open_draft(payload):
        return draft_for(payload, **open_q(payload))

    def tot(payload):
        member, known = payload['draft']['claims'][0]['evidence_ids'][0], payload['draft']['claims'][-1]['evidence_ids'][0]
        return {'candidates': [
            {'candidate_id': 'A', 'action_type': 'NO_ACTION', 'draft_text': 'Wait for TL confirmation.', 'evidence_ids': [known],
             'evidence_support': 'STRONG', 'applicability': 'UNCLEAR', 'severity_fit': 'FITS', 'rationale': 'Follows the draft.'},
            {'candidate_id': 'B', 'action_type': 'ESCALATE_ENGINEERING', 'evidence_ids': [member],
             'draft_text': 'Escalate the confirmed TTS generation loop to engineering.', 'evidence_support': 'STRONG',
             'applicability': 'UNCLEAR', 'severity_fit': 'FITS', 'rationale': 'The member message confirms a generation loop.'}],
            'preferred_candidate_id': 'B', 'close_call': False, 'rationale': 'B is decisive.'}
    sent = []

    def draft_only(payload):  # Verdicts for the draft's statements only, as if an earlier check were reused.
        sent.append(payload)
        return {**supported(payload), 'verdicts': [v for v in supported(payload)['verdicts']
                                                   if not v['statement_id'].startswith('alternative:')]}
    client = Fake(draft=open_draft, tot=tot, grounding=draft_only)
    result = run('repeated_ending', client, retriever, view)
    assert client.stages_called() == ['draft', 'tot', 'grounding']
    assert [s['statement_id'] for s in sent[0]['statements'] if s['kind'] == 'ALTERNATIVE'] == ['alternative:A', 'alternative:B']
    b = next(c for c in result['tot']['candidates'] if c['candidate_id'] == 'B')
    assert b['valid'] and b['issues'] == [] and b['grounding'] == 'NOT_JUDGED'
    assert result['tot']['preferred_candidate_id'] is None and result['tot']['presentation'] == 'NO_GROUNDED_ALTERNATIVES'
    assert result['grounding']['status'] == 'PASSED'  # Alternatives are not card content; the draft's own statements passed.
    assert 'generation loop' not in json.dumps(result['card'])

    judged = run('repeated_ending', Fake(draft=open_draft, tot=tot, grounding=lambda p: supported(p, **{'alternative:B': 'UNSUPPORTED'})),
                 retriever, view)
    assert judged['tot']['grounded_candidate_ids'] == ['A'] and judged['tot']['preferred_candidate_id'] is None
    [diag] = [d for d in judged['diagnostics'] if d['code'] == 'ALTERNATIVE_NOT_GROUNDED']
    assert diag['statement_id'] == 'alternative:B' and 'confirmed TTS generation loop' in diag['text']
    assert judged['card']['recommended_action'] == result['card']['recommended_action']
    assert 'generation loop' not in json.dumps(judged['card'])


# ---- Announcement applicability, documentation targets, resolution ------------------------------------

def test_routine_reminder_announcement_is_not_current_handling(retriever, view):
    """DETERMINISTIC applicability and structure; MOCKED SEMANTIC verification. A routine reminder keeps its
    identity, dates, authority and scope but stays an unestablished ANNOUNCEMENT: guidance resting on it fails
    structurally unless assessed as a relevant directive (verbatim quote), and even then only the final grounding's
    own verdict on the announcement can make it current handling."""
    tools = ResearchTools(retriever, project='audio_multimodal', batch='audio_batch_06', as_of=retriever.manifest['cutoff'],
                          budget=Budget({}), top_k=40)
    tools.search('Reminder to use headphones for the audio calibration exercise', purpose='test', source_types=['announcement'])
    eid, item = next((k, i) for k, i in tools.ledger.items() if REMINDER in k)
    assert item['use'] == 'ANNOUNCEMENT' and item['excerpt'].startswith('[ANNOUNCEMENT posted')
    assert item['citation']['source']['thread_id'] == REMINDER and item['dates']['source_date']
    assert item['authority']['role'] == 'TEAM_LEAD' and item['scope']['batch_id'] == 'audio_batch_06'
    assert all(i['use'] != 'CURRENT_HANDLING' for i in tools.ledger.values())  # Never assigned by source type.
    claim = {'claim_id': 'c1', 'kind': 'GUIDANCE', 'text': 'Use headphones.', 'evidence_ids': [eid]}
    assert [i['code'] for i in claim_issues(make_draft(claims=[claim]), tools.ledger)] == ['ANNOUNCEMENT_NOT_ESTABLISHED_AS_HANDLING']
    misquoted = make_draft(claims=[claim], announcement_assessments=[{
        'evidence_id': eid, 'relevant': True, 'directive': True, 'directive_quote': 'Always use headphones for playback tasks.',
        'rationale': 'Audio announcement.'}])
    assert [i['code'] for i in announcement_issues(misquoted, tools.ledger)] == ['QUOTE_NOT_VERBATIM']
    assert [i['code'] for i in claim_issues(misquoted, tools.ledger)] == ['ANNOUNCEMENT_NOT_ESTABLISHED_AS_HANDLING']

    def reminder_draft(payload):  # Wrongly treats the reminder as playback handling.
        rid = next(i['evidence_id'] for i in payload['retrieved_evidence'] if REMINDER in i['evidence_id'])
        return draft_for(payload, claims=[draft_for(payload)['claims'][0], {
            'claim_id': 'c2', 'kind': 'GUIDANCE', 'text': 'Use headphones for the audio calibration exercise.', 'evidence_ids': [rid]}],
            proposed_action={'action_type': 'POST_ALIGNMENT', 'draft_text': 'Tell tutors to use headphones when the player fails.',
                             'support_claim_ids': ['c2']},
            announcement_assessments=[{'evidence_id': rid, 'relevant': True, 'directive': True, 'rationale': 'Audio batch 06.',
                                       'directive_quote': 'Reminder to use headphones for the audio calibration exercise.'}])

    def reject(payload):
        return supported(payload, **{s['statement_id']: 'UNSUPPORTED' for s in payload['statements']
                                     if s['kind'] == 'ANNOUNCEMENT_HANDLING'})
    result = run('audio_playback', Fake(draft=reminder_draft, grounding=reject), retriever, view,
                 initial='Reminder to use headphones for the audio calibration exercise')
    assert any(REMINDER in i for i in result['retrieval_trace'][0]['result_ids']), 'precondition: the reminder was retrieved'
    verdicts = {s['statement_id']: s for s in result['grounding']['statements']}
    assert verdicts['claim:c2']['model_verdict'] == 'SUPPORTED' and verdicts['claim:c2']['verdict'] == 'ANNOUNCEMENT_NOT_VERIFIED'
    # The judge supported c2 itself; its announcement dependency voided it before sufficiency was applied.
    assert verdicts['action']['verdict'] == 'ESSENTIAL_PREMISE_VOIDED_BY_DEPENDENCY'
    assert result['grounding']['status'] == 'FAILED' and result['established_handling'] == []
    card = result['card']
    assert card['recommended_action'] is None and not any(REMINDER in (s['note'] or '') for s in card['supporting_sources'])


def test_documentation_actions_target_only_stale_or_missing_sections(retriever):
    """DETERMINISTIC. A documentation action names what it changes. Correcting the superseded help-page section is
    allowed; correcting already-updated current instructions or FAQ entries (no reported conflict) is flagged, as is
    a section the cited chunk does not contain or an action with no target."""
    tools = safety_tools(retriever)
    ledger = tools.ledger
    stale = next(k for k, i in ledger.items() if i['citation']['authoring'] == 'safety-qn-help-page@1.0'
                 and i['citation']['sections'] == ['Contact details'])
    current = [k for k, i in ledger.items() if i['use'] == 'CURRENT_GUIDANCE' and i['citation']['authoring'].startswith(
        ('safety-classification-instructions', 'safety-classification-faq'))]
    assert current

    def doc_draft(targets, conflicts=()):
        return make_draft(claims=[{'claim_id': 'c1', 'kind': 'GUIDANCE', 'text': 'Current rule.', 'evidence_ids': [current[0]]}],
                          proposed_action={'action_type': 'UPDATE_DOCUMENTATION', 'draft_text': 'Fix the copy.',
                                           'support_claim_ids': ['c1'], 'targets': targets}, source_conflicts=list(conflicts))
    assert action_issues(doc_draft([{'evidence_id': stale, 'section': 'Contact details', 'change': 'CORRECT'}]), ledger) == []
    flagged = action_issues(doc_draft([{'evidence_id': c, 'change': 'CORRECT'} for c in current]), ledger)
    assert len(flagged) == len(current) and all(i.startswith('ACTION_TARGET_ALREADY_CURRENT') for i in flagged)
    assert action_issues(doc_draft([{'evidence_id': current[0], 'change': 'CORRECT'}],
                                   conflicts=[{'evidence_ids': [current[0], stale], 'description': 'They disagree.'}]), ledger) == []
    wrong_section = action_issues(doc_draft([{'evidence_id': stale, 'section': 'Other safety concerns', 'change': 'CORRECT'}]), ledger)
    assert [i.split(':')[0] for i in wrong_section] == ['ACTION_TARGET_SECTION_NOT_CITED']
    with pytest.raises(ValidationError, match='names the source and section'):
        make_draft(proposed_action={'action_type': 'UPDATE_DOCUMENTATION', 'draft_text': 'Fix it.', 'support_claim_ids': []})


def test_resolution_is_per_member_from_thread_evidence_not_agent1_labels(retriever, view):
    """DETERMINISTIC. Agent 1 resolution labels are attributed inputs: a member state must cite that member's own
    thread; the topic state never follows one member; with no member-level evidence the card says UNKNOWN even where
    Agent 1 recorded PARTIALLY_RESOLVED (partly unverified)."""
    assert topic_resolution(['a', 'b'], {'a': 'RESOLVED_IN_THREAD', 'b': 'UNRESOLVED'}) == 'MIXED'
    assert topic_resolution(['a', 'b'], {'a': 'RESOLVED_IN_THREAD'}) == 'UNKNOWN'
    assert topic_resolution(['a', 'b'], {'a': 'RESOLVED_IN_THREAD', 'b': 'RESOLVED_IN_THREAD'}) == 'RESOLVED_IN_THREAD'
    packet = topic_packet(view, SCEN['fictional_pii'])
    ledger = {i['evidence_id']: i for i in member_messages(packet['members'])}
    a, b = packet['member_ids'][:2]
    other = next(k for k, i in ledger.items() if i['member_id'] == b)
    draft = make_draft(resolution=[{'member_id': a, 'state': 'PARTIALLY_RESOLVED', 'evidence_ids': [other], 'basis': 'Borrowed.'},
                                   {'member_id': 'member_outside', 'state': 'UNRESOLVED', 'evidence_ids': [], 'basis': 'x'}])
    assert [i['code'] for i in resolution_issues(draft, ledger, set(packet['member_ids']))] == [
        'RESOLUTION_NEEDS_THREAD_EVIDENCE', 'UNKNOWN_MEMBER']
    attributed = packet['agent1_resolution']
    assert 'PARTIALLY_RESOLVED' in {x['state'] for x in attributed}
    assert any(x['agent1_verification_status'] == 'NEEDS_REVIEW' for x in attributed)
    result = run('fictional_pii', Fake(draft=draft_for, grounding=supported), retriever, view)
    assert result['card']['resolution_status'] == 'UNKNOWN' and result['resolution']['agent1_attributed'] == attributed
    assert '1 of 3 were not verified by Agent 1.' in result['card']['reasoning']
    assert result['coverage']['uncarried_obligations'] == []
