"""TL decisions and model-review actions: one durable, authoritative store, separate from the immutable cards.

Store: one SQLite file (stdlib sqlite3, WAL, synchronous=FULL). Rows are append-only: a later decision on the same
card supersedes the earlier one by sequence and both stay in the history. Only the separate indexing-status table
is updated in place, so a failed or repeated indexing never touches a saved decision.

Contracts (persistence extension, documented in docs/agent3-plan.md, Milestone 6):
- TLDecisionEntry (dashboard-tl-decision-v1) wraps the unchanged DecisionRecord v1 with what that record has no
  field for: run and card binding (run directory, run_id, cards.json hash), the structured resolution kind, the
  TL-edited vs model-grounded text, the TL note, the request key and the superseded entry.
- ModelReviewEntry (dashboard-model-review-action-v1) wraps one ReviewAction for one ModelReviewItem of one run.
  ACCEPT resolves the flag for that run, REJECT records a negative example, DEFER keeps it open. Neither touches a card.

Every write carries a client idempotency key. The same key with the same request returns the stored result (no
second row); the same key with a different request is refused; a request whose expected head is not the current
head is a conflict. The result is returned only after the transaction commits.
"""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from threadsense.agents.advice_contracts import (
    ACTION_LABELS, DecisionRecord, ModelReviewItem, ReviewAction, SeverityLevel, record_review_action, stable_id,
)
from threadsense.routing import ROOT, aware

STORE_PATH = ROOT/'.state/dashboard/tl_decisions.sqlite3'
DECISION_CONTRACT = 'dashboard-tl-decision-v1'
REVIEW_CONTRACT = 'dashboard-model-review-action-v1'
DecisionKind = Literal['APPROVE_ACTION', 'CONFIRM_FAQ_UPDATE', 'CONFIRM_ANNOUNCEMENT', 'OVERRIDE_SEVERITY', 'DISMISS',
                       'ROUTE_TO_EXPERT']
KINDS_BY_LINE = {'RECOMMENDED_ACTION': ('APPROVE_ACTION',),
                 'NEEDS_REVIEW': ('CONFIRM_FAQ_UPDATE', 'CONFIRM_ANNOUNCEMENT', 'OVERRIDE_SEVERITY', 'DISMISS', 'ROUTE_TO_EXPERT'),
                 'OBSERVATION': ()}
EXPERTS = {'ENGINEERING': 'ESCALATE_ENGINEERING', 'LANGUAGE_SPECIALIST': 'ROUTE_TO_LANGUAGE_SPECIALIST'}
# Action type each structured resolution approves; the card's draft is reused only when its type matches.
KIND_ACTIONS = {'CONFIRM_FAQ_UPDATE': 'UPDATE_FAQ', 'CONFIRM_ANNOUNCEMENT': 'POST_ALIGNMENT'}
EFFECTS = {'ACCEPT': 'RESOLVED_FOR_RUN', 'REJECT': 'NEGATIVE_EXAMPLE', 'DEFER': 'KEPT_OPEN'}
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class DecisionError(ValueError):
    """The request cannot become a valid decision (HTTP 422)."""


class StaleHead(Exception):
    """The TL acted on an older state of this card or review item (HTTP 409)."""

    def __init__(self, current):
        super().__init__('Another decision was saved since this one was prepared.')
        self.current = current


class KeyReused(Exception):
    """An idempotency key was reused for a different request (HTTP 422); the first result is unchanged."""

    def __init__(self, original):
        super().__init__('This request key was already used for a different request.')
        self.original = original


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Frozen(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)


class DecisionRequest(Strict):
    kind: DecisionKind
    actor_id: Text
    expected_head: str | None = None  # entry_id of the latest decision the TL saw on this card; None if none.
    text: str | None = None           # Text the TL approves; None keeps the card's draft unchanged.
    note: str | None = None
    severity: SeverityLevel | None = None
    expert: Literal['ENGINEERING', 'LANGUAGE_SPECIALIST'] | None = None
    alternative_id: str | None = None  # Start from a supported ToT alternative instead of the card's own draft.


class ReviewRequest(Strict):
    action: Literal['ACCEPT', 'REJECT', 'DEFER']
    actor_id: Text
    expected_head: str | None = None
    note: str | None = None


