"""Milestone 4: bounded Agent 3 Advisor pilot over selected handoff topics.

Per topic: freshness-checked retrieval (current guidance first) -> Advisor draft ->
targeted follow-up retrieval for the gaps the draft names -> at most one revision ->
deterministic checks (structure, severity binding to the unchanged rubric, temporal
priority) -> conditional shallow ToT -> ONE final semantic grounding call over every
statement that can reach the card (claims, summary, action, severity rationale/signals,
affected reporters, member resolution, announcement handling) and over the ToT
alternatives -> authorization (only SUPPORTED statements reach the card) -> deterministic
card routing. Nothing after the final grounding call can add or change a statement.

Every model and retrieval call is charged to a finite budget, and draft, revision and ToT
each run only if a call stays reserved for the final grounding. Nothing is retried: the
live client sends at most one HTTP request per stage (enforced at the transport) and a
failed stage is recorded while the topic's members and obligations still reach a card.
The model never calls tools itself: it names gaps and follow-up queries, and
ResearchTools executes them within the budget.
"""
from hashlib import sha256
import json
import os
from pathlib import Path
from urllib.parse import urlparse

from pydantic import ValidationError

from threadsense.agents import advisor_tot
from threadsense.agents.advice_contracts import ModelReviewItem, stable_id
from threadsense.agents.advice_inputs import coverage, load_effective_view, review_items_from_view
from threadsense.agents.advisor_checks import (
    action_issues, agent1_resolution, announcement_issues, assemble_card, authorize, build_severity, claim_issues,
    established, grounding_result, inherited_flags, statements, structural_issues, temporal_check, unauthorized,
)
from threadsense.agents.advisor_contracts import AdvisorDraft, GroundingJudgment
from threadsense.agents.advisor_evidence import Budget, BudgetExhausted, ResearchTools, member_messages, open_retriever
from threadsense.handoff_inputs import ROOT, file_hash, read_json
from threadsense.retrieval.config import DEFAULTS
from threadsense.severity_rubric import load_rubric

PILOT_VERSION = 'agent3-advisor-pilot-v2'
SCENARIOS = ROOT/'data/evaluation/agent3_pilot_scenarios.json'
HANDOFF = ROOT/'data/processed/agent2_handoff_v2_projection'
# Per topic: draft + one revision + one ToT + final grounding = 4 model calls at most, the last always
# reserved for grounding; retrieval: initial + supersession check + 3 follow-ups = 5 (one spare).
# Run totals cap 7 scenarios.
BUDGET = {'model_calls_per_topic': 4, 'model_calls_total': 28, 'retrieval_calls_per_topic': 6, 'retrieval_calls_total': 42}
MAX_FOLLOW_UPS = 3
TOP_K = 5
# Live request limits (CrewAIClient): one HTTP request per stage, no SDK retries, bounded output.
MAX_COMPLETION_TOKENS = 4096
REQUEST_TIMEOUT_SECONDS = 120
HTTP_REQUESTS_PER_STAGE = 1
# Set before CrewAI/LiteLLM import: no telemetry export, no remote model-price download.
QUIET_ENV = {'CREWAI_DISABLE_TELEMETRY': 'true', 'OTEL_SDK_DISABLED': 'true', 'LITELLM_LOCAL_MODEL_COST_MAP': 'True'}

DRAFT_RULES = (
    'You are the ThreadSense Advisor preparing one topic for a team lead\'s morning brief. Use only the evidence '
    'provided and cite it by evidence_id. Member messages (origin member_message) are the only evidence for incident '
    'facts: what happened and who reported being affected. Retrieved sources support guidance and history according to '
    'their "use": CURRENT_GUIDANCE may support what applies now; PRIOR_DECISION and HISTORY_ONLY explain earlier '
    'decisions or old rules and must not be presented as current guidance; UNRESOLVED_VERSION must not be resolved by '
    'you. ANNOUNCEMENT items include routine reminders, schedules and example-collection notes: before a GUIDANCE claim '
    'relies on one, list it in announcement_assessments as relevant (same project, batch and problem) and directive (it '
    'tells people what to do), quoting the directing sentence verbatim; otherwise mark it not relevant or not directive. '
    'Read each excerpt with its status line, dates, scope, authority and recorded states. A nonempty result list is not '
    'sufficient evidence: in gaps, name any support your proposed action still lacks (an applicable instruction, current '
    'handling, the outcome of a relevant prior decision, recurrence, supersession or conflict, expert routing). Give a '
    'follow_up query (source_types; version_mode history for past decisions, recurrence or supersession) only when '
    'retrieval could fill the gap. Do not invent causes, outcomes, approvals, counts or fixes. Severity: apply the rubric '
    'unchanged; MEDIUM or HIGH must cite a rubric signal by level, index and exact text, supported by member messages; '
    'affected_reporters lists only people whose own message reports being affected, not everyone who replied. '
    'Resolution: give each member a state (UNRESOLVED, PARTIALLY_RESOLVED, RESOLVED_IN_THREAD or UNKNOWN) from that '
    'member\'s own thread messages, citing them; Agent 1\'s resolution label is an attributed input, often unverified, '
    'and is not evidence; one member\'s resolution says nothing about another member. UPDATE_DOCUMENTATION and '
    'UPDATE_FAQ name targets (evidence_id, section, ADD for a missing entry, CORRECT or REMOVE for stale wording); target '
    'only what the evidence shows is missing or stale, never a source the evidence shows is already updated. Severity, '
    'confidence, resolution and evidence sufficiency are separate judgments. Set open_confirmation OPEN when the recorded '
    'guidance or decisions leave the question for a team lead to confirm. List source_conflicts between evidence items '
    'that disagree. If no evidence addresses the topic, set evidence_sufficiency UNSUPPORTED and propose no operational '
    'action. Upstream review flags stay open; you cannot clear them. Everything that reaches the card is checked '
    'statement by statement against the evidence it cites: the summary, each claim, the action, the severity rationale '
    'and signals, each affected reporter, each member resolution and each announcement you establish.')
