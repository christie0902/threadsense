
from enum import Enum
from pydantic import BaseModel, Field


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

    severity: str
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
