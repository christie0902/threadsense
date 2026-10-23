"""Deterministic rules compare visible evidence without running an LLM."""

from datetime import datetime, timezone

import pytest

from threadsense.agents.contracts import DecisionEvidenceAudit, ResolutionState, ThreadInterpretation
from threadsense.agents.decision_evidence_audit import build_prose_units, validate_decision_evidence_audit
from threadsense.agents.interpretation_verifier import verify_interpretation
from threadsense.models import Message, Reaction, Role, Thread


def stub_prose_assessments_for_rule_tests(thread, candidate, *, summary_verdict="SUPPORTED"):
    """Test-only structural stub for metadata/coverage rules, not a fidelity oracle.

    The glossary cases explicitly reject their incorrect summary. Prose-fidelity
    tests use reviewed assessments in test_decision_evidence_audit.py instead.
    """
    return [{
        "unit_id": unit["unit_id"], "candidate_text": unit["candidate_text"],
        "verdict": summary_verdict if unit["candidate_field"] == "summary" else "SUPPORTED",
        "source_interpretation": "Synthetic prose stub; this test exercises a deterministic rule.",
        "explanation": "Synthetic test assessment, not a claim of independently reviewed prose fidelity.",
        "evidence_message_ids": [message.message_id for message in thread.messages],
        "evidence_quotes": [message.text for message in thread.messages],
    } for unit in build_prose_units(candidate)]


def scenario(*, second_answered=False):
    now = datetime(2026, 10, 1, tzinfo=timezone.utc)
    root_text = "Should I quarantine this task, and which issue category should I report?"
    texts = [root_text, "Quarantine this task.", "Report a playback error." if second_answered else "Please send the error state."]
    thread = Thread(
        thread_id="root", project_id="audio", channel_id="channel",
        channel_name="audio-general", channel_type="GENERAL", created_at=now,
        messages=[
            Message(message_id=mid, author_id=f"user-{mid}", author_name=mid,
                    author_role="TUTOR" if mid == "root" else "TEAM_LEAD",
                    timestamp=now, text=text)
            for mid, text in zip(["root", "first", "second"], texts)
        ],
    )
    decisions = ["Should the task be quarantined?", "Which issue category should be reported?"]
    audit_payload = {
        "thread_id": "root", "root_request_quote": root_text,
        "requested_decisions": decisions,
        "reply_assessments": [{
            "message_id": message.message_id,
            "contribution": "PARTIAL_ANSWER" if index == 0 or second_answered else "DIAGNOSTIC_ONLY",
            "evidence_quote": message.text,
            "explanation": "Settles part of the original request." if index == 0 or second_answered else "Requests evidence only.",
        } for index, message in enumerate(thread.messages[1:])],
        "decision_coverage": [{
            "requested_decision": decision,
            "status": "ANSWERED" if index == 0 or second_answered else "UNANSWERED",
            "answer_message_ids": [["first"], ["second"] if second_answered else []][index],
            "rationale": "The handling is explicit." if index == 0 else "The category is supplied." if second_answered else "No category was supplied.",
        } for index, decision in enumerate(decisions)],
        "interpretation_findings": [],
        "uncertainties": [],
    }
    interpretation = ThreadInterpretation(
        thread_id="root", summary="The lead directs quarantine and discusses the reporting category.",
        central_question=root_text,
        resolution_state="RESOLVED_IN_THREAD" if second_answered else "PARTIALLY_RESOLVED",
        authoritative_response_present=True,
        authority_evidence_message_ids=["first", "second"] if second_answered else ["first"],
        resolution_rationale="Both decisions are answered." if second_answered else "Quarantine is decided; the reporting category remains open.",
        confidence=0.7,
    )
    audit_payload["prose_assessments"] = stub_prose_assessments_for_rule_tests(thread, interpretation)
    audit = DecisionEvidenceAudit.model_validate(audit_payload)
    validate_decision_evidence_audit(thread, audit, interpretation)
    return thread, interpretation, audit


@pytest.mark.parametrize("second_answered", [False, True])
def test_coverage_distinguishes_partial_from_complete_multiple_decisions(second_answered):
    thread, interpretation, audit = scenario(second_answered=second_answered)
    assert verify_interpretation(thread, interpretation, audit) == []

    wrong = interpretation.model_copy(update={
        "resolution_state": ResolutionState.UNRESOLVED if second_answered else ResolutionState.RESOLVED_IN_THREAD
    })
    findings = verify_interpretation(thread, wrong, audit)
    assert "RESOLUTION" in {finding.category.value for finding in findings}


def test_diagnostic_authority_citation_is_invalid_even_when_other_reply_answers():
    thread, interpretation, audit = scenario()
    wrong = interpretation.model_copy(update={"authority_evidence_message_ids": ["second"]})
    findings = verify_interpretation(thread, wrong, audit)
    authority = [finding for finding in findings if finding.category == "AUTHORITY"]
    assert authority
    assert any("second" in finding.evidence_message_ids for finding in authority)


