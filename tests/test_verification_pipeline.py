"""Bounded verification against independently reviewed, visible Slack evidence.

All model operations are injected fakes. These tests establish orchestration and
domain rules; they do not claim that a mocked audit proves free-text fidelity.
"""

from copy import deepcopy
from functools import lru_cache
import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from threadsense.adapters.mock_slack import MockSlackAdapter
from threadsense.agents.contracts import DecisionEvidenceAudit, SourceEvidenceAnalysis, ProseComparison, ThreadInterpretation, VerificationFinding
from threadsense.agents.decision_evidence_audit import build_prose_units, validate_decision_evidence_audit
from threadsense.agents.verification_pipeline import verify_and_revise


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "data/fixtures/slack_generated"
REGRESSIONS = (
    "1790915374.000127",
    "1790882197.000111",
    "1790909920.000138",
    "1790903186.000110",
)


@pytest.fixture(scope="module")
def cases():
    adapter = MockSlackAdapter(
        fixture_dir=str(FIXTURES / "channels"),
        users_file=str(FIXTURES / "users.json"),
    )
    threads = {
        thread.thread_id: thread
        for channel in ("C_AUDIO_GENERAL", "C_AUDIO_QA")
        for thread in adapter.get_threads(channel)
        if thread.thread_id in REGRESSIONS
    }
    records = json.loads(
        (ROOT / "data/processed/agent1_authority_fix/interpretations.json").read_text(
            encoding="utf-8"
        )
    )
    originals = {
        row["thread_id"]: ThreadInterpretation.model_validate(row["interpretation"])
        for row in records
        if row["thread_id"] in REGRESSIONS
    }
    return threads, originals


def reviewed_audit(thread, candidate):
    """Explicit expectations reviewed against raw messages, never hidden labels."""
    tid = thread.thread_id
    classifications = {
        "1790915374.000127": ["OTHER", "DIAGNOSTIC_ONLY"],
        "1790882197.000111": ["DIAGNOSTIC_ONLY"] * 3,
        "1790909920.000138": ["PARTIAL_ANSWER", "COMPLETE_ANSWER"],
        "1790903186.000110": ["DIAGNOSTIC_ONLY"],
    }
    question = {
        "1790915374.000127": "Should the silent clip be quarantined or given a quality score?",
        "1790882197.000111": "Should the task be quarantined when the player never loads?",
        "1790909920.000138": "Should the omission be classified as an audio or transcript error?",
        "1790903186.000110": "Can QA clarify the waveform loading without playback?",
    }[tid]
    root = next(message for message in thread.messages if message.message_id == tid)
    replies = [message for message in thread.messages if message.message_id != tid]
    answered = tid == "1790909920.000138"
    return DecisionEvidenceAudit.model_validate({
        "thread_id": tid,
        "root_request_quote": root.text,
        "requested_decisions": [question],
        "reply_assessments": [
            {
                "message_id": message.message_id,
                "contribution": contribution,
                "evidence_quote": message.text,
                "explanation": (
                    "Substantive classification guidance for the original request."
                    if contribution in {"COMPLETE_ANSWER", "PARTIAL_ANSWER"}
                    else "Context or investigation does not decide the original request."
                ),
            }
            for message, contribution in zip(replies, classifications[tid])
        ],
        "decision_coverage": [{
            "requested_decision": question,
            "status": "ANSWERED" if answered else "UNANSWERED",
            "answer_message_ids": ["1790910023.000226"] if answered else [],
            "rationale": "Direct classification supplied." if answered else "No requested decision supplied.",
        }],
        "interpretation_findings": [],
        "uncertainties": [],
        "prose_assessments": reviewed_prose_assessments(thread, candidate),
    })


