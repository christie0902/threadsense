"""Lessons from human review: short reviewer guidance for Agents 1 and 2, saved with a Model Review Queue rejection.

A team lead rejecting an Agent 1 interpretation or an Agent 2 grouping may write a lesson (at most 400 characters, no
LLM involved). It is saved in the same transaction as the rejection (the existing review-action request carries an
optional `lesson`); a rejection without a lesson is unchanged. Contracts: LessonRecord (dashboard-review-lesson-v1)
inside append-only events (dashboard-review-lesson-event-v1, table `lesson_events`, store migration 2).

Lifecycle: ACTIVE <-> INACTIVE (deactivate / reactivate); ACTIVE or INACTIVE -> SUPERSEDED when the team lead saves an
edited version, which is a new lesson naming the one it replaces (both events in one transaction). Earlier events are
never changed; each lesson keeps its originating run, review item and review action.

Scope: the lesson's project by default (PROJECT); every project only when ALL_PROJECTS is chosen explicitly. Later
Agent 1/2 runs read a snapshot of the lessons active at its cutoff (build_snapshot; agents/review_lessons selects).
A lesson is guidance only: it is not project policy or evidence, and it clears no review obligation (the item's own
state is the review action's, as before).
"""
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from threadsense.agents.advice_contracts import stable_id
from threadsense.agents.review_lessons import AGENTS, CATEGORIES, MAX_LESSON_CHARS, SNAPSHOT_CONTRACT
from threadsense.agents.reviewer_context import content_sha256
from threadsense.dashboard.decisions import ORIGIN_NAMESPACES, DecisionError
from threadsense.routing import aware

LESSON_CONTRACT = 'dashboard-review-lesson-v1'
EVENT_CONTRACT = 'dashboard-review-lesson-event-v1'
# Which agent a review item's origin points to by default (the team lead may choose the other one).
ORIGIN_AGENT = {'agent1': 'AGENT_1', 'agent2': 'AGENT_2', 'assisted_content_review': 'AGENT_2'}
State = Literal['ACTIVE', 'INACTIVE', 'SUPERSEDED']
TRANSITIONS = {'ACTIVE': {'DEACTIVATE': 'INACTIVE'}, 'INACTIVE': {'REACTIVATE': 'ACTIVE'}}
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Frozen(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)


class LessonInput(Strict):
    """The optional lesson on a rejection, or the new version when superseding."""
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=12, max_length=MAX_LESSON_CHARS)]
    applies_to: Literal['PROJECT', 'ALL_PROJECTS'] = 'PROJECT'
    category: str = 'GENERAL'
    target_agent: Literal['AGENT_1', 'AGENT_2'] | None = None  # None: from the review item's origin

    @field_validator('text')
    @classmethod
    def plain(cls, value):
        if '{' in value or '}' in value:  # Kept out of request templates; a lesson is plain guidance.
            raise ValueError('A lesson cannot contain curly braces.')
        return value


class SupersedeRequest(Strict):
    actor_id: Text
    expected_head: str | None = None  # Head event of the lesson being replaced.
    lesson: LessonInput


class LessonActionRequest(Strict):
    action: Literal['DEACTIVATE', 'REACTIVATE']
    actor_id: Text
    expected_head: str | None = None
    note: Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] | None = None


class LessonRecord(Frozen):
    contract_version: Literal['dashboard-review-lesson-v1'] = LESSON_CONTRACT
    lesson_id: Annotated[str, StringConstraints(pattern=r'^lesson_[0-9a-f]{32}$')]
    namespace: Literal['operational', 'demo', 'test']
    target_agent: Literal['AGENT_1', 'AGENT_2']
    applies_to: Literal['PROJECT', 'ALL_PROJECTS']
    project_id: Text                      # The originating project (the scope when applies_to is PROJECT).
    category: Text
    text: Text
    origin: dict                          # run_key, run_id, run_instance, item_id, item_kind, item_origin, review_entry_id
    supersedes_lesson_id: str | None = None
    saved_at: Text
    saved_by: Text
    saved_by_role: Literal['TEAM_LEAD']
    lesson_is_guidance_not_policy: Literal[True] = True
    lesson_is_not_evidence: Literal[True] = True
    lesson_clears_no_review_obligation: Literal[True] = True

    @model_validator(mode='after')
    def consistent(self):
        aware(self.saved_at)
        if self.category not in CATEGORIES[self.target_agent]:
            raise ValueError(f'{self.category} is not a category for {self.target_agent} '
                             f'(allowed: {", ".join(CATEGORIES[self.target_agent])}).')
        return self


