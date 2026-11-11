"""AI-quality feedback from reviewers: immutable events in the decision store, kept apart from operational decisions.

Two different things are recorded on a card:
- the operational decision (decisions.py: Approve/Confirm/Dismiss/... on the card, Accept/Reject/Defer on a Model Review
  Queue item): what the team lead decides to do. Agreeing is not proof that every claim is right, a rejection can be a
  business preference, and a deferral is no label at all. None of them creates feedback or corrective memory.
- AI-quality feedback (this module): the reviewer says which output is wrong (a summary, evidence, a recommendation,
  a verifier verdict, the grouping, the severity, other), optionally how to correct it, and whether the correction
  may be used in future runs.

Lifecycle (append-only events, contract dashboard-ai-feedback-event-v1; a later event never edits an earlier one):
SUBMITTED -> CONFIRMED (an authorized team lead confirms it explicitly) -> WITHDRAWN, or SUPERSEDED when a confirmed
newer report names it in `supersedes_feedback_id`; SUBMITTED -> WITHDRAWN. Submissions are idempotent (request key)
and lifecycle actions carry the expected head event, like decisions.

Eligible for future runs = CONFIRMED, opted in, a correction text, and a scope of 1-5 Slack threads in one project.
Only eligible corrections enter a reviewer-feedback snapshot (build_snapshot), which a later Agent 3 run reads as
labelled advisory context (agents/reviewer_context). A snapshot is computed from the events recorded up to its
cutoff, so a later withdrawal changes later snapshots and never an earlier one. Feedback never edits a card, a run
artifact, a source document, a prompt, a rule or the rubric, and it executes nothing.
"""
import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from threadsense.agents.advice_contracts import stable_id
from threadsense.agents.reviewer_context import SNAPSHOT_CONTRACT, content_sha256
from threadsense.dashboard.decisions import ORIGIN_NAMESPACES, DecisionError
from threadsense.routing import aware

REPORT_CONTRACT = 'dashboard-ai-feedback-v1'
EVENT_CONTRACT = 'dashboard-ai-feedback-event-v1'
CASE_CONTRACT = 'reviewer-feedback-eval-candidate-v1'
Category = Literal['INTERPRETATION_SUMMARY', 'EVIDENCE', 'RECOMMENDATION', 'VERIFIER_FALSE_ACCEPTANCE',
                   'VERIFIER_FALSE_REJECTION', 'TOPIC_GROUPING', 'SEVERITY', 'OTHER']
CATEGORY_LABELS = {
    'INTERPRETATION_SUMMARY': 'Interpretation or summary', 'EVIDENCE': 'Missing, irrelevant, or outdated evidence',
    'RECOMMENDATION': 'Unsupported or impractical recommendation', 'VERIFIER_FALSE_ACCEPTANCE': 'Verifier false acceptance',
    'VERIFIER_FALSE_REJECTION': 'Verifier false rejection', 'TOPIC_GROUPING': 'Topic grouping', 'SEVERITY': 'Severity',
    'OTHER': 'Other'}
PROBLEMS = {'EVIDENCE': ('MISSING', 'IRRELEVANT', 'OUTDATED'), 'RECOMMENDATION': ('UNSUPPORTED', 'IMPRACTICAL')}
TargetKind = Literal['CARD', 'STATEMENT', 'REVIEW_ITEM']
State = Literal['SUBMITTED', 'CONFIRMED', 'WITHDRAWN', 'SUPERSEDED']
TRANSITIONS = {'SUBMITTED': {'CONFIRM': 'CONFIRMED', 'WITHDRAW': 'WITHDRAWN'}, 'CONFIRMED': {'WITHDRAW': 'WITHDRAWN'}}
EVENT_TYPES = {'CONFIRM': 'CONFIRMED', 'WITHDRAW': 'WITHDRAWN'}
MAX_TEXT = 1500
MIN_CORRECTION = 12   # An actual correction, not "fix this".
MAX_SCOPE_THREADS = 5  # Card-level feedback on a larger consolidated card must name its threads.
MAX_REFS = 10
REF_PATTERN = re.compile(r'^(m|k):\S{3,300}$')
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_TEXT)]


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Frozen(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)