REVISION_RULES = (
    'Revise your previous draft once, using the follow-up retrieval results now included in the evidence. Keep every '
    'claim cited; weaken or remove claims the evidence does not support. No further retrieval will run: leave remaining '
    'gaps with follow_up null. ' + DRAFT_RULES)
GROUNDING_RULES = (
    'Judge each statement only against the excerpts of the evidence it cites (evidence_ids); that a citation exists is '
    'not support. SUPPORTED only if the cited excerpts state or directly entail the whole statement; PARTIALLY_SUPPORTED '
    'if any material part is missing; UNSUPPORTED otherwise. A status line marking an excerpt historical, unresolved or a '
    'prior record means it cannot support a statement about what applies now. By kind: SUMMARY and SEVERITY_RATIONALE '
    'must follow from the cited excerpts with no added cause, count or outcome; ACTION must follow from its cited support, '
    'and its targets must be what the evidence shows is stale or missing; AFFECTED_REPORTER needs that person\'s own '
    'message reporting that they are affected; RESOLUTION needs the thread messages to show that state; '
    'ANNOUNCEMENT_HANDLING needs the announcement to give that directive and to apply to this topic\'s project, batch and '
    'problem (a routine reminder, schedule or example-collection note does not); ALTERNATIVE is a candidate action: judge '
    'whether its cited excerpts support it. Return exactly one verdict for every statement_id.')


class ScenarioError(ValueError):
    """A selected topic is not available in the handoff as specified (recorded, never repaired)."""


class RequestCeilingExceeded(RuntimeError):
    """A stage tried to send more HTTP requests than its ceiling; the extra request was not sent."""


class BoundaryNotObserved(RuntimeError):
    """A model call returned without any request passing the guarded transport; call accounting is unverified."""


class RequestGuard:
    """Count HTTP requests at the httpx transport for one stage and refuse any beyond `limit` before it is
    sent, whichever layer (CrewAI rate-limit retry, LiteLLM, provider SDK) attempts it. Single-threaded use."""

    def __init__(self, limit=HTTP_REQUESTS_PER_STAGE):
        self.limit, self.sent, self.blocked = limit, [], []

    def __enter__(self):
        import httpx
        self._original, guard = httpx.HTTPTransport.handle_request, self

        def handle(transport, request):
            if len(guard.sent) >= guard.limit:
                guard.blocked.append(str(request.url))
                raise RequestCeilingExceeded(f'{guard.limit} HTTP request(s) per stage; {request.url} was not sent')
            guard.sent.append(str(request.url))
            return guard._original(transport, request)
        httpx.HTTPTransport.handle_request = handle
        return self

    def __exit__(self, *exc):
        import httpx
        httpx.HTTPTransport.handle_request = self._original
        return False

    def stats(self):
        return {'sent': len(self.sent), 'blocked': len(self.blocked), 'hosts': sorted({urlparse(u).netloc for u in self.sent})}


class ScriptedClient:
    """Offline semantic stand-in: returns prepared responses. Never a claim about model quality."""
    label = 'SCRIPTED_MOCK'

    def __init__(self, path):
        self.path, self.responses = Path(path), read_json(path)['responses']
        self.fingerprint = file_hash(self.path)

    def complete(self, stage, payload, schema):
        return json.dumps(self.responses[payload['scenario_id']][stage], ensure_ascii=False)


def live_settings():
    """The configured live model and request limits (reads .env for the model name; never returns a key)."""
    from threadsense.config import get_model_settings
    model, key_name = get_model_settings()
    return {'model': model, 'api_key_variable': key_name, 'interface': 'crewai.LLM.call via LiteLLM (no Agent/Crew loop, no tools)',
            'temperature': 0, 'max_completion_tokens_per_call': MAX_COMPLETION_TOKENS, 'timeout_seconds': REQUEST_TIMEOUT_SECONDS,
            'response_format': 'json_object', 'provider_sdk_max_retries': 0,
            'http_requests_per_stage': HTTP_REQUESTS_PER_STAGE, 'quiet_env': QUIET_ENV}