def corrected_interpretation(original):
    data = original.model_dump(mode="json")
    if original.thread_id == "1790915374.000127":
        data["summary"] = data["summary"].replace("QN (quality note)", "QN (Quarantine)")
    elif original.thread_id == "1790882197.000111":
        data["summary"] = (
            "Yuki asks whether to quarantine (QN) because the player never loads, "
            "recalling a possible workaround from the previous queue. Mina asks "
            "whether another clip plays; Tariq requests the Label Tool (LT) error "
            "state and time; Priya requests task IDs and reproduction evidence. "
            "Neither quarantine handling nor applicability of the old workaround is decided."
        )
        data["resolution_state"] = "UNRESOLVED"
        data["authoritative_response_present"] = False
        data["authority_evidence_message_ids"] = []
        data["resolution_rationale"] = (
            "All three replies gather evidence; none answers whether to quarantine the task."
        )
    elif original.thread_id == "1790909920.000138":
        # The protected baseline reverses which artifact is missing the sentence.
        # An accurate fixture must not bless that independent summary discrepancy.
        data["summary"] = (
            "Avery asks how to classify an omission. Jordan says a sentence in the "
            "reference text is missing from the recording. Hana directs the team "
            "to record a transcript/audio correspondence error, not playback failure."
        )
    return ThreadInterpretation.model_validate(data)


@lru_cache(maxsize=1)
def reviewed_originals():
    """Only the visible frozen inputs used by these four regression cases."""
    records = json.loads((ROOT / "data/processed/agent1_authority_fix/interpretations.json").read_text(encoding="utf-8"))
    return {row["thread_id"]: ThreadInterpretation.model_validate(row["interpretation"])
            for row in records if row["thread_id"] in REGRESSIONS}


def reviewed_prose_assessments(thread, candidate):
    """Explicit sentence-level judgments, reviewed against the original messages.

    Only the saved and deliberately corrected prose variants below are accepted.
    Changing a candidate's text requires changing its reviewed expectations;
    there is no fallback that labels arbitrary or incorrect prose SUPPORTED.
    """
    original = reviewed_originals()[thread.thread_id]
    corrected = corrected_interpretation(original)
    # unit_id -> (verdict, source message indexes, reviewed source meaning).
    checks = {
        "1790903186.000110": {
            "summary:1": ("SUPPORTED", [0], "Leo asks about a waveform loading while playback does not start."),
            "summary:2": ("SUPPORTED", [1], "Mina requests task/browser/audio-loading evidence and warns that spinning does not reveal content."),
            "central_question:1": ("SUPPORTED", [0], "The root asks QA to clarify the waveform-without-playback case."),
            "resolution_rationale:1": ("SUPPORTED", [0, 1], "The sole reply requests diagnostics rather than answering the root request."),
            "resolution_rationale:2": ("SUPPORTED", [1], "Mina seeks information without providing a resolution."),
        },
        "1790915374.000127": {
            "summary:1": ("UNSUPPORTED", [0], "The root asks about Quarantine (QN) versus a quality score; QN does not mean quality note in the official glossary."),
            "summary:2": ("SUPPORTED", [1], "Carla reports empty-sounding files from prompts expecting speech."),
            "summary:3": ("SUPPORTED", [2], "Linh asks whether silence persists after checking volume and a second clip."),
            "central_question:1": ("SUPPORTED", [0], "The reported clip is silent despite a waveform."),
            "central_question:2": ("SUPPORTED", [0], "The requested choice is Quarantine versus a quality score."),
            "resolution_rationale:1": ("SUPPORTED", [0, 1, 2], "Neither reply decides whether to quarantine or score the clip."),
            "resolution_rationale:2": ("SUPPORTED", [1, 2], "The replies offer context and diagnostic questions, not a decision."),
        },
        "1790882197.000111": {
            "summary:1": ("UNSUPPORTED", [0], "Yuki recalls a possible workaround, but does not establish that it failed; QN means Quarantine, not quality issue."),
            "summary:2": ("SUPPORTED", [1], "Mina asks whether another clip plays and notes that a spinning player does not establish audio content."),
            "summary:3": ("SUPPORTED", [2], "Tariq requests the Label Tool error state and time, with the wider cause unconfirmed."),
            "summary:4": ("SUPPORTED", [3], "Priya requests task IDs and reproduction before deciding whether the old workaround applies."),
            "central_question:1": ("SUPPORTED", [0], "Yuki asks whether to quarantine because the player never loads."),
            "resolution_rationale:1": ("SUPPORTED", [1, 2], "The replies suggest checking another clip and gathering the error state."),
            "resolution_rationale:2": ("UNSUPPORTED", [0, 3], "The quarantine decision remains open; the source does not redefine QN as a quality issue."),
        },
        "1790909920.000138": {
            "summary:1": ("SUPPORTED", [0], "Avery asks how to score an audio omission versus a transcript-field error."),
            "summary:2": ("CONTRADICTED", [1], "The sentence is present in the reference text and missing from the recording, not missing from the reference text."),
            "summary:3": ("SUPPORTED", [2], "Hana directs a transcript/audio correspondence error rather than playback failure."),
            "central_question:1": ("SUPPORTED", [0], "The candidate preserves Avery's classification question."),
            "resolution_rationale:1": ("SUPPORTED", [2], "Hana explicitly supplies the classification to record."),
            "resolution_rationale:2": ("SUPPORTED", [0, 2], "Hana's item-specific classification answers the requested choice."),
        },
    }[thread.thread_id]
    revised_checks = {
        "1790915374.000127": {
            "summary:1": ("SUPPORTED", [0], "The corrected expansion is Quarantine; the silent-clip question is preserved."),
        },
        "1790882197.000111": {
            "summary:1": ("SUPPORTED", [0], "Yuki asks about Quarantine and recalls only a possible earlier workaround."),
            "summary:2": ("SUPPORTED", [1, 2, 3], "All three replies gather playback, error-state, and reproduction evidence."),
            "summary:3": ("SUPPORTED", [0, 1, 2, 3], "Neither quarantine handling nor applicability of the old workaround is decided."),
            "resolution_rationale:1": ("SUPPORTED", [1, 2, 3], "All replies gather evidence; none supplies the quarantine decision."),
        },
        "1790909920.000138": {
            "summary:1": ("SUPPORTED", [0], "Avery asks how to classify an omission."),
            "summary:2": ("SUPPORTED", [1], "The revised summary preserves that the reference has a sentence missing from the recording."),
            "summary:3": ("SUPPORTED", [2], "The revised summary preserves Hana's correspondence-error guidance."),
        },
    }.get(thread.thread_id, {})
    original_units = {unit["unit_id"]: unit for unit in build_prose_units(original)}
    corrected_units = {unit["unit_id"]: unit for unit in build_prose_units(corrected)}
    assert set(checks) == set(original_units)
    assessments = []
    for unit in build_prose_units(candidate):
        unit_id, text = unit["unit_id"], unit["candidate_text"]
        if unit_id in original_units and text == original_units[unit_id]["candidate_text"]:
            verdict, indexes, meaning = checks[unit_id]
        else:
            assert unit_id in corrected_units and text == corrected_units[unit_id]["candidate_text"], (
                "Missing reviewed expectation for candidate prose", thread.thread_id, unit,
            )
            verdict, indexes, meaning = revised_checks[unit_id]
        assessments.append({
            "unit_id": unit_id, "candidate_text": text, "verdict": verdict,
            "source_interpretation": meaning, "explanation": meaning,
            "evidence_message_ids": [thread.messages[index].message_id for index in indexes],
            "evidence_quotes": [thread.messages[index].text for index in indexes],
        })
    return assessments