class FeedbackRequest(Strict):
    actor_id: Text
    category: Category
    problem: str | None = None                # EVIDENCE: MISSING/IRRELEVANT/OUTDATED; RECOMMENDATION: UNSUPPORTED/IMPRACTICAL
    target_kind: TargetKind = 'CARD'
    target_id: str | None = None              # statement_id or review item_id; None for the card itself
    what_is_wrong: Text
    suggested_correction: Annotated[str, StringConstraints(strip_whitespace=True, max_length=MAX_TEXT)] | None = None
    source_refs: list[str] = Field(default_factory=list, max_length=MAX_REFS)
    scope_threads: list[str] | None = None    # 'channel/thread' among the card's threads; None derives the scope
    use_in_future_runs: bool = False
    supersedes_feedback_id: str | None = None
    expected_head: None = None                # A submission starts a new feedback record.


class FeedbackActionRequest(Strict):
    action: Literal['CONFIRM', 'WITHDRAW']
    actor_id: Text
    expected_head: str | None = None
    note: Annotated[str, StringConstraints(strip_whitespace=True, max_length=MAX_TEXT)] | None = None


class Thread(Frozen):
    channel_id: Text
    thread_id: Text


class Target(Frozen):
    kind: TargetKind
    id: Text
    statement_kind: str | None = None
    earlier_text: str | None = None       # The output as saved (verbatim).
    earlier_verdict: str | None = None    # The verifier's recorded verdict on it, if any.
    earlier_rationale: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    review_item_kind: str | None = None


class Scope(Frozen):
    project_id: Text
    batch_id: str | None = None
    candidate_group_id: str | None = None
    topic_id: str | None = None
    threads: list[Thread]
    basis: Literal['STATEMENT_EVIDENCE', 'REVIEW_ITEM_MEMBERS', 'CARD_THREADS', 'REVIEWER_SELECTED']


class FutureUse(Frozen):
    requested: bool
    blockers: list[str] = Field(default_factory=list)  # Why it could not be used, even once confirmed.
    note: Literal['Advisory context for matching later runs only; it never edits source documents, prompts, rules or '
                  'cards and executes nothing.'] = ('Advisory context for matching later runs only; it never edits source '
                                                    'documents, prompts, rules or cards and executes nothing.')

    @model_validator(mode='after')
    def consistent(self):
        if self.requested and self.blockers:
            raise ValueError('Future use was requested but the correction is not usable: ' + '; '.join(self.blockers))
        return self


class FeedbackReport(Frozen):
    """What the reviewer reported, with the run binding and an immutable snapshot of the output it is about."""
    contract_version: Literal['dashboard-ai-feedback-v1'] = REPORT_CONTRACT
    feedback_id: Annotated[str, StringConstraints(pattern=r'^feedback_[0-9a-f]{32}$')]
    namespace: Literal['operational', 'demo', 'test']
    run_key: Text
    run_id: Text
    run_instance: Annotated[str, StringConstraints(pattern=r'^[0-9a-f]{64}$')]
    run_mode: Literal['LIVE', 'SCRIPTED', 'TEST_FIXTURE', 'UNKNOWN']
    cards_sha256: Text
    card_id: Text
    card_line: Text
    topic_name: Text
    category: Category
    problem: str | None = None
    target: Target
    what_is_wrong: Text
    suggested_correction: str | None = None
    source_refs: list[dict] = Field(default_factory=list)  # {ref, in_card_evidence}
    scope: Scope
    original_output: dict                                  # Card fields as saved (summary, line, severity, next step).
    artifacts: dict                                        # Immutable files: cards.json and the topic result, with hashes.
    versions: dict                                         # Model, prompts, knowledge snapshot, rubric (None if not recorded).
    future_use: FutureUse
    supersedes_feedback_id: str | None = None
    submitted_at: Text
    submitted_by: Text
    submitted_by_role: Literal['TEAM_LEAD']
    feedback_is_not_policy: Literal[True] = True
    feedback_is_not_ground_truth: Literal[True] = True

    @model_validator(mode='after')
    def consistent(self):
        aware(self.submitted_at)
        allowed = PROBLEMS.get(self.category, ())
        if self.problem is not None and self.problem not in allowed:  # Optional where defined, absent elsewhere.
            raise ValueError(f'{self.problem} is not a {self.category} problem (allowed: {", ".join(allowed) or "none"}).')
        return self


