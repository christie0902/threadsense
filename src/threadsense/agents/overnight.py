"""Milestone 5: the overnight Agent 3 workflow as a LangGraph graph over the existing CrewAI Advisor.

Graph (sequential): load_handoff -> extract_announcements -> prepare_retrieval -> plan_work -> process_topic (once per
work item, looping) -> validate_accounting -> aggregate -> persist. Research, conditional ToT, final grounding and card
routing all stay inside the Advisor (`advisor_pilot.advise`); the graph adds no model call of its own.

- Inputs: the Agent 2 handoff (accounting-validated), the announcement route it carries, and the run window's
  announcements extracted zero-call by the existing ingestion (`source_ingestion`); announcements never go to Agent 1
  interpretation and are checked against the retrieval snapshot by canonical identity. The snapshot is opened and its
  freshness checked once; the run cutoff must equal the snapshot cutoff.
- Work: one item per Agent 2 topic, plus one per projection-gap group (its unassigned members, no taxonomy invented).
  Every discussion member, unassigned member, inherited obligation, announcement-route member and obligation and
  naming caution gets a recorded disposition; counts come from the inputs.
- Failures and budgets: a topic that raises is recorded (members and obligations kept) and the run continues. The
  HTTP request guard, per-topic limits, input-token limit and cost ledger are the Advisor's; the run adds a run-wide
  request ceiling and dollar budget. A topic starts only if two requests (draft and grounding) still fit; otherwise it
  and every later topic are UNPROCESSED_BUDGET. No automatic retries.
- Persistence (run artifacts, not LangGraph checkpoints): the frozen run manifest (cutoff, input/configuration
  fingerprints), completed topic results, and the budget/ledger state after every request. A resumed run reuses
  completed topics without new requests and keeps the spent budget; a topic interrupted mid-run is not resent unless
  the operator releases it explicitly; changed inputs refuse the resume. Nothing here is a knowledge or decision store.
- Output: a morning-brief JSON and readable report built only from validated card content, the Model Review Queue
  (separate from cards), accounting, incomplete work, usage and separate diagnostics.
"""
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
from typing import TypedDict

from threadsense.agents import advisor_pilot as pilot
from threadsense.agents.advice_contracts import AdviceCardV3, ModelReviewItem, stable_id
from threadsense.agents.advice_inputs import (
    accounting_issues, load_effective_view, obligation_keys, review_items_from_announcement_route, review_items_from_view,
)
from threadsense.agents.advisor_evidence import Budget, open_retriever
from threadsense.agents.topic_pipeline import write_json
from threadsense.handoff_inputs import ROOT, file_hash, read_json
from threadsense.retrieval.config import FIXTURE_ROOT
from threadsense.severity_rubric import load_rubric

WORKFLOW_VERSION = 'agent3-overnight-v1'
BRIEF_VERSION = 'agent3-morning-brief-v1'
PER_TOPIC = {'model_calls_per_topic': 4, 'retrieval_calls_per_topic': 6}
REQUESTS_TO_START = 2  # A topic needs at least its draft and its final grounding call.
# What has been validated live, by prompt version (recorded in every manifest).
VALIDATION_BASELINE = {
    'agent3-advisor-prompts-v6': 'LIVE_VALIDATED: data/experiments/agent3_readability_v1 (audio, Submit)',
    'agent3-advisor-prompts-v6.1': 'OFFLINE_ONLY: three deterministic fixes and open_review_flags; first live use is the '
                                   'Milestone 5 smoke test',
    'replay_rule': 'Replay reuses only unchanged judgments; a pending judgment is never counted as grounding PASSED.',
}


class OvernightError(RuntimeError):
    """The run cannot start or resume as specified (incompatible inputs, invalid handoff, accounting failure)."""


class PersistenceError(pilot.RunStateError):
    """The run state could not be saved; the run stops rather than send requests its saved budget does not show."""


def _digest(value):
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode('utf-8')).hexdigest()


def _key(work_id):
    return work_id.replace(':', '__').replace('/', '__')


# ---- Offline semantic stand-in ---------------------------------------------------------------------------------

class HandoffScriptedClient:
    """Offline stand-in for a whole handoff, never a claim about model quality. Topics that are pilot scenarios get the
    prepared pilot judgments (SCRIPTED_PILOT); every other topic gets a fixed placeholder (SCRIPTED_PLACEHOLDER): a
    draft that only cites a member message, proposes nothing and leaves severity unassessed, and a grounding response
    that judges nothing (so nothing reaches a card as established)."""
    label = 'SCRIPTED_MOCK'

    def __init__(self, scripted_path=ROOT/'tests/fixtures/agent3_pilot_scripted_judgments.json', pilot_map=None):
        self.path = Path(scripted_path)
        self.responses = read_json(self.path)['responses']
        self.pilot_map = dict(pilot_map or {})  # work_id -> pilot scenario id
        self.fingerprint = file_hash(self.path)

    def source(self, work_id):
        return 'SCRIPTED_PILOT' if work_id in self.pilot_map else 'SCRIPTED_PLACEHOLDER'

    def complete(self, stage, payload, schema):
        scenario = self.pilot_map.get(payload['scenario_id'])
        if scenario is not None:
            return json.dumps(self.responses[scenario][stage], ensure_ascii=False)
        return json.dumps(placeholder(stage, payload), ensure_ascii=False)