def reviewed_source(thread):
    audit = reviewed_audit(thread, reviewed_originals()[thread.thread_id])
    return SourceEvidenceAnalysis.model_validate({
        key: value for key, value in audit.model_dump().items() if key in SourceEvidenceAnalysis.model_fields
    })


def reviewed_comparison(thread, candidate):
    return ProseComparison(prose_assessments=reviewed_audit(thread, candidate).prose_assessments)


@pytest.fixture(autouse=True)
def inject_reviewed_source(monkeypatch):
    monkeypatch.setattr("threadsense.agents.verification_pipeline.analyze_source",
                        lambda thread, **kwargs: reviewed_source(thread))


@pytest.mark.parametrize("tid", ["1790903186.000110", "1790909920.000138"])
def test_accurate_interpretation_passes_unchanged_and_skips_revision(cases, tid):
    threads, originals = cases
    original = corrected_interpretation(originals[tid])
    auditor = Mock(return_value=reviewed_comparison(threads[tid], original))
    reviser = Mock(side_effect=AssertionError("A passing interpretation needs no revision"))

    result = verify_and_revise(threads[tid], original, comparator=auditor, reviser=reviser)

    assert result.status == "VERIFIED"
    assert result.interpretation == original
    assert result.original_interpretation == original.model_dump(mode="json")
    assert result.revision_count == 0
    assert result.effective_attempt == "original"
    assert len(result.passes) == 1
    assert not result.findings
    assert not result.provisional_fields
    assert not result.review_reason
    assert auditor.call_count == 1
    reviser.assert_not_called()


