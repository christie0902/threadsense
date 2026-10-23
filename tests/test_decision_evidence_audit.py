"""Independent audit reference, quote, and coverage checks without model calls."""

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from threadsense.agents.verification_pipeline import verify_and_revise

import pytest

from threadsense.agents import decision_evidence_audit as auditor_module
from threadsense.agents.contracts import DecisionEvidenceAudit
from threadsense.models import Message, Thread
from threadsense.agents.contracts import ThreadInterpretation
from threadsense.agents.interpretation_verifier import verify_interpretation


@pytest.fixture
def thread():
    now = datetime(2026, 10, 1, tzinfo=timezone.utc)
    return Thread(
        thread_id="root", project_id="audio", channel_id="channel",
        channel_name="audio-general", channel_type="GENERAL", created_at=now,
        messages=[
            Message(message_id="root", author_id="trainer", author_name="Trainer",
                    author_role="TUTOR", timestamp=now,
                    text="Should the task be quarantined?"),
            Message(message_id="reply", author_id="lead", author_name="Lead",
                    author_role="TEAM_LEAD", timestamp=now,
                    text="Please capture the Label Tool error state before a decision."),
        ],
    )


@pytest.fixture
def candidate(thread):
    return ThreadInterpretation(
        thread_id=thread.thread_id,
        summary="The lead approved quarantine.",
        central_question="Should the task be quarantined?",
        resolution_state="UNRESOLVED",
        resolution_rationale="The lead requests evidence without deciding.",
        confidence=0.9,
    )


@pytest.fixture
def payload(thread, candidate):
    question = "Should the task be quarantined?"
    return {
        "thread_id": thread.thread_id,
        "root_request_quote": thread.messages[0].text,
        "requested_decisions": [question],
        "reply_assessments": [{
            "message_id": "reply", "contribution": "DIAGNOSTIC_ONLY",
            "evidence_quote": thread.messages[1].text,
            "explanation": "Requests evidence without deciding quarantine handling.",
        }],
        "decision_coverage": [{
            "requested_decision": question, "status": "UNANSWERED",
            "answer_message_ids": [], "rationale": "The handling decision remains unanswered.",
        }],
        "uncertainties": [],
        "interpretation_findings": [],
        # Reviewed against this synthetic conversation: the approval claim is
        # false. A valid audit can (and here must) report a prose discrepancy.
        "prose_assessments": [
            {
                "unit_id": unit_id, "candidate_text": text, "verdict": verdict,
                "source_interpretation": meaning, "explanation": meaning,
                "evidence_message_ids": [message.message_id],
                "evidence_quotes": [message.text],
            }
            for unit_id, text, verdict, meaning, message in [
                ("summary:1", candidate.summary, "CONTRADICTED",
                 "The lead requests evidence before making a decision.", thread.messages[1]),
                ("central_question:1", candidate.central_question, "SUPPORTED",
                 "The root asks whether to quarantine the task.", thread.messages[0]),
                ("resolution_rationale:1", candidate.resolution_rationale, "SUPPORTED",
                 "The reply requests evidence and leaves the decision open.", thread.messages[1]),
            ]
        ],
    }


@pytest.mark.parametrize("fenced", [False, True])
def test_valid_audit_has_exact_original_evidence(thread, payload, candidate, fenced):
    raw = json.dumps(payload)
    if fenced:
        raw = f"```json\n{raw}\n```"
    result = auditor_module.parse_audit_response(thread, raw, candidate)
    assert result == DecisionEvidenceAudit.model_validate(payload)


