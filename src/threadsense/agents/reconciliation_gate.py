
"""Screen reconciliation proposals before downstream use."""

from dataclasses import dataclass
from enum import Enum

from threadsense.agents.contracts import ThreadInterpretation
from threadsense.agents.audit_reconciliation import (
    ReconciliationDraft,
    correct_known_terminology,
)
from threadsense.agents.interpretation_verifier import (
    find_glossary_conflicts,
)
from threadsense.agents.thread_interpreter import (
    validate_interpretation_references,
)
from threadsense.models import Thread


class ReconciliationGateStatus(str, Enum):
    SAFE_TERMINOLOGY_PATCH = "SAFE_TERMINOLOGY_PATCH"
    SEMANTIC_CHECK_REQUIRED = "SEMANTIC_CHECK_REQUIRED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    NO_DISCREPANCIES = "NO_DISCREPANCIES"


@dataclass(frozen=True)
class ReconciliationGateResult:
    thread_id: str
    status: ReconciliationGateStatus
    rationale: str


def screen_reconciliation(
    thread: Thread,
    original: ThreadInterpretation,
    draft: ReconciliationDraft,
) -> ReconciliationGateResult:
    """Evaluate whether proposed changes require further checking."""

    if (
        thread.thread_id != original.thread_id
        or draft.thread_id != thread.thread_id
    ):
        raise ValueError("Thread IDs do not match.")

    def result(status, rationale):
        return ReconciliationGateResult(
            thread_id=thread.thread_id,
            status=status,
            rationale=rationale,
        )

    if draft.status == "NO_DISCREPANCIES_DETECTED":
        return result(
            ReconciliationGateStatus.NO_DISCREPANCIES,
            "No discrepancy detected. This is not proof of accuracy.",
        )

    if draft.status == "NEEDS_REVIEW":
        return result(
            ReconciliationGateStatus.NEEDS_REVIEW,
            "The reconciliation process could not produce "
            "a reliable correction.",
        )

    if draft.status != "PROPOSED_NOT_VERIFIED":
        raise ValueError(f"Unknown draft status: {draft.status}")

    proposed = draft.proposed_interpretation

    if proposed is None:
        raise ValueError("Correction proposal is missing.")

    validate_interpretation_references(thread, proposed)

    if find_glossary_conflicts(proposed):
        return result(
            ReconciliationGateStatus.NEEDS_REVIEW,
            "The proposed correction still contains known "
            "terminology conflicts.",
        )

    original_data = original.model_dump(mode="python")
    proposed_data = proposed.model_dump(mode="python")

    actual_changes = tuple(
        field
        for field in original_data
        if original_data[field] != proposed_data[field]
    )

    if actual_changes != draft.changed_fields:
        raise ValueError(
            "Draft changed_fields does not match the proposal."
        )

    # Reconstruct the ONLY changes permitted for a safe
    # deterministic terminology patch.
    expected_data = original.model_dump(mode="python")

    for field in (
        "summary",
        "central_question",
        "resolution_rationale",
    ):
        if expected_data[field] is not None:
            expected_data[field] = correct_known_terminology(
                expected_data[field]
            )

    expected = ThreadInterpretation.model_validate(
        expected_data
    )

    if (
        set(draft.discrepancy_categories) == {"TERMINOLOGY"}
        and proposed == expected
        and actual_changes
    ):
        return result(
            ReconciliationGateStatus.SAFE_TERMINOLOGY_PATCH,
            "Only approved deterministic terminology replacements "
            "were made. Other interpretation fields remain unchanged.",
        )

    return result(
        ReconciliationGateStatus.SEMANTIC_CHECK_REQUIRED,
        "The proposal changes meaning, resolution, authority, "
        "or other fields requiring independent verification.",
    )
