"""One source analysis, two prose comparisons at most, and one Agent 1 revision."""

from collections.abc import Callable
import os
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from threadsense.agents.contracts import (
    DecisionEvidenceAudit, SourceEvidenceAnalysis, ProseComparison, ResolutionState, ThreadInterpretation,
    VerificationCategory, VerificationFinding, VerificationOutcome,
)
from threadsense.agents.decision_evidence_audit import (
    validate_decision_evidence_audit, validate_source_analysis,
)
from threadsense.agents.prose_comparison import analyze_source, compare_prose
from threadsense.agents.verification_requests import EvidencePersistenceError, VerificationConfigurationError
from threadsense.agents.interpretation_verifier import verify_interpretation
from threadsense.agents.interpretation_revision import revise_interpretation
from threadsense.agents.thread_interpreter import validate_interpretation_references
from threadsense.models import Thread


INTERPRETATION_FIELDS = [
    "summary", "central_question", "resolution_state", "resolution_rationale",
    "authoritative_response_present", "authority_evidence_message_ids", "confidence",
]


class VerificationPass(BaseModel):
    number: int = Field(ge=1, le=2)
    interpretation: dict[str, Any]
    audit: DecisionEvidenceAudit | None = None
    findings: list[VerificationFinding] = Field(default_factory=list)
    error: str | None = None

    @property
    def passed(self) -> bool:
        return self.audit is not None and not self.findings and self.error is None


class VerificationResult(BaseModel):
    status: VerificationOutcome
    source_analysis: SourceEvidenceAnalysis | None = None
    interpretation: ThreadInterpretation
    original_interpretation: dict[str, Any]
    revised_interpretation: ThreadInterpretation | None = None
    findings: list[VerificationFinding] = Field(default_factory=list)
    passes: list[VerificationPass] = Field(default_factory=list, max_length=2)
    revision_count: int = Field(default=0, ge=0, le=1)
    revision_error: str | None = None
    provisional_fields: list[str] = Field(default_factory=list)
    review_reason: str | None = None
    effective_attempt: Literal["original", "revision", "fallback"] = "original"

    @model_validator(mode="after")
    def check_outcome(self):
        if self.status == VerificationOutcome.NEEDS_REVIEW:
            if not self.review_reason or not self.provisional_fields:
                raise ValueError("NEEDS_REVIEW requires a reason and provisional fields.")
        else:
            if self.source_analysis is None:
                raise ValueError("Passing outcomes require validated source analysis.")
            if self.findings or self.review_reason or self.provisional_fields:
                raise ValueError("Passing outcomes cannot contain unresolved findings.")
            if not self.passes or not self.passes[-1].passed:
                raise ValueError("Passing outcomes require a validated passing audit.")
            for attempt in self.passes:
                if attempt.audit is not None and any(
                    getattr(attempt.audit, key) != getattr(self.source_analysis, key)
                    for key in SourceEvidenceAnalysis.model_fields
                ):
                    raise ValueError("Both passes must reuse the same source analysis.")
            if self.status == VerificationOutcome.VERIFIED:
                if self.revision_count or len(self.passes) != 1 or self.effective_attempt != "original":
                    raise ValueError("VERIFIED must retain the original after one pass.")
            elif (self.revision_count != 1 or len(self.passes) != 2
                  or self.revised_interpretation is None or self.effective_attempt != "revision"):
                raise ValueError("CORRECTED requires one revision and two passes.")
        return self


def _error_text(error: Exception) -> str:
    text = f"{type(error).__name__}: {error}"
    for name in ("OPENAI_API_KEY", "OPENROUTER_API_KEY"):
        key = os.getenv(name, "").strip()
        if key:
            text = text.replace(key, "[redacted]")
    return text[:4000]


def _raw_dict(value: ThreadInterpretation | dict) -> dict:
    return value.model_dump(mode="json") if isinstance(value, ThreadInterpretation) else dict(value)


