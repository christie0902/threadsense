"""Mocked split-stage orchestration and explicitly labeled historical replay.

Replay wraps saved single-unit responses in the new batch envelope in memory.
It demonstrates parser/finding compatibility, not fresh batched model accuracy.
"""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from tests.test_verification_pipeline import (
    cases, corrected_interpretation, reviewed_comparison, reviewed_source,
)
from threadsense.agents import verification_requests as transport
from threadsense.agents.contracts import DecisionEvidenceAudit, SourceEvidenceAnalysis
from threadsense.agents.decision_evidence_audit import build_prose_units
from threadsense.agents.interpretation_verifier import verify_interpretation
from threadsense.agents.prose_comparison import (
    build_prose_request, build_source_request, parse_prose_response, parse_source_response,
)
from threadsense.agents.verification_pipeline import verify_and_revise
from threadsense.experiments.prose_comparison import score_results
from threadsense.models import Thread
from threadsense.terminology import get_terms


ROOT = Path(__file__).resolve().parents[1]
REPLAY = ROOT / "data/experiments/prose_comparison_live_v2"


def response(raw, *, finish="stop"):
    return 200, json.dumps({"choices": [{"message": {"content": raw}, "finish_reason": finish}]}).encode(), None


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setenv("THREADSENSE_MODEL", "openai/gpt-4o-mini-2024-07-18")
    monkeypatch.setenv("THREADSENSE_VERIFIER_MODEL", "openai/gpt-4.1")
    monkeypatch.setenv("OPENAI_API_KEY", "offline-integration-key")


def test_source_and_prose_requests_are_separate_complete_and_label_free(cases):
    threads, originals = cases
    thread = threads["1790909920.000138"]
    candidate = originals[thread.thread_id].model_dump(mode="json")
    candidate.update(expected_verdict="DO_NOT_SEND_LABEL", previous_audit="DO_NOT_SEND_AUDIT",
                     evaluation="DO_NOT_SEND_EVALUATION")
    source = build_source_request(thread, get_terms(), "openai/gpt-4.1")
    prose = build_prose_request(thread, get_terms(), candidate, "openai/gpt-4.1")
    source_input = json.loads(source["messages"][1]["content"])
    prose_input = json.loads(prose["messages"][1]["content"])
    assert set(source_input) == {"original_conversation", "approved_glossary"}
    assert set(prose_input) == set(source_input) | {"candidate_prose_units"}
    assert prose_input["candidate_prose_units"] == build_prose_units(candidate)
    assert source_input["original_conversation"] == thread.model_dump(mode="json")
    assert prose_input["original_conversation"] == source_input["original_conversation"]
    for request in (source, prose):
        assert len(request["messages"]) == 2
        assert "DO_NOT_SEND" not in json.dumps(request)
        assert request["model"] == "gpt-4.1"
    assert candidate["summary"] not in json.dumps(source)
    # Source-only output rejects even empty candidate-specific fields.
    source_payload = reviewed_source(thread).model_dump(mode="json")
    source_payload["prose_assessments"] = []
    with pytest.raises(ValueError, match="Extra inputs"):
        parse_source_response(thread, json.dumps(source_payload))


@pytest.mark.parametrize("corruption", ["missing", "duplicate", "stale", "unknown_id", "fake_quote", "duplicate_citation", "blank", "extra"])
def test_batched_parser_rejects_incomplete_or_fabricated_assessments(cases, corruption):
    threads, originals = cases
    tid = "1790903186.000110"
    payload = reviewed_comparison(threads[tid], originals[tid]).model_dump(mode="json")
    units = payload["prose_assessments"]
    if corruption == "missing":
        units.pop()
    elif corruption == "duplicate":
        units.append(deepcopy(units[0]))
    elif corruption == "stale":
        units[0]["candidate_text"] += " Changed."
    elif corruption == "unknown_id":
        units[0]["evidence_message_ids"][0] = "fabricated"
    elif corruption == "fake_quote":
        units[0]["evidence_quotes"][0] = "A fabricated quotation."
    elif corruption == "duplicate_citation":
        units[0]["evidence_message_ids"] *= 2
        units[0]["evidence_quotes"] *= 2
    elif corruption == "blank":
        units[0]["source_interpretation"] = " "
    else:
        payload["decision_coverage"] = []
    with pytest.raises(ValueError):
        parse_prose_response(threads[tid], json.dumps(payload), originals[tid])


