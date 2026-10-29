"""Agent 3 v1 contracts: AdviceCard, DecisionRecord, AnnouncementRecord, ModelReviewItem.

Validators enforce structural guardrails only. They do not ground claims, assess
severity or detect conflicts; those checks are recorded here by later stages.
Severity (rubric impact) and confidence (model certainty) stay separate fields.
"""
from copy import deepcopy
from hashlib import sha256
import json
import re
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from threadsense.knowledge_sources import SourceRecord
from threadsense.routing import aware

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
SeverityLevel = Literal['LOW', 'MEDIUM', 'HIGH', 'N/A', 'UNKNOWN']  # severity_rubric.SeverityLevel values
# Action vocabulary used by the historical decision records in data/knowledge/decisions.
ActionType = Literal['POST_ALIGNMENT', 'SCHEDULE_ALIGNMENT', 'UPDATE_DOCUMENTATION', 'UPDATE_FAQ',
                     'ESCALATE_ENGINEERING', 'ROUTE_TO_LANGUAGE_SPECIALIST', 'NO_ACTION']
CardLine = Literal['RECOMMENDED_ACTION', 'NEEDS_REVIEW', 'OBSERVATION']
# GROUNDING_NOT_RUN marks a card still waiting for its grounding check (not a failure).
ReviewCode = Literal['LOW_CONFIDENCE', 'HIGH_SEVERITY', 'TEMPORAL_CONFLICT', 'GROUNDING_FAILURE',
                     'GROUNDING_NOT_RUN', 'OPEN_CONFIRMATION', 'INHERITED_FLAG', 'OTHER']
HANDOFF_CONTRACTS = ('agent2-taxonomy-handoff-v1', 'agent2-taxonomy-handoff-v2')
LOW_CONFIDENCE_BELOW = 0.60
ORDINARY_CONFIDENCE_FROM = 0.85
SLACK_TS = re.compile(r'\d+\.\d{1,6}')


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Frozen(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)


def confidence_band(confidence):
    """<0.60 LOW (Needs Review), [0.60, 0.85) MODERATE presentation, >=0.85 HIGH eligibility."""
    if confidence < LOW_CONFIDENCE_BELOW:
        return 'LOW'
    return 'MODERATE' if confidence < ORDINARY_CONFIDENCE_FROM else 'HIGH'


def stable_id(prefix, value):
    """Deterministic ID from JSON content; never from paths or wall-clock time."""
    body = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
    return f'{prefix}_' + sha256(body.encode('utf-8')).hexdigest()[:32]


class EvidenceRef(Frozen):
    """A citation. Chunk IDs stay null until a chunking stage actually creates them."""
    kind: Literal['slack_message', 'knowledge_source', 'agent_record']
    project_id: str | None = None
    batch_id: str | None = None
    scope: Literal['project', 'shared', 'unknown'] | None = None
    channel_id: str | None = None
    thread_id: str | None = None
    message_id: str | None = None
    document_id: str | None = None
    version_id: str | None = None
    authoring_document_id: str | None = None
    authoring_version: str | None = None
    section: str | None = None
    chunk_id: str | None = None
    candidate_group_id: str | None = None
    member_id: str | None = None
    artifact: str | None = None
    artifact_sha256: str | None = None
    quote: str | None = None
    note: str | None = None

    @model_validator(mode='after')
    def complete(self):
        if self.kind == 'slack_message':
            if not all((self.channel_id, self.thread_id, self.message_id)):
                raise ValueError('Slack evidence needs channel, thread and message IDs.')
            for value in (self.thread_id, self.message_id):
                if not SLACK_TS.fullmatch(value):
                    raise ValueError('Slack IDs must keep the exact seconds.microseconds string.')
        elif self.kind == 'knowledge_source':
            if not (self.document_id and self.version_id):
                raise ValueError('Knowledge evidence needs canonical document and version IDs.')
        elif not (self.candidate_group_id or self.member_id):
            raise ValueError('Agent-record evidence needs a candidate group or member ID.')
        if self.scope == 'project' and not self.project_id:
            raise ValueError('Project-scoped evidence needs its project.')
        return self


