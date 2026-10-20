
"""Compare Agent 1 interpretations with independent audit evidence."""

from dataclasses import dataclass

from threadsense.agents.contracts import (
    DecisionEvidenceAudit,
    ThreadInterpretation,
    VerificationCategory,
    VerificationFinding,
    ResolutionState,
)
from threadsense.agents.audit_signals import (
    derive_audit_signals,
)
from threadsense.agents.interpretation_verifier import (
    find_glossary_conflicts,
)
from threadsense.models import Thread


@dataclass(frozen=True)
class AuditComparison:
    thread_id: str
    findings: tuple[VerificationFinding, ...]
    suggested_resolution: ResolutionState | None

    @property
    def needs_reconciliation(self) -> bool:
        return bool(self.findings)


def compare_interpretation_with_audit(
    thread: Thread,
    interpretation: ThreadInterpretation,
    audit: DecisionEvidenceAudit,
) -> AuditComparison:
    """Identify differences without modifying Agent 1 output."""

    if interpretation.thread_id != thread.thread_id:
        raise ValueError("Interpretation thread ID mismatch.")

    # This also validates the audit's references and quotes.
    signals = derive_audit_signals(thread, audit)

    findings = []

    # 1. Terminology consistency
    conflicts = find_glossary_conflicts(interpretation)

    for conflict in conflicts:
        findings.append(
            VerificationFinding(
                category=VerificationCategory.TERMINOLOGY,
                explanation=conflict,
                evidence_message_ids=[],
            )
        )

    # 2. Resolution consistency
    if (
        signals.suggested_resolution is not None
        and interpretation.resolution_state
        != signals.suggested_resolution
    ):
        findings.append(
            VerificationFinding(
                category=VerificationCategory.RESOLUTION,
                explanation=(
                    f"Agent 1 classified this thread as "
                    f"{interpretation.resolution_state.value}, "
                    f"but the independent audit suggests "
                    f"{signals.suggested_resolution.value}. "
                    f"{signals.rationale}"
                ),
                evidence_message_ids=[
                    item.message_id
                    for item in audit.reply_assessments
                ],
            )
        )

    # 3. Authority consistency
    # Only make this comparison when the audit found
    # no substantive answer and needs no extra reasoning.
    if not signals.needs_additional_reasoning:
        unsupported = (
            set(interpretation.authority_evidence_message_ids)
            - set(signals.authority_answer_candidates)
        )

        if unsupported:
            findings.append(
                VerificationFinding(
                    category=VerificationCategory.AUTHORITY,
                    explanation=(
                        "Agent 1 cited authoritative answer evidence, "
                        "but the independent audit classified these "
                        "replies as non-answers to the root request."
                    ),
                    evidence_message_ids=sorted(unsupported),
                )
            )

    return AuditComparison(
        thread_id=thread.thread_id,
        findings=tuple(findings),
        suggested_resolution=signals.suggested_resolution,
    )
