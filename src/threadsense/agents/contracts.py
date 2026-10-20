from threadsense.agents.severity import SeverityLevel
from enum import Enum
from pydantic import BaseModel, Field, model_validator


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


class VerificationStatus(str, Enum):
    PASS = "PASS"
    CORRECTION_PROPOSED = "CORRECTION_PROPOSED"
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


class InterpretationVerification(BaseModel):
    thread_id: str
    status: VerificationStatus

    findings: list[VerificationFinding] = Field(
        default_factory=list
    )

    proposed_interpretation: ThreadInterpretation | None = None

    rationale: str = Field(min_length=1)

    @model_validator(mode="after")
    def check_consistency(self):
        if self.status == VerificationStatus.PASS:
            if self.findings or self.proposed_interpretation:
                raise ValueError(
                    "PASS must not contain findings or corrections"
                )

        if self.status == VerificationStatus.CORRECTION_PROPOSED:
            if not self.findings:
                raise ValueError(
                    "A correction requires documented findings"
                )
            if self.proposed_interpretation is None:
                raise ValueError(
                    "A correction requires a proposed interpretation"
                )

        if self.proposed_interpretation is not None:
            if self.proposed_interpretation.thread_id != self.thread_id:
                raise ValueError(
                    "Corrected interpretation has a different thread_id"
                )

        return self


class ReplyContribution(str, Enum):
    COMPLETE_ANSWER = "COMPLETE_ANSWER"
    PARTIAL_ANSWER = "PARTIAL_ANSWER"
    DIAGNOSTIC_ONLY = "DIAGNOSTIC_ONLY"
    ACKNOWLEDGMENT = "ACKNOWLEDGMENT"
    OTHER = "OTHER"


class ReplyEvidenceAssessment(BaseModel):
    message_id: str
    contribution: ReplyContribution

    # Exact excerpt from this Slack reply.
    evidence_quote: str = Field(min_length=1)

    # Explain the relationship to the original request.
    explanation: str = Field(min_length=1)


class DecisionEvidenceAudit(BaseModel):
    thread_id: str

    # Empty for an announcement without a requested decision.
    requested_decisions: list[str] = Field(
        default_factory=list
    )

    # Analyze replies independently of Agent 1's labels.
    reply_assessments: list[ReplyEvidenceAssessment] = Field(
        default_factory=list
    )
