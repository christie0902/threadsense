"""Agent 3 Advisor pilot model I/O: draft (v2), grounding judgment (v2), shallow ToT comparison (v1).

These are what a model returns. They cite evidence only by the evidence_id values the
pilot assigned in its evidence ledger; validators here are structural. Grounding,
severity binding, temporal checks and card routing happen in advisor_checks.py.
v2 adds per-member resolution, announcement assessments and documentation targets to the
draft, and judges every statement that can reach a card (not only claims).
"""
from typing import Literal

from pydantic import Field, model_validator

from threadsense.agents.advice_contracts import ActionType, SeverityLevel, Strict, Text

SourceType = Literal['guideline', 'faq', 'decision', 'announcement']
Need = Literal['APPLICABLE_INSTRUCTION', 'CURRENT_HANDLING', 'PRIOR_DECISION_OUTCOME', 'RECURRENCE',
               'SUPERSESSION_OR_CONFLICT', 'EXPERT_ROUTING', 'OTHER']
# INCIDENT_FACT: what happened (member Slack messages only). GUIDANCE: what applies now
# (current guideline/FAQ/announcement). HISTORY: what was decided or observed before.
ClaimKind = Literal['INCIDENT_FACT', 'GUIDANCE', 'HISTORY', 'INFERENCE']
DOCUMENT_ACTIONS = ('UPDATE_DOCUMENTATION', 'UPDATE_FAQ')


def _distinct(values, label):
    if len(values) != len(set(values)):
        raise ValueError(f'{label} must be distinct.')


class FollowUpQuery(Strict):
    query: Text
    source_types: list[SourceType] = Field(min_length=1)
    version_mode: Literal['current', 'history'] = 'current'


class EvidenceGap(Strict):
    """Missing support for the proposed action. follow_up=None: retrieval cannot fill it (e.g. needs a TL)."""
    gap_id: Text
    need: Need
    description: Text
    follow_up: FollowUpQuery | None = None


class Claim(Strict):
    claim_id: Text
    kind: ClaimKind
    text: Text
    evidence_ids: list[str] = Field(default_factory=list)
    quote: str | None = None  # Optional verbatim excerpt from one cited item.
    material: bool = True


class SignalCitation(Strict):
    level: Literal['MEDIUM', 'HIGH']
    signal_index: int = Field(ge=0)
    signal_text: Text
    support: Text
    evidence_ids: list[str] = Field(min_length=1)


class ReporterCitation(Strict):
    """An affected reporter is a person whose own message reports being affected."""
    author_id: Text
    evidence_id: Text


class SeverityProposal(Strict):
    level: SeverityLevel
    rationale: Text
    signals: list[SignalCitation] = Field(default_factory=list)
    affected_reporters: list[ReporterCitation] = Field(default_factory=list)
    recurrence: Literal['NOT_CHECKED', 'NONE_FOUND', 'FOUND'] = 'NOT_CHECKED'
    recurrence_evidence_ids: list[str] = Field(default_factory=list)


class ActionTarget(Strict):
    """What a documentation or FAQ action changes: ADD a missing entry, CORRECT or REMOVE stale wording."""
    evidence_id: Text
    section: str | None = None
    change: Literal['ADD', 'CORRECT', 'REMOVE']


class ActionProposal(Strict):
    action_type: ActionType
    draft_text: str | None = None
    scope_note: str | None = None
    support_claim_ids: list[str] = Field(default_factory=list)
    targets: list[ActionTarget] = Field(default_factory=list)

    @model_validator(mode='after')
    def targeted(self):
        if self.action_type in DOCUMENT_ACTIONS and not self.targets:
            raise ValueError(f'{self.action_type} names the source and section it changes.')
        return self


class AnnouncementAssessment(Strict):
    """Whether a posted announcement applies to this topic and directs handling (quoted verbatim)."""
    evidence_id: Text
    relevant: bool
    directive: bool
    directive_quote: str | None = None
    rationale: Text

    @model_validator(mode='after')
    def quoted(self):
        if self.relevant and self.directive and not (self.directive_quote or '').strip():
            raise ValueError('A relevant directive quotes the directing sentence.')
        return self