class FeedbackEvent(Frozen):
    contract_version: Literal['dashboard-ai-feedback-event-v1'] = EVENT_CONTRACT
    entry_id: Annotated[str, StringConstraints(pattern=r'^feedbackevent_[0-9a-f]{32}$')]
    feedback_id: Annotated[str, StringConstraints(pattern=r'^feedback_[0-9a-f]{32}$')]
    sequence: int = Field(ge=1)
    supersedes_entry_id: str | None = None   # The previous event on this feedback (the head the action was made on).
    run_key: Text
    namespace: Literal['operational', 'demo', 'test']
    event_type: State
    state_after: State
    recorded_at: Text
    actor_id: str | None = None              # None only for the system SUPERSEDED event.
    actor_role: Literal['TEAM_LEAD'] | None = None
    note: str | None = None
    report: FeedbackReport | None = None     # Only on SUBMITTED.
    superseded_by_feedback_id: str | None = None
    idempotency_key: str | None = None
    request_sha256: str | None = None

    @model_validator(mode='after')
    def consistent(self):
        aware(self.recorded_at)
        if (self.event_type == 'SUBMITTED') != (self.report is not None) or (self.sequence == 1) != (self.event_type == 'SUBMITTED'):
            raise ValueError('Only the first event submits the report.')
        if (self.event_type == 'SUPERSEDED') != (self.superseded_by_feedback_id is not None):
            raise ValueError('A superseded event names the feedback that supersedes it.')
        if (self.actor_id is None) != (self.event_type == 'SUPERSEDED'):
            raise ValueError('Every event but the system supersession has a team-lead actor.')
        if self.event_type != self.state_after:
            raise ValueError('The event type is the state it leads to.')
        return self


# ---- Building reports and events -------------------------------------------------------------------------------

def thread_key(t):
    return f"{t['channel_id']}/{t['thread_id']}"


def card_threads(card):
    members = set(card['lineage']['member_ids'])
    return [{'channel_id': t['channel_id'], 'thread_id': t['thread_id'], 'member_id': t.get('member_id')}
            for t in card['related_threads'] if t.get('member_id') in members or not t.get('member_id')]


def targets(run, card_id):
    """What a reviewer can point at on this card: its saved statements (grounding statement IDs, verdicts as recorded)
    and the Model Review Queue items about it. The card itself is always a target."""
    result = (run.topics.get(card_id) or {}).get('result') or {}
    statements = [{'id': s['statement_id'], 'kind': s['kind'], 'text': s['text'], 'verdict': s.get('verdict'),
                   'rationale': s.get('rationale'), 'evidence_ids': s.get('evidence_ids') or []}
                  for s in (result.get('grounding') or {}).get('statements') or []]
    items = [{'id': i.item_id, 'kind': i.kind, 'reason': i.reason, 'member_ids': i.member_ids}
             for i in run.queue.values() if card_id in i.related_card_ids]
    return {'statements': statements, 'review_items': items,
            'threads': [{**t, 'key': thread_key(t)} for t in card_threads(run.card(card_id))]}


