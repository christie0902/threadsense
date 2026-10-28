
from dataclasses import dataclass
from enum import Enum

from threadsense.agents.contracts import TopicAnalysis
from threadsense.legacy.severity_types import SeverityLevel


class ReviewStatus(str, Enum):
    PROVISIONAL = "PROVISIONAL"
    NEEDS_REVIEW = "NEEDS_REVIEW"


@dataclass(frozen=True)
class ReviewScreening:
    candidate_group_id: str
    status: ReviewStatus
    reasons: tuple[str, ...]


def screen_for_review(
    analysis: TopicAnalysis,
    *,
    was_repaired: bool = False,
) -> ReviewScreening:
    """Identify analyses requiring human review."""

    reasons = []

    # 1. Multiple topics may indicate over-splitting.
    if len(analysis.topics) > 1:
        reasons.append(
            "Candidate group was split into multiple topics."
        )

    # 2. Incoherent groups need topic-boundary review.
    if not analysis.is_coherent:
        reasons.append(
            "Agent identified different underlying issues."
        )

    # 3. The agent explicitly requested review.
    if analysis.needs_human_review:
        reasons.append(
            analysis.review_reason or "Agent requested review."
        )

    # 4. Repaired analyses deserve additional scrutiny.
    if was_repaired:
        reasons.append(
            "Analysis required a validation-guided repair."
        )

    # 5. Serious operational risks require TL review.
    if any(
        topic.severity == SeverityLevel.HIGH
        for topic in analysis.topics
    ):
        reasons.append(
            "HIGH severity requires Team Lead review."
        )

    # 6. Detect inconsistent severity/actionability.
    if any(
        topic.severity == SeverityLevel.NOT_APPLICABLE
        and topic.actionable
        for topic in analysis.topics
    ):
        reasons.append(
            "N/A severity conflicts with actionable=True."
        )

    status = (
        ReviewStatus.NEEDS_REVIEW
        if reasons
        else ReviewStatus.PROVISIONAL
    )

    return ReviewScreening(
        candidate_group_id=analysis.candidate_group_id,
        status=status,
        reasons=tuple(reasons),
    )