class CrewAIClient:
    """Live model through CrewAI's LLM: one message, one HTTP request, no retries, no tools. Paid.

    Measured offline (tests/test_agent3_request_boundary.py): the Agent/Crew executor sends a second
    request when output is not a final answer, the OpenAI SDK retries 5xx/connection errors twice by
    default, and CrewAI wraps every LLM.call in a fixed 3-attempt rate-limit retry. Hence a direct
    LLM.call, max_retries=0, and RequestGuard, which blocks any second request before it is sent."""
    label = 'LIVE_MODEL'

    def __init__(self):
        for name, value in QUIET_ENV.items():
            os.environ.setdefault(name, value)
        from crewai import LLM
        from threadsense.config import get_api_key
        self.settings = live_settings()
        model = self.settings['model']
        self.llm = LLM(model=model, is_litellm=True,
                       base_url='https://openrouter.ai/api/v1' if model.startswith('openrouter/') else 'https://api.openai.com/v1',
                       api_key=get_api_key(self.settings['api_key_variable']), temperature=0,
                       max_tokens=MAX_COMPLETION_TOKENS, timeout=REQUEST_TIMEOUT_SECONDS, max_retries=0,
                       response_format={'type': 'json_object'})
        self.fingerprint, self.last_requests = model, None

    def complete(self, stage, payload, schema):
        messages = [{'role': 'system', 'content': 'You are the ThreadSense Advisor. You advise annotation team leads and '
                                                  'never go beyond the evidence provided. Reply with one JSON object.'},
                    {'role': 'user', 'content': task_description(payload, schema)}]
        guard = RequestGuard()
        try:
            with guard:
                raw = self.llm.call(messages)
        finally:
            self.last_requests = guard.stats()
        if not guard.sent:
            raise BoundaryNotObserved('The model response arrived without a request through the guarded transport.')
        return str(raw)


def task_description(payload, schema):
    """Exactly what the model receives as the user message: rules plus the full JSON payload."""
    body = json.dumps(payload, ensure_ascii=False)
    return f"{payload['rules']}\n\nInput JSON:\n{body}\n\nReturn exactly one JSON object for {schema.__name__} " \
           'matching output_schema. No prose outside the JSON.'


def _json_text(raw):
    text = raw.strip()
    if text.startswith('```'):
        text = text.split('\n', 1)[1].rsplit('```', 1)[0]
    return text


class Stages:
    """Budgeted model stages for one topic; zero retries, failures recorded and returned as None.
    `reserve` holds back calls for later stages (the final grounding call)."""

    def __init__(self, client, budget, scenario_id):
        self.client, self.budget, self.scenario_id, self.log = client, budget, scenario_id, []

    def __call__(self, stage, payload, schema, reserve=0):
        entry = {'stage': stage, 'schema': schema.__name__}
        left = self.budget.remaining('model_calls')
        if left is not None and left < 1 + reserve:
            status = 'SKIPPED_RESERVED_FOR_GROUNDING' if left >= 1 else 'SKIPPED_BUDGET'
            self.log.append({**entry, 'status': status, 'error': f'{left} model call(s) left; {reserve} reserved for final grounding'})
            return None
        try:
            self.budget.charge('model_calls')
        except BudgetExhausted as error:
            self.log.append({**entry, 'status': 'SKIPPED_BUDGET', 'error': str(error)})
            return None
        try:
            raw = self.client.complete(stage, {**payload, 'scenario_id': self.scenario_id, 'stage': stage,
                                               'output_schema': schema.model_json_schema()}, schema)
            entry.update(raw=raw, raw_sha256=sha256(raw.encode('utf-8')).hexdigest())
            value = schema.model_validate(json.loads(_json_text(raw)))
        except BoundaryNotObserved:
            raise  # Unverifiable call accounting stops the run.
        except Exception as error:  # Any provider, parsing or validation error: record it, never retry.
            self.log.append({**entry, **self._requests(), 'status': 'FAILED', 'error': f'{type(error).__name__}: {str(error)[:400]}'})
            return None
        self.log.append({**entry, **self._requests(), 'status': 'OK'})
        return value

    def _requests(self):
        stats = getattr(self.client, 'last_requests', None)
        return {'http_requests': stats} if stats is not None else {}


def topic_packet(view, scenario):
    gid = scenario['candidate_group_id']
    record = next((r for r in view['records'] if r['candidate_group_id'] == gid), None)
    if record is None:
        raise ScenarioError(f'Group {gid} is not in the handoff.')
    gap = None
    if scenario.get('topic_name'):
        topics = [t for t in record['topics'] if t['topic_name'] == scenario['topic_name']]
        if len(topics) != 1:
            raise ScenarioError(f"Group {gid} has {len(topics)} topics named {scenario['topic_name']!r}.")
        topic = topics[0]
        member_ids, topic_id, label = list(topic['member_ids']), topic['topic_id'], topic['topic_name']
        preliminary = topic.get('preliminary_severity')
    else:
        member_ids, topic_id = list(record['unassigned_member_ids']), None
        gap = next((r for r in record['review_reasons'] if r.startswith('Projection gap')), None)
        if not member_ids or gap is None:
            raise ScenarioError(f'Group {gid} has no unassigned projection-gap members.')
        label = f'Unassigned members of {gid} (projection gap; no Agent 2 topic)'
        preliminary = record.get('unassigned_preliminary_severity')
    members = sorted((m for m in record['members'] if m['member_id'] in member_ids), key=lambda m: float(m['thread_id']))
    return {'record': record, 'candidate_group_id': gid, 'topic_id': topic_id, 'topic_label': label,
            'topic_name': scenario.get('topic_name'), 'projection_gap': gap, 'project_id': record['project_id'],
            'batch_id': record['batch_id'], 'member_ids': [m['member_id'] for m in members], 'members': members,
            'agent1_resolution': agent1_resolution(members),
            'preliminary_severity': preliminary, 'handoff_contract': record['taxonomy_handoff']['contract_version'],
            'export_sha256': view['canonical_sha256'], 'schema_version': record['schema_version'],
            'threads': [{'project_id': m['project_id'], 'batch_id': m['batch_id'], 'channel_id': m['channel_id'],
                         'thread_id': m['thread_id'], 'member_id': m['member_id'],
                         'messages': m['original_thread']['messages']} for m in members]}


