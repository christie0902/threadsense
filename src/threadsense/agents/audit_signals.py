
"""Derive resolution and authority signals from validated audits."""

from dataclasses import dataclass

from threadsense.agents.contracts import (
    DecisionEvidenceAudit,
    ReplyContribution,
    ResolutionState,
)
from threadsense.agents.decision_evidence_audit import (
    validate_decision_evidence_audit,
)
from threadsense.agents.thread_interpreter import (
    get_authority_eligible_message_ids,
)
from threadsense.models import Thread


@dataclass(frozen=True)
class AuditSignals:
    suggested_resolution: ResolutionState | None
    authority_answer_candidates: tuple[str, ...]
    needs_additional_reasoning: bool
    rationale: str


ANSWER_TYPES = {
    ReplyContribution.COMPLETE_ANSWER,
    ReplyContribution.PARTIAL_ANSWER,
}


def derive_audit_signals(
    thread: Thread,
    audit: DecisionEvidenceAudit,
) -> AuditSignals:
    """Derive conservative signals from reply classifications."""

    # Never derive signals from structurally invalid evidence.
    validate_decision_evidence_audit(thread, audit)

    if not audit.requested_decisions:
        return AuditSignals(
            suggested_resolution=None,
            authority_answer_candidates=(),
            needs_additional_reasoning=True,
            rationale=(
                "No requested decision identified. "
                "Do not assign a resolution state automatically."
            ),
        )

    answer_ids = [
        item.message_id
        for item in audit.reply_assessments
        if item.contribution in ANSWER_TYPES
    ]

    # No reply was classified as answering the root request.
    if not answer_ids:
        return AuditSignals(
            suggested_resolution=ResolutionState.UNRESOLVED,
            authority_answer_candidates=(),
            needs_additional_reasoning=False,
            rationale=(
                "Every reply was classified as diagnostic, "
                "acknowledgment, or other non-answer. "
                "No substantive answer to the root request was found."
            ),
        )

    # Only substantive-answer candidates may qualify for authority.
    eligible = get_authority_eligible_message_ids(thread)

    candidates = tuple(
        message_id
        for message_id in answer_ids
        if message_id in eligible
    )

    return AuditSignals(
        suggested_resolution=None,
        authority_answer_candidates=candidates,
        needs_additional_reasoning=True,
        rationale=(
            "One or more replies were classified as substantive "
            "answers. Additional reasoning is needed to determine "
            "whether they collectively resolve the entire request."
        ),
    )