def _target_and_scope(run, card, request):
    found, card_level = targets(run, card['card_id']), card_threads(card)
    by_member = {t['member_id']: t for t in card_level if t.get('member_id')}
    ledger = run.ledger(card['card_id'])
    if request.target_kind == 'CARD':
        if request.target_id not in (None, card['card_id']):
            raise DecisionError('Card-level feedback is about this card; give no other target ID.')
        target = Target(kind='CARD', id=card['card_id'], earlier_text=card.get('summary'))
        threads, basis = card_level, 'CARD_THREADS'
    elif request.target_kind == 'STATEMENT':
        s = next((x for x in found['statements'] if x['id'] == request.target_id), None)
        if s is None:
            raise DecisionError(f'{request.target_id} is not a saved statement of this card.')
        target = Target(kind='STATEMENT', id=s['id'], statement_kind=s['kind'], earlier_text=s['text'],
                        earlier_verdict=s['verdict'], earlier_rationale=s['rationale'], evidence_ids=s['evidence_ids'])
        cited = [ledger[e] for e in s['evidence_ids'] if (ledger.get(e) or {}).get('origin') == 'member_message']
        threads = list({thread_key(e): {'channel_id': e['channel_id'], 'thread_id': e['thread_id']} for e in cited}.values())
        basis = 'STATEMENT_EVIDENCE'
        if not threads:
            threads, basis = card_level, 'CARD_THREADS'
    else:
        item = next((x for x in found['review_items'] if x['id'] == request.target_id), None)
        if item is None:
            raise DecisionError(f'{request.target_id} is not a Model Review Queue item about this card.')
        target = Target(kind='REVIEW_ITEM', id=item['id'], earlier_text=item['reason'], review_item_kind=item['kind'])
        threads = [by_member[m] for m in item['member_ids'] if m in by_member]
        basis = 'REVIEW_ITEM_MEMBERS'
        if not threads:
            threads, basis = card_level, 'CARD_THREADS'
    if request.scope_threads is not None:
        known = {thread_key(t): t for t in card_level}
        unknown = [k for k in request.scope_threads if k not in known]
        if unknown:
            raise DecisionError(f'Scope threads must be threads of this card: {", ".join(unknown)}.')
        threads, basis = [known[k] for k in dict.fromkeys(request.scope_threads)], 'REVIEWER_SELECTED'
    lineage = card['lineage']
    scope = Scope(project_id=card['project_id'], batch_id=lineage.get('batch_id'),
                  candidate_group_id=lineage.get('candidate_group_id'), topic_id=lineage.get('topic_id'),
                  threads=[{'channel_id': t['channel_id'], 'thread_id': t['thread_id']} for t in threads], basis=basis)
    return target, scope


def blockers(correction, scope):
    out = []
    if len(correction or '') < MIN_CORRECTION:
        out.append(f'write the correction itself (at least {MIN_CORRECTION} characters)')
    if not scope.threads:
        out.append('the card has no Slack thread to scope the correction to')
    if len(scope.threads) > MAX_SCOPE_THREADS:
        out.append(f'the scope has {len(scope.threads)} threads; choose at most {MAX_SCOPE_THREADS} it applies to')
    return out


def versions(run):
    f = run.manifest.get('fingerprints') or {}
    client, prompts, index = f.get('semantic_client') or {}, f.get('prompts') or {}, f.get('index') or {}
    return {'semantic_client': client.get('label'), 'model': (client.get('settings') or {}).get('model'),
            'prompt_version': prompts.get('prompt_version'), 'pilot_version': f.get('pilot_version'),
            'prompts_sha256': content_sha256({'p': prompts}) if prompts else None,
            'knowledge_snapshot': {k: index.get(k) for k in ('index_dir', 'build_fingerprint', 'corpus_fingerprint', 'cutoff')}
            if index else None,
            'rubric': f.get('rubric'), 'derivation': (run.manifest.get('derivation') or {}).get('version')}