@pytest.mark.parametrize("case", [
    "wrong_thread", "fabricated_root_quote", "duplicate_reply", "missing_reply",
    "unknown_reply", "fabricated_reply_quote", "empty_reply_quote", "missing_coverage",
    "unknown_decision", "duplicate_decision", "duplicate_requested_decision",
    "diagnostic_as_answer", "root_as_answer", "answered_without_evidence",
    "unanswered_with_evidence", "duplicate_answer_evidence",
])
def test_invalid_audit_is_rejected(thread, payload, candidate, case):
    auditor_module.parse_audit_response(thread, json.dumps(payload), candidate)
    broken = deepcopy(payload)
    if case == "wrong_thread":
        broken["thread_id"] = "other"
    elif case == "fabricated_root_quote":
        broken["root_request_quote"] = "The team approved quarantine."
    elif case == "duplicate_reply":
        broken["reply_assessments"] *= 2
    elif case == "missing_reply":
        broken["reply_assessments"] = []
    elif case == "unknown_reply":
        broken["reply_assessments"][0]["message_id"] = "invented"
    elif case == "fabricated_reply_quote":
        broken["reply_assessments"][0]["evidence_quote"] = "Definitely quarantine the task."
    elif case == "empty_reply_quote":
        broken["reply_assessments"][0]["evidence_quote"] = ""
    elif case == "missing_coverage":
        broken["decision_coverage"] = []
    elif case == "unknown_decision":
        broken["decision_coverage"][0]["requested_decision"] = "Invented decision"
    elif case == "duplicate_decision":
        broken["decision_coverage"] *= 2
    elif case == "duplicate_requested_decision":
        broken["requested_decisions"] *= 2
    elif case in {"diagnostic_as_answer", "root_as_answer", "answered_without_evidence", "duplicate_answer_evidence"}:
        broken["decision_coverage"][0]["status"] = "ANSWERED"
        broken["decision_coverage"][0]["answer_message_ids"] = {
            "diagnostic_as_answer": ["reply"], "root_as_answer": ["root"],
            "answered_without_evidence": [], "duplicate_answer_evidence": ["reply", "reply"],
        }[case]
    elif case == "unanswered_with_evidence":
        broken["decision_coverage"][0]["answer_message_ids"] = ["reply"]

    expected_errors = {
        "wrong_thread": "Audit thread ID does not match",
        "fabricated_root_quote": "Root request quote is not verbatim",
        "duplicate_reply": "Duplicate reply assessments",
        "missing_reply": "Reply coverage mismatch",
        "unknown_reply": "Reply coverage mismatch",
        "fabricated_reply_quote": "Evidence quote does not match",
        "empty_reply_quote": "reply_assessments.0.evidence_quote",
        "missing_coverage": "Decision coverage must assess every requested decision",
        "unknown_decision": "Decision coverage must assess every requested decision",
        "duplicate_decision": "Duplicate decision coverage items",
        "duplicate_requested_decision": "Duplicate requested decisions",
        "diagnostic_as_answer": "not classified as substantive answers",
        "root_as_answer": "not classified as substantive answers",
        "answered_without_evidence": "Answered decisions require answer evidence",
        "unanswered_with_evidence": "Unanswered decisions cannot cite answer evidence",
        "duplicate_answer_evidence": "Duplicate answer message IDs",
    }
    with pytest.raises(ValueError, match=expected_errors[case]):
        auditor_module.parse_audit_response(thread, json.dumps(broken), candidate)


@pytest.mark.parametrize("case", ["duplicate_message", "missing_root"])
def test_ambiguous_source_message_identity_is_rejected(thread, payload, candidate, case):
    if case == "duplicate_message":
        broken = thread.model_copy(update={"messages": thread.messages + [thread.messages[1]]})
    else:
        broken = thread.model_copy(update={"messages": thread.messages[1:]})
    expected = "duplicate message IDs" if case == "duplicate_message" else "Expected exactly one root message"
    with pytest.raises(ValueError, match=expected):
        auditor_module.parse_audit_response(broken, json.dumps(payload), candidate)


def test_complete_reply_cannot_support_unanswered_coverage(thread, payload, candidate):
    payload["reply_assessments"][0]["contribution"] = "COMPLETE_ANSWER"
    with pytest.raises(ValueError, match="Substantive reply classifications contradict entirely unanswered coverage"):
        auditor_module.parse_audit_response(thread, json.dumps(payload), candidate)


def test_legacy_experimental_audit_requires_new_coverage_validation(thread, payload, candidate):
    payload.pop("root_request_quote")
    payload.pop("decision_coverage")
    with pytest.raises(ValueError, match="root_request_quote") as error:
        auditor_module.parse_audit_response(thread, json.dumps(payload), candidate)
    assert {item["loc"] for item in error.value.errors()} == {("root_request_quote",), ("decision_coverage",)}


def test_audit_must_explicitly_report_candidate_comparison_even_with_no_findings(thread, payload, candidate):
    payload.pop("interpretation_findings")
    with pytest.raises(ValueError, match="interpretation_findings"):
        auditor_module.parse_audit_response(thread, json.dumps(payload), candidate)