class TextProvenance(Frozen):
    """MODEL_GROUNDED: the card's validated draft, unchanged. TL_EDITED: the TL changed that draft.
    TL_WRITTEN: the TL wrote text the card did not propose. NONE: the decision carries no text.
    grounded_source names where model-grounded text came from: the card's draft or a supported ToT alternative."""
    origin: Literal['MODEL_GROUNDED', 'TL_EDITED', 'TL_WRITTEN', 'NONE']
    model_grounded_text: str | None = None
    grounded_source: Literal['CARD_DRAFT', 'SUPPORTED_ALTERNATIVE'] | None = None
    alternative_id: str | None = None
    tl_text: str | None = None

    @model_validator(mode='after')
    def consistent(self):
        if self.origin == 'MODEL_GROUNDED' and (not self.model_grounded_text or self.tl_text is not None):
            raise ValueError('Model-grounded text is the card draft, with no TL text.')
        if self.origin in ('TL_EDITED', 'TL_WRITTEN') and not (self.tl_text or '').strip():
            raise ValueError('TL-edited or TL-written text is required.')
        if self.origin == 'TL_EDITED' and (not self.model_grounded_text or self.tl_text == self.model_grounded_text):
            raise ValueError('An edit changes an existing card draft.')
        if self.origin == 'NONE' and self.tl_text is not None:
            raise ValueError('A decision without text has no TL text.')
        return self


class TLDecisionEntry(Frozen):
    contract_version: Literal['dashboard-tl-decision-v1'] = DECISION_CONTRACT
    entry_id: Annotated[str, StringConstraints(pattern=r'^decision_[0-9a-f]{32}$')]
    sequence: int = Field(ge=1)
    supersedes_entry_id: str | None = None
    run_key: Text
    run_id: Text
    run_mode: Literal['LIVE', 'SCRIPTED', 'TEST_FIXTURE', 'UNKNOWN']
    cards_sha256: Text
    card_id: Text
    card_line: Literal['RECOMMENDED_ACTION', 'NEEDS_REVIEW', 'OBSERVATION']
    topic_name: Text
    project_id: Text
    batch_id: str | None = None
    kind: DecisionKind
    recorded_at: Text
    actor_id: Text
    actor_role: Literal['TEAM_LEAD']
    text: TextProvenance
    note: str | None = None
    expert: Literal['ENGINEERING', 'LANGUAGE_SPECIALIST'] | None = None
    decision: DecisionRecord
    idempotency_key: Text
    request_sha256: Text
    # Fixed statements: approval is not execution; a disposition is not evidence the issue is resolved; an
    # override is this TL's decision for this card, not a rubric change.
    approval_is_not_execution: Literal[True] = True
    disposition_is_not_resolution_evidence: Literal[True] = True
    severity_override_is_not_rubric_change: Literal[True] = True

    @model_validator(mode='after')
    def consistent(self):
        aware(self.recorded_at)
        d = self.decision
        if d.decision_id != self.entry_id or d.project_id != self.project_id:
            raise ValueError('Entry and DecisionRecord disagree.')
        if d.execution.state != 'NOT_EXECUTED' or d.outcome.state != 'NOT_OBSERVED':
            raise ValueError('A dashboard decision records no execution and no observed outcome.')
        if (self.sequence == 1) != (self.supersedes_entry_id is None):
            raise ValueError('Only the first decision on a card supersedes nothing.')
        if self.kind not in KINDS_BY_LINE[self.card_line]:
            raise ValueError(f'{self.kind} does not apply to a {self.card_line} card.')
        return self