def _problem(explanation: str) -> VerificationFinding:
    return VerificationFinding(
        category=VerificationCategory.EVIDENCE,
        explanation=explanation,
        disputed_fields=INTERPRETATION_FIELDS,
    )


def _usable(thread: Thread, value: dict) -> ThreadInterpretation | None:
    try:
        interpretation = ThreadInterpretation.model_validate(value)
        validate_interpretation_references(thread, interpretation)
        return interpretation
    except (ValueError, TypeError):
        return None


def retain_for_review(
    thread: Thread, original: ThreadInterpretation | dict, reason: str, *, revision_count: int = 0,
) -> VerificationResult:
    """Retain one consumable record even when validation or processing failed."""
    data = _raw_dict(original)
    interpretation = _usable(thread, data)
    attempt = "original"
    if interpretation is None:
        # Explicitly provisional, never an invented answer or a discarded thread.
        interpretation = ThreadInterpretation(
            thread_id=thread.thread_id,
            summary="Unverified Slack thread: the saved interpretation could not be validated.",
            central_question=None,
            resolution_state=ResolutionState.UNRESOLVED,
            resolution_rationale="Provisional placeholder; the original evidence requires review.",
            confidence=0,
        )
        attempt = "fallback"
    return VerificationResult(
        status=VerificationOutcome.NEEDS_REVIEW,
        interpretation=interpretation,
        original_interpretation=data,
        findings=[_problem(reason)],
        revision_count=revision_count,
        provisional_fields=INTERPRETATION_FIELDS,
        review_reason=reason,
        effective_attempt=attempt,
    )