@pytest.mark.parametrize("pass_number", [1, 2])
def test_saved_old_schema_pilot_response_requires_prose_assessments(pass_number):
    # Use committed pilot evidence, not an optional local run or augmented raw
    # response. No synthetic assessments are injected into these old payloads.
    base = Path(__file__).resolve().parents[1] / "data/processed/agent1_verified_pilot_v1"
    directory = base / "records/64b1fa303985b0aabec75d2d73bceb1e3b77e0fe222b4ed395a0496c67428024"
    source = base / "sources/a31ce82a0c8540f826509060d3eed8fe5f0b9af35166fc2a123f69a671a726fe.json"
    path = directory / f"audit_{pass_number}.raw.txt"
    before = path.read_bytes()
    raw = before.decode("utf-8")
    assert "prose_assessments" not in json.loads(raw)
    thread = Thread.model_validate_json(source.read_text(encoding="utf-8"))
    record = json.loads((directory / "result.json").read_text(encoding="utf-8"))
    candidate = record["result"]["passes"][pass_number - 1]["interpretation"]
    with pytest.raises(ValueError, match="prose_assessments") as error:
        auditor_module.parse_audit_response(thread, raw, candidate)
    assert [(item["loc"], item["type"]) for item in error.value.errors()] == [
        (("prose_assessments",), "missing"),
    ]
    assert path.read_bytes() == before


@pytest.mark.parametrize("missing_field", [
    "requested_decisions", "reply_assessments", "decision_coverage", "uncertainties", "prose_assessments",
])
def test_no_reply_announcement_requires_explicit_audit_lists(thread, missing_field):
    thread = thread.model_copy(deep=True)
    thread.messages = thread.messages[:1]
    thread.messages[0].text = "Status update: Label Tool maintenance is scheduled."
    candidate = ThreadInterpretation(
        thread_id=thread.thread_id, summary=thread.messages[0].text,
        central_question=None, resolution_state="UNRESOLVED",
        resolution_rationale="This is an announcement without a requested decision.", confidence=0.7,
    )
    payload = {
        "thread_id": thread.thread_id,
        "root_request_quote": thread.messages[0].text,
        "requested_decisions": [],
        "reply_assessments": [],
        "decision_coverage": [],
        "uncertainties": [],
        "interpretation_findings": [],
        "prose_assessments": [
            {
                "unit_id": unit_id, "candidate_text": text, "verdict": "SUPPORTED",
                "source_interpretation": "The root announces maintenance without asking a question.",
                "explanation": "The announcement is accurately described.",
                "evidence_message_ids": [thread.thread_id],
                "evidence_quotes": [thread.messages[0].text],
            }
            for unit_id, text in [("summary:1", candidate.summary),
                                  ("resolution_rationale:1", candidate.resolution_rationale)]
        ],
    }
    # Deliberate empty judgments are valid, even without any replies.
    auditor_module.parse_audit_response(thread, json.dumps(payload), candidate)
    payload.pop(missing_field)
    # Omitting a required assessment must not masquerade as an empty judgment.
    with pytest.raises(ValueError, match=missing_field):
        auditor_module.parse_audit_response(thread, json.dumps(payload), candidate)


@pytest.mark.parametrize("corruption", [
    "missing_ids", "missing_quotes", "invented_quote", "unknown_id", "wrong_quote_count",
    "missing_fields", "identity_field", "unknown_field",
])
def test_candidate_comparison_findings_require_exact_source_quotes_and_prose_fields(thread, payload, candidate, corruption):
    finding = {
        "category": "SUMMARY", "explanation": "Candidate invents completed resolution.",
        "evidence_message_ids": ["reply"], "evidence_quotes": [thread.messages[1].text],
        "disputed_fields": ["summary"],
    }
    if corruption == "missing_ids":
        finding["evidence_message_ids"] = []
    elif corruption == "missing_quotes":
        finding["evidence_quotes"] = []
    elif corruption == "invented_quote":
        finding["evidence_quotes"] = ["The task is resolved."]
    elif corruption == "unknown_id":
        finding["evidence_message_ids"] = ["invented"]
    elif corruption == "wrong_quote_count":
        finding["evidence_quotes"] *= 2
    elif corruption == "missing_fields":
        finding["disputed_fields"] = []
    elif corruption == "identity_field":
        finding["disputed_fields"] = ["thread_id"]
    elif corruption == "unknown_field":
        finding["disputed_fields"] = ["invented_field"]
    payload["interpretation_findings"] = [finding]
    expected = (
        "supported candidate content fields" if corruption in {"missing_fields", "identity_field", "unknown_field"}
        else "unknown message" if corruption == "unknown_id"
        else "quotation is not verbatim" if corruption == "invented_quote"
        else "matching evidence IDs and quotations"
    )
    with pytest.raises(ValueError, match=expected):
        auditor_module.parse_audit_response(thread, json.dumps(payload), candidate)