def initial_query(packet):
    """Topic name plus the earliest member's central question (no source IDs, no answers)."""
    question = packet['members'][0]['agent1_record']['interpretation']['central_question']
    return f"{packet['topic_name']}. {question}" if packet['topic_name'] else question


def rubric_payload(rubric):
    return {'version': rubric['version'], 'scope': rubric['rubric_scope'],
            'levels': {level: {'definition': e['definition'], 'examples': e['examples'],
                               'signals': [{'index': i, 'text': s} for i, s in enumerate(e['required_signals'])]}
                       for level, e in rubric['levels'].items()}}


def _interpretations(packet):
    out = []
    for m in packet['members']:
        a, i = m['agent1_record'], m['agent1_record']['interpretation']
        out.append({'member_id': m['member_id'], 'thread_id': m['thread_id'], 'summary': i['summary'],
                    'central_question': i['central_question'],
                    'attributed_agent1_resolution': {
                        'state': i['resolution_state'], 'rationale': (i.get('resolution_rationale') or '')[:400],
                        'agent1_verification_status': a.get('verification_status'),
                        'note': 'Agent 1 label, not evidence; NEEDS_REVIEW means Agent 1 did not verify it. Assess '
                                'resolution from the member messages.'},
                    'agent1_review_required': a['review_required'], 'agent1_review_reason': (a.get('review_reason') or '')[:600],
                    'note': 'Agent 1 interpretation, not source evidence; cite member messages for incident facts.'})
    return out


def _topic(packet, as_of):
    return {'project_id': packet['project_id'], 'batch_id': packet['batch_id'], 'candidate_group_id': packet['candidate_group_id'],
            'topic_id': packet['topic_id'], 'topic_label': packet['topic_label'], 'projection_gap': packet['projection_gap'],
            'as_of': as_of, 'member_ids': packet['member_ids']}


def _split(ledger):
    return ([v for v in ledger.values() if v['origin'] == 'member_message'],
            [v for v in ledger.values() if v['origin'] == 'retrieved_source'])


def _research_payload(rules, topic, ledger, tools, rubric, interpretations):
    members, retrieved = _split(ledger)
    return {'rules': rules, 'topic': topic, 'member_evidence': members, 'agent1_interpretations': interpretations,
            'retrieved_evidence': retrieved, 'retrieval_notes': tools.notes(), 'rubric': rubric_payload(rubric),
            'limits': {'follow_up_queries': MAX_FOLLOW_UPS}}


def grounding_payload(stmts, ledger, topic):
    """Statements that cite evidence, plus each cited item once (statements citing nothing are never sent)."""
    sent = [s for s in stmts if s['evidence_ids']]
    cited = dict.fromkeys(e for s in sent for e in s['evidence_ids'])
    return {'rules': GROUNDING_RULES, 'topic': topic,
            'statements': [{k: s[k] for k in ('statement_id', 'kind', 'text', 'evidence_ids')} for s in sent],
            'evidence': [ledger[e] for e in cited]}


def _final_grounding(call, draft, ledger, topic, stmts, structural, actions):
    if structural or actions:
        return grounding_result(draft, ledger, stmts, structural=structural, actions=actions)
    if not any(s['evidence_ids'] for s in stmts):
        return grounding_result(draft, ledger, stmts, reason='NOTHING_CITED')
    judgment = call('grounding', grounding_payload(stmts, ledger, topic), GroundingJudgment)
    return grounding_result(draft, ledger, stmts, judgment=judgment, ran=judgment is not None,
                            reason='GROUNDING_CALL_FAILED_OR_OVER_BUDGET')


def _review_items(packet, card):
    items = review_items_from_view({'records': [packet['record']]})
    linked = set(card.lineage.member_ids)
    return [ModelReviewItem.model_validate({**i.model_dump(mode='json'), 'related_card_ids': [card.card_id]})
            if set(i.member_ids) & linked or not i.member_ids else i for i in items]


NOT_RUN = {'structural_issues': [], 'action_issues': [], 'statements': [], 'unsupported': [], 'unjudged': [],
           'extraneous_verdicts': []}