class ModelReviewEntry(Frozen):
    contract_version: Literal['dashboard-model-review-action-v1'] = REVIEW_CONTRACT
    entry_id: Annotated[str, StringConstraints(pattern=r'^reviewaction_[0-9a-f]{32}$')]
    sequence: int = Field(ge=1)
    supersedes_entry_id: str | None = None
    run_key: Text
    run_id: Text
    item_id: Text
    project_id: Text
    action: ReviewAction
    effect: Literal['RESOLVED_FOR_RUN', 'NEGATIVE_EXAMPLE', 'KEPT_OPEN']
    related_card_ids: list[str] = Field(default_factory=list)  # Listed for context; never modified.
    idempotency_key: Text
    request_sha256: Text
    cards_untouched: Literal[True] = True

    @model_validator(mode='after')
    def consistent(self):
        if self.effect != EFFECTS[self.action.action]:
            raise ValueError('Review effect disagrees with the action.')
        return self


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def request_hash(target, body):
    data = json.dumps({'target': target, 'body': body}, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
    return sha256(data.encode('utf-8')).hexdigest()


def build_decision(*, run, card, request, actors, sequence, head, recorded_at, key, request_sha, alternatives=()):
    """DecisionRecord + entry for one TL request on one card; refuses anything the card or contract does not allow."""
    if request.kind not in KINDS_BY_LINE[card['card_line']]:
        allowed = ', '.join(KINDS_BY_LINE[card['card_line']]) or 'none'
        raise DecisionError(f"{request.kind} does not apply to a {card['card_line']} card (allowed: {allowed}).")
    actor = actors.get(request.actor_id)
    if actor is None:
        raise DecisionError(f'{request.actor_id} is not a recorded team lead.')
    action, source = card.get('recommended_action') or {}, 'CARD_DRAFT'
    if request.alternative_id is not None:
        if request.kind in ('APPROVE_ACTION', 'DISMISS', 'OVERRIDE_SEVERITY'):
            raise DecisionError(f'{request.kind} applies to the card itself, not to an alternative.')
        chosen = [a for a in alternatives if a['candidate_id'] == request.alternative_id]
        if not chosen:
            raise DecisionError(f'{request.alternative_id} is not a supported alternative on this card.')
        action, source = chosen[0], 'SUPPORTED_ALTERNATIVE'
    draft, level = action.get('draft_text'), card['severity']['level']
    edited = request.text if request.text is not None and request.text.strip() else None
    note = (request.note or '').strip() or None
    override = approved = None
    if request.kind == 'APPROVE_ACTION':
        approved = [action['action_type']]
        reuse = draft
    elif request.kind in KIND_ACTIONS:
        approved = [KIND_ACTIONS[request.kind]]
        reuse = draft if action.get('action_type') == approved[0] else None
        if request.alternative_id is not None and reuse is None:
            raise DecisionError('That alternative proposes a different action than this resolution.')
        if reuse is None and edited is None:
            raise DecisionError(f'This card has no {ACTION_LABELS[approved[0]].lower()} draft; write the text to confirm.')
    elif request.kind == 'ROUTE_TO_EXPERT':
        if request.expert is None:
            raise DecisionError('Choose the expert to route to.')
        approved = [EXPERTS[request.expert]]
        reuse = draft if action.get('action_type') == approved[0] else None
    else:
        reuse = None
        if edited is not None:
            raise DecisionError(f'{request.kind} carries no draft text; use the note for the reason.')
        if note is None:
            raise DecisionError('Give the reason for this decision.')
        if request.kind == 'OVERRIDE_SEVERITY':
            if request.severity is None or request.severity == level:
                raise DecisionError(f'Choose a severity different from the assessed {level}.')
            override = {'proposed': level, 'tl_selected': request.severity, 'reason': note}
    if request.kind != 'OVERRIDE_SEVERITY' and request.severity is not None:
        raise DecisionError('A severity is only given with a severity override.')
    if request.kind != 'ROUTE_TO_EXPERT' and request.expert is not None:
        raise DecisionError('An expert is only given when routing to an expert.')
    if request.alternative_id is not None and reuse is None:
        raise DecisionError('That alternative proposes a different action than this resolution.')
    grounded = {'grounded_source': source, 'alternative_id': request.alternative_id} if reuse else {}
    if edited is None or edited == reuse:
        text = {'origin': 'MODEL_GROUNDED', 'model_grounded_text': reuse, **grounded} if reuse else {'origin': 'NONE'}
    else:
        text = {'origin': 'TL_EDITED' if reuse else 'TL_WRITTEN', 'model_grounded_text': reuse, 'tl_text': edited, **grounded}
    outcome = {'DISMISS': 'REJECTED', 'OVERRIDE_SEVERITY': 'OVERRIDDEN'}.get(
        request.kind, 'APPROVED_WITH_EDITS' if text['origin'] in ('TL_EDITED', 'TL_WRITTEN') else 'APPROVED')
    lineage = card['lineage']
    entry_id = stable_id('decision', {'run_key': run.key, 'card_id': card['card_id'], 'sequence': sequence,
                                      'idempotency_key': key})
    record = DecisionRecord(
        decision_id=entry_id, project_id=card['project_id'], batch_id=lineage.get('batch_id'),
        original_advice={'advice_id': card['card_id'] + (f':{request.alternative_id}' if request.alternative_id else ''),
                         'card_id': card['card_id'],
                         'provenance': f"agent3 AdviceCard v3, run {run.brief['run_id']} ({run.key}, {run.mode})"
                                       + (f'; supported ToT alternative {request.alternative_id}' if request.alternative_id else ''),
                         'proposed_action': action.get('action_type'), 'proposed_text': draft,
                         'proposed_severity': level if override else None},
        tl_response={'outcome': outcome, 'actor_id': actor['actor_id'], 'actor_role': actor['role'], 'reviewed_at': recorded_at,
                     'text': text.get('tl_text'), 'approved_actions': approved or [], 'severity_override': override},
        execution={'state': 'NOT_EXECUTED', 'source_status': 'not_executed'},
        outcome={'state': 'NOT_OBSERVED', 'source_status': 'not_observed'},
        applicability=f"TL decision on one AdviceCard ({card['topic_name']}) in {card['project_id']}"
                      f"{' / ' + lineage['batch_id'] if lineage.get('batch_id') else ''}; it is not current guidance.",
        source={'kind': 'agent_record', 'project_id': card['project_id'], 'batch_id': lineage.get('batch_id'), 'scope': 'project',
                'candidate_group_id': lineage['candidate_group_id'], 'artifact': f'{run.key}/cards.json',
                'artifact_sha256': run.cards_sha256, 'note': card['card_id']})
    return TLDecisionEntry(
        entry_id=entry_id, sequence=sequence, supersedes_entry_id=head['entry_id'] if head else None, run_key=run.key,
        run_id=run.brief['run_id'], run_mode=run.mode, cards_sha256=run.cards_sha256, card_id=card['card_id'],
        card_line=card['card_line'], topic_name=card['topic_name'], project_id=card['project_id'],
        batch_id=lineage.get('batch_id'), kind=request.kind, recorded_at=recorded_at, actor_id=actor['actor_id'],
        actor_role=actor['role'], text=text, note=note, expert=request.expert, decision=record, idempotency_key=key,
        request_sha256=request_sha)


def build_review_action(*, run, item, request, actors, sequence, head, recorded_at, key, request_sha):
    actor = actors.get(request.actor_id)
    if actor is None:
        raise DecisionError(f'{request.actor_id} is not a recorded team lead.')
    action = ReviewAction(action=request.action, actor_id=actor['actor_id'], actor_role=actor['role'], acted_at=recorded_at,
                          note=(request.note or '').strip() or None)
    return ModelReviewEntry(
        entry_id=stable_id('reviewaction', {'run_key': run.key, 'item_id': item.item_id, 'sequence': sequence,
                                            'idempotency_key': key}),
        sequence=sequence, supersedes_entry_id=head['entry_id'] if head else None, run_key=run.key,
        run_id=run.brief['run_id'], item_id=item.item_id, project_id=item.project_id, action=action,
        effect=EFFECTS[request.action], related_card_ids=item.related_card_ids, idempotency_key=key, request_sha256=request_sha)


def review_item_with_actions(item, entries):
    """The run's ModelReviewItem with this store's actions appended (record_review_action); cards untouched."""
    for entry in entries:
        item = record_review_action(item, entry['action'])
    return item


SCHEMA = '''
CREATE TABLE IF NOT EXISTS requests (
    idempotency_key TEXT PRIMARY KEY, target TEXT NOT NULL, request_sha256 TEXT NOT NULL,
    entry_id TEXT NOT NULL, response TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS card_decisions (
    entry_id TEXT PRIMARY KEY, run_key TEXT NOT NULL, card_id TEXT NOT NULL, sequence INTEGER NOT NULL,
    recorded_at TEXT NOT NULL, entry TEXT NOT NULL, UNIQUE (run_key, card_id, sequence));
CREATE TABLE IF NOT EXISTS review_actions (
    entry_id TEXT PRIMARY KEY, run_key TEXT NOT NULL, item_id TEXT NOT NULL, sequence INTEGER NOT NULL,
    recorded_at TEXT NOT NULL, entry TEXT NOT NULL, UNIQUE (run_key, item_id, sequence));
CREATE TABLE IF NOT EXISTS indexing (
    entry_id TEXT PRIMARY KEY REFERENCES card_decisions(entry_id), document_id TEXT NOT NULL, version_id TEXT NOT NULL,
    authoring TEXT NOT NULL, status TEXT NOT NULL, snapshot TEXT, snapshot_fingerprint TEXT, error TEXT,
    updated_at TEXT NOT NULL);
'''
TABLES = {'card': ('card_decisions', 'card_id'), 'review': ('review_actions', 'item_id')}


class DecisionStore:
    def __init__(self, path=STORE_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.executescript(SCHEMA)

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        db.execute('PRAGMA synchronous=FULL')
        db.execute('PRAGMA foreign_keys=ON')
        db.row_factory = sqlite3.Row
        return _Closing(db)

    def submit(self, *, kind, run_key, target_id, key, body, build, on_insert=None):
        """Idempotent append. Returns (response, replayed). build(head, sequence, request_sha) makes the entry."""
        table, column = TABLES[kind]
        target = [kind, run_key, target_id]
        digest = request_hash(target, body)
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                row = db.execute('SELECT request_sha256, response FROM requests WHERE idempotency_key=?', (key,)).fetchone()
                if row is not None:
                    db.execute('ROLLBACK')
                    if row['request_sha256'] != digest:
                        raise KeyReused(json.loads(row['response']))
                    return json.loads(row['response']), True
                head = self._head(db, table, column, run_key, target_id)
                if body.get('expected_head') != (head['entry_id'] if head else None):
                    db.execute('ROLLBACK')
                    raise StaleHead(head)
                entry = build(head, (head['sequence'] if head else 0) + 1, digest).model_dump(mode='json')
                db.execute(f'INSERT INTO {table} (entry_id, run_key, {column}, sequence, recorded_at, entry) VALUES (?,?,?,?,?,?)',
                           (entry['entry_id'], run_key, target_id, entry['sequence'], entry.get('recorded_at') or
                            entry['action']['acted_at'], json.dumps(entry, ensure_ascii=False, sort_keys=True)))
                if on_insert:
                    on_insert(db, entry)
                response = {'entry': entry}
                db.execute('INSERT INTO requests VALUES (?,?,?,?,?,?)', (key, json.dumps(target), digest, entry['entry_id'],
                                                                        json.dumps(response, ensure_ascii=False, sort_keys=True), now_iso()))
                db.execute('COMMIT')
            except BaseException:
                if db.in_transaction:
                    db.execute('ROLLBACK')
                raise
        return response, False

    @staticmethod
    def _head(db, table, column, run_key, target_id):
        row = db.execute(f'SELECT entry FROM {table} WHERE run_key=? AND {column}=? ORDER BY sequence DESC LIMIT 1',
                         (run_key, target_id)).fetchone()
        return json.loads(row['entry']) if row else None

    def history(self, kind, run_key, target_id=None):
        table, column = TABLES[kind]
        query, args = f'SELECT entry FROM {table} WHERE run_key=?', [run_key]
        if target_id is not None:
            query, args = query + f' AND {column}=?', args + [target_id]
        with self._connect() as db:
            rows = db.execute(query + f' ORDER BY {column}, sequence', args).fetchall()
        return [json.loads(r['entry']) for r in rows]

    def all_card_decisions(self):
        with self._connect() as db:
            return [json.loads(r['entry']) for r in db.execute('SELECT entry FROM card_decisions ORDER BY recorded_at, entry_id')]

    def counts(self):
        with self._connect() as db:
            return {t: db.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]
                    for t in ('requests', 'card_decisions', 'review_actions', 'indexing')}

    def indexing(self, entry_ids=None):
        with self._connect() as db:
            rows = db.execute('SELECT * FROM indexing ORDER BY entry_id').fetchall()
        return {r['entry_id']: dict(r) for r in rows if entry_ids is None or r['entry_id'] in entry_ids}

    def mark_indexing(self, entry_ids, status, *, snapshot=None, fingerprint=None, error=None):
        """Indexing status only; decisions are never changed here."""
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            for entry_id in entry_ids:
                db.execute('UPDATE indexing SET status=?, snapshot=?, snapshot_fingerprint=?, error=?, updated_at=? WHERE entry_id=?',
                           (status, snapshot, fingerprint, error, now_iso(), entry_id))
            db.execute('COMMIT')


class _Closing:
    """sqlite3 connections commit but do not close in a with block; this closes them."""

    def __init__(self, db):
        self.db = db

    def __enter__(self):
        return self.db

    def __exit__(self, *exc):
        self.db.close()
        return False