def test_candidate_comparison_accepts_source_grounded_prose_discrepancy(thread, payload, candidate):
    finding = {
        "category": "SUMMARY", "explanation": "The candidate claims resolution while the lead requests evidence.",
        "evidence_message_ids": ["reply"], "evidence_quotes": [thread.messages[1].text],
        "disputed_fields": ["summary"],
    }
    payload["interpretation_findings"] = [finding]
    audit = auditor_module.parse_audit_response(thread, json.dumps(payload), candidate)
    assert audit.interpretation_findings[0].evidence_quotes == [thread.messages[1].text]


def test_auditor_compares_current_candidate_with_original_thread_and_preserves_invalid_raw_output(
    thread, monkeypatch
):
    inputs_seen = []
    raw_outputs = []
    constructor_calls = []

    def kickoff(*, inputs):
        inputs_seen.append(inputs)
        return SimpleNamespace(raw="invalid raw output retained for review")

    def constructor(**kwargs):
        constructor_calls.append(kwargs)
        return SimpleNamespace(**kwargs)

    monkeypatch.setattr(auditor_module, "create_verifier_llm", lambda: object())
    monkeypatch.setattr(auditor_module, "Agent", constructor)
    monkeypatch.setattr(auditor_module, "Task", constructor)
    monkeypatch.setattr(auditor_module, "Crew", lambda **kwargs: SimpleNamespace(kickoff=kickoff))

    candidate = {"thread_id": thread.thread_id, "summary": "Candidate to review"}
    with pytest.raises(ValueError):
        auditor_module.audit_thread_decisions(
            thread, interpretation=candidate, on_raw_output=raw_outputs.append
        )

    assert raw_outputs == ["invalid raw output retained for review"]
    assert len(inputs_seen) == 1
    inputs = inputs_seen[0]
    assert json.loads(inputs["thread_json"]) == thread.model_dump(mode="json")
    assert json.loads(inputs["interpretation_json"]) == candidate
    assert not any("previous" in key or "findings" in key for key in inputs)
    assert "data/evaluation" not in json.dumps(inputs)
    agent_config = next(kwargs for kwargs in constructor_calls if "role" in kwargs)
    assert agent_config["max_iter"] == 1
    assert agent_config["max_retry_limit"] == 0
    assert agent_config["tools"] == []
    assert agent_config["allow_delegation"] is False

@pytest.mark.parametrize("field", [
    "resolution_state",
    "authoritative_response_present",
    "authority_evidence_message_ids",
])
def test_audit_accepts_structured_content_findings(thread, payload, candidate, field):
    payload["interpretation_findings"] = [{
        "category": (
            "RESOLUTION" if field == "resolution_state" else "AUTHORITY"
        ),
        "explanation": (
            "The reply requests evidence without answering "
            "the quarantine question."
        ),
        "evidence_message_ids": ["reply"],
        "evidence_quotes": [thread.messages[1].text],
        "disputed_fields": [field],
    }]

    audit = auditor_module.parse_audit_response(
        thread, json.dumps(payload), candidate
    )

    assert audit.interpretation_findings[0].disputed_fields == [field]

@pytest.fixture
def prose_case(thread, payload):
    candidate = ThreadInterpretation(
        thread_id=thread.thread_id,
        summary="The lead approved quarantine.",
        central_question="Should the task be quarantined?",
        resolution_state="UNRESOLVED",
        authoritative_response_present=False,
        authority_evidence_message_ids=[],
        resolution_rationale="The lead requests evidence without deciding.",
        confidence=0.9,
    )

    # Explicit expectations for this synthetic conversation.
    checks = [
        (
            "summary:1",
            candidate.summary,
            "CONTRADICTED",
            "The lead requests evidence before making a decision.",
            thread.messages[1],
        ),
        (
            "central_question:1",
            candidate.central_question,
            "SUPPORTED",
            "The root asks whether to quarantine the task.",
            thread.messages[0],
        ),
        (
            "resolution_rationale:1",
            candidate.resolution_rationale,
            "SUPPORTED",
            "The reply requests evidence and leaves the decision open.",
            thread.messages[1],
        ),
    ]

    data = deepcopy(payload)
    data["interpretation_findings"] = []
    data["prose_assessments"] = [
        {
            "unit_id": unit_id,
            "candidate_text": text,
            "source_interpretation": meaning,
            "verdict": verdict,
            "evidence_message_ids": [message.message_id],
            "evidence_quotes": [message.text],
            "explanation": meaning,
        }
        for unit_id, text, verdict, meaning, message in checks
    ]
    return candidate, data