class ThreadRef(Frozen):
    project_id: str
    batch_id: str | None = None
    channel_id: str
    thread_id: str
    member_id: str | None = None

    @model_validator(mode='after')
    def exact_ts(self):
        if not SLACK_TS.fullmatch(self.thread_id):
            raise ValueError('Thread IDs must keep the exact Slack timestamp string.')
        return self


class CountEvidence(Frozen):
    """UNKNOWN is never zero. KNOWN/LOWER_BOUND need a stated basis."""
    status: Literal['KNOWN', 'LOWER_BOUND', 'UNKNOWN'] = 'UNKNOWN'
    count: int | None = Field(default=None, ge=0)
    ids: list[str] = Field(default_factory=list)
    basis: str | None = None
    evidence: list[EvidenceRef] = Field(default_factory=list)

    @model_validator(mode='after')
    def consistent(self):
        if len(self.ids) != len(set(self.ids)):
            raise ValueError('Counted IDs must be distinct; duplicates cannot inflate counts.')
        if self.status == 'UNKNOWN':
            if self.count is not None or self.ids:
                raise ValueError('An unknown count has no number and no counted IDs.')
            return self
        if self.count is None or not (self.basis or '').strip():
            raise ValueError('A known or lower-bound count needs a number and a basis.')
        if self.ids and (self.count != len(self.ids) if self.status == 'KNOWN' else self.count < len(self.ids)):
            raise ValueError('Count disagrees with its distinct IDs.')
        return self


class Denominator(Frozen):
    count: int = Field(ge=1)
    unit: Literal['reporters', 'tasks']
    basis: Text
    evidence: list[EvidenceRef] = Field(default_factory=list)


class Recurrence(Frozen):
    status: Literal['NOT_CHECKED', 'NONE_FOUND', 'FOUND'] = 'NOT_CHECKED'
    sources: list[EvidenceRef] = Field(default_factory=list)
    event_series_ids: list[str] = Field(default_factory=list)

    @model_validator(mode='after')
    def consistent(self):
        if self.status == 'FOUND' and not self.sources:
            raise ValueError('Found recurrence needs cited historical sources.')
        if self.status != 'FOUND' and (self.sources or self.event_series_ids):
            raise ValueError('Only FOUND recurrence cites historical sources.')
        return self


class StructuralCounts(Frozen):
    """Reliable mechanical counts. Participants are not affected reporters."""
    threads: int = Field(ge=0)
    messages: int = Field(ge=0)
    distinct_participants: int = Field(ge=0)
    duplicate_threads_ignored: int = Field(ge=0)
    duplicate_messages_ignored: int = Field(ge=0)
    computed_from: Text
    participants_are_not_affected_reporters: Literal[True] = True


class OccurrenceEvidence(Frozen):
    affected_reporters: CountEvidence = Field(default_factory=CountEvidence)
    affected_tasks: CountEvidence = Field(default_factory=CountEvidence)
    relevant_threads: list[ThreadRef] = Field(default_factory=list)
    reporting_window: dict[str, str] | None = None
    historical_recurrence: Recurrence = Field(default_factory=Recurrence)
    known_denominator: Denominator | None = None
    structural: StructuralCounts | None = None
    # Affected reports are identified semantically by the later assessment stage.
    semantic_identification: Literal['PENDING', 'ASSESSED'] = 'PENDING'

    @model_validator(mode='after')
    def consistent(self):
        keys = [(t.channel_id, t.thread_id) for t in self.relevant_threads]
        if len(keys) != len(set(keys)):
            raise ValueError('Relevant threads must be distinct.')
        if self.semantic_identification == 'PENDING' and (
                self.affected_reporters.status != 'UNKNOWN' or self.affected_tasks.status != 'UNKNOWN'):
            raise ValueError('Affected reporters/tasks stay UNKNOWN until semantic identification.')
        if self.reporting_window is not None:
            start, end = aware(self.reporting_window['start']), aware(self.reporting_window['end'])
            if end < start:
                raise ValueError('Reporting window ends before it starts.')
        d = self.known_denominator
        if d is not None:
            counted = self.affected_reporters if d.unit == 'reporters' else self.affected_tasks
            if counted.count is not None and counted.status == 'KNOWN' and counted.count > d.count:
                raise ValueError('Affected count exceeds its known denominator.')
        return self