def build_report(*, run, card, request, actors, feedback_id, recorded_at, history, origin='TL_DASHBOARD'):
    actor = actors.get(request.actor_id)
    if actor is None:
        raise DecisionError(f'{request.actor_id} is not a recorded team lead.')
    target, scope = _target_and_scope(run, card, request)
    correction = (request.suggested_correction or '').strip() or None
    blocked = blockers(correction, scope)
    if request.use_in_future_runs and blocked:
        raise DecisionError('Cannot offer this for future runs: ' + '; '.join(blocked) + '.')
    ledger = run.ledger(card['card_id'])
    refs = []
    for ref in dict.fromkeys(r.strip() for r in request.source_refs if r.strip()):
        if not REF_PATTERN.match(ref):
            raise DecisionError(f'{ref!r} is not an evidence ID (m:<channel>:<message> or k:<source>).')
        refs.append({'ref': ref, 'in_card_evidence': ref in ledger})
    if request.supersedes_feedback_id is not None:
        earlier = fold(history(request.supersedes_feedback_id))
        if earlier is None:
            raise DecisionError(f'{request.supersedes_feedback_id} is not a recorded feedback report.')
        if earlier['report']['scope']['project_id'] != card['project_id']:
            raise DecisionError('A correction can only supersede feedback in the same project.')
        if earlier['state'] not in TRANSITIONS:
            raise DecisionError(f"{request.supersedes_feedback_id} is already {earlier['state'].lower()}.")
    topic_path = run.topic_paths.get(card['card_id'])
    return FeedbackReport(
        feedback_id=feedback_id, namespace=ORIGIN_NAMESPACES.get(origin, run.namespace), run_key=run.key,
        run_id=run.brief['run_id'], run_instance=run.instance, run_mode=run.mode, cards_sha256=run.cards_sha256,
        card_id=card['card_id'], card_line=card['card_line'], topic_name=card['topic_name'], category=request.category,
        problem=request.problem, target=target, what_is_wrong=request.what_is_wrong, suggested_correction=correction,
        source_refs=refs, scope=scope,
        original_output={'summary': card.get('summary'), 'card_line': card['card_line'],
                         'severity': card['severity']['level'], 'next_step': card.get('next_step'),
                         'recommended_action': (card.get('recommended_action') or {}).get('label')},
        artifacts={'cards': {'path': f'{run.key}/cards.json', 'sha256': run.cards_sha256},
                   'topic_result': {'path': f'{run.key}/{topic_path.relative_to(run.path).as_posix()}',
                                    'sha256': run.file_hash(topic_path)} if topic_path else None},
        versions=versions(run), future_use=FutureUse(requested=request.use_in_future_runs, blockers=blocked),
        supersedes_feedback_id=request.supersedes_feedback_id, submitted_at=recorded_at, submitted_by=actor['actor_id'],
        submitted_by_role=actor['role'])


def feedback_id_for(run, card_id, key):
    return stable_id('feedback', {'run_ref': run.ref, 'card_id': card_id, 'idempotency_key': key})


def submission(*, run, report, key, request_sha):
    return FeedbackEvent(
        entry_id=stable_id('feedbackevent', {'feedback_id': report.feedback_id, 'sequence': 1}), feedback_id=report.feedback_id,
        sequence=1, run_key=run.ref, namespace=report.namespace, event_type='SUBMITTED', state_after='SUBMITTED',
        recorded_at=report.submitted_at, actor_id=report.submitted_by, actor_role=report.submitted_by_role, report=report,
        idempotency_key=key, request_sha256=request_sha)


def action_event(*, head, request, actors, sequence, recorded_at, key, request_sha):
    actor = actors.get(request.actor_id)
    if actor is None:
        raise DecisionError(f'{request.actor_id} is not a recorded team lead.')
    state = head['state_after']
    if request.action not in TRANSITIONS.get(state, {}):
        raise DecisionError(f'A {state.lower()} feedback report cannot be {EVENT_TYPES[request.action].lower()}.')
    after = TRANSITIONS[state][request.action]
    return FeedbackEvent(
        entry_id=stable_id('feedbackevent', {'feedback_id': head['feedback_id'], 'sequence': sequence, 'idempotency_key': key}),
        feedback_id=head['feedback_id'], sequence=sequence, supersedes_entry_id=head['entry_id'], run_key=head['run_key'],
        namespace=head['namespace'], event_type=after, state_after=after, recorded_at=recorded_at, actor_id=actor['actor_id'],
        actor_role=actor['role'], note=request.note or None, idempotency_key=key, request_sha256=request_sha)


def supersede_on_confirm(store, db, entry, history_in_tx):
    """Inside the confirming transaction: a confirmed report that names an earlier one moves it to SUPERSEDED (a new
    event on the earlier report; its own events are unchanged). An earlier report already withdrawn stays withdrawn."""
    if entry['event_type'] != 'CONFIRMED':
        return
    first = history_in_tx(db, entry['feedback_id'])[0]
    earlier_id = first['report']['supersedes_feedback_id']
    if earlier_id is None:
        return
    earlier = history_in_tx(db, earlier_id)
    head = earlier[-1]
    if head['state_after'] not in TRANSITIONS:
        return
    event = FeedbackEvent(
        entry_id=stable_id('feedbackevent', {'feedback_id': earlier_id, 'sequence': head['sequence'] + 1,
                                             'superseded_by': entry['feedback_id']}),
        feedback_id=earlier_id, sequence=head['sequence'] + 1, supersedes_entry_id=head['entry_id'], run_key=head['run_key'],
        namespace=head['namespace'], event_type='SUPERSEDED', state_after='SUPERSEDED', recorded_at=entry['recorded_at'],
        superseded_by_feedback_id=entry['feedback_id'],
        note=f"Superseded by {entry['feedback_id']}, confirmed by {entry['actor_id']}.").model_dump(mode='json')
    store.insert_feedback_event(db, event)


