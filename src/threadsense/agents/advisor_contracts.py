"""Agent 3 Advisor pilot model I/O: draft (v6), grounding judgment (v4), shallow ToT comparison (v2).

These are what a model returns. They cite evidence only by the evidence_id values the
pilot assigned in its evidence ledger; validators here are structural. Grounding,
severity binding, temporal checks and card routing happen in advisor_checks.py.
v2 adds per-member resolution, announcement assessments and documentation targets to the
draft, and judges every statement that can reach a card (not only claims). v3 marks quotes as
verbatim or paraphrase, adds verified CAUSE claims, requires a specific open question with the
evidence that leaves it open, and adds an evidence-coverage assessment. Draft v4 adds scoped
THREAD_INSTRUCTION claims (a team lead's in-thread instruction, not project guidance) and separates
members' reports of recurrence from corroborated historical recurrence; grounding v3 adds an
explicit judgment of whether the passed premises suffice for the exact proposed action. Draft v5 writes prose
that refers to people by role, never by name, and records who wrote, started or took part in a thread as
canonical-ID attributions; grounding v4 also judges the sufficiency of each reviewed ToT alternative. Draft v6
adds the team lead-facing action instruction and rationale (draft_text is the copyable draft) and an optional review
note; ToT v2 adds a candidate instruction. Draft v7 requires an operational action to state its intervention need (why
acting now is needed, from the evidence); the final grounding judges it like any statement. Recorded v6 drafts keep
the v6 rules.
"""
from typing import Literal

from pydantic import Field, model_validator

from threadsense.agents.advice_contracts import ActionType, SeverityLevel, Strict, Text

SourceType = Literal['guideline', 'faq', 'decision', 'announcement']
Need = Literal['APPLICABLE_INSTRUCTION', 'CURRENT_HANDLING', 'PRIOR_DECISION_OUTCOME', 'RECURRENCE',
               'SUPERSESSION_OR_CONFLICT', 'EXPERT_ROUTING', 'OTHER']
# INCIDENT_FACT: what members report (member Slack messages only; a report, not a verified cause).
# CAUSE: a verified cause (needs a retrieved record or a team lead/engineer message that verifies it).
# GUIDANCE: what applies now (current guideline/FAQ/established announcement). THREAD_INSTRUCTION: a team
# lead's instruction inside a member thread, scoped to that thread (not project guidance). HISTORY: what was
# decided or observed before. INFERENCE: the Advisor's reasoning from cited evidence.
ClaimKind = Literal['INCIDENT_FACT', 'CAUSE', 'GUIDANCE', 'THREAD_INSTRUCTION', 'HISTORY', 'INFERENCE']
CoverageNeed = Literal['CURRENT_GUIDANCE', 'ANNOUNCEMENTS', 'PRIOR_DECISIONS', 'MEMBER_QUESTIONS']
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


class Attribution(Strict):
    """Who the claim's role wording refers to, by canonical user ID. AUTHOR: wrote the cited message (reports, asks,
    confirms, instructs). THREAD_STARTER: started the cited message's thread. PARTICIPANT: posted in that thread
    (only for a claim about taking part)."""
    user_id: Text
    relation: Literal['AUTHOR', 'THREAD_STARTER', 'PARTICIPANT']
    evidence_id: Text


class Claim(Strict):
    claim_id: Text
    kind: ClaimKind
    text: Text  # Role-based prose: "a tutor reports", "the team lead instructs"; never a personal name.
    evidence_ids: list[str] = Field(default_factory=list)
    attributions: list[Attribution] = Field(default_factory=list)
    quote: str | None = None  # Optional excerpt from one cited item.
    quote_kind: Literal['VERBATIM', 'PARAPHRASE'] = 'VERBATIM'  # VERBATIM must match the source exactly.
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
    # Historical recurrence: corroborated by retrieved records only.
    recurrence: Literal['NOT_CHECKED', 'NONE_FOUND', 'FOUND'] = 'NOT_CHECKED'
    recurrence_evidence_ids: list[str] = Field(default_factory=list)
    # Members saying it is "happening again": a report, not corroborated history.
    reported_recurrence_evidence_ids: list[str] = Field(default_factory=list)


class ActionTarget(Strict):
    """What a documentation or FAQ action changes: ADD a missing entry, CORRECT or REMOVE stale wording."""
    evidence_id: Text
    section: str | None = None
    change: Literal['ADD', 'CORRECT', 'REMOVE']


# Evidence-backed reasons to intervene. "A reminder might help" is none of these.
InterventionKind = Literal['UNRESOLVED_HANDLING_QUESTION', 'GUIDANCE_GAP', 'APPLICABLE_PENDING_DECISION',
                           'OPERATIONAL_PROBLEM']


class InterventionNeed(Strict):
    """Why this topic needs intervention now, as shown by the cited evidence (judged as statement action:need)."""
    kind: InterventionKind
    statement: Text
    evidence_ids: list[str] = Field(min_length=1)


class ActionProposal(Strict):
    action_type: ActionType
    intervention_need: InterventionNeed | None = None  # Required (draft v7) for any action other than NO_ACTION.
    instruction: str | None = None  # One concrete sentence telling the team lead what to do.
    rationale: str | None = None  # Why that helps, in 1-2 short sentences.
    draft_text: str | None = None  # The copyable draft (announcement, escalation message, documentation wording).
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