def verify_and_revise(
    thread: Thread,
    original: ThreadInterpretation | dict,
    *,
    source_analyzer: Callable | None = None,
    comparator: Callable | None = None,
    reviser: Callable | None = None,
    on_raw_output: Callable[[str, str], None] | None = None,
    on_stage_start: Callable[[str], None] | None = None,
    on_artifact: Callable[[str, str, bytes], None] | None = None,
) -> VerificationResult:
    """Reuse source evidence and check every current prose unit afresh; <=4 calls."""
    source_analyzer = source_analyzer or analyze_source
    comparator = comparator or compare_prose
    reviser = reviser or revise_interpretation
    original_data = _raw_dict(original)

    def start_stage(stage):
        if on_stage_start is not None:
            try:
                on_stage_start(stage)
            except Exception as error:
                raise EvidencePersistenceError(_error_text(error)) from error

    def raw_callback(stage):
        def preserve(raw):
            if on_raw_output is not None:
                try:
                    on_raw_output(stage, raw)
                except Exception as error:
                    raise EvidencePersistenceError(_error_text(error)) from error
        return preserve

    def artifact_callback(stage):
        def preserve(name, body):
            if on_artifact is not None:
                try:
                    on_artifact(stage, name, body)
                except Exception as error:
                    raise EvidencePersistenceError(_error_text(error)) from error
        return preserve

    def callbacks(stage):
        return {"on_raw_output": raw_callback(stage), "on_artifact": artifact_callback(stage)}

    try:
        start_stage("source_analysis")
        generated = source_analyzer(thread, **callbacks("source_analysis"))
        source = SourceEvidenceAnalysis.model_validate(
            generated.model_dump() if isinstance(generated, SourceEvidenceAnalysis) else generated
        )
        validate_source_analysis(thread, source)
    except (EvidencePersistenceError, VerificationConfigurationError):
        raise
    except Exception as exc:
        # The unchanged source cannot be repaired by rewriting a candidate.
        return retain_for_review(thread, original_data, "Source analysis unavailable or invalid: " + _error_text(exc))

    def check(candidate: dict, number: int) -> VerificationPass:
        findings = []
        interpretation = None
        error = None
        audit = None
        try:
            interpretation = ThreadInterpretation.model_validate(candidate)
        except (ValueError, TypeError) as exc:
            findings.append(_problem("Invalid interpretation schema: " + _error_text(exc)))
        try:
            start_stage(f"prose_{number}")
            generated = comparator(thread, interpretation=candidate, **callbacks(f"prose_{number}"))
            comparison = ProseComparison.model_validate(
                generated.model_dump() if isinstance(generated, ProseComparison) else generated
            )
            audit = DecisionEvidenceAudit(
                **source.model_dump(), **comparison.model_dump(), interpretation_findings=[],
            )
            validate_decision_evidence_audit(thread, audit, candidate)
        except (EvidencePersistenceError, VerificationConfigurationError):
            raise
        except Exception as exc:
            audit = None
            error = _error_text(exc)
            findings.append(_problem("Independent evidence audit unavailable or invalid: " + error))
        if interpretation is not None:
            try:
                findings.extend(verify_interpretation(thread, interpretation, audit))
            except Exception as exc:
                error = _error_text(exc)
                findings.append(_problem("Deterministic verification failed: " + error))
        return VerificationPass(
            number=number, interpretation=candidate, audit=audit, findings=findings, error=error,
        )

    first = check(original_data, 1)
    if first.passed:
        return VerificationResult(
            status=VerificationOutcome.VERIFIED, source_analysis=source,
            interpretation=ThreadInterpretation.model_validate(original_data),
            original_interpretation=original_data,
            passes=[first],
        )

    try:
        previous = ThreadInterpretation.model_validate(original_data)
    except (ValueError, TypeError):
        previous = original_data
    try:
        start_stage("revision_1")
        revised = reviser(
            thread, previous, first.findings, source.model_copy(deep=True),
            **callbacks("revision_1"),
        )
        revised = ThreadInterpretation.model_validate(
            revised.model_dump() if isinstance(revised, ThreadInterpretation) else revised
        )
    except (EvidencePersistenceError, VerificationConfigurationError):
        raise
    except Exception as exc:
        error = _error_text(exc)
        result = retain_for_review(
            thread, original_data, "The single targeted revision failed: " + error,
            revision_count=1,
        )
        result.source_analysis = source
        result.passes = [first]
        result.findings = [*first.findings, *result.findings]
        result.revision_error = error
        return result

    second = check(revised.model_dump(mode="json"), 2)
    if second.passed:
        return VerificationResult(
            status=VerificationOutcome.CORRECTED, source_analysis=source,
            interpretation=revised,
            original_interpretation=original_data,
            revised_interpretation=revised,
            passes=[first, second],
            revision_count=1,
            effective_attempt="revision",
        )

    def disputed_fields(findings):
        return sorted({field for item in findings for field in item.disputed_fields}) or INTERPRETATION_FIELDS

    # Prefer structural validity, then fewer disputed fields. Ties preserve
    # the original; model confidence is never a selection score.
    old_usable = _usable(thread, original_data)
    new_usable = _usable(thread, second.interpretation)
    prefer_revision = new_usable is not None and (
        old_usable is None or (
            second.audit is not None
            and len(disputed_fields(second.findings)) < len(disputed_fields(first.findings))
        )
    )
    chosen_pass = second if prefer_revision else first
    chosen = new_usable if prefer_revision else old_usable
    reason = "Still unverified after one targeted revision: " + "; ".join(
        finding.explanation for finding in second.findings
    )
    if chosen is None:
        result = retain_for_review(thread, original_data, reason, revision_count=1)
        result.source_analysis = source
        result.passes = [first, second]
        result.revised_interpretation = revised
        return result
    return VerificationResult(
        status=VerificationOutcome.NEEDS_REVIEW, source_analysis=source,
        interpretation=chosen,
        original_interpretation=original_data,
        revised_interpretation=revised,
        passes=[first, second],
        findings=chosen_pass.findings,
        revision_count=1,
        provisional_fields=disputed_fields(
            chosen_pass.findings if prefer_revision else [*first.findings, *second.findings]
        ),
        review_reason=reason,
        effective_attempt="revision" if prefer_revision else "original",
    )