class LessonEvent(Frozen):
    contract_version: Literal['dashboard-review-lesson-event-v1'] = EVENT_CONTRACT
    entry_id: Annotated[str, StringConstraints(pattern=r'^lessonevent_[0-9a-f]{32}$')]
    lesson_id: Annotated[str, StringConstraints(pattern=r'^lesson_[0-9a-f]{32}$')]
    sequence: int = Field(ge=1)
    supersedes_entry_id: str | None = None
    run_key: Text                          # The originating run reference (key#instance).
    namespace: Literal['operational', 'demo', 'test']
    event_type: Literal['SAVED', 'DEACTIVATED', 'REACTIVATED', 'SUPERSEDED']
    state_after: State
    recorded_at: Text
    actor_id: Text
    actor_role: Literal['TEAM_LEAD']
    note: str | None = None
    lesson: LessonRecord | None = None     # Only on SAVED.
    superseded_by_lesson_id: str | None = None
    idempotency_key: str | None = None
    request_sha256: str | None = None

    @model_validator(mode='after')
    def consistent(self):
        aware(self.recorded_at)
        if (self.event_type == 'SAVED') != (self.lesson is not None) or (self.sequence == 1) != (self.event_type == 'SAVED'):
            raise ValueError('Only the first event saves the lesson.')
        if (self.event_type == 'SUPERSEDED') != (self.superseded_by_lesson_id is not None):
            raise ValueError('A superseded event names the lesson that replaces it.')
        expected = {'SAVED': 'ACTIVE', 'DEACTIVATED': 'INACTIVE', 'REACTIVATED': 'ACTIVE', 'SUPERSEDED': 'SUPERSEDED'}
        if self.state_after != expected[self.event_type]:
            raise ValueError('The state does not follow from the event.')
        return self


def lesson_id_for(run_ref, item_id, key):
    return stable_id('lesson', {'run_ref': run_ref, 'item_id': item_id, 'idempotency_key': key})


def new_lesson(*, lesson, actor, recorded_at, namespace, project_id, origin, default_agent, lesson_id, run_key, key,
               request_sha, supersedes=None):
    """The SAVED event of a new lesson (on a rejection, or as the edited version of an earlier lesson)."""
    agent = lesson.target_agent or default_agent
    if agent not in AGENTS:
        raise DecisionError('Lessons are for Agent 1 interpretations and Agent 2 groupings; choose the target agent.')
    try:
        record = LessonRecord(lesson_id=lesson_id, namespace=namespace, target_agent=agent, applies_to=lesson.applies_to,
                              project_id=project_id, category=lesson.category, text=lesson.text, origin=origin,
                              supersedes_lesson_id=supersedes, saved_at=recorded_at, saved_by=actor['actor_id'],
                              saved_by_role=actor['role'])
    except ValueError as error:
        raise DecisionError(str(error)) from None
    return LessonEvent(entry_id=stable_id('lessonevent', {'lesson_id': lesson_id, 'sequence': 1}), lesson_id=lesson_id,
                       sequence=1, run_key=run_key, namespace=namespace, event_type='SAVED', state_after='ACTIVE',
                       recorded_at=recorded_at, actor_id=actor['actor_id'], actor_role=actor['role'], lesson=record,
                       idempotency_key=key, request_sha256=request_sha).model_dump(mode='json')


def from_rejection(*, run, item, review_entry, lesson, actors, key, request_sha):
    """The lesson saved with a REJECT review action (called inside its transaction)."""
    if review_entry['action']['action'] != 'REJECT':
        raise DecisionError('A lesson is saved only with a rejection.')
    if item.origin not in ORIGIN_AGENT and lesson.target_agent is None:
        raise DecisionError('Lessons are for Agent 1 and Agent 2 review items.')
    actor = actors[review_entry['action']['actor_id']]
    origin = {'run_key': run.key, 'run_id': run.brief['run_id'], 'run_instance': run.instance, 'item_id': item.item_id,
              'item_kind': item.kind, 'item_origin': item.origin, 'item_reason': item.reason,
              'review_entry_id': review_entry['entry_id']}
    return new_lesson(lesson=lesson, actor=actor, recorded_at=review_entry['action']['acted_at'], namespace=review_entry['namespace'],
                      project_id=item.project_id, origin=origin, default_agent=ORIGIN_AGENT.get(item.origin),
                      lesson_id=lesson_id_for(run.ref, item.item_id, key), run_key=run.ref, key=key, request_sha=request_sha)