def placeholder(stage, payload):
    note = 'Scripted placeholder: no model judgment was made for this topic.'
    if stage in ('draft', 'revision'):
        first = [i['evidence_id'] for i in payload.get('member_evidence', [])][:1]
        return {'summary': note, 'reasoning': note, 'evidence_sufficiency': 'INSUFFICIENT', 'proposed_action': None,
                'claims': [{'claim_id': 'p1', 'kind': 'INCIDENT_FACT', 'text': 'A member reports a problem in this thread.',
                            'evidence_ids': first}] if first else [],
                'severity': {'level': 'UNKNOWN', 'rationale': note}, 'confidence': 0.0, 'open_confirmation': 'NONE',
                'coverage': [{'need': n, 'status': 'MISSING', 'note': note}
                             for n in ('CURRENT_GUIDANCE', 'ANNOUNCEMENTS', 'PRIOR_DECISIONS', 'MEMBER_QUESTIONS')]}
    if stage == 'tot':
        return {'candidates': [{'candidate_id': c, 'action_type': 'NO_ACTION', 'draft_text': note, 'evidence_ids': [],
                                'evidence_support': 'NONE', 'applicability': 'UNCLEAR', 'severity_fit': 'UNKNOWN',
                                'rationale': note} for c in ('placeholder_a', 'placeholder_b')],
                'preferred_candidate_id': None, 'close_call': True, 'rationale': note}
    return {'verdicts': [], 'action_sufficiency': None, 'alternative_sufficiency': []}  # Nothing judged.


# ---- Persistent budget and ledger ------------------------------------------------------------------------------

class RunState:
    """Budget counters and the cost ledger, saved atomically after every charge, reservation and settlement, so an
    interrupted run resumes with its spent budget. A reservation still open when the run stopped is an uncertain
    request: it is charged in full on resume and never resent automatically."""

    def __init__(self, path, limits, ledger=None):
        self.path, self.limits, self.ledger = Path(path), limits, ledger
        self.budget = _PersistentBudget(limits, self)
        self.uncertain = []
        if self.path.exists():
            saved = read_json(self.path)
            self.budget.used = dict(saved['budget_used'])
            if ledger is not None and saved.get('ledger'):
                ledger.spent_usd, ledger.entries = saved['ledger']['spent_usd'], list(saved['ledger']['requests'])
                open_usd = saved['ledger']['reserved_usd']
                if open_usd > 1e-12:  # Uncertain completion: charge the full reservation, do not resend.
                    ledger.spent_usd += open_usd
                    ledger.entries.append({'label': 'interrupted request', 'reserved_usd': round(open_usd, 6),
                                           'charged_usd': round(open_usd, 6),
                                           'basis': 'uncertain completion (run interrupted): full reservation charged'})
                    self.uncertain.append(open_usd)
        if ledger is not None:
            ledger.on_change = self.save
        self.save()

    def save(self):
        try:
            write_json(self.path, {'budget_limits': self.limits, 'budget_used': self.budget.used,
                                   'ledger': self.ledger.summary() if self.ledger is not None else None})
        except OSError as error:
            raise PersistenceError(f'run state not saved: {type(error).__name__}: {error}') from error

    def requests_left(self):
        return self.limits['model_calls_total'] - self.budget.used.get('model_calls', 0)

    def can_start(self, client):
        """(ok, reason): room for a draft and a final grounding call in requests and dollars."""
        if getattr(client, 'halted', None):
            return False, f'client halted: {type(client.halted).__name__}'
        if self.requests_left() < REQUESTS_TO_START:
            return False, f"run request budget: {self.requests_left()} of {self.limits['model_calls_total']} left"
        ledger = self.ledger
        if ledger is not None:
            per_request = ledger.per_request_usd
            if ledger.spent_usd + ledger.reserved_usd + REQUESTS_TO_START * per_request > ledger.limit_usd + 1e-12:
                return False, f'run cost budget: ${ledger.spent_usd:.4f} spent of ${ledger.limit_usd:.2f}'
        return True, None


class _PersistentBudget(Budget):
    def __init__(self, limits, state):
        super().__init__(limits)
        self._state = state

    def charge(self, kind):
        super().charge(kind)
        if kind == 'model_calls':  # Saved before the request is sent; retrieval counts ride along.
            self._state.save()


class PersistentLedger(pilot.CostLedger):
    """The Advisor's cost ledger, reporting every change so the run state is saved before a request is sent."""

    def __init__(self, limit_usd, per_request_usd):
        super().__init__(limit_usd)
        self.per_request_usd, self.on_change = per_request_usd, None

    def reserve(self, *args, **kwargs):
        value = super().reserve(*args, **kwargs)
        if self.on_change:
            self.on_change()
        return value

    def settle(self, *args, **kwargs):
        value = super().settle(*args, **kwargs)
        if self.on_change:
            self.on_change()
        return value


# ---- Runtime (heavy objects stay outside the graph state) --------------------------------------------------------