class SignalMatch(Frozen):
    """A semantically supported rubric signal, cited by level/index with its exact text."""
    level: Literal['MEDIUM', 'HIGH']
    signal_index: int = Field(ge=0)
    signal_text: Text
    support: Text
    evidence: list[EvidenceRef] = Field(min_length=1)


class SeverityAssessment(Frozen):
    level: SeverityLevel
    assessment_status: Literal['ASSESSED', 'UNASSESSED']
    rubric_version: str | None = None
    rubric_content_sha256: str | None = None
    rubric_project_id: str | None = None
    # SHARED_DEFAULT: the requested project is assessed with the shared default rubric.
    rubric_scope: Literal['SHARED_DEFAULT', 'PROJECT_SPECIFIC'] | None = None
    rationale: str | None = None
    matched_signals: list[SignalMatch] = Field(default_factory=list)
    evidence: list[EvidenceRef] = Field(default_factory=list)
    occurrence: OccurrenceEvidence = Field(default_factory=OccurrenceEvidence)
    inherited_from: dict[str, Any] | None = None

    @model_validator(mode='after')
    def consistent(self):
        if self.assessment_status == 'UNASSESSED':
            if self.level != 'UNKNOWN' or self.matched_signals:
                raise ValueError('Unassessed severity is UNKNOWN and cites no signals.')
            return self
        if not (self.rubric_version and self.rubric_content_sha256 and self.rubric_scope and (self.rationale or '').strip()):
            raise ValueError('Assessed severity records the rubric version/hash/scope and a rationale.')
        if self.level in {'MEDIUM', 'HIGH'} and not any(m.level == self.level for m in self.matched_signals):
            raise ValueError(f'{self.level} needs at least one supported {self.level} rubric signal.')
        keys = [(m.level, m.signal_index) for m in self.matched_signals]
        if len(keys) != len(set(keys)):
            raise ValueError('Each rubric signal is cited once.')
        return self


def unassessed_severity(handoff_severity=None):
    """Agent 2's deferred UNKNOWN/UNASSESSED placeholder, kept verbatim as lineage."""
    return SeverityAssessment(level='UNKNOWN', assessment_status='UNASSESSED',
                              inherited_from=deepcopy(handoff_severity))


class ReviewReason(Frozen):
    code: ReviewCode
    detail: Text
    obligation_ids: list[str] = Field(default_factory=list)
    evidence: list[EvidenceRef] = Field(default_factory=list)


class InheritedFlag(Frozen):
    """An Agent 1/2 or assisted-review obligation applicable to this operational card."""
    origin: Literal['agent1', 'agent2', 'assisted_content_review']
    kind: Text
    candidate_group_id: str
    obligation_id: str | None = None
    member_ids: list[str] = Field(default_factory=list)
    detail: str | None = None

    @model_validator(mode='after')
    def addressable(self):
        if not (self.obligation_id or self.member_ids):
            raise ValueError('An inherited flag needs an obligation ID or member IDs.')
        return self


class RecommendedAction(Frozen):
    action_type: ActionType
    draft_text: str | None = None
    scope_note: str | None = None


class CardChecks(Frozen):
    """Results recorded by later checkers. NOT_RUN means no semantic grounding happened
    (neither passed nor failed); only PASSED makes a card eligible for RECOMMENDED_ACTION."""
    grounding: Literal['NOT_RUN', 'PASSED', 'FAILED'] = 'NOT_RUN'
    temporal_conflict: Literal['NOT_CHECKED', 'NONE_FOUND', 'DETECTED'] = 'NOT_CHECKED'
    open_confirmation: Literal['NOT_CHECKED', 'NONE', 'OPEN'] = 'NOT_CHECKED'