# ---- Reading the history ---------------------------------------------------------------------------------------

def fold(events, cutoff=None):
    """Current view of one feedback report from its events (only those recorded at or before cutoff, if given)."""
    if cutoff is not None:
        events = [e for e in events if aware(e['recorded_at']) <= aware(cutoff)]
    if not events:
        return None
    report, head = events[0]['report'], events[-1]
    confirm = next((e for e in events if e['event_type'] == 'CONFIRMED'), None)
    state = head['state_after']
    eligible = state == 'CONFIRMED' and report['future_use']['requested'] and not report['future_use']['blockers']
    why = ('Eligible: confirmed, opted in, with a correction and a thread scope.' if eligible else
           'Not offered for future runs by the reviewer.' if not report['future_use']['requested'] else
           'Awaiting confirmation by a team lead.' if state == 'SUBMITTED' else
           f'{state.capitalize()}: no longer used in new snapshots.')
    return {'feedback_id': report['feedback_id'], 'state': state, 'report': report, 'head': head, 'events': events,
            'confirmed_at': confirm and confirm['recorded_at'], 'confirmed_by': confirm and confirm['actor_id'],
            'self_confirmed': bool(confirm) and confirm['actor_id'] == report['submitted_by'],
            'superseded_by': head.get('superseded_by_feedback_id'), 'eligible_for_future_runs': eligible,
            'eligibility': why}


def grouped(events):
    out = {}
    for e in events:
        out.setdefault(e['feedback_id'], []).append(e)
    return {k: sorted(v, key=lambda e: e['sequence']) for k, v in out.items()}


def counts(views, used=()):
    """Workflow counts for one run's feedback, not accuracy."""
    return {'submitted': len(views), 'confirmed': sum(v['state'] == 'CONFIRMED' for v in views),
            'eligible_for_future_runs': sum(v['eligible_for_future_runs'] for v in views),
            'withdrawn': sum(v['state'] == 'WITHDRAWN' for v in views),
            'superseded': sum(v['state'] == 'SUPERSEDED' for v in views),
            'corrections_used_by_this_run': len(set(used))}


# ---- Snapshot for later runs -----------------------------------------------------------------------------------

DEFAULT_NAMESPACES = ('operational',)