def test_terminology_revision_preserves_correct_fields(cases):
    threads, originals = cases
    tid = "1790915374.000127"
    original = originals[tid]
    corrected = corrected_interpretation(original)
    audit = reviewed_comparison(threads[tid], original)
    auditor = Mock(side_effect=[audit, reviewed_comparison(threads[tid], corrected)])

    def revise(thread, previous, findings, evidence_audit, *, on_raw_output=None, on_artifact=None):
        assert thread == threads[tid]
        assert previous == original
        assert evidence_audit == reviewed_source(thread)
        # The deterministic terminology finding remains; the new prose contract
        # also flags that same incorrect expansion in its summary assessment.
        assert {finding.category.value for finding in findings} == {"TERMINOLOGY", "SUMMARY"}
        assert any("Quarantine" in finding.explanation for finding in findings)
        return corrected

    reviser = Mock(side_effect=revise)
    result = verify_and_revise(threads[tid], original, comparator=auditor, reviser=reviser)

    assert result.status == "CORRECTED"
    assert result.interpretation == corrected
    assert result.revised_interpretation == corrected
    assert result.effective_attempt == "revision"
    assert result.revision_count == 1
    assert len(result.passes) == 2
    assert auditor.call_count == 2
    assert reviser.call_count == 1
    original_fields = original.model_dump(exclude={"summary"})
    assert corrected.model_dump(exclude={"summary"}) == original_fields
    assert not result.findings


def test_wrong_resolution_and_authority_receive_specific_evidence_feedback(cases):
    threads, originals = cases
    tid = "1790882197.000111"
    original = originals[tid]
    audit = reviewed_comparison(threads[tid], original)
    corrected = corrected_interpretation(original)

    def revise(thread, previous, findings, evidence_audit, *, on_raw_output=None, on_artifact=None):
        categories = {finding.category.value for finding in findings}
        assert {"TERMINOLOGY", "RESOLUTION", "AUTHORITY"} <= categories
        assert any("UNRESOLVED" in finding.explanation for finding in findings)
        assert any("1790882343.000339" in finding.evidence_message_ids for finding in findings)
        assert evidence_audit == reviewed_source(thread)
        assert previous == original
        return corrected

    result = verify_and_revise(
        threads[tid], original,
        comparator=Mock(side_effect=[audit, reviewed_comparison(threads[tid], corrected)]),
        reviser=Mock(side_effect=revise)
    )

    assert result.status == "CORRECTED"
    assert result.interpretation.resolution_state == "UNRESOLVED"
    assert not result.interpretation.authoritative_response_present
    assert result.interpretation.authority_evidence_message_ids == []
    assert len(result.passes) == 2
    assert result.passes[0].findings
    assert not result.passes[1].findings


def test_answered_thread_summary_inversion_is_corrected_without_losing_endorsement(cases):
    threads, originals = cases
    tid = "1790909920.000138"
    thread = threads[tid]
    original = originals[tid]
    corrected = corrected_interpretation(original)
    source = next(message for message in thread.messages if message.message_id == "1790909965.000113")
    finding = VerificationFinding(
        category="SUMMARY",
        explanation=(
            "The summary says the sentence is missing from the reference text, "
            "but Jordan says it is missing from the recording."
        ),
        evidence_message_ids=[source.message_id],
        evidence_quotes=[source.text],
        disputed_fields=["summary"],
    )
    first = reviewed_comparison(thread, original)
    second = reviewed_comparison(thread, corrected)
    auditor = Mock(side_effect=[first, second])

    def revise(current_thread, previous, findings, audit, *, on_raw_output=None, on_artifact=None):
        assert current_thread == thread
        assert previous == original
        assert any(item.category == finding.category and item.evidence_quotes == finding.evidence_quotes
                   and item.disputed_fields == finding.disputed_fields for item in findings)
        assert audit == reviewed_source(thread)
        return corrected

    result = verify_and_revise(thread, original, comparator=auditor, reviser=Mock(side_effect=revise))

    assert result.status == "CORRECTED"
    assert result.interpretation == corrected
    assert result.interpretation.resolution_state == "RESOLVED_IN_THREAD"
    assert result.interpretation.authority_evidence_message_ids == ["1790910023.000226"]
    assert result.interpretation.model_dump(exclude={"summary"}) == original.model_dump(exclude={"summary"})
    assert auditor.call_count == 2
    # The new contract produces the same specific discrepancy from the prose unit.
    # Legacy explicit findings remain validated separately by verifier tests.
    assert result.passes[0].error is None
    assert len(result.passes[0].findings) == 1
    prose_finding = result.passes[0].findings[0]
    assert prose_finding.category == "SUMMARY"
    assert prose_finding.disputed_fields == ["summary"]
    assert "summary:2: CONTRADICTED" in prose_finding.explanation
    assert prose_finding.evidence_message_ids == [source.message_id]
    assert prose_finding.evidence_quotes == [source.text]
    assert not result.passes[1].findings