def test_diagnostic_instructions_can_fully_answer_a_request_for_diagnostics():
    thread, _, _ = scenario()
    thread = thread.model_copy(deep=True)
    thread.messages = thread.messages[:2]
    thread.messages[0].text = "Which evidence should I collect before reporting the problem?"
    thread.messages[1].text = "Collect the task ID, browser error, and reproduction steps."
    question = "Which evidence should be collected?"
    audit_payload = {
        "thread_id": "root", "root_request_quote": thread.messages[0].text,
        "requested_decisions": [question],
        "reply_assessments": [{
            "message_id": "first", "contribution": "COMPLETE_ANSWER",
            "evidence_quote": thread.messages[1].text,
            "explanation": "Exactly answers the requested evidence-collection guidance.",
        }],
        "decision_coverage": [{
            "requested_decision": question, "status": "ANSWERED",
            "answer_message_ids": ["first"], "rationale": "All requested collection guidance is supplied.",
        }],
        "interpretation_findings": [],
        "uncertainties": [],
    }
    interpretation = ThreadInterpretation(
        thread_id="root", summary="The lead lists the required evidence.",
        central_question=thread.messages[0].text, resolution_state="RESOLVED_IN_THREAD",
        authoritative_response_present=True, authority_evidence_message_ids=["first"],
        resolution_rationale="The evidence-collection question is fully answered.", confidence=0.7,
    )
    audit_payload["prose_assessments"] = stub_prose_assessments_for_rule_tests(thread, interpretation)
    audit = DecisionEvidenceAudit.model_validate(audit_payload)
    assert verify_interpretation(thread, interpretation, audit) == []


@pytest.mark.parametrize("emoji", ["this", "agree", "white_check_mark"])
def test_qualifying_endorsements_require_actual_tl_reactor(emoji):
    thread, interpretation, audit = scenario()
    thread = thread.model_copy(deep=True)
    thread.messages[1].author_role = Role.QA_TUTOR
    thread.messages[1].reactions = [Reaction(
        name=emoji, users=["lead"], count=1, reactor_roles={"lead": "TEAM_LEAD"}
    )]
    assert verify_interpretation(thread, interpretation, audit) == []

    thread.messages[1].reactions[0].reactor_roles = {"lead": Role.TUTOR}
    assert verify_interpretation(thread, interpretation, audit)


@pytest.mark.parametrize("reaction", [
    {"name": "eyes", "users": ["lead"], "count": 1, "reactor_roles": {"lead": "TEAM_LEAD"}},
    {"name": "this", "users": ["trainer"], "count": 1, "reactor_roles": {"trainer": "TUTOR", "lead": "TEAM_LEAD"}},
    {"name": "this", "users": ["lead"], "count": 1, "reactor_roles": {}},
    {"name": "this", "users": [], "count": 1, "reactor_roles": {"lead": "TEAM_LEAD"}},
])
def test_acknowledgment_or_unattributed_reaction_cannot_confer_authority(reaction):
    thread, interpretation, audit = scenario()
    thread = thread.model_copy(deep=True)
    thread.messages[1].author_role = Role.QA_TUTOR
    thread.messages[1].reactions = [Reaction.model_validate(reaction)]
    assert verify_interpretation(thread, interpretation, audit)


@pytest.mark.parametrize("scope", [True, False, None])
def test_engineer_authority_requires_explicit_technical_scope(scope):
    thread, interpretation, audit = scenario()
    thread = thread.model_copy(deep=True)
    thread.messages[1].author_role = Role.ENGINEER
    audit = audit.model_copy(deep=True)
    audit.reply_assessments[0].technical_scope = scope
    findings = verify_interpretation(thread, interpretation, audit)
    if scope is True:
        assert findings == []
    else:
        assert "AUTHORITY" in {finding.category.value for finding in findings}


@pytest.mark.parametrize("text", [
    "This is a QN (quality note).", "This is a quality issue (QN).",
    "Use LT (Learning Tool) for the task.",
])
def test_known_glossary_conflicts_cannot_pass_even_with_matching_decisions(text):
    thread, interpretation, audit = scenario()
    interpretation = interpretation.model_copy(update={"summary": text})
    payload = audit.model_dump()
    payload["prose_assessments"] = stub_prose_assessments_for_rule_tests(
        thread, interpretation, summary_verdict="UNSUPPORTED",
    )
    audit = DecisionEvidenceAudit.model_validate(payload)
    validate_decision_evidence_audit(thread, audit, interpretation)
    assert "TERMINOLOGY" in {
        finding.category.value for finding in verify_interpretation(thread, interpretation, audit)
    }


def test_audit_uncertainty_is_not_silently_verified():
    thread, interpretation, audit = scenario()
    audit = audit.model_copy(update={"uncertainties": ["The intended classification is ambiguous."]})
    assert verify_interpretation(thread, interpretation, audit)


def test_confidence_does_not_override_contradictory_evidence():
    thread, interpretation, audit = scenario()
    interpretation = interpretation.model_copy(update={"resolution_state": ResolutionState.RESOLVED_IN_THREAD, "confidence": 1.0})
    assert "RESOLUTION" in {
        finding.category.value for finding in verify_interpretation(thread, interpretation, audit)
    }