def advise(scenario, *, view, retriever, client, budget, rubric, run_id, as_of, initial=None):
    """One topic. Never raises for model or budget problems; ScenarioError only for a missing topic.
    `initial` replaces the derived initial query (used to test recovery from an incomplete first pass)."""
    budget.start_topic()
    packet = topic_packet(view, scenario)
    ledger = {i['evidence_id']: i for i in member_messages(packet['members'])}
    tools = ResearchTools(retriever, project=packet['project_id'], batch=packet['batch_id'], as_of=as_of,
                          budget=budget, top_k=TOP_K, ledger=ledger)
    call, topic, interpretations = Stages(client, budget, scenario['id']), _topic(packet, as_of), _interpretations(packet)
    query = initial or initial_query(packet)
    tools.search(query, purpose='initial_current_guidance')
    if tools.withheld:  # Superseded material exists in this project: check whether it bears on the topic.
        tools.search(query, purpose='supersession_check', version_mode='history')
    first = draft = call('draft', _research_payload(DRAFT_RULES, topic, ledger, tools, rubric, interpretations),
                         AdvisorDraft, reserve=1)
    follow_ups, unfilled = [], []
    if draft is not None:
        requested = [g for g in draft.gaps if g.follow_up]
        for i, gap in enumerate(requested):
            entry = {'gap_id': gap.gap_id, 'need': gap.need, 'query': gap.follow_up.query,
                     'source_types': gap.follow_up.source_types, 'version_mode': gap.follow_up.version_mode}
            if i >= MAX_FOLLOW_UPS:
                follow_ups.append({**entry, 'status': 'DROPPED_FOLLOW_UP_LIMIT'})
                continue
            before = set(ledger)
            found = tools.search(gap.follow_up.query, purpose=f'gap:{gap.need}', source_types=gap.follow_up.source_types,
                                 version_mode=gap.follow_up.version_mode, gap_id=gap.gap_id)
            follow_ups.append({**entry, 'status': 'DONE' if found else 'SKIPPED_BUDGET',
                               'new_evidence_ids': sorted(set(ledger) - before)})
        if any(f['status'] == 'DONE' for f in follow_ups):
            payload = _research_payload(REVISION_RULES, topic, ledger, tools, rubric, interpretations)
            revised = call('revision', {**payload, 'previous_draft': draft.model_dump(), 'follow_ups': follow_ups},
                           AdvisorDraft, reserve=1)
            draft = revised or draft
        unfilled = [g.model_dump() for g in draft.gaps]
    flags = inherited_flags(packet['record'], packet['member_ids'], projection_gap=packet['projection_gap'])
    tot, diagnostics, temporal_pre = {'status': 'NOT_TRIGGERED', 'triggers': []}, [], None
    if draft is None:
        grounding, temporal, final = {**NOT_RUN, 'status': 'NOT_RUN', 'basis': 'NO_DRAFT'}, None, unauthorized(packet)
    else:
        structural, actions = structural_issues(draft, ledger, set(packet['member_ids'])), action_issues(draft, ledger)
        severity, severity_issues = build_severity(draft.severity, ledger, packet, rubric)
        temporal_pre = temporal_check(draft, ledger)
        tot = advisor_tot.compare(call, draft=draft, temporal=temporal_pre, ledger=ledger, handling=established(draft, ledger),
                                  skip='Structural grounding failed; alternatives could not be grounded.'
                                  if structural or actions else None, payload={
            'topic': topic, 'draft': draft.model_dump(), 'evidence': list(ledger.values()),
            'proposed_severity': {'level': severity.level, 'assessment_status': severity.assessment_status,
                                  'note': 'Bound to the rubric; not yet grounded.'},
            'rubric_levels': sorted(rubric['levels'])})
        stmts = statements(draft, ledger, severity=severity, alternatives=advisor_tot.alternatives(tot))
        grounding = _final_grounding(call, draft, ledger, topic, stmts, structural, actions)
        tot = advisor_tot.finalize(tot, grounding)
        final = authorize(draft, grounding, ledger, packet, severity=severity, severity_issues=severity_issues, rubric=rubric)
        # Recorded supersession is credited only to announcements the final grounding verified.
        temporal = temporal_check(draft, ledger, final['handling'])
        diagnostics += [{'code': 'ALTERNATIVE_NOT_GROUNDED' if w['kind'] == 'ALTERNATIVE' else 'WITHHELD_STATEMENT', **w}
                        for w in final['withheld']]
        if draft.evidence_sufficiency == 'UNSUPPORTED' and draft.proposed_action and \
                draft.proposed_action.action_type != 'NO_ACTION':
            diagnostics.append({'code': 'UNSUPPORTED_ACTION_NOT_CARRIED', 'action': draft.proposed_action.model_dump()})
    outcome = {'draft': draft, 'ledger': ledger, 'inherited_flags': flags, 'grounding': grounding, 'temporal': temporal,
               'final': final, 'evidence_sufficiency': draft.evidence_sufficiency if draft else None,
               'failures': [e for e in call.log if e['status'] != 'OK']}
    try:
        card = assemble_card(outcome, packet, run_id=run_id)
    except ValidationError as error:
        diagnostics.append({'code': 'CARD_ASSEMBLY_FAILED', 'error': str(error)[:1500]})
        card = assemble_card({**outcome, 'draft': None, 'temporal': None, 'evidence_sufficiency': None, 'final': unauthorized(packet),
                              'grounding': {**NOT_RUN, 'status': 'NOT_RUN', 'basis': 'CARD_ASSEMBLY_FAILED'},
                              'failures': outcome['failures'] + [{'stage': 'card_assembly', 'status': 'FAILED', 'error': 'see diagnostics'}]},
                             packet, run_id=run_id)
    items = _review_items(packet, card)
    covered = coverage({'records': [packet['record']]}, cards=[card], review_items=items)
    # Members of the group's other topics are outside this scenario (not lost); obligations must all be carried.
    covered = {'group_members_outside_this_card': covered['missing_members'],
               'uncarried_obligations': covered['missing_obligations']}
    return {'scenario': scenario, 'status': 'CARD', 'topic': {**topic, 'initial_query': query},
            'retrieval_trace': tools.trace, 'retrieval_notes': tools.notes(), 'follow_ups': follow_ups,
            'unfilled_gaps': unfilled, 'model_calls': call.log,
            'drafts': {'initial': first.model_dump() if first else None,
                       'final': draft.model_dump() if draft else None, 'revised': draft is not first},
            'grounding': grounding, 'temporal': temporal, 'temporal_before_grounding': temporal_pre,
            'severity': {'assessment': final['severity'].model_dump(mode='json'), 'issues': final['severity_issues'],
                         'notes': final['severity_notes'], 'proposal': draft.severity.model_dump() if draft else None},
            'resolution': {'topic': final['resolution'], 'members': final['member_resolution'],
                           'agent1_attributed': packet['agent1_resolution']},
            'established_handling': sorted(final['handling']),
            'tot': tot, 'evidence_ledger': ledger, 'card': card.model_dump(mode='json'),
            'review_items': [i.model_dump(mode='json') for i in items], 'coverage': covered,
            'budget': {'consumed': budget.topic_usage(), 'limits': BUDGET}, 'diagnostics': diagnostics}