def action_event(*, head, request, actors, sequence, recorded_at, key, request_sha):
    actor = actors.get(request.actor_id)
    if actor is None:
        raise DecisionError(f'{request.actor_id} is not a recorded team lead.')
    after = TRANSITIONS.get(head['state_after'], {}).get(request.action)
    if after is None:
        raise DecisionError(f"A {head['state_after'].lower()} lesson cannot be {request.action.lower()}d.")
    return LessonEvent(
        entry_id=stable_id('lessonevent', {'lesson_id': head['lesson_id'], 'sequence': sequence, 'idempotency_key': key}),
        lesson_id=head['lesson_id'], sequence=sequence, supersedes_entry_id=head['entry_id'], run_key=head['run_key'],
        namespace=head['namespace'], event_type={'INACTIVE': 'DEACTIVATED', 'ACTIVE': 'REACTIVATED'}[after], state_after=after,
        recorded_at=recorded_at, actor_id=actor['actor_id'], actor_role=actor['role'], note=request.note or None,
        idempotency_key=key, request_sha256=request_sha)


def superseding(*, earlier, request, actors, recorded_at, key, request_sha, new_id):
    """(new lesson's SAVED event, the earlier lesson's SUPERSEDED event); the caller checks the earlier head."""
    actor = actors.get(request.actor_id)
    if actor is None:
        raise DecisionError(f'{request.actor_id} is not a recorded team lead.')
    head, record = earlier[-1], earlier[0]['lesson']
    if head['state_after'] == 'SUPERSEDED':
        raise DecisionError('This lesson was already replaced by a newer version.')
    saved = new_lesson(lesson=request.lesson.model_copy(update={'target_agent': request.lesson.target_agent or record['target_agent']}),
                       actor=actor, recorded_at=recorded_at, namespace=record['namespace'], project_id=record['project_id'],
                       origin=record['origin'], default_agent=record['target_agent'], lesson_id=new_id, run_key=head['run_key'],
                       key=key, request_sha=request_sha, supersedes=record['lesson_id'])
    old = LessonEvent(
        entry_id=stable_id('lessonevent', {'lesson_id': record['lesson_id'], 'sequence': head['sequence'] + 1, 'by': new_id}),
        lesson_id=record['lesson_id'], sequence=head['sequence'] + 1, supersedes_entry_id=head['entry_id'],
        run_key=head['run_key'], namespace=head['namespace'], event_type='SUPERSEDED', state_after='SUPERSEDED',
        recorded_at=recorded_at, actor_id=actor['actor_id'], actor_role=actor['role'], superseded_by_lesson_id=new_id,
        note=f'Replaced by an edited version ({new_id}).').model_dump(mode='json')
    return saved, old


def fold(events, cutoff=None):
    if cutoff is not None:
        events = [e for e in events if aware(e['recorded_at']) <= aware(cutoff)]
    if not events:
        return None
    head = events[-1]
    return {'lesson_id': head['lesson_id'], 'state': head['state_after'], 'lesson': events[0]['lesson'], 'head': head,
            'events': events, 'superseded_by': head.get('superseded_by_lesson_id')}


def grouped(events):
    out = {}
    for e in events:
        out.setdefault(e['lesson_id'], []).append(e)
    return {k: sorted(v, key=lambda e: e['sequence']) for k, v in out.items()}


def views(events):
    return sorted((fold(h) for h in grouped(events).values()), key=lambda v: v['lesson']['saved_at'], reverse=True)


def build_snapshot(events, *, cutoff, namespaces=('operational',)):
    """review-lessons-snapshot-v1: the lessons ACTIVE at cutoff in the chosen namespaces. Deterministic."""
    unknown = set(namespaces) - {'operational', 'demo', 'test'}
    if unknown:
        raise ValueError(f'Unknown lesson namespaces: {sorted(unknown)}.')
    aware(cutoff)
    lessons, excluded = [], []
    for lid, history in sorted(grouped(events).items()):
        view = fold(history, cutoff)
        if view is None:
            continue
        l = view['lesson']
        reasons = ([] if l['namespace'] in namespaces else [f"namespace {l['namespace']} not included"]) + (
            [] if view['state'] == 'ACTIVE' else [view['state'].lower()])
        if reasons:
            excluded.append({'lesson_id': lid, 'state_at_cutoff': view['state'], 'reasons': reasons})
            continue
        lessons.append({k: l[k] for k in ('lesson_id', 'target_agent', 'applies_to', 'project_id', 'category', 'text',
                                          'saved_at', 'saved_by', 'supersedes_lesson_id', 'namespace')}
                       | {'origin': {k: l['origin'][k] for k in ('run_key', 'run_instance', 'item_id', 'item_kind', 'review_entry_id')}})
    snapshot = {'contract_version': SNAPSHOT_CONTRACT, 'cutoff': cutoff, 'namespaces': sorted(namespaces),
                'note': 'Active lessons from human review for Agents 1 and 2: reviewer guidance, not policy or evidence.',
                'lessons': lessons, 'excluded': excluded}
    return {**snapshot, 'snapshot_sha256': content_sha256(snapshot)}