class Runtime:
    def __init__(self, out_dir, *, client, cutoff, handoff=pilot.HANDOFF, fixture_root=FIXTURE_ROOT, only=None,
                 max_requests=None, ledger=None, mode='SCRIPTED', retriever_factory=open_retriever, advise=None,
                 release=(), settings=None):
        self.out, self.client, self.cutoff, self.handoff, self.fixture_root = Path(out_dir), client, cutoff, Path(handoff), Path(fixture_root)
        self.only, self.max_requests, self.ledger, self.mode = (list(only) if only else None), max_requests, ledger, mode
        self.retriever_factory, self.advise, self.release = retriever_factory, advise or pilot.advise, set(release)
        self.settings = settings
        self.view = self.retriever = self.rubric = self.state = None
        self.routing = self.extraction = None
        self.work, self.results, self.outcomes = [], {}, {}


class GraphState(TypedDict, total=False):
    cursor: int
    total: int
    stop_reason: str
    stop_outcome: str
    status: str
    counts: dict


# ---- Nodes -----------------------------------------------------------------------------------------------------

def load_handoff(rt):
    view = load_effective_view(rt.handoff)
    issues, members = accounting_issues(view)
    if issues:
        raise OvernightError(f'Agent 2 handoff fails accounting: {issues[:5]}')
    routing_path = rt.handoff/'routing_manifest.json'
    rt.routing = read_json(routing_path) if routing_path.is_file() else {'announcement_sources': []}
    rt.view = view
    return {'counts': {'handoff_members': members}}


def extract_announcements(rt):
    """The run window's announcements through the existing zero-call ingestion (validated, not stored: the knowledge
    store is not written). Discussion threads are only counted here; nothing is sent to Agent 1."""
    from threadsense.source_ingestion import extraction_report, fixture_routes
    discussion, announcements, routing = fixture_routes(rt.fixture_root, cutoff=rt.cutoff)
    report = extraction_report(discussion, announcements, routing, canonical_members=rt.routing['announcement_sources'])
    rt.extraction = {'window': report['window'], 'state': report['state'], 'discussion_threads_in_window': len(discussion),
                     'announcement_threads_in_window': len(announcements), 'validated_records': report['validated_records'],
                     'extraction_failures': report['extraction_failures'], 'record_outcomes': report['record_outcomes'],
                     'agent1_interpretation_calls': 0, 'model_calls': report['model_calls']}
    return {}


def prepare_retrieval(rt):
    rt.retriever = rt.retriever_factory()
    if rt.retriever.manifest['cutoff'] != _iso(rt.cutoff):
        raise OvernightError(f"Run cutoff {rt.cutoff} differs from the retrieval snapshot cutoff "
                             f"{rt.retriever.manifest['cutoff']}; rebuild the snapshot for this window.")
    indexed_docs = {c['document_id'] for c in rt.retriever.chunks.values()}
    indexed_threads = {(c['metadata'].get('channel_id'), c['metadata'].get('thread_id')) for c in rt.retriever.chunks.values()}
    for outcome in rt.extraction['record_outcomes']:
        identity = outcome['identity']
        outcome['in_retrieval_snapshot'] = (outcome.get('document_id') in indexed_docs
                                            or (identity['channel_id'], identity['thread_id']) in indexed_threads)
    rt.rubric = load_rubric(None)
    return {}


def _iso(value):
    from threadsense.routing import aware
    return aware(value).isoformat().replace('+00:00', 'Z')


def plan(view, only=None):
    """Work items from the handoff: every topic, and every projection-gap group's unassigned members. `only` selects
    by work ID, topic ID or pilot scenario ID; the rest are OUT_OF_SCOPE for this run (recorded, not dropped)."""
    pilots = {(s['candidate_group_id'], s.get('topic_name')): s['id'] for s in read_json(pilot.SCENARIOS)['scenarios']
              if not s.get('control')}
    work = []
    for row in view['records']:
        base = {'candidate_group_id': row['candidate_group_id'], 'project_id': row['project_id'], 'batch_id': row.get('batch_id')}
        for t in row['topics']:
            work.append({**base, 'work_id': f"topic:{t['topic_id']}", 'kind': 'TOPIC', 'topic_id': t['topic_id'],
                         'topic_name': t['topic_name'], 'member_ids': list(t['member_ids']),
                         'pilot_scenario': pilots.get((row['candidate_group_id'], t['topic_name']))})
        gap = next((r for r in row['review_reasons'] if r.startswith('Projection gap')), None)
        if row['unassigned_member_ids'] and gap:
            work.append({**base, 'work_id': f"gap:{row['candidate_group_id']}", 'kind': 'PROJECTION_GAP', 'topic_id': None,
                         'topic_name': None, 'member_ids': list(row['unassigned_member_ids']), 'projection_gap': gap,
                         'pilot_scenario': pilots.get((row['candidate_group_id'], None))})
    selected = set(only or [])
    for item in work:
        item['in_scope'] = not selected or bool({item['work_id'], item['topic_id'], item['pilot_scenario']} & selected)
    unknown = selected - {x for item in work for x in (item['work_id'], item['topic_id'], item['pilot_scenario'])}
    if unknown:
        raise OvernightError(f'--only names no work item: {sorted(unknown)}')
    return work


def plan_work(rt):
    rt.work = plan(rt.view, rt.only)
    if isinstance(rt.client, HandoffScriptedClient):
        rt.client.pilot_map = {w['work_id']: w['pilot_scenario'] for w in rt.work if w['pilot_scenario']}
    in_scope = [w for w in rt.work if w['in_scope']]
    limits = {**PER_TOPIC, 'model_calls_total': rt.max_requests or PER_TOPIC['model_calls_per_topic'] * len(in_scope),
              'retrieval_calls_total': PER_TOPIC['retrieval_calls_per_topic'] * len(in_scope)}
    manifest = freeze(rt, limits)
    rt.state = RunState(rt.out/'progress'/'run_state.json', limits, rt.ledger)
    return {'cursor': 0, 'total': len(rt.work), 'counts': {'work_items': len(rt.work), 'in_scope': len(in_scope)},
            'status': 'RESUMED' if manifest['resumed'] else 'STARTED'}