@pytest.mark.parametrize("corruption", [
    "missing_unit",
    "duplicate_unit",
    "changed_text",
    "invented_quote",
])
def test_prose_invalid_assessments_are_rejected(
    thread, prose_case, corruption
):
    candidate, data = prose_case
    assessments = data["prose_assessments"]

    if corruption == "missing_unit":
        assessments.pop()
        expected_error = "Prose coverage mismatch"
    elif corruption == "duplicate_unit":
        assessments.append(deepcopy(assessments[0]))
        expected_error = "Duplicate prose assessments"
    elif corruption == "changed_text":
        assessments[0]["candidate_text"] = "Silently rewritten summary."
        expected_error = "candidate text was changed"
    else:
        assessments[0]["evidence_quotes"] = ["Quarantine is approved."]
        expected_error = "quotation is not verbatim"

    with pytest.raises(ValueError, match=expected_error):
        auditor_module.parse_audit_response(
            thread, json.dumps(data), candidate
        )

def test_prose_contradiction_becomes_a_revision_finding(thread, prose_case):
    candidate, data = prose_case
    audit = auditor_module.parse_audit_response(
        thread, json.dumps(data), candidate
    )

    assert audit.interpretation_findings == []

    findings = verify_interpretation(thread, candidate, audit)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.category.value == "SUMMARY"
    assert finding.disputed_fields == ["summary"]
    assert "summary:1" in finding.explanation
    assert "CONTRADICTED" in finding.explanation
    assert finding.evidence_message_ids == ["reply"]
    assert finding.evidence_quotes == [thread.messages[1].text]

@pytest.mark.parametrize("mode, expected_status", [
    ("corrected", "CORRECTED"),
    ("unchanged", "NEEDS_REVIEW"),
    ("stale_audit", "NEEDS_REVIEW"),
])

def test_prose_revision_requires_a_matching_fresh_audit(
    thread, prose_case, mode, expected_status
):
    candidate, first_audit = prose_case
    revised = candidate.model_copy(deep=True)
    second_audit = deepcopy(first_audit)

    if mode != "unchanged":
        revised.summary = (
            "The lead requests evidence before deciding quarantine."
        )

    if mode == "corrected":
        assessment = next(
            item for item in second_audit["prose_assessments"]
            if item["unit_id"] == "summary:1"
        )
        assessment["candidate_text"] = revised.summary
        assessment["verdict"] = "SUPPORTED"
        assessment["explanation"] = (
            "The revised summary accurately describes the evidence request."
        )

    from threadsense.agents.contracts import SourceEvidenceAnalysis
    source = {key: first_audit[key] for key in SourceEvidenceAnalysis.model_fields}
    source_analyzer = Mock(return_value=source)
    auditor = Mock(side_effect=[{
        "prose_assessments": item["prose_assessments"]
    } for item in (first_audit, second_audit)])
    reviser = Mock(return_value=revised)

    result = verify_and_revise(
        thread,
        candidate,
        source_analyzer=source_analyzer, comparator=auditor,
        reviser=reviser,
    )

    assert result.status == expected_status
    assert result.revision_count == 1
    assert len(result.passes) == 2
    assert auditor.call_count == 2
    reviser.assert_called_once()
    source_analyzer.assert_called_once()

    # Revision must receive the prose discrepancy, not a schema error.
    first_pass = result.passes[0]
    assert first_pass.error is None
    assert len(first_pass.findings) == 1
    assert first_pass.findings[0].disputed_fields == ["summary"]
    assert reviser.call_args.args[2] == first_pass.findings

    # The second audit must receive the revised candidate.
    assert auditor.call_args_list[1].kwargs["interpretation"] == (
        revised.model_dump(mode="json")
    )

    second_pass = result.passes[1]
    if mode == "stale_audit":
        assert second_pass.error is not None
        assert "candidate text was changed" in second_pass.error
    else:
        assert second_pass.error is None
        assert second_pass.passed == (mode == "corrected")

    if mode == "corrected":
        assert result.interpretation == revised
        assert result.findings == []
    else:
        assert "summary" in result.provisional_fields