def test_failed_second_verification_stops_after_one_revision(cases):
    threads, originals = cases
    tid = "1790882197.000111"
    original = originals[tid]
    auditor = Mock(side_effect=[reviewed_comparison(threads[tid], original),
                               reviewed_comparison(threads[tid], original)])
    reviser = Mock(return_value=original.model_copy(deep=True))

    result = verify_and_revise(threads[tid], original, comparator=auditor, reviser=reviser)

    assert result.status == "NEEDS_REVIEW"
    assert result.interpretation.thread_id == tid
    assert result.review_reason
    assert result.findings
    assert {"resolution_state", "authority_evidence_message_ids"} <= set(result.provisional_fields)
    assert result.revision_count == 1
    assert len(result.passes) == 2
    assert auditor.call_count == 2
    assert reviser.call_count == 1


def test_second_pass_compares_revised_prose_afresh_and_detects_new_uncertainty(cases):
    threads, originals = cases
    tid = "1790915374.000127"
    corrected = corrected_interpretation(originals[tid])
    first = reviewed_comparison(threads[tid], originals[tid])
    uncertain = reviewed_comparison(threads[tid], corrected).model_copy(deep=True)
    uncertain.prose_assessments[0].verdict = "UNCERTAIN"
    uncertain.prose_assessments[0].explanation = "The revised wording remains ambiguous."
    auditor = Mock(side_effect=[first, uncertain])
    result = verify_and_revise(
        threads[tid], originals[tid], comparator=auditor, reviser=Mock(return_value=corrected)
    )

    assert result.status == "NEEDS_REVIEW"
    assert result.review_reason
    assert auditor.call_count == 2
    for call, candidate in zip(auditor.call_args_list, [originals[tid], corrected]):
        assert call.args == (threads[tid],)
        assert ThreadInterpretation.model_validate(call.kwargs["interpretation"]) == candidate
        assert not {"previous_audit", "audit", "findings", "previous_findings"} & set(call.kwargs)
    assert result.revision_count == 1
    assert all(item.error is None for item in result.passes)
    assert any("UNCERTAIN" in finding.explanation for finding in result.passes[1].findings)


def test_revision_with_invalid_evidence_does_not_replace_better_original(cases):
    threads, originals = cases
    tid = "1790915374.000127"
    original = originals[tid]
    revised = corrected_interpretation(original).model_copy(update={
        "authority_evidence_message_ids": ["fabricated-message"],
        "authoritative_response_present": True,
    })
    result = verify_and_revise(
        threads[tid], original,
        comparator=Mock(side_effect=[reviewed_comparison(threads[tid], original), reviewed_comparison(threads[tid], revised)]),
        reviser=Mock(return_value=revised),
    )

    assert result.status == "NEEDS_REVIEW"
    assert result.interpretation == original
    assert result.effective_attempt == "original"
    assert result.revision_count == 1
    assert result.review_reason
    assert result.passes[1].error is None
    assert any("fabricated-message" in finding.explanation for finding in result.passes[1].findings)


@pytest.mark.parametrize("failure", [RuntimeError("Model unavailable"), ValueError("Invalid model JSON")])
def test_revision_failure_preserves_original_and_flags_review(cases, failure):
    threads, originals = cases
    tid = "1790882197.000111"
    auditor = Mock(return_value=reviewed_comparison(threads[tid], originals[tid]))
    reviser = Mock(side_effect=failure)

    result = verify_and_revise(threads[tid], originals[tid], comparator=auditor, reviser=reviser)

    assert result.status == "NEEDS_REVIEW"
    assert result.interpretation == originals[tid]
    assert result.revision_error
    assert result.review_reason
    assert result.revision_count == 1
    assert reviser.call_count == 1
    assert auditor.call_count <= 2