def fingerprints(rt, limits):
    r = rt.retriever
    return {'workflow_version': WORKFLOW_VERSION, 'pilot_version': pilot.PILOT_VERSION, 'prompts': pilot.prompt_fingerprints(),
            'cutoff': _iso(rt.cutoff), 'window': rt.extraction['window'],
            'handoff': {'run': _rel(rt.handoff), 'canonical_sha256': rt.view['canonical_sha256'],
                        'routing_manifest_sha256': file_hash(rt.handoff/'routing_manifest.json')
                        if (rt.handoff/'routing_manifest.json').is_file() else None},
            'announcements_sha256': _digest([o['identity'] | {'document_id': o.get('document_id'), 'version_id': o.get('version_id')}
                                             for o in rt.extraction['record_outcomes']]),
            'index': {k: r.manifest[k] for k in ('build_fingerprint', 'chunking_version', 'corpus_fingerprint', 'cutoff')},
            'rubric': {k: rt.rubric[k] for k in ('version', 'content_sha256')},
            'semantic_client': {'label': rt.client.label, 'fingerprint': getattr(rt.client, 'fingerprint', None),
                                'settings': rt.settings},
            'mode': rt.mode, 'only': rt.only, 'budget_limits': limits,
            'cost_limit_usd': rt.ledger.limit_usd if rt.ledger is not None else None,
            'work_plan_sha256': _digest([{k: w[k] for k in ('work_id', 'member_ids', 'in_scope')} for w in rt.work])}


def _rel(path):
    path = Path(path).resolve()
    return path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path)


def freeze(rt, limits):
    """Write the run manifest once; a resume must match it exactly (no silent reuse of incompatible results)."""
    path = rt.out/'run_manifest.json'
    current = fingerprints(rt, limits)
    if path.exists():
        saved = read_json(path)
        changed = sorted(k for k in current if _digest(current[k]) != _digest(saved['fingerprints'].get(k)))
        if changed:
            raise OvernightError(f'Cannot resume {rt.out}: changed since the run started: {changed}. Start a new run directory.')
        return {**saved, 'resumed': True}
    manifest = {'workflow_version': WORKFLOW_VERSION, 'run_id': stable_id('agent3overnight', current),
                'fingerprints': current, 'validation_baseline': VALIDATION_BASELINE, 'resumed': False}
    write_json(path, manifest, exclusive=True)
    return manifest


def run_id(rt):
    return read_json(rt.out/'run_manifest.json')['run_id']


def process_topic(rt, state):
    """One work item. Reuses a completed result; never resends an interrupted one unless released; stops on budget."""
    item = rt.work[state['cursor']]
    wid, key = item['work_id'], _key(item['work_id'])
    result_path, flight = rt.out/'topics'/f'{key}.json', rt.out/'progress'/'in_flight'/f'{key}.json'
    legacy = rt.out/'topics'/f"{wid.replace(':', '__')}.json"  # Nested path written by the first smoke run.
    if not result_path.exists() and legacy.exists():
        result_path = legacy
    update = {'cursor': state['cursor'] + 1}
    if not item['in_scope']:
        rt.outcomes[wid] = {'outcome': 'OUT_OF_SCOPE', 'detail': 'Not selected for this run (--only).'}
        return update
    if result_path.exists():  # Completed earlier (this run or before an interruption): no new requests.
        saved = read_json(result_path)
        rt.results[wid] = saved
        rt.outcomes[wid] = {**saved['workflow'], 'reused_on_resume': state.get('status') == 'RESUMED'}
        return update
    if flight.exists() and wid not in rt.release:
        rt.outcomes[wid] = {'outcome': 'INTERRUPTED_UNCERTAIN', 'detail': 'Interrupted mid-topic; a request may have been '
                            'sent. Not resent automatically; release it explicitly to process it again.',
                            'in_flight': read_json(flight)}
        return update
    if state.get('stop_reason'):
        rt.outcomes[wid] = {'outcome': state['stop_outcome'], 'detail': state['stop_reason']}
        return update
    ok, reason = rt.state.can_start(rt.client)
    if not ok:
        rt.outcomes[wid] = {'outcome': 'UNPROCESSED_BUDGET', 'detail': reason}
        return {**update, 'stop_reason': reason, 'stop_outcome': 'UNPROCESSED_BUDGET'}
    write_json(flight, {'work_id': wid, 'budget_used_before': dict(rt.state.budget.used)})
    scenario = {'id': wid, 'candidate_group_id': item['candidate_group_id'], 'focus': item['topic_name'] or 'projection gap',
                **({'topic_id': item['topic_id']} if item['topic_id'] else {})}
    try:
        result = rt.advise(scenario, view=rt.view, retriever=rt.retriever, client=rt.client, budget=rt.state.budget,
                           rubric=rt.rubric, run_id=run_id(rt), as_of=rt.retriever.manifest['cutoff'])
        AdviceCardV3.model_validate(result['card'])
        failed = [c for c in result['model_calls'] if c['status'] != 'OK']
        workflow = {'outcome': 'CARD_WITH_STAGE_FAILURES' if failed else 'CARD', 'card_id': result['card']['card_id'],
                    'card_line': result['card']['card_line'], 'grounding': result['grounding']['status'],
                    'stage_failures': [{k: c.get(k) for k in ('stage', 'status', 'failure_class')} for c in failed],
                    'semantic_source': rt.client.source(wid) if hasattr(rt.client, 'source') else rt.client.label}
    except PersistenceError as error:  # The saved budget may be stale: stop rather than continue unrecorded.
        rt.outcomes[wid] = {'outcome': 'TOPIC_FAILED', 'failure_class': 'PERSISTENCE', 'error': str(error),
                            'detail': 'Run state could not be saved; the run stopped. Its in-flight marker is kept.'}
        return {**update, 'stop_reason': f'run state could not be saved: {error}', 'stop_outcome': 'UNPROCESSED_RUN_STOPPED'}
    except pilot.BoundaryNotObserved as error:  # Call accounting unverifiable: stop the run.
        flight.unlink(missing_ok=True)
        rt.outcomes[wid] = {'outcome': 'TOPIC_FAILED', 'failure_class': 'BOUNDARY_NOT_OBSERVED', 'error': str(error)}
        return {**update, 'stop_reason': f'request boundary not observed: {error}', 'stop_outcome': 'UNPROCESSED_RUN_STOPPED'}
    except Exception as error:  # noqa: BLE001 - isolate the topic; record it, never retry.
        result = None
        workflow = {'outcome': 'TOPIC_FAILED', 'failure_class': 'PIPELINE' if not isinstance(error, pilot.ScenarioError)
                    else 'SCENARIO', 'error': f'{type(error).__name__}: {error}'}
    write_json(result_path, {'work_item': item, 'workflow': workflow, **({'result': result} if result else {})})
    flight.unlink(missing_ok=True)
    if result:
        rt.results[wid] = {'work_item': item, 'workflow': workflow, 'result': result}
    rt.outcomes[wid] = workflow
    return update