class CardLineage(Frozen):
    agent3_run_id: Text
    handoff_contract: Literal['agent2-taxonomy-handoff-v1', 'agent2-taxonomy-handoff-v2']
    agent2_export_sha256: Text
    agent2_schema_version: int
    candidate_group_id: Text
    topic_id: str | None = None  # Null for group-level rejected/unassigned members.
    member_ids: list[str] = Field(min_length=1)
    project_id: Text
    batch_id: str | None = None

    @model_validator(mode='after')
    def distinct(self):
        if len(self.member_ids) != len(set(self.member_ids)):
            raise ValueError('Lineage member IDs must be distinct.')
        return self


def required_review_codes(card):
    """Agreed guardrails that force Needs Review; severity and confidence evaluated separately."""
    codes = set()
    if card['confidence'] < LOW_CONFIDENCE_BELOW:
        codes.add('LOW_CONFIDENCE')
    if card['severity']['level'] == 'HIGH':
        codes.add('HIGH_SEVERITY')
    if card['inherited_flags']:
        codes.add('INHERITED_FLAG')
    checks = card.get('checks') or {}
    if checks.get('temporal_conflict') == 'DETECTED':
        codes.add('TEMPORAL_CONFLICT')
    if checks.get('grounding') == 'FAILED':
        codes.add('GROUNDING_FAILURE')
    if checks.get('open_confirmation') == 'OPEN':
        codes.add('OPEN_CONFIRMATION')
    return codes


class AdviceCard(Frozen):
    contract_version: Literal['agent3-advice-card-v1'] = 'agent3-advice-card-v1'
    record_type: Literal['ADVICE_CARD'] = 'ADVICE_CARD'
    card_id: Annotated[str, StringConstraints(pattern=r'^card_[0-9a-f]{32}$')]
    project_id: Text
    topic_name: Text
    card_line: CardLine
    summary: Text
    severity: SeverityAssessment
    severity_is_provisional: bool
    resolution_status: Literal['UNRESOLVED', 'PARTIALLY_RESOLVED', 'RESOLVED_IN_THREAD', 'MIXED', 'UNKNOWN']
    recommended_action: RecommendedAction | None = None
    reasoning: Text
    supporting_sources: list[EvidenceRef] = Field(default_factory=list)
    related_threads: list[ThreadRef] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    confidence_band: Literal['LOW', 'MODERATE', 'HIGH'] | None = None
    needs_review_reasons: list[ReviewReason] = Field(default_factory=list)
    inherited_flags: list[InheritedFlag] = Field(default_factory=list)
    checks: CardChecks = Field(default_factory=CardChecks)
    lineage: CardLineage

    @model_validator(mode='before')
    @classmethod
    def derive_band(cls, data):
        if isinstance(data, dict) and data.get('confidence_band') is None and isinstance(data.get('confidence'), (int, float)):
            data = {**data, 'confidence_band': confidence_band(data['confidence'])}
        return data

    @model_validator(mode='after')
    def guardrails(self):
        if self.confidence_band != confidence_band(self.confidence):
            raise ValueError('Confidence band disagrees with confidence.')
        if self.lineage.project_id != self.project_id or any(t.project_id != self.project_id for t in self.related_threads):
            raise ValueError('Card lineage and related threads must stay in the card project.')
        for source in self.supporting_sources:
            if source.scope == 'project' and source.project_id != self.project_id:
                raise ValueError('A project-scoped source from another project cannot support this card.')
        if self.severity.assessment_status == 'UNASSESSED' and not self.severity_is_provisional:
            raise ValueError('Unassessed severity must be marked provisional.')
        data = self.model_dump(mode='json')
        present = {reason.code for reason in self.needs_review_reasons}
        missing = required_review_codes(data) - present
        if missing:
            raise ValueError(f'Card is missing required review reasons: {sorted(missing)}.')
        contradicted = {code for code, check, value in (
            ('TEMPORAL_CONFLICT', 'temporal_conflict', 'NONE_FOUND'), ('GROUNDING_FAILURE', 'grounding', 'PASSED'),
            ('OPEN_CONFIRMATION', 'open_confirmation', 'NONE')) if code in present and data['checks'][check] == value}
        # Grounding reasons must name the recorded state exactly: NOT_RUN is never a failure.
        if 'GROUNDING_NOT_RUN' in present and data['checks']['grounding'] != 'NOT_RUN':
            contradicted.add('GROUNDING_NOT_RUN')
        if 'GROUNDING_FAILURE' in present and data['checks']['grounding'] != 'FAILED':
            contradicted.add('GROUNDING_FAILURE')
        if contradicted:
            raise ValueError(f'Review reasons contradict recorded checks: {sorted(contradicted)}.')
        if 'INHERITED_FLAG' in present and not self.inherited_flags:
            raise ValueError('INHERITED_FLAG reason needs the inherited flags it refers to.')
        if self.needs_review_reasons and self.card_line != 'NEEDS_REVIEW':
            raise ValueError('A card with review reasons must use the NEEDS_REVIEW line.')
        if self.card_line == 'NEEDS_REVIEW' and not self.needs_review_reasons:
            raise ValueError('NEEDS_REVIEW requires at least one reason.')
        action = self.recommended_action
        if self.card_line == 'RECOMMENDED_ACTION':
            if action is None or action.action_type == 'NO_ACTION':
                raise ValueError('RECOMMENDED_ACTION requires an operational recommended action.')
            if not self.supporting_sources:
                raise ValueError('RECOMMENDED_ACTION requires cited supporting sources.')
            if self.checks.grounding != 'PASSED':
                raise ValueError(f'RECOMMENDED_ACTION requires grounding PASSED; it is {self.checks.grounding}.')
        if self.card_line == 'OBSERVATION' and action is not None and action.action_type != 'NO_ACTION':
            raise ValueError('OBSERVATION cards carry no operational action.')
        return self