@pytest.mark.parametrize("malformed", [None, {"thread_id": "wrong"}, "not an interpretation"])
def test_malformed_revision_cannot_discard_thread(cases, malformed):
    threads, originals = cases
    tid = "1790915374.000127"
    result = verify_and_revise(
        threads[tid], originals[tid], comparator=Mock(return_value=reviewed_comparison(threads[tid], originals[tid])),
        reviser=Mock(return_value=malformed),
    )
    assert result.status == "NEEDS_REVIEW"
    assert result.interpretation.thread_id == tid
    assert result.interpretation == originals[tid]
    assert result.revision_count == 1
    assert result.review_reason


def test_audit_failures_are_retained_and_correction_is_attempted(cases):
    threads, originals = cases
    tid = "1790903186.000110"
    auditor = Mock(side_effect=ValueError("Auditor response was not valid JSON"))
    reviser = Mock(return_value=originals[tid])

    result = verify_and_revise(threads[tid], originals[tid], comparator=auditor, reviser=reviser)

    assert result.status == "NEEDS_REVIEW"
    assert result.interpretation == originals[tid]
    assert result.review_reason
    assert result.revision_count == 1
    assert reviser.call_count == 1
    assert auditor.call_count == 2
    assert all(item.error or item.findings for item in result.passes)


@pytest.mark.parametrize("missing_response", [None, "", {}])
def test_missing_audit_response_cannot_pass_structural_checks_alone(cases, missing_response):
    threads, originals = cases
    tid = "1790903186.000110"
    auditor = Mock(return_value=missing_response)
    reviser = Mock(return_value=originals[tid])
    result = verify_and_revise(threads[tid], originals[tid], comparator=auditor, reviser=reviser)

    assert result.status == "NEEDS_REVIEW"
    assert result.interpretation.thread_id == tid
    assert result.review_reason
    assert reviser.call_count == 1
    assert auditor.call_count == 2


def test_structurally_invalid_audit_object_cannot_verify_accurate_interpretation(cases):
    threads, originals = cases
    tid = "1790903186.000110"
    source = reviewed_source(threads[tid]).model_copy(deep=True)
    source.reply_assessments[0].evidence_quote = "The issue has been resolved."
    analyzer = Mock(return_value=source)
    comparator, reviser = Mock(), Mock()
    result = verify_and_revise(
        threads[tid], originals[tid], source_analyzer=analyzer,
        comparator=comparator, reviser=reviser,
    )
    assert result.status == "NEEDS_REVIEW"
    assert "Evidence quote does not match" in result.review_reason
    assert result.revision_count == 0
    assert result.interpretation.thread_id == tid
    analyzer.assert_called_once()
    comparator.assert_not_called()
    reviser.assert_not_called()


def test_invalid_original_payload_retains_source_provenance(cases):
    threads, originals = cases
    tid = "1790903186.000110"
    invalid = {"thread_id": tid, "summary": "Malformed prior model response"}
    audit_payload = reviewed_audit(threads[tid], originals[tid]).model_dump(mode="json")
    # Explicit synthetic assessment of the malformed payload's only prose unit.
    # Its summary is not asserted to represent the Slack conversation.
    audit_payload["prose_assessments"] = [{
        "unit_id": "summary:1", "candidate_text": invalid["summary"], "verdict": "UNSUPPORTED",
        "source_interpretation": "The root asks QA about waveform loading without playback.",
        "explanation": "This malformed placeholder supplies no interpretation of the source.",
        "evidence_message_ids": [tid], "evidence_quotes": [threads[tid].messages[0].text],
    }]
    audit = DecisionEvidenceAudit.model_validate(audit_payload)
    validate_decision_evidence_audit(threads[tid], audit, invalid)
    result = verify_and_revise(
        threads[tid], invalid, comparator=Mock(return_value=ProseComparison(prose_assessments=audit.prose_assessments)),
        reviser=Mock(side_effect=ValueError("No corrected interpretation available")),
    )

    assert result.status == "NEEDS_REVIEW"
    assert result.original_interpretation == invalid
    assert result.interpretation.thread_id == tid
    assert result.effective_attempt == "fallback"
    assert result.review_reason
    assert result.provisional_fields