def control(scenario, *, retriever, client, budget, rubric, as_of):
    """Negative control: a question with no handoff members, so no card. Unsupported stays visible."""
    budget.start_topic()
    ledger = {}
    tools = ResearchTools(retriever, project=scenario['project_id'], batch=scenario.get('batch_id'), as_of=as_of,
                          budget=budget, top_k=TOP_K, ledger=ledger)
    call = Stages(client, budget, scenario['id'])
    tools.search(scenario['question'], purpose='initial_current_guidance')
    topic = {'project_id': scenario['project_id'], 'batch_id': scenario.get('batch_id'), 'question': scenario['question'],
             'as_of': as_of, 'member_ids': []}
    draft = call('draft', {**_research_payload(DRAFT_RULES, topic, ledger, tools, rubric, []), 'member_evidence': []},
                 AdvisorDraft, reserve=1)
    grounding = None
    if draft is not None:
        stmts = statements(draft, ledger)
        grounding = _final_grounding(call, draft, ledger, topic, stmts,
                                     claim_issues(draft, ledger) + announcement_issues(draft, ledger), action_issues(draft, ledger))
    supported = draft is not None and draft.evidence_sufficiency == 'SUFFICIENT' and grounding['status'] == 'PASSED'
    return {'scenario': scenario, 'status': 'CONTROL', 'control_outcome': 'SUPPORTED' if supported else
            'NO_DRAFT' if draft is None else 'UNSUPPORTED',
            'retrieval_trace': tools.trace, 'retrieved_results': sum(len(s.get('result_ids', [])) for s in tools.trace),
            'model_calls': call.log, 'drafts': {'final': draft.model_dump() if draft else None}, 'grounding': grounding,
            'evidence_ledger': ledger, 'card': None, 'budget': {'consumed': budget.topic_usage(), 'limits': BUDGET},
            'note': 'External question with no handoff members: retrieved results are nearest neighbours, not evidence, '
                    'and no card is produced. Unsupported handoff members still get cards (see the topic scenarios).'}


def run_pilot(*, client, retriever=None, view=None, scenarios=None, budget_limits=BUDGET, handoff=HANDOFF):
    """Run the selected scenarios. The index freshness check happens once, here, before research."""
    retriever = retriever or open_retriever()
    view = view if view is not None else load_effective_view(handoff)
    spec = read_json(SCENARIOS) if scenarios is None else scenarios
    rubric, as_of, budget = load_rubric(None), retriever.manifest['cutoff'], Budget(budget_limits)
    run_id = stable_id('agent3pilot', {'version': PILOT_VERSION, 'scenarios': [s['id'] for s in spec['scenarios']],
                                       'export': view['canonical_sha256'], 'index': retriever.manifest['build_fingerprint'],
                                       'semantic': client.label, 'client': getattr(client, 'fingerprint', None)})
    results = []
    for scenario in spec['scenarios']:
        try:
            if scenario.get('control'):
                results.append(control(scenario, retriever=retriever, client=client, budget=budget, rubric=rubric, as_of=as_of))
            else:
                results.append(advise(scenario, view=view, retriever=retriever, client=client, budget=budget,
                                      rubric=rubric, run_id=run_id, as_of=as_of))
        except ScenarioError as error:
            results.append({'scenario': scenario, 'status': 'SCENARIO_UNAVAILABLE', 'error': str(error), 'card': None})
        except BoundaryNotObserved as error:  # Call accounting unverifiable: stop, record, make no further calls.
            results.append({'scenario': scenario, 'status': 'STOPPED_BOUNDARY_NOT_OBSERVED', 'error': str(error), 'card': None})
            break
    manifest = {
        'pilot_version': PILOT_VERSION, 'run_id': run_id, 'semantic_judgments': client.label,
        'semantic_client_fingerprint': getattr(client, 'fingerprint', None),
        'live_request_settings': getattr(client, 'settings', None),
        'handoff': {'run': Path(handoff).resolve().relative_to(ROOT).as_posix() if Path(handoff).resolve().is_relative_to(ROOT)
                    else str(handoff), 'canonical_sha256': view['canonical_sha256']},
        'index': {k: retriever.manifest[k] for k in ('build_fingerprint', 'chunking_version', 'corpus_fingerprint', 'cutoff')},
        'freshness': 'CURRENT (checked once before research)', 'as_of': as_of,
        'rubric': {k: rubric[k] for k in ('version', 'content_sha256', 'rubric_scope')},
        'retrieval': {'top_k': TOP_K, 'mode': 'hybrid', 'use_mmr': True, 'mmr_lambda': DEFAULTS['mmr_lambda'],
                      'rrf_only_option': 'Retriever.search(use_mmr=False); not used by the pilot',
                      'initial_version_mode': 'current', 'max_follow_ups_per_topic': MAX_FOLLOW_UPS},
        'budget_limits': budget_limits, 'budget_consumed': dict(budget.used),
        'http_requests': {'sent': sum(c.get('http_requests', {}).get('sent', 0) for r in results for c in r.get('model_calls', [])),
                          'blocked': sum(c.get('http_requests', {}).get('blocked', 0) for r in results for c in r.get('model_calls', []))},
        'scenarios': [{'id': r['scenario']['id'], 'status': r['status'],
                       'card_line': (r.get('card') or {}).get('card_line'), 'control_outcome': r.get('control_outcome')}
                      for r in results]}
    return {'manifest': manifest, 'results': results}