class ReviewAction(Frozen):
    action: Literal['ACCEPT', 'REJECT', 'DEFER']
    actor_id: Text
    actor_role: str | None = None
    acted_at: Text
    note: str | None = None

    @model_validator(mode='after')
    def timed(self):
        aware(self.acted_at)
        return self


class ModelReviewItem(Frozen):
    """Agent 1/2/3 model-output review, separate from operational AdviceCards."""
    contract_version: Literal['agent3-model-review-item-v1'] = 'agent3-model-review-item-v1'
    record_type: Literal['MODEL_REVIEW_ITEM'] = 'MODEL_REVIEW_ITEM'
    item_id: Annotated[str, StringConstraints(pattern=r'^review_[0-9a-f]{32}$')]
    origin: Literal['agent1', 'agent2', 'assisted_content_review', 'agent3']
    kind: Text
    project_id: Text
    batch_id: str | None = None
    candidate_group_id: Text
    topic_id: str | None = None
    member_ids: list[str] = Field(default_factory=list)
    obligation_id: str | None = None
    reason: Text
    source_obligation: dict[str, Any] = Field(default_factory=dict)  # Verbatim upstream copy.
    related_card_ids: list[Annotated[str, StringConstraints(pattern=r'^card_[0-9a-f]{32}$')]] = Field(default_factory=list)
    actions: list[ReviewAction] = Field(default_factory=list)  # Append-only history.

    @model_validator(mode='after')
    def addressable(self):
        if not (self.obligation_id or self.member_ids):
            raise ValueError('A review item needs an obligation ID or member IDs.')
        return self

    @property
    def review_state(self):
        """DEFER keeps it open. ACCEPT/REJECT record a reviewer decision; cards are untouched."""
        if not self.actions or self.actions[-1].action == 'DEFER':
            return 'OPEN'
        return 'ACCEPTED' if self.actions[-1].action == 'ACCEPT' else 'REJECTED'


def record_review_action(item, action):
    """Return a new review item with the action appended; never edits any AdviceCard."""
    action = ReviewAction.model_validate(action)
    return ModelReviewItem.model_validate({**item.model_dump(mode='json'),
                                           'actions': [*item.model_dump(mode='json')['actions'], action.model_dump(mode='json')]})


class OriginalAdvice(Frozen):
    advice_id: Text
    card_id: str | None = None
    provenance: Text
    proposed_action: ActionType | None = None
    proposed_text: str | None = None
    proposed_severity: SeverityLevel | None = None


class SeverityOverride(Frozen):
    proposed: SeverityLevel
    tl_selected: SeverityLevel
    reason: Text

    @model_validator(mode='after')
    def changed(self):
        if self.proposed == self.tl_selected:
            raise ValueError('A severity override must change the proposed level.')
        return self