class MemberResolution(Strict):
    """One member thread's resolution, from its messages; Agent 1's label is an attributed input, not evidence."""
    member_id: Text
    state: Literal['UNRESOLVED', 'PARTIALLY_RESOLVED', 'RESOLVED_IN_THREAD', 'UNKNOWN']
    evidence_ids: list[str] = Field(default_factory=list)
    basis: Text


class SourceConflict(Strict):
    evidence_ids: list[str] = Field(min_length=2)
    description: Text


class AdvisorDraft(Strict):
    contract_version: Literal['agent3-advisor-draft-v2'] = 'agent3-advisor-draft-v2'
    summary: Text
    reasoning: Text
    claims: list[Claim] = Field(default_factory=list)
    gaps: list[EvidenceGap] = Field(default_factory=list)
    evidence_sufficiency: Literal['SUFFICIENT', 'INSUFFICIENT', 'UNSUPPORTED']
    proposed_action: ActionProposal | None = None
    severity: SeverityProposal
    confidence: float = Field(ge=0.0, le=1.0)
    open_confirmation: Literal['OPEN', 'NONE']
    open_confirmation_detail: str | None = None
    source_conflicts: list[SourceConflict] = Field(default_factory=list)
    announcement_assessments: list[AnnouncementAssessment] = Field(default_factory=list)
    resolution: list[MemberResolution] = Field(default_factory=list)

    @model_validator(mode='after')
    def consistent(self):
        claims = [c.claim_id for c in self.claims]
        _distinct(claims, 'Claim IDs')
        _distinct([g.gap_id for g in self.gaps], 'Gap IDs')
        _distinct([a.evidence_id for a in self.announcement_assessments], 'Assessed announcements')
        _distinct([r.member_id for r in self.resolution], 'Resolution member IDs')
        if self.proposed_action and set(self.proposed_action.support_claim_ids) - set(claims):
            raise ValueError('Action support must reference claims in this draft.')
        if self.open_confirmation == 'OPEN' and not (self.open_confirmation_detail or '').strip():
            raise ValueError('An open confirmation states what is waiting for confirmation.')
        return self


class StatementVerdict(Strict):
    statement_id: Text
    verdict: Literal['SUPPORTED', 'PARTIALLY_SUPPORTED', 'UNSUPPORTED']
    rationale: Text


class GroundingJudgment(Strict):
    """One verdict per statement presented (claims, summary, action, severity, reporters, resolution,
    announcement handling and ToT alternatives)."""
    contract_version: Literal['agent3-grounding-judgment-v2'] = 'agent3-grounding-judgment-v2'
    verdicts: list[StatementVerdict]

    @model_validator(mode='after')
    def distinct(self):
        _distinct([v.statement_id for v in self.verdicts], 'Verdict statement IDs')
        return self


class CandidateAction(Strict):
    candidate_id: Text
    action_type: ActionType
    draft_text: Text
    evidence_ids: list[str] = Field(default_factory=list)
    evidence_support: Literal['STRONG', 'PARTIAL', 'WEAK', 'NONE']
    applicability: Literal['CURRENT', 'HISTORICAL_ONLY', 'MIXED', 'UNCLEAR']
    severity_fit: Literal['FITS', 'PARTIAL', 'POOR', 'UNKNOWN']
    rationale: Text


class ToTComparison(Strict):
    contract_version: Literal['agent3-tot-comparison-v1'] = 'agent3-tot-comparison-v1'
    candidates: list[CandidateAction] = Field(min_length=2, max_length=3)
    preferred_candidate_id: str | None = None
    close_call: bool
    rationale: Text

    @model_validator(mode='after')
    def consistent(self):
        ids = [c.candidate_id for c in self.candidates]
        _distinct(ids, 'Candidate IDs')
        if self.preferred_candidate_id is not None and self.preferred_candidate_id not in ids:
            raise ValueError('The preferred candidate must be one of the candidates.')
        return self