def test_raw_outputs_survive_validation_errors(cases):
    threads, originals = cases
    tid = "1790915374.000127"
    raw_outputs = []

    def auditor(thread, *, interpretation=None, on_raw_output=None, on_artifact=None):
        on_raw_output("not valid audit JSON")
        raise ValueError("Audit could not be validated")

    def reviser(thread, previous, findings, audit, *, on_raw_output=None, on_artifact=None):
        on_raw_output("not valid revision JSON")
        raise ValueError("Revision could not be validated")

    result = verify_and_revise(
        threads[tid], originals[tid], comparator=auditor, reviser=reviser,
        on_raw_output=lambda stage, raw: raw_outputs.append((stage, raw)),
    )
    assert result.status == "NEEDS_REVIEW"
    assert {raw for _, raw in raw_outputs} == {"not valid audit JSON", "not valid revision JSON"}
    assert len({stage for stage, _ in raw_outputs}) == len(raw_outputs)


def test_all_regression_threads_remain_exactly_once_without_mutating_inputs(cases):
    threads, originals = cases
    before_threads = {tid: thread.model_dump(mode="json") for tid, thread in threads.items()}
    before_originals = {tid: original.model_dump(mode="json") for tid, original in originals.items()}
    snapshots = deepcopy((before_threads, before_originals))
    results = []
    for tid in REGRESSIONS:
        original = corrected_interpretation(originals[tid]) if tid == "1790909920.000138" else originals[tid]
        # Deliberately leave one problematic interpretation disputed.
        revised = originals[tid] if tid == "1790882197.000111" else corrected_interpretation(originals[tid])
        results.append(verify_and_revise(
            threads[tid], original,
            comparator=Mock(side_effect=[reviewed_comparison(threads[tid], original), reviewed_comparison(threads[tid], revised)]),
            reviser=Mock(return_value=revised),
        ))

    assert {result.interpretation.thread_id for result in results} == set(REGRESSIONS)
    assert len(results) == len(REGRESSIONS)
    assert {result.status for result in results} == {"VERIFIED", "CORRECTED", "NEEDS_REVIEW"}
    assert all(result.interpretation is not None for result in results)
    assert {tid: thread.model_dump(mode="json") for tid, thread in threads.items()} == snapshots[0]
    assert {tid: original.model_dump(mode="json") for tid, original in originals.items()} == snapshots[1]


def test_stages_are_recorded_before_each_model_invocation(cases):
    threads, originals = cases
    tid = "1790915374.000127"
    events = []

    def audit(thread, **kwargs):
        events.append("audit-call")
        return reviewed_comparison(thread, kwargs["interpretation"])

    def revise(thread, previous, findings, audit, **kwargs):
        events.append("revision-call")
        return corrected_interpretation(previous)

    result = verify_and_revise(threads[tid], originals[tid], comparator=audit, reviser=revise,
                              on_stage_start=lambda stage: events.append(stage))
    assert result.status == "CORRECTED"
    assert events == ["source_analysis", "prose_1", "audit-call", "revision_1", "revision-call", "prose_2", "audit-call"]


@pytest.mark.parametrize("failed_stage", ["source_analysis", "prose_1", "revision_1", "prose_2"])
def test_failed_stage_recording_prevents_that_model_call_and_any_following_stage(cases, failed_stage):
    from threadsense.agents.verification_pipeline import EvidencePersistenceError

    threads, originals = cases
    tid = "1790915374.000127"
    auditor = Mock(side_effect=[reviewed_comparison(threads[tid], originals[tid]),
                               reviewed_comparison(threads[tid], corrected_interpretation(originals[tid]))])
    reviser = Mock(return_value=corrected_interpretation(originals[tid]))

    def persist(stage):
        if stage == failed_stage:
            raise OSError("Cannot persist stage")

    with pytest.raises(EvidencePersistenceError, match="Cannot persist stage"):
        verify_and_revise(threads[tid], originals[tid], comparator=auditor, reviser=reviser,
                          on_stage_start=persist)
    assert auditor.call_count == (0 if failed_stage in {"source_analysis", "prose_1"} else 1)
    assert reviser.call_count == (1 if failed_stage == "prose_2" else 0)
