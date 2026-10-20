
"""Produce conservative interpretation corrections from audit evidence."""

import re
from dataclasses import dataclass

from threadsense.agents.contracts import (
    DecisionEvidenceAudit,
    ResolutionState,
    ThreadInterpretation,
)
from threadsense.agents.audit_comparison import (
    compare_interpretation_with_audit,
)
from threadsense.agents.audit_signals import derive_audit_signals
from threadsense.agents.interpretation_verifier import (
    find_glossary_conflicts,
)
from threadsense.agents.thread_interpreter import (
    validate_interpretation_references,
)
from threadsense.models import Thread
from threadsense.terminology import get_terms


@dataclass(frozen=True)
class ReconciliationDraft:
    thread_id: str
    status: str
    proposed_interpretation: ThreadInterpretation | None
    changed_fields: tuple[str, ...]
    discrepancy_categories: tuple[str, ...]


def correct_known_terminology(text: str) -> str:
    """Correct only recognized, explicit incorrect QN expansions."""

    if str(get_terms().get("QN", "")).strip().lower() != "quarantine":
        return text

    text = re.sub(
        r"\bQN\s*\(\s*quality (?:note|issue)\s*\)",
        "QN (Quarantine)",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"\bquality (?:note|issue)\s*\(\s*QN\s*\)",
        "Quarantine (QN)",
        text,
        flags=re.IGNORECASE,
    )

    return text


def propose_reconciliation(
    thread: Thread,
    original: ThreadInterpretation,
    audit: DecisionEvidenceAudit,
) -> ReconciliationDraft:
    """Build an evidence-based correction without approving it."""

    comparison = compare_interpretation_with_audit(
        thread, original, audit
    )

    signals = derive_audit_signals(thread, audit)

    categories = tuple(sorted({
        finding.category.value
        for finding in comparison.findings
    }))

    if not comparison.needs_reconciliation:
        return ReconciliationDraft(
            thread_id=thread.thread_id,
            status="NO_DISCREPANCIES_DETECTED",
            proposed_interpretation=None,
            changed_fields=(),
            discrepancy_categories=(),
        )

    data = original.model_dump(mode="python")

    # 1. Correct explicit, known terminology errors.
    if "TERMINOLOGY" in categories:
        for field in (
            "summary",
            "central_question",
            "resolution_rationale",
        ):
            if data[field] is not None:
                data[field] = correct_known_terminology(
                    data[field]
                )

    # 2. Apply the conservative no-answer finding.
    # This is a PROPOSAL based on an LLM audit, not ground truth.
    if (
        signals.suggested_resolution == ResolutionState.UNRESOLVED
        and not signals.needs_additional_reasoning
    ):
        data["resolution_state"] = ResolutionState.UNRESOLVED
        data["authority_evidence_message_ids"] = []
        data["authoritative_response_present"] = False

        if "RESOLUTION" in categories or "AUTHORITY" in categories:
            data["resolution_rationale"] = (
                "The replies provide diagnostic or contextual "
                "information, but no substantive guidance "
                "answers the decision requested in the root message."
            )

    # 3. Revalidate the proposed interpretation.
    proposed = ThreadInterpretation.model_validate(data)
    validate_interpretation_references(thread, proposed)

    # Never release a proposal with remaining known glossary errors.
    if find_glossary_conflicts(proposed):
        return ReconciliationDraft(
            thread_id=thread.thread_id,
            status="NEEDS_REVIEW",
            proposed_interpretation=None,
            changed_fields=(),
            discrepancy_categories=categories,
        )

    original_data = original.model_dump(mode="python")
    proposed_data = proposed.model_dump(mode="python")

    changes = tuple(
        field
        for field in original_data
        if original_data[field] != proposed_data[field]
    )

    if not changes:
        return ReconciliationDraft(
            thread_id=thread.thread_id,
            status="NEEDS_REVIEW",
            proposed_interpretation=None,
            changed_fields=(),
            discrepancy_categories=categories,
        )

    return ReconciliationDraft(
        thread_id=thread.thread_id,
        status="PROPOSED_NOT_VERIFIED",
        proposed_interpretation=proposed,
        changed_fields=changes,
        discrepancy_categories=categories,
    )