def validate_accounting(rt):
    """Every member, obligation and caution gets a disposition; counts come from the inputs."""
    view, items = rt.view, {w['work_id']: w for w in rt.work}
    card_of = {wid: r['result']['card'] for wid, r in rt.results.items() if r.get('result')}
    work_of = {m: w['work_id'] for w in rt.work for m in w['member_ids']}
    members, issues = [], []
    for row in view['records']:
        dispositions = {d['member_id']: d['disposition'] for d in row['member_dispositions']}
        for m in row['members']:
            mid, wid = m['member_id'], work_of.get(m['member_id'])
            outcome = rt.outcomes.get(wid, {}) if wid else {'outcome': 'REVIEW_ONLY_NO_TOPIC'}
            card = card_of.get(wid)
            members.append({'member_id': mid, 'candidate_group_id': row['candidate_group_id'], 'project_id': row['project_id'],
                            'agent2_disposition': dispositions[mid], 'work_id': wid, 'outcome': outcome['outcome'],
                            'card_id': card['card_id'] if card else None,
                            'inherited_agent1_obligation': m['agent1_record']['review_required']})
    announcement = [{'member_id': m['member_id'], 'project_id': m['project_id'], 'channel_id': m['channel_id'],
                     'thread_id': m['thread_id'], 'outcome': 'ANNOUNCEMENT_ROUTE (knowledge source; not interpreted)',
                     'inherited_agent1_obligation': m['agent1_record']['review_required']}
                    for m in rt.routing['announcement_sources']]
    queue = review_queue(rt, card_of)
    carried = Counter()
    for item in queue:
        carried[(item['origin'], item['kind'])] += 1
    expected = {'members': sum(len(r['members']) for r in view['records']), 'announcement_route_members': len(announcement)}
    seen = Counter(m['member_id'] for m in members) + Counter(m['member_id'] for m in announcement)
    issues += [f'Member {mid} recorded {n} times.' for mid, n in seen.items() if n != 1]
    if len(members) != expected['members']:
        issues.append(f"{len(members)} discussion members recorded, {expected['members']} in the handoff.")
    missing = obligation_keys(view) - {_obligation_key(i) for i in queue}
    issues += [f'Obligation not in the review queue: {list(k)}' for k in sorted(missing)]
    route_obligations = sum(m['inherited_agent1_obligation'] for m in announcement)
    if carried[('agent1', 'inherited_agent1_review_announcement_route')] != route_obligations:
        issues.append('Announcement-route obligations are not all in the review queue.')
    unprocessed = [w for w in rt.work if rt.outcomes.get(w['work_id'], {}).get('outcome') not in (
        'CARD', 'CARD_WITH_STAGE_FAILURES', 'OUT_OF_SCOPE')]
    out_of_scope = [w for w in rt.work if rt.outcomes[w['work_id']]['outcome'] == 'OUT_OF_SCOPE']
    counts = {
        'discussion_members': len(members), 'members_by_agent2_disposition': dict(Counter(m['agent2_disposition'] for m in members)),
        'members_by_outcome': dict(Counter(m['outcome'] for m in members)),
        'members_on_cards': sum(1 for m in members if m['card_id']),
        'announcement_route_members': len(announcement), 'announcement_route_obligations': route_obligations,
        'inherited_agent1_obligations': sum(m['inherited_agent1_obligation'] for m in members),
        'naming_cautions': sum(len(r.get('content_review_obligations', [])) for r in view['records']),
        'agent2_obligations': sum(len(r.get('agent2_review_obligations', [])) for r in view['records']),
        'projection_gap_groups': sum(1 for w in rt.work if w['kind'] == 'PROJECTION_GAP'),
        'topics': sum(1 for w in rt.work if w['kind'] == 'TOPIC'), 'work_items': len(rt.work),
        'work_by_outcome': dict(Counter(rt.outcomes[w['work_id']]['outcome'] for w in rt.work)),
        'cards': len(card_of), 'cards_by_line': dict(Counter(c['card_line'] for c in card_of.values())),
        'review_queue_items': len(queue), 'review_queue_by_kind': {f'{o}:{k}': n for (o, k), n in sorted(carried.items())},
        'window_announcements': rt.extraction['announcement_threads_in_window'],
        'window_announcements_in_snapshot': sum(o.get('in_retrieval_snapshot', False) for o in rt.extraction['record_outcomes']),
    }
    pending_passed = [c['card_id'] for c in card_of.values() if c['checks']['grounding'] == 'PASSED' and any(
        s['verdict'] == 'PENDING' for s in rt.results[_work_of_card(rt, c)]['result']['grounding']['statements'])]
    issues += [f'Card {c} shows grounding PASSED with pending judgments.' for c in pending_passed]
    rt.accounting = {'status': 'COMPLETE' if not issues else 'FAILED', 'issues': issues, 'counts': counts,
                     'members': members, 'announcement_route': announcement,
                     'incomplete_work': [{**{k: w[k] for k in ('work_id', 'kind', 'candidate_group_id', 'topic_id', 'topic_name',
                                                               'member_ids')},
                                          'obligations': [i['item_id'] for i in queue if set(i['member_ids']) & set(w['member_ids'])],
                                          **rt.outcomes[w['work_id']]} for w in unprocessed],
                     'out_of_scope_work': [{'work_id': w['work_id'], 'kind': w['kind'], 'members': len(w['member_ids'])}
                                           for w in out_of_scope],
                     'projection_gaps': [{'candidate_group_id': w['candidate_group_id'], 'member_ids': w['member_ids'],
                                          'reason': w['projection_gap'], 'outcome': rt.outcomes[w['work_id']]['outcome']}
                                         for w in rt.work if w['kind'] == 'PROJECTION_GAP']}
    rt.queue = queue
    return {'counts': counts, 'status': rt.accounting['status']}