def _tokens(text):
    try:
        import tiktoken
        return len(tiktoken.get_encoding('o200k_base').encode(text)), 'o200k_base'
    except Exception:  # noqa: BLE001 - an estimate only
        return len(text) // 4, 'chars/4'


def plan(*, retriever=None, view=None, scenarios=None, handoff=HANDOFF):
    """Zero model calls: freshness check, topic packets, the initial retrieval each topic would start from,
    and the size of the first (draft) request."""
    retriever = retriever or open_retriever()
    view = view if view is not None else load_effective_view(handoff)
    spec, as_of, rows = read_json(SCENARIOS) if scenarios is None else scenarios, retriever.manifest['cutoff'], []
    rubric = load_rubric(None)
    for scenario in spec['scenarios']:
        budget = Budget(BUDGET)
        try:
            packet = None if scenario.get('control') else topic_packet(view, scenario)
        except ScenarioError as error:
            rows.append({'id': scenario['id'], 'status': 'SCENARIO_UNAVAILABLE', 'error': str(error)})
            continue
        project = scenario['project_id'] if packet is None else packet['project_id']
        batch = scenario.get('batch_id') if packet is None else packet['batch_id']
        ledger = {} if packet is None else {i['evidence_id']: i for i in member_messages(packet['members'])}
        tools = ResearchTools(retriever, project=project, batch=batch, as_of=as_of, budget=budget, top_k=TOP_K, ledger=ledger)
        query = scenario['question'] if packet is None else initial_query(packet)
        found = tools.search(query, purpose='initial_current_guidance')
        topic = {'project_id': project, 'batch_id': batch, 'as_of': as_of} if packet is None else _topic(packet, as_of)
        payload = _research_payload(DRAFT_RULES, topic, ledger, tools, rubric, [] if packet is None else _interpretations(packet))
        tokens, counter = _tokens(task_description({**payload, 'output_schema': AdvisorDraft.model_json_schema()}, AdvisorDraft))
        rows.append({'id': scenario['id'], 'status': 'PLANNED', 'project_id': project, 'batch_id': batch,
                     'topic': None if packet is None else packet['topic_label'],
                     'member_ids': [] if packet is None else packet['member_ids'], 'initial_query': query,
                     'member_evidence_ids': [k for k, v in ledger.items() if v['origin'] == 'member_message'],
                     'initial_results': [(r['evidence_id'], r['use'], r['applicability']['state']) for r in found['results']],
                     'withheld_by_version': tools.notes()['withheld_by_version'],
                     'supersession_check_planned': bool(tools.withheld),
                     'draft_prompt_tokens_estimate': tokens, 'token_counter': counter})
    return {'as_of': as_of, 'budget_limits': BUDGET, 'model_calls': 0, 'scenarios': rows,
            'request_limits': {'http_requests_per_stage': HTTP_REQUESTS_PER_STAGE, 'provider_sdk_max_retries': 0,
                               'max_completion_tokens_per_call': MAX_COMPLETION_TOKENS,
                               'max_http_requests_per_run': BUDGET['model_calls_total'] * HTTP_REQUESTS_PER_STAGE}}


def _dump(path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1, sort_keys=True) + '\n', encoding='utf-8')


def write_outputs(out_dir, run):
    """Write to a new directory only; never overwrites a previous run."""
    out = Path(out_dir)
    if out.exists():
        raise FileExistsError(f'{out} exists; pilot runs write to a new directory.')
    (out/'results').mkdir(parents=True)
    _dump(out/'manifest.json', run['manifest'])
    for result in run['results']:
        _dump(out/'results'/f"{result['scenario']['id']}.json", result)
    _dump(out/'cards.json', [r['card'] for r in run['results'] if r.get('card')])
    _dump(out/'review_items.json', [i for r in run['results'] for i in r.get('review_items', [])])
    (out/'report.md').write_text(report(run), encoding='utf-8')
    return out