def build_snapshot(events, *, cutoff, namespaces=DEFAULT_NAMESPACES):
    """reviewer-feedback-snapshot-v1 from the store's events as of cutoff. Deterministic: the same events, cutoff and
    namespaces give the same bytes and the same snapshot_sha256."""
    unknown = set(namespaces) - {'operational', 'demo', 'test'}
    if unknown:
        raise ValueError(f'Unknown feedback namespaces: {sorted(unknown)}.')
    aware(cutoff)
    corrections, excluded = [], []
    for fid, history in sorted(grouped(events).items()):
        view = fold(history, cutoff)
        if view is None:
            continue  # Submitted after the cutoff.
        r = view['report']
        reasons = ([] if r['namespace'] in namespaces else [f"namespace {r['namespace']} not included"]) + (
            [] if view['eligible_for_future_runs'] else [view['eligibility']])
        if reasons:
            excluded.append({'feedback_id': fid, 'state_at_cutoff': view['state'], 'reasons': reasons})
            continue
        corrections.append({
            'feedback_id': fid, 'authority': 'REVIEWER_CORRECTION', 'namespace': r['namespace'], 'category': r['category'],
            'problem': r['problem'], 'target': {k: r['target'].get(k) for k in ('kind', 'id', 'statement_kind', 'earlier_text',
                                                                                 'earlier_verdict')},
            'what_is_wrong': r['what_is_wrong'], 'correction': r['suggested_correction'],
            'source_refs': [x['ref'] for x in r['source_refs']], 'scope': r['scope'],
            'provenance': {k: r[k] for k in ('run_key', 'run_id', 'run_instance', 'card_id', 'cards_sha256')}
            | {'topic_result': r['artifacts'].get('topic_result'), 'versions': r['versions']},
            'submitted_at': r['submitted_at'], 'submitted_by': r['submitted_by'], 'confirmed_at': view['confirmed_at'],
            'confirmed_by': view['confirmed_by'], 'self_confirmed': view['self_confirmed'],
            'supersedes_feedback_id': r['supersedes_feedback_id']})
    snapshot = {'contract_version': SNAPSHOT_CONTRACT, 'cutoff': cutoff, 'namespaces': sorted(namespaces),
                'note': 'Confirmed reviewer corrections for use as labelled advisory context in later runs. Not project '
                        'policy, not source evidence, not ground truth; scoped to the listed project and threads.',
                'corrections': corrections, 'excluded': excluded,
                'counts': {'corrections': len(corrections), 'excluded': len(excluded)}}
    return {**snapshot, 'snapshot_sha256': content_sha256(snapshot)}


# ---- Evaluation candidates -------------------------------------------------------------------------------------

def evaluation_cases(events, *, namespaces=DEFAULT_NAMESPACES):
    """(confirmed, unconfirmed, excluded): JSONL-ready candidates. Withdrawn and superseded reports are excluded (listed
    with their state). Labels are reviewer assertions to be checked, never ground truth or training data."""
    confirmed, unconfirmed, excluded = [], [], []
    for fid, history in sorted(grouped(events).items()):
        view = fold(history)
        r = view['report']
        if r['namespace'] not in namespaces:
            excluded.append({'feedback_id': fid, 'state': view['state'], 'reason': f"namespace {r['namespace']}"})
            continue
        if view['state'] in ('WITHDRAWN', 'SUPERSEDED'):
            excluded.append({'feedback_id': fid, 'state': view['state'], 'reason': view['state'].lower(),
                             **({'superseded_by': view['superseded_by']} if view['superseded_by'] else {})})
            continue
        case = {
            'case_contract': CASE_CONTRACT, 'case_id': 'evalcand_' + fid[len('feedback_'):],
            'split': 'CONFIRMED' if view['state'] == 'CONFIRMED' else 'UNCONFIRMED', 'feedback_id': fid,
            'category': r['category'], 'problem': r['problem'], 'namespace': r['namespace'],
            'input_refs': {**{k: r[k] for k in ('run_key', 'run_id', 'run_instance', 'run_mode', 'card_id')},
                           'project_id': r['scope']['project_id'], 'batch_id': r['scope']['batch_id'],
                           'candidate_group_id': r['scope']['candidate_group_id'], 'topic_id': r['scope']['topic_id'],
                           'threads': r['scope']['threads'], 'evidence_ids': r['target']['evidence_ids'],
                           'artifacts': r['artifacts'], 'versions': r['versions']},
            'original_output': {'target': r['target'], 'card': r['original_output']},
            'feedback': {'what_is_wrong': r['what_is_wrong'], 'suggested_correction': r['suggested_correction'],
                         'source_refs': r['source_refs']},
            'scope': r['scope'],
            'confirmation': {'status': view['state'], 'confirmed_by': view['confirmed_by'], 'confirmed_at': view['confirmed_at'],
                             'self_confirmed': view['self_confirmed']},
            'future_use': {'requested': r['future_use']['requested'], 'eligible': view['eligible_for_future_runs']},
            'label_status': 'REVIEWER_ASSERTION_NOT_GROUND_TRUTH',
            'intended_use': 'EVALUATION_CANDIDATE_ONLY_NOT_TRAINING',
            'history': [{k: e.get(k) for k in ('event_type', 'recorded_at', 'actor_id', 'note')} for e in history]}
        (confirmed if case['split'] == 'CONFIRMED' else unconfirmed).append(case)
    return confirmed, unconfirmed, excluded