class TLResponse(Frozen):
    outcome: Literal['PENDING', 'APPROVED', 'APPROVED_WITH_EDITS', 'REJECTED', 'DEFERRED', 'OVERRIDDEN']
    actor_id: str | None = None
    actor_role: str | None = None
    reviewed_at: str | None = None
    text: str | None = None
    approved_actions: list[ActionType] = Field(default_factory=list)
    severity_override: SeverityOverride | None = None

    @model_validator(mode='after')
    def consistent(self):
        if self.reviewed_at is not None:
            aware(self.reviewed_at)
        if self.outcome != 'PENDING' and not self.actor_id:
            raise ValueError('A recorded TL response names its actor.')
        if self.outcome == 'APPROVED_WITH_EDITS' and not (self.text or '').strip():
            raise ValueError('An edited approval preserves the edited instruction text.')
        if self.outcome == 'OVERRIDDEN' and self.severity_override is None and not self.approved_actions:
            raise ValueError('An override records what the TL selected instead.')
        if self.outcome in {'REJECTED', 'DEFERRED', 'PENDING'} and any(a != 'NO_ACTION' for a in self.approved_actions):
            raise ValueError('Rejected, deferred or pending advice approves no operational action.')
        return self


class ExecutionState(Frozen):
    """What was actually done. Approval alone never implies posting or implementation."""
    state: Literal['NOT_EXECUTED', 'PENDING', 'IN_PROGRESS', 'COMPLETED', 'PARTIALLY_COMPLETED', 'UNKNOWN']
    source_status: str | None = None
    evidence: list[EvidenceRef] = Field(default_factory=list)


class OutcomeState(Frozen):
    """What was observed afterwards; independent of approval and execution."""
    state: Literal['NOT_OBSERVED', 'OPEN', 'IMPROVED', 'RESOLVED', 'UNSUCCESSFUL', 'UNDETERMINED',
                   'NO_ISSUE_FOUND', 'NO_CHANGE', 'UNKNOWN']
    source_status: str | None = None
    scope_note: str | None = None
    evidence: list[EvidenceRef] = Field(default_factory=list)


class DecisionRecord(Frozen):
    """original advice -> TL response -> execution state -> observed outcome."""
    contract_version: Literal['agent3-decision-record-v1'] = 'agent3-decision-record-v1'
    record_type: Literal['DECISION_RECORD'] = 'DECISION_RECORD'
    decision_id: Text
    project_id: Text
    batch_id: str | None = None
    event_series_id: str | None = None
    original_advice: OriginalAdvice | None = None
    tl_response: TLResponse
    execution: ExecutionState
    outcome: OutcomeState
    applicability: str | None = None
    valid_until: str | None = None
    review_due_at: str | None = None
    source: EvidenceRef | None = None

    @model_validator(mode='after')
    def consistent(self):
        for value in (self.valid_until, self.review_due_at):
            if value is not None:
                aware(value)
        if self.tl_response.outcome in {'REJECTED', 'DEFERRED', 'PENDING'} and self.execution.state in {
                'IN_PROGRESS', 'COMPLETED', 'PARTIALLY_COMPLETED'}:
            raise ValueError('Advice that was not approved cannot be recorded as executed.')
        return self


class AnnouncementRecord(Frozen):
    """A last-24h or historical announcement, wrapping the shared SourceRecord unchanged."""
    contract_version: Literal['agent3-announcement-record-v1'] = 'agent3-announcement-record-v1'
    record_type: Literal['ANNOUNCEMENT_RECORD'] = 'ANNOUNCEMENT_RECORD'
    source: SourceRecord
    in_extraction_window: bool | None = None  # Null when no daily window applies.
    related_decision_ids: list[str] = Field(default_factory=list)
    overlapping_representations: list[EvidenceRef] = Field(default_factory=list)

    @model_validator(mode='after')
    def announcement_only(self):
        if self.source.document_type != 'announcement':
            raise ValueError('AnnouncementRecord wraps announcement sources only.')
        return self

    @property
    def document_id(self):
        return self.source.record_id

    @property
    def version_id(self):
        return self.source.version_id