@pytest.mark.parametrize("tid", ["1790903186.000110", "1790882197.000111", "1790909920.000138", "1790915374.000127"])
def test_full_transport_path_reuses_source_checks_fresh_prose_and_caps_calls(cases, configured, monkeypatch, tid):
    threads, originals = cases
    thread, original = threads[tid], originals[tid]
    revised = corrected_interpretation(original)
    needs_revision = revised != original
    payloads = [reviewed_source(thread), reviewed_comparison(thread, original)]
    if needs_revision:
        payloads += [revised, reviewed_comparison(thread, revised)]
    stages, requests, artifacts, raw = [], [], {}, []

    def complete(endpoint, body, key):
        requests.append(json.loads(body))
        assert key == "offline-integration-key"
        assert artifacts[(stages[-1], "request.json")] == body
        assert (stages[-1], "call.json") in artifacts
        return response(payloads[len(requests) - 1].model_dump_json())

    monkeypatch.setattr(transport, "send_once", complete)
    result = verify_and_revise(
        thread, original, on_stage_start=stages.append,
        on_artifact=lambda stage, name, body: artifacts.__setitem__((stage, name), body),
        on_raw_output=lambda stage, text: raw.append((stage, text)),
    )
    assert result.status == ("CORRECTED" if needs_revision else "VERIFIED")
    assert result.interpretation == revised
    assert stages == (["source_analysis", "prose_1", "revision_1", "prose_2"] if needs_revision
                      else ["source_analysis", "prose_1"])
    assert len(requests) == len(stages) <= 4
    assert result.source_analysis == reviewed_source(thread)
    for attempt in result.passes:
        assert {k: v for k, v in attempt.audit.model_dump().items() if k in SourceEvidenceAnalysis.model_fields} == result.source_analysis.model_dump()
    assert all((stage, "response.raw.bin") in artifacts for stage in stages)
    assert len(raw) == len(stages)
    if needs_revision:
        assert requests[2]["model"] == "gpt-4o-mini-2024-07-18"
        assert [request["model"] for i, request in enumerate(requests) if i != 2] == ["gpt-4.1"] * 3
        assert json.loads(requests[1]["messages"][1]["content"])["candidate_prose_units"] == build_prose_units(original)
        assert json.loads(requests[3]["messages"][1]["content"])["candidate_prose_units"] == build_prose_units(revised)
        assert "VALIDATED SOURCE ANALYSIS" in requests[2]["messages"][1]["content"]


@pytest.mark.parametrize("failed_stage, count", [(0, 1), (1, 4), (2, 3), (3, 4)])
@pytest.mark.parametrize("failure", ["429", "malformed", "truncated"])
def test_failure_paths_never_retry_or_exceed_four_calls(cases, configured, monkeypatch, failed_stage, count, failure):
    threads, originals = cases
    tid = "1790909920.000138"
    thread, original = threads[tid], originals[tid]
    revised = corrected_interpretation(original)
    payloads = [reviewed_source(thread), reviewed_comparison(thread, original), revised, reviewed_comparison(thread, revised)]
    calls, raw_bodies = [], []

    def complete(*args):
        index = len(calls)
        calls.append(index)
        if index == failed_stage:
            if failure == "429":
                return 429, b'{"error":"rate limited"}', None
            return response("invalid JSON" if failure == "malformed" else payloads[index].model_dump_json(),
                            finish="length" if failure == "truncated" else "stop")
        return response(payloads[index].model_dump_json())

    monkeypatch.setattr(transport, "send_once", complete)
    result = verify_and_revise(thread, original, on_artifact=lambda *args: raw_bodies.append(args))
    assert len(calls) == count <= 4
    # An invalid first prose batch can be replaced by fresh valid evidence after
    # the single revision; failed source/revision/final prose cannot pass.
    assert result.status == ("CORRECTED" if failed_stage == 1 else "NEEDS_REVIEW")
    assert len([r for r in raw_bodies if r[1] == "response.raw.bin"]) == count
    if failed_stage == 1:
        assert result.passes[0].error
    elif failed_stage == 2:
        assert result.revision_error
    else:
        assert result.review_reason and result.provisional_fields


@pytest.mark.parametrize("failed_artifact, expected_calls", [("request.json", 0), ("call.json", 0), ("response.raw.bin", 1)])
def test_evidence_persistence_failure_stops_all_model_work(cases, configured, monkeypatch, failed_artifact, expected_calls):
    threads, originals = cases
    thread = threads["1790903186.000110"]
    send = Mock(return_value=response(reviewed_source(thread).model_dump_json()))
    monkeypatch.setattr(transport, "send_once", send)

    def persist(stage, name, body):
        if name == failed_artifact:
            raise OSError("Disk full")

    with pytest.raises(transport.EvidencePersistenceError):
        verify_and_revise(thread, originals[thread.thread_id], on_artifact=persist)
    assert send.call_count == expected_calls


def test_single_attempt_transport_has_no_http_retry_or_redirect(monkeypatch):
    connection = Mock()
    connection.getresponse.return_value.status = 429
    connection.getresponse.return_value.read.return_value = b"rate limited"
    constructor = Mock(return_value=connection)
    monkeypatch.setattr(transport.http.client, "HTTPSConnection", constructor)
    assert transport.send_once("https://api.openai.com/v1/chat/completions", b"{}", "offline") == (429, b"rate limited", None)
    constructor.assert_called_once()
    connection.request.assert_called_once()
    connection.getresponse.assert_called_once()
    connection.close.assert_called_once()