def _work_of_card(rt, card):
    return next(wid for wid, r in rt.results.items() if r.get('result') and r['result']['card']['card_id'] == card['card_id'])


def _obligation_key(item):
    if item['origin'] == 'agent1':
        return ('agent1', item['member_ids'][0])
    if item['origin'] == 'agent2':
        return ('agent2', item['candidate_group_id'], item['kind'])
    return ('content', item['obligation_id'])


def review_queue(rt, card_of):
    """The Model Review Queue: every upstream obligation (handoff and announcement route), linked to the cards that
    carry its members. Kept separate from the operational cards."""
    cards_by_member = {}
    for card in card_of.values():
        for mid in card['lineage']['member_ids']:
            cards_by_member.setdefault(mid, []).append(card['card_id'])
    items = review_items_from_view(rt.view) + review_items_from_announcement_route(rt.routing['announcement_sources'])
    out = []
    for item in items:
        related = sorted({c for mid in item.member_ids for c in cards_by_member.get(mid, [])} | (
            {c['card_id'] for c in card_of.values() if c['lineage']['candidate_group_id'] == item.candidate_group_id}
            if item.origin == 'assisted_content_review' else set()))
        out.append(ModelReviewItem.model_validate({**item.model_dump(mode='json'), 'related_card_ids': related}).model_dump(mode='json'))
    return out


def aggregate(rt):
    """The morning brief from validated card content only (no narrative generation)."""
    cards = [AdviceCardV3.model_validate(r['result']['card']).model_dump(mode='json') for r in rt.results.values() if r.get('result')]
    sources = {r['result']['card']['card_id']: rt.outcomes[wid].get('semantic_source') for wid, r in rt.results.items() if r.get('result')}
    usage = usage_of(rt)
    status = ('ACCOUNTING_FAILED' if rt.accounting['status'] != 'COMPLETE' else
              'INCOMPLETE' if any(w['outcome'] in ('UNPROCESSED_BUDGET', 'UNPROCESSED_RUN_STOPPED', 'INTERRUPTED_UNCERTAIN')
                                  for w in rt.accounting['incomplete_work'])
              else 'COMPLETE_WITH_FAILURES' if any(w['outcome'] == 'TOPIC_FAILED' for w in rt.accounting['incomplete_work'])
              else 'COMPLETE')
    rt.brief = {
        'brief_version': BRIEF_VERSION, 'run_id': run_id(rt), 'status': status, 'cutoff': _iso(rt.cutoff),
        'window': rt.extraction['window'], 'semantic_judgments': rt.client.label,
        'semantic_note': ('Scripted: prepared pilot judgments (SCRIPTED_PILOT) for pilot topics, a placeholder that judges '
                          'nothing (SCRIPTED_PLACEHOLDER) elsewhere; says nothing about model quality.'
                          if rt.client.label == 'SCRIPTED_MOCK' else f'Live model judgments ({rt.client.label}).'),
        'validation_baseline': VALIDATION_BASELINE, 'counts': rt.accounting['counts'],
        'cards': [brief_card(c, sources.get(c['card_id'])) for c in sorted(cards, key=_card_order)],
        'scope': {'only': rt.only, 'work_items_in_scope': sum(w['in_scope'] for w in rt.work), 'work_items': len(rt.work),
                  'out_of_scope_work': rt.accounting['out_of_scope_work']},
        'model_review_queue': rt.queue, 'incomplete_work': rt.accounting['incomplete_work'],
        'projection_gaps': rt.accounting['projection_gaps'],
        'announcements_in_window': [{**o['identity'], 'document_id': o.get('document_id'), 'version_id': o.get('version_id'),
                                     'in_retrieval_snapshot': o.get('in_retrieval_snapshot')}
                                    for o in rt.extraction['record_outcomes']],
        'announcement_extraction': {k: rt.extraction[k] for k in ('state', 'validated_records', 'extraction_failures',
                                                                  'agent1_interpretation_calls', 'model_calls')},
        'usage': usage, 'accounting': {k: rt.accounting[k] for k in ('status', 'issues')}}
    return {'status': status}


