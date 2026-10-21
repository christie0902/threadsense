"""Independent audit reference, quote, and coverage checks without model calls."""

from copy import deepcopy
from datetime import datetime, timezone
import json
from types import SimpleNamespace

import pytest

from threadsense.agents import decision_evidence_audit as auditor_module
from threadsense.agents.contracts import DecisionEvidenceAudit
from threadsense.models import Message, Thread


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
def payload(thread):
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
    }


@pytest.mark.parametrize("fenced", [False, True])
def test_valid_audit_has_exact_original_evidence(thread, payload, fenced):
    raw = json.dumps(payload)
    if fenced:
        raw = f"```json\n{raw}\n```"
    result = auditor_module.parse_audit_response(thread, raw)
    assert result == DecisionEvidenceAudit.model_validate(payload)


@pytest.mark.parametrize("case", [
    "wrong_thread", "fabricated_root_quote", "duplicate_reply", "missing_reply",
    "unknown_reply", "fabricated_reply_quote", "empty_reply_quote", "missing_coverage",
    "unknown_decision", "duplicate_decision", "duplicate_requested_decision",
    "diagnostic_as_answer", "root_as_answer", "answered_without_evidence",
    "unanswered_with_evidence", "duplicate_answer_evidence",
])
def test_invalid_audit_is_rejected(thread, payload, case):
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

    with pytest.raises(ValueError):
        auditor_module.parse_audit_response(thread, json.dumps(broken))


@pytest.mark.parametrize("case", ["duplicate_message", "missing_root"])
def test_ambiguous_source_message_identity_is_rejected(thread, payload, case):
    if case == "duplicate_message":
        broken = thread.model_copy(update={"messages": thread.messages + [thread.messages[1]]})
    else:
        broken = thread.model_copy(update={"messages": thread.messages[1:]})
    with pytest.raises(ValueError):
        auditor_module.parse_audit_response(broken, json.dumps(payload))


def test_complete_reply_cannot_support_unanswered_coverage(thread, payload):
    payload["reply_assessments"][0]["contribution"] = "COMPLETE_ANSWER"
    with pytest.raises(ValueError):
        auditor_module.parse_audit_response(thread, json.dumps(payload))


def test_legacy_experimental_audit_requires_new_coverage_validation(thread, payload):
    payload.pop("root_request_quote")
    payload.pop("decision_coverage")
    with pytest.raises(ValueError):
        auditor_module.parse_audit_response(thread, json.dumps(payload))


def test_audit_must_explicitly_report_candidate_comparison_even_with_no_findings(thread, payload):
    payload.pop("interpretation_findings")
    with pytest.raises(ValueError):
        auditor_module.parse_audit_response(thread, json.dumps(payload))


@pytest.mark.parametrize("missing_field", [
    "requested_decisions", "reply_assessments", "decision_coverage", "uncertainties",
])
def test_no_reply_announcement_requires_explicit_audit_lists(thread, missing_field):
    thread = thread.model_copy(deep=True)
    thread.messages = thread.messages[:1]
    thread.messages[0].text = "Status update: Label Tool maintenance is scheduled."
    payload = {
        "thread_id": thread.thread_id,
        "root_request_quote": thread.messages[0].text,
        "requested_decisions": [],
        "reply_assessments": [],
        "decision_coverage": [],
        "uncertainties": [],
        "interpretation_findings": [],
    }
    # Deliberate empty judgments are valid, even without any replies.
    auditor_module.parse_audit_response(thread, json.dumps(payload))
    payload.pop(missing_field)
    # Omitting a required assessment must not masquerade as an empty judgment.
    with pytest.raises(ValueError, match=missing_field):
        auditor_module.parse_audit_response(thread, json.dumps(payload))


@pytest.mark.parametrize("corruption", [
    "missing_ids", "missing_quotes", "invented_quote", "unknown_id", "wrong_quote_count",
    "missing_fields", "identity_field", "unknown_field",
])
def test_candidate_comparison_findings_require_exact_source_quotes_and_prose_fields(thread, payload, corruption):
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
    with pytest.raises(ValueError):
        auditor_module.parse_audit_response(thread, json.dumps(payload))


def test_candidate_comparison_accepts_source_grounded_prose_discrepancy(thread, payload):
    finding = {
        "category": "SUMMARY", "explanation": "The candidate claims resolution while the lead requests evidence.",
        "evidence_message_ids": ["reply"], "evidence_quotes": [thread.messages[1].text],
        "disputed_fields": ["summary"],
    }
    payload["interpretation_findings"] = [finding]
    audit = auditor_module.parse_audit_response(thread, json.dumps(payload))
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
def test_audit_accepts_structured_content_findings(thread, payload, field):
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
        thread, json.dumps(payload)
    )

    assert audit.interpretation_findings[0].disputed_fields == [field]