def _fmt_ids(ids):
    return ', '.join(f'`{i}`' for i in ids) or 'none'


def report(run):
    m = run['manifest']
    lines = [f"# Agent 3 pilot - {m['run_id']}", '',
             f"Semantic judgments: **{m['semantic_judgments']}**. Deterministic checks (citations, applicability, "
             'severity binding, temporal priority, authorization, routing, budgets) ran for real; with SCRIPTED_MOCK, the '
             'draft, grounding and comparison judgments are prepared responses and say nothing about model quality.', '',
             f"Handoff `{m['handoff']['run']}`; index `{m['index']['chunking_version']}` "
             f"({m['freshness']}); as-of {m['as_of']}; rubric {m['rubric']['version']} ({m['rubric']['rubric_scope']}).", '',
             f"Budget limits {m['budget_limits']}; consumed {m['budget_consumed']}; HTTP requests {m['http_requests']}.", '']
    for r in run['results']:
        s = r['scenario']
        lines += [f"## {s['id']}: {s['focus']}", '']
        if r['status'] in ('SCENARIO_UNAVAILABLE', 'STOPPED_BOUNDARY_NOT_OBSERVED'):
            lines += [f"**{r['status']}:** {r['error']}", '']
            continue
        if r['status'] == 'CONTROL':
            lines += [f"Control outcome: **{r['control_outcome']}** (no card). Retrieved {r['retrieved_results']} results; "
                      f"model calls {[c['stage'] + ':' + c['status'] for c in r['model_calls']]}.", '']
            continue
        card, g = r['card'], r['grounding']
        withheld = [d for d in r['diagnostics'] if d['code'] == 'WITHHELD_STATEMENT']
        lines += [f"Topic: {card['topic_name']} (`{card['lineage']['candidate_group_id']}`, {len(card['lineage']['member_ids'])} members)",
                  f"- Card line: **{card['card_line']}**; action: "
                  f"{(card['recommended_action'] or {}).get('action_type')}; confidence {card['confidence']} ({card['confidence_band']})",
                  f"- Severity: {card['severity']['level']} ({card['severity']['assessment_status']}); signals "
                  f"{[f'{x['level']}[{x['signal_index']}]' for x in card['severity']['matched_signals']]}; "
                  f"affected reporters {card['severity']['occurrence']['affected_reporters']['status']} "
                  f"{card['severity']['occurrence']['affected_reporters'].get('count')}; issues {r['severity']['issues'] or 'none'}",
                  f"- Resolution: {r['resolution']['topic']} from grounded member states "
                  f"{sorted(r['resolution']['members'].values())}; Agent 1 attributed "
                  f"{sorted((a['state'], a['agent1_verification_status']) for a in r['resolution']['agent1_attributed'])}",
                  f"- Grounding: **{g['status']}** ({g['basis']}); {len(g['statements'])} statements; structural issues "
                  f"{[i['code'] for i in g['structural_issues']] + g['action_issues'] or 'none'}; not supported "
                  f"{g['unsupported'] + g['unjudged'] or 'none'}",
                  f"- Established announcement handling: {_fmt_ids(r['established_handling'])}",
                  f"- Withheld from the card: " + ('; '.join(f"{w['statement_id']} ({w['verdict']}): {w['text'][:140]}" for w in withheld)
                                                    or 'none'),
                  f"- Temporal: {(r['temporal'] or {}).get('status')}; findings "
                  f"{[(f['code'], f['status']) for f in (r['temporal'] or {}).get('findings', [])] or 'none'}",
                  f"- ToT: {r['tot']['status']} {r['tot'].get('triggers')}"
                  + (f"; presentation {r['tot']['presentation']}; candidates "
                     f"{[(c['candidate_id'], c['action_type'], c['valid'], c['grounding'], c['issues']) for c in r['tot']['candidates']]}"
                     if r['tot']['status'] == 'COMPARED' else ''),
                  '- Review reasons: ' + ('; '.join(f"{x['code']}: {x['detail'][:160]}" for x in card['needs_review_reasons']) or 'none'),
                  f"- Inherited flags: {len(card['inherited_flags'])}; uncarried obligations "
                  f"{r['coverage']['uncarried_obligations'] or 'none'}; group members in other topics (outside this card) "
                  f"{len(r['coverage']['group_members_outside_this_card'])}",
                  f"- Model calls: {[c['stage'] + ':' + c['status'] for c in r['model_calls']]}; budget used {r['budget']['consumed']}",
                  '', '| Step | Purpose | Mode | Types | New evidence |', '| --- | --- | --- | --- | --- |']
        for t in r['retrieval_trace']:
            lines.append(f"| {t['step']} | {t['purpose']} | {t['version_mode']} | {','.join(t['source_types'])} | "
                         f"{_fmt_ids(t.get('new_evidence_ids', [])) if t['status'] == 'DONE' else t['status']} |")
        cited = [x['note'] or '' for x in card['supporting_sources'] if x['kind'] == 'knowledge_source']
        lines += ['', f"Cited sources: {', '.join(cited) or 'none'}", '']
    return '\n'.join(lines) + '\n'