def _card_order(card):
    severity = {'HIGH': 0, 'MEDIUM': 1, 'LOW': 2}.get(card['severity']['level'], 3)
    return ({'RECOMMENDED_ACTION': 0, 'NEEDS_REVIEW': 1, 'OBSERVATION': 2}[card['card_line']], severity, card['topic_name'])


def brief_card(card, semantic_source):
    """A card as the team lead reads it, with references; diagnostics are not included here."""
    action = card['recommended_action']
    return {'card_id': card['card_id'], 'project_id': card['project_id'], 'topic_name': card['topic_name'],
            'card_line': card['card_line'], 'semantic_source': semantic_source,
            'severity': {'level': card['severity']['level'], 'status': card['severity']['assessment_status']},
            'resolution_status': card['resolution_status'], 'summary': card['summary'],
            'recommended_action': {k: action[k] for k in ('label', 'instruction', 'rationale', 'draft_text', 'scope_note',
                                                          'targets', 'source')} if action else None,
            'review_notes': card['review_notes'], 'reasoning': card['reasoning'],
            'related_threads': [{k: t[k] for k in ('label', 'display_reference', 'permalink', 'channel_id', 'thread_id', 'member_id')}
                                for t in card['related_threads']],
            'sources': [s for s in card['supporting_sources'] if s['kind'] == 'knowledge_source'],
            'confidence_band': card['confidence_band'], 'lineage': card['lineage']}


def usage_of(rt):
    rows, total = [], Counter()
    for wid, r in rt.results.items():
        if not r.get('result'):
            continue
        row = Counter()
        for call in r['result']['model_calls']:
            stats = call.get('http_requests') or {}
            row['requests_sent'] += stats.get('sent', 0)
            row['requests_blocked'] += stats.get('blocked', 0)
            row['charged_usd'] += stats.get('charged_usd') or 0
            for resp in stats.get('responses') or []:
                u = resp.get('usage') or {}
                row['input_tokens'] += u.get('prompt_tokens', 0)
                row['output_tokens'] += u.get('completion_tokens', 0)
                row['reasoning_tokens'] += (u.get('completion_tokens_details') or {}).get('reasoning_tokens') or 0
            row['model_calls'] += call['status'] == 'OK' or call['status'] == 'FAILED'
        failures = Counter(c.get('failure_class') for c in r['result']['model_calls'] if c['status'] == 'FAILED')
        rows.append({'work_id': wid, **row, 'failures_by_class': dict(failures)})
        total.update(row)
        total.update({f'failures_{k}': n for k, n in failures.items()})
    return {'totals': dict(total), 'per_work_item': rows, 'run_budget': read_json(rt.out/'progress'/'run_state.json'),
            'uncertain_requests_charged': len(rt.state.uncertain)}


def persist(rt):
    write_json(rt.out/'morning_brief.json', rt.brief)
    (rt.out/'morning_brief.md').write_text(report(rt.brief), encoding='utf-8')
    write_json(rt.out/'accounting.json', rt.accounting)
    write_json(rt.out/'review_queue.json', rt.queue)
    write_json(rt.out/'cards.json', [r['result']['card'] for r in rt.results.values() if r.get('result')])
    write_json(rt.out/'diagnostics.json', {wid: {'diagnostics': r['result']['diagnostics'],
                                                 'structural_issues': r['result']['grounding']['structural_issues'],
                                                 'failures': [c for c in r['result']['model_calls'] if c['status'] != 'OK'],
                                                 'coverage_issues': r['result']['coverage_issues'],
                                                 'action_notes': r['result']['action_notes']}
                                           for wid, r in rt.results.items() if r.get('result')}
               | {wid: o for wid, o in rt.outcomes.items() if o['outcome'] == 'TOPIC_FAILED'})
    (rt.out/'graph.mmd').write_text(build_graph(rt).get_graph().draw_mermaid(), encoding='utf-8')
    return {}


