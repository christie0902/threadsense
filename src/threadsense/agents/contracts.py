from threadsense.agents.severity import SeverityLevel
from enum import Enum
from pydantic import BaseModel, Field, model_validator
from typing import Literal


class ResolutionState(str, Enum):
    UNRESOLVED = "UNRESOLVED"
    PARTIALLY_RESOLVED = "PARTIALLY_RESOLVED"
    RESOLVED_IN_THREAD = "RESOLVED_IN_THREAD"


class ThreadInterpretation(BaseModel):
    thread_id: str

    summary: str
    central_question: str | None = None

    resolution_state: ResolutionState

    authoritative_response_present: bool = False

    authority_evidence_message_ids: list[str] = Field(
        default_factory=list
    )

    resolution_rationale: str

    confidence: float = Field(ge=0.0, le=1.0)


class TopicRollup(BaseModel):
    topic_name: str
    representative_question: str | None = None
    summary: str

    thread_ids: list[str] = Field(min_length=1)
    evidence_message_ids: list[str] = Field(default_factory=list)

    severity: SeverityLevel
    severity_rationale: str

    actionable: bool
    actionability_rationale: str

    open_questions: list[str] = Field(default_factory=list)
    research_needs: list[str] = Field(default_factory=list)


class TopicAnalysis(BaseModel):
    candidate_group_id: str
    project_id: str
    batch_id: str

    is_coherent: bool
    coherence_rationale: str

    topics: list[TopicRollup] = Field(min_length=1)

    needs_human_review: bool = False
    review_reason: str | None = None


class VerificationOutcome(str, Enum):
    VERIFIED = "VERIFIED"
    CORRECTED = "CORRECTED"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class VerificationCategory(str, Enum):
    SUMMARY = "SUMMARY"
    CENTRAL_QUESTION = "CENTRAL_QUESTION"
    RESOLUTION = "RESOLUTION"
    AUTHORITY = "AUTHORITY"
    TERMINOLOGY = "TERMINOLOGY"
    EVIDENCE = "EVIDENCE"
    OTHER = "OTHER"


class VerificationFinding(BaseModel):
    category: VerificationCategory
    explanation: str = Field(min_length=1)
    evidence_message_ids: list[str] = Field(default_factory=list)
    evidence_quotes: list[str] = Field(default_factory=list)
    disputed_fields: list[str] = Field(default_factory=list)


class ReplyContribution(str, Enum):
    COMPLETE_ANSWER = "COMPLETE_ANSWER"
    PARTIAL_ANSWER = "PARTIAL_ANSWER"
    DIAGNOSTIC_ONLY = "DIAGNOSTIC_ONLY"
    ACKNOWLEDGMENT = "ACKNOWLEDGMENT"
    OTHER = "OTHER"
    UNCERTAIN = "UNCERTAIN"


class ReplyEvidenceAssessment(BaseModel):
    message_id: str
    contribution: ReplyContribution

    # Exact excerpt from this Slack reply.
    evidence_quote: str = Field(min_length=1)

    # Explain the relationship to the original request.
    explanation: str = Field(min_length=1)
    # The auditor establishes technical relevance, independently of role eligibility.
    technical_scope: bool | None = None


class DecisionCoverageStatus(str, Enum):
    ANSWERED = "ANSWERED"
    PARTIALLY_ANSWERED = "PARTIALLY_ANSWERED"
    UNANSWERED = "UNANSWERED"
    UNCERTAIN = "UNCERTAIN"


class DecisionCoverageItem(BaseModel):
    requested_decision: str = Field(min_length=1)
    status: DecisionCoverageStatus

    answer_message_ids: list[str] = Field(default_factory=list)
    rationale: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_coverage(self):
        if len(self.answer_message_ids) != len(
            set(self.answer_message_ids)
        ):
            raise ValueError("Duplicate answer message IDs.")

        if self.status in {
            DecisionCoverageStatus.ANSWERED,
            DecisionCoverageStatus.PARTIALLY_ANSWERED,
        } and not self.answer_message_ids:
            raise ValueError(
                "Answered decisions require answer evidence."
            )

        if (
            self.status == DecisionCoverageStatus.UNANSWERED
            and self.answer_message_ids
        ):
            raise ValueError(
                "Unanswered decisions cannot cite answer evidence."
            )

        return self

class ProseEvidenceAssessment(BaseModel):
    unit_id: str = Field(min_length=1)
    candidate_text: str = Field(min_length=1)
    source_interpretation: str = Field(min_length=1)

    verdict: Literal[
        "SUPPORTED",
        "CONTRADICTED",
        "UNSUPPORTED",
        "UNCERTAIN",
    ]

    evidence_message_ids: list[str]
    evidence_quotes: list[str]
    explanation: str = Field(min_length=1)

class SourceEvidenceAnalysis(BaseModel):
    """Candidate-independent evidence, shared by both verification passes."""

    model_config = {"extra": "forbid"}
    thread_id: str
    root_request_quote: str = Field(min_length=1)
    requested_decisions: list[str]
    reply_assessments: list[ReplyEvidenceAssessment]
    # Coverage is established once from the source, never from a candidate.
    decision_coverage: list[DecisionCoverageItem]
    uncertainties: list[str] = Field(
        description=(
            "Ambiguities that prevent reliable interpretation of the conversation. "
            "An unanswered operational decision is not interpretation uncertainty; "
            "record it in decision_coverage and explain it in the rationale. "
            "Return [] when the absence of an answer is clear."
        )
    )


class ProseComparison(BaseModel):
    """One complete batch of assessments for the current candidate only."""

    model_config = {"extra": "forbid"}
    prose_assessments: list[ProseEvidenceAssessment]


class DecisionEvidenceAudit(SourceEvidenceAnalysis):
    """Validated source analysis combined with fresh candidate assessments.

    Also retains the explicit finding field used by historical audit callers.
    The split production workflow derives findings deterministically instead.
    """
    # Required even when empty: a source-only audit cannot certify candidate prose.
    prose_assessments: list[ProseEvidenceAssessment]
    interpretation_findings: list[VerificationFinding]