@pytest.mark.parametrize("status", [400, 401, 403, 404, 422])
def test_configuration_rejection_stops_without_substituting_models(cases, configured, monkeypatch, status):
    threads, originals = cases
    thread = threads["1790903186.000110"]
    send = Mock(return_value=(status, b'{"error":"configuration rejected"}', None))
    monkeypatch.setattr(transport, "send_once", send)
    artifacts = []
    with pytest.raises(transport.VerificationConfigurationError, match=f"HTTP {status}"):
        verify_and_revise(thread, originals[thread.thread_id], on_artifact=lambda *args: artifacts.append(args))
    send.assert_called_once()
    assert any(name == "response.raw.bin" for _, name, _ in artifacts)


def test_all_prose_units_are_sent_without_truncation(cases):
    threads, originals = cases
    thread = threads["1790903186.000110"]
    candidate = originals[thread.thread_id].model_dump()
    candidate["summary"] = " ".join(f"Synthetic sentence number {i}." for i in range(200))
    request = build_prose_request(thread, get_terms(), candidate, "openai/gpt-4.1")
    supplied = json.loads(request["messages"][1]["content"])["candidate_prose_units"]
    assert supplied == build_prose_units(candidate)
    assert len([u for u in supplied if u["candidate_field"] == "summary"]) == 200


def test_source_ambiguity_is_reused_and_cannot_be_cleared_by_supported_prose(cases):
    threads, originals = cases
    tid = "1790903186.000110"
    thread, original = threads[tid], originals[tid]
    source = reviewed_source(thread).model_copy(update={"uncertainties": ["Synthetic unresolved source ambiguity."]})
    analyze = Mock(return_value=source)
    compare = Mock(return_value=reviewed_comparison(thread, original))
    revise = Mock(return_value=original)
    result = verify_and_revise(thread, original, source_analyzer=analyze, comparator=compare, reviser=revise)
    assert result.status == "NEEDS_REVIEW"
    analyze.assert_called_once()
    revise.assert_called_once()
    assert compare.call_count == 2
    assert all(any("Independent audit uncertainty" in f.explanation for f in p.findings) for p in result.passes)


def test_saved_live_experiment_replay_preserves_all_verdicts_and_mismatches():
    """REPLAY ONLY: no new accuracy measurement; saved artifacts remain unchanged."""
    paths = [p for p in REPLAY.rglob("*") if p.is_file()]
    before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    saved_expected = json.loads((REPLAY / "expected_verdicts.json").read_text())
    results = []
    for directory in sorted(REPLAY.glob("case_*")):
        request = json.loads((directory / "request.json").read_text())
        inputs = json.loads(request["messages"][1]["content"])
        thread = Thread.model_validate(inputs["original_conversation"])
        raw = json.loads((directory / "assessment.raw.txt").read_text())
        assert raw["candidate_text"] == inputs["candidate_prose_unit"]["candidate_text"]
        # Synthetic in-memory batch adapter: preserve every semantic field and
        # verdict, remap only the unit ID to build_prose_units' field identity.
        adapted = {**raw, "unit_id": "summary:1"}
        candidate = {"summary": raw["candidate_text"]}
        comparison = parse_prose_response(thread, json.dumps({"prose_assessments": [adapted]}), candidate)
        assert comparison.prose_assessments[0].verdict == raw["verdict"]
        source = reviewed_source(thread)
        audit = DecisionEvidenceAudit(**source.model_dump(), **comparison.model_dump(), interpretation_findings=[])
        # Use a minimal candidate only for parsing here; the live model saw one
        # unit, not a complete production interpretation.
        from threadsense.agents.contracts import ThreadInterpretation
        interpretation = ThreadInterpretation(thread_id=thread.thread_id, summary=raw["candidate_text"],
            central_question=None, resolution_state="UNRESOLVED", resolution_rationale="", confidence=0)
        findings = verify_interpretation(thread, interpretation, audit)
        prose_findings = [f for f in findings if "Prose unit summary:1:" in f.explanation]
        assert len(prose_findings) == int(raw["verdict"] != "SUPPORTED")
        if prose_findings:
            assert prose_findings[0].evidence_quotes == raw["evidence_quotes"]
        results.append({"case_id": directory.name, "status": "OK", "assessment": raw})
    expected = saved_expected  # Snapshot keyed by neutral case ID, never a runtime input.
    scores = score_results(results, expected)
    assert scores["metrics"]["faithful_acceptance"]["correct"] == 4
    assert scores["metrics"]["incorrect_rejection"]["correct"] == 4
    assert scores["metrics"]["exact_verdict_agreement"]["correct"] == 6
    assert {m["case_id"] for m in scores["mismatches"]} == {"case_02", "case_07"}
    assert all(m["expected_verdict"] == "UNSUPPORTED" and m["observed_verdict"] == "CONTRADICTED" for m in scores["mismatches"])
    assert before == {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