def report(brief):
    """Readable morning brief from the validated card fields; nothing is generated here."""
    c = brief['counts']
    lines = [f"# Morning brief - {brief['cutoff']}", '',
             f"Status: **{brief['status']}**. Semantic judgments: {brief['semantic_judgments']}. {brief['semantic_note']}", '',
             f"Window {brief['window']['start']} to {brief['window']['cutoff']}: {c['window_announcements']} announcements "
             f"({c['window_announcements_in_snapshot']} in the retrieval snapshot).", '',
             f"{c['cards']} cards ({', '.join(f'{k} {v}' for k, v in sorted(c['cards_by_line'].items())) or 'none'}); "
             f"{c['review_queue_items']} Model Review Queue items; {c['discussion_members']} discussion members "
             f"({c['members_on_cards']} on cards); {c['announcement_route_members']} announcement-route members.", '']
    scope = brief['scope']
    if scope['only']:
        lines += [f"Scoped run: {scope['work_items_in_scope']} of {scope['work_items']} work items "
                  f"({len(scope['out_of_scope_work'])} out of scope; their members and review items are still accounted for).", '']
    if brief['incomplete_work']:
        lines += ['## Incomplete work', '']
        lines += [f"- {w['topic_name'] or w['work_id']} ({w['kind']}): **{w['outcome']}** - {w.get('detail') or w.get('error') or ''} "
                  f"({len(w['member_ids'])} members, {len(w['obligations'])} review items kept)" for w in brief['incomplete_work']]
        lines.append('')
    for card in brief['cards']:
        action = card['recommended_action']
        lines += [f"## {card['topic_name']}", '',
                  f"{card['card_line'].replace('_', ' ').title()} - severity {card['severity']['level'].lower()} "
                  f"({card['severity']['status'].lower()}), {card['resolution_status'].replace('_', ' ').lower()}"
                  + (f" - {card['semantic_source']}" if card['semantic_source'] != 'LIVE_MODEL' else ''), '',
                  f"**What happened.** {card['summary']}", '']
        if action:
            lines += [f"**What to do: {action['label']}.**" + (f" {action['instruction']}" if action['instruction'] else ''), '']
            if action['rationale']:
                lines += [f"**Why.** {action['rationale']}", '']
            if action['draft_text']:
                lines += ['**Draft to copy:**', '', *[f'> {line}' for line in action['draft_text'].splitlines()], '']
        if card['review_notes']:
            lines += ['**Still needs review:**', *[f'- {n}' for n in card['review_notes']], '']
        lines += ['Threads: ' + '; '.join(f"{t['label']} ({t['display_reference']})" for t in card['related_threads']), '']
        if card['sources']:
            lines += ['Sources: ' + '; '.join(f"{s['authoring_document_id'] or s['document_id']}"
                                              f"{'@' + s['authoring_version'] if s['authoring_version'] else ''}"
                                              f"{' (' + s['section'] + ')' if s['section'] else ''}" for s in card['sources']), '']
    lines += ['## Model Review Queue', '', f"{len(brief['model_review_queue'])} items (separate from the cards above):", '']
    kinds = Counter(f"{i['origin']} {i['kind']}" for i in brief['model_review_queue'])
    lines += [f'- {k}: {n}' for k, n in sorted(kinds.items())]
    u = brief['usage']['totals']
    lines += ['', '## Usage', '', f"Requests sent {u.get('requests_sent', 0)}, blocked {u.get('requests_blocked', 0)}; input "
              f"{u.get('input_tokens', 0)}, output {u.get('output_tokens', 0)} tokens; charged ${u.get('charged_usd', 0):.4f}.", '']
    return '\n'.join(lines) + '\n'


# ---- Graph -----------------------------------------------------------------------------------------------------

def build_graph(rt):
    from langgraph.graph import END, START, StateGraph
    graph = StateGraph(GraphState)
    for name, fn in (('load_handoff', load_handoff), ('extract_announcements', extract_announcements),
                     ('prepare_retrieval', prepare_retrieval), ('plan_work', plan_work),
                     ('validate_accounting', validate_accounting), ('aggregate', aggregate), ('persist', persist)):
        graph.add_node(name, lambda state, fn=fn: fn(rt))
    graph.add_node('process_topic', lambda state: process_topic(rt, state))
    graph.add_edge(START, 'load_handoff')
    for a, b in (('load_handoff', 'extract_announcements'), ('extract_announcements', 'prepare_retrieval'),
                 ('prepare_retrieval', 'plan_work'), ('validate_accounting', 'aggregate'), ('aggregate', 'persist')):
        graph.add_edge(a, b)
    graph.add_edge('persist', END)
    more = lambda state: 'process_topic' if state['cursor'] < state['total'] else 'validate_accounting'  # noqa: E731
    graph.add_conditional_edges('plan_work', more, ['process_topic', 'validate_accounting'])
    graph.add_conditional_edges('process_topic', more, ['process_topic', 'validate_accounting'])
    return graph.compile()


def run(rt):
    """Run (or resume) the workflow into rt.out. Returns the final graph state."""
    rt.out.mkdir(parents=True, exist_ok=True)
    try:
        return build_graph(rt).invoke({}, config={'recursion_limit': 10_000})
    finally:  # Close only a snapshot this run opened (always close Chroma clients created in-process).
        if rt.retriever_factory is open_retriever and rt.retriever is not None and getattr(rt.retriever, 'client', None) is not None:
            try:
                rt.retriever.client.close()
            except Exception:  # noqa: BLE001 - closing is best effort
                pass