class CoverageItem(Strict):
    """Whether the evidence needed for this need is present. MISSING names the gap that requests it."""
    need: CoverageNeed
    status: Literal['COVERED', 'NOT_APPLICABLE', 'MISSING']
    evidence_ids: list[str] = Field(default_factory=list)
    note: Text
    gap_id: str | None = None

    @model_validator(mode='after')
    def consistent(self):
        if self.status == 'COVERED' and not self.evidence_ids:
            raise ValueError('COVERED cites the evidence that covers it.')
        return self


class AdvisorDraft(Strict):
    contract_version: Literal['agent3-advisor-draft-v7', 'agent3-advisor-draft-v6'] = 'agent3-advisor-draft-v7'
    summary: Text  # What happened, 1-2 short sentences for the team lead.
    reasoning: Text
    claims: list[Claim] = Field(default_factory=list)
    gaps: list[EvidenceGap] = Field(default_factory=list)
    evidence_sufficiency: Literal['SUFFICIENT', 'INSUFFICIENT', 'UNSUPPORTED']
    proposed_action: ActionProposal | None = None
    severity: SeverityProposal
    confidence: float = Field(ge=0.0, le=1.0)
    # OPEN only for a specific question the evidence leaves unsettled; a TL approving execution is not one.
    open_confirmation: Literal['OPEN', 'NONE']
    open_question: str | None = None
    open_question_evidence_ids: list[str] = Field(default_factory=list)
    source_conflicts: list[SourceConflict] = Field(default_factory=list)
    announcement_assessments: list[AnnouncementAssessment] = Field(default_factory=list)
    resolution: list[MemberResolution] = Field(default_factory=list)
    coverage: list[CoverageItem] = Field(default_factory=list)
    review_note: str | None = None  # Only when something specific still needs the team lead's review.

    @model_validator(mode='after')
    def consistent(self):
        claims = [c.claim_id for c in self.claims]
        _distinct(claims, 'Claim IDs')
        _distinct([g.gap_id for g in self.gaps], 'Gap IDs')
        _distinct([a.evidence_id for a in self.announcement_assessments], 'Assessed announcements')
        _distinct([r.member_id for r in self.resolution], 'Resolution member IDs')
        if self.proposed_action and set(self.proposed_action.support_claim_ids) - set(claims):
            raise ValueError('Action support must reference claims in this draft.')
        action = self.proposed_action
        if (self.contract_version == 'agent3-advisor-draft-v7' and action is not None and action.action_type != 'NO_ACTION'
                and action.intervention_need is None):
            raise ValueError('An operational action states its intervention_need (why intervening now is needed, with '
                             'the evidence that shows it); otherwise propose NO_ACTION.')
        if self.open_confirmation == 'OPEN' and not ((self.open_question or '').strip() and self.open_question_evidence_ids):
            raise ValueError('An open confirmation states the specific unresolved question and cites the evidence '
                             'that leaves it open.')
        _distinct([c.need for c in self.coverage], 'Coverage needs')
        return self


class StatementVerdict(Strict):
    statement_id: Text
    verdict: Literal['SUPPORTED', 'PARTIALLY_SUPPORTED', 'UNSUPPORTED']
    rationale: Text


class ActionSufficiency(Strict):
    """Whether the premises that passed justify the exact proposed action (wording, conditions and scope)."""
    verdict: Literal['SUFFICIENT', 'INSUFFICIENT']
    essential_statement_ids: list[str] = Field(default_factory=list)  # Premises the action cannot stand without.
    rationale: Text


class AlternativeSufficiency(ActionSufficiency):
    """The same sufficiency judgment for one reviewed ToT alternative (statement_id alternative:<candidate>)."""
    statement_id: Text


class GroundingJudgment(Strict):
    """One verdict per statement presented (claims, summary, action, severity, reporters, resolution,
    announcement handling, source agreement and ToT alternatives), plus the sufficiency judgment for the action
    and for each operational alternative sent."""
    contract_version: Literal['agent3-grounding-judgment-v4'] = 'agent3-grounding-judgment-v4'
    verdicts: list[StatementVerdict]
    action_sufficiency: ActionSufficiency | None = None
    alternative_sufficiency: list[AlternativeSufficiency] = Field(default_factory=list)

    @model_validator(mode='after')
    def distinct(self):
        _distinct([v.statement_id for v in self.verdicts], 'Verdict statement IDs')
        _distinct([a.statement_id for a in self.alternative_sufficiency], 'Alternative sufficiency statement IDs')
        return self


class CandidateAction(Strict):
    candidate_id: Text
    action_type: ActionType
    instruction: str | None = None
    draft_text: Text
    evidence_ids: list[str] = Field(default_factory=list)
    evidence_support: Literal['STRONG', 'PARTIAL', 'WEAK', 'NONE']
    applicability: Literal['CURRENT', 'HISTORICAL_ONLY', 'MIXED', 'UNCLEAR']
    severity_fit: Literal['FITS', 'PARTIAL', 'POOR', 'UNKNOWN']
    rationale: Text


class ToTComparison(Strict):
    contract_version: Literal['agent3-tot-comparison-v2'] = 'agent3-tot-comparison-v2'
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
