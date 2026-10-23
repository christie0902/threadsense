"""Offline checks for the isolated comparator; all HTTP responses are mocked."""

from collections import Counter
from copy import deepcopy
import json
from unittest.mock import Mock

import pytest

from threadsense.experiments import prose_comparison as experiment


@pytest.fixture
def benchmark():
    return experiment.load_benchmark()


def reviewed_response(case, expected):
    """Synthetic provider response, using explicit reviewed benchmark evidence."""
    review = expected[case["case_id"]]
    return {
        **case["candidate"], "verdict": review["expected_verdict"],
        "source_interpretation": review["review_reason"], "explanation": review["review_reason"],
        "evidence_message_ids": review["evidence_message_ids"], "evidence_quotes": review["evidence_quotes"],
    }


def response_envelope(content):
    return experiment.json_bytes({"choices": [{"message": {"role": "assistant", "content": content}}]})


def test_benchmark_has_eight_reviewed_synthetic_variants_from_four_v5_sources(benchmark):
    cases, expected, provenance = benchmark
    assert len(cases) == 8
    assert Counter(case["thread"].thread_id for case in cases) == {
        "1790882197.000111": 2, "1790903186.000110": 2,
        "1790909920.000138": 2, "1790915374.000127": 2,
    }
    assert Counter(review["candidate_kind"] for review in expected.values()) == {"faithful": 4, "incorrect": 4}
    assert experiment.read_json(experiment.BENCHMARK / "cases.json")["candidate_origin"] == "synthetic_benchmark_input"
    for name, digest in provenance.items():
        assert experiment.sha256((experiment.ROOT / name).read_bytes()) == digest
    assert expected["case_02"]["expected_verdict"] == "UNSUPPORTED"
    assert expected["case_03"]["expected_verdict"] == "CONTRADICTED"
    assert expected["case_06"]["expected_verdict"] == "CONTRADICTED"
    assert expected["case_07"]["expected_verdict"] == "UNSUPPORTED"


@pytest.mark.parametrize("model, provider_model", [
    ("openai/gpt-4o-mini-2024-07-18", "gpt-4o-mini-2024-07-18"),
    ("openrouter/openai/gpt-4o-mini", "openai/gpt-4o-mini"),
])
def test_requests_contain_only_source_glossary_and_one_unit_without_labels_or_history(benchmark, model, provider_model):
    cases, expected, _ = benchmark
    glossary = experiment.get_terms()
    for case in cases:
        body = experiment.build_request(case["thread"], glossary, case["candidate"], model)
        assert body["model"] == provider_model
        assert [message["role"] for message in body["messages"]] == ["system", "user"]
        content = json.loads(body["messages"][1]["content"])
        assert set(content) == {"original_conversation", "approved_glossary", "candidate_prose_unit"}
        assert content["original_conversation"] == case["thread"].model_dump(mode="json")
        assert content["approved_glossary"] == glossary
        assert content["candidate_prose_unit"] == case["candidate"]
        serialized = json.dumps(body)
        for forbidden in ("expected_verdict", "candidate_kind", "review_reason", "case_id",
                          "interpretation_findings", "reply_assessments", "decision_coverage", "resolution_state"):
            assert forbidden not in serialized
        before = deepcopy(body)
        expected[case["case_id"]]["review_reason"] = "PRIVATE_EXPECTATION_CANARY"
        assert experiment.build_request(case["thread"], glossary, case["candidate"], model) == before
        assert "PRIVATE_EXPECTATION_CANARY" not in serialized
    eyes_case = next(case for case in cases if case["case_id"] == "case_04")
    root = eyes_case["thread"].messages[0]
    assert root.reactions[0].name == "eyes"
    assert root.reactions[0].reactor_roles["U006"] == "TEAM_LEAD"


def test_request_rejects_label_metadata_inside_candidate(benchmark):
    cases, _, _ = benchmark
    case = cases[0]
    with pytest.raises(ValueError, match="One candidate unit"):
        experiment.build_request(case["thread"], {}, {**case["candidate"], "expected_verdict": "SUPPORTED"}, "openai/test")


@pytest.mark.parametrize("case_index", range(8))
def test_reviewed_mock_responses_validate_against_exact_saved_evidence(benchmark, case_index):
    cases, expected, _ = benchmark
    case = cases[case_index]
    payload = reviewed_response(case, expected)
    assessment = experiment.parse_assessment(json.dumps(payload), case["thread"], case["candidate"])
    assert assessment.model_dump() == payload


@pytest.mark.parametrize("corruption, expected_error", [
    ("unit_id", "unit_id does not match"),
    ("candidate_text", "candidate_text was changed"),
    ("unknown_id", "Unknown source evidence"),
    ("fabricated_quote", "not exact source evidence"),
    ("blank_quote", "not exact source evidence"),
    ("missing_quotes", "parallel quotations"),
    ("missing_ids", "parallel quotations"),
    ("duplicate_ids", "unique evidence IDs"),
    ("blank_explanation", "must not be blank"),
    ("blank_source", "must not be blank"),
    ("missing_verdict", "verdict"),
    ("invalid_verdict", "verdict"),
])
def test_evidence_and_identity_fail_for_the_intended_reason(benchmark, corruption, expected_error):
    cases, expected, _ = benchmark
    case = cases[0]
    payload = deepcopy(reviewed_response(case, expected))
    if corruption in {"unit_id", "candidate_text"}:
        payload[corruption] = "changed"
    elif corruption == "unknown_id":
        payload["evidence_message_ids"] = ["invented"]
    elif corruption == "fabricated_quote":
        payload["evidence_quotes"] = ["A sentence is missing from the reference text."]
    elif corruption == "blank_quote":
        payload["evidence_quotes"] = [" "]
    elif corruption == "missing_quotes":
        payload["evidence_quotes"] = []
    elif corruption == "missing_ids":
        payload["evidence_message_ids"] = []
    elif corruption == "duplicate_ids":
        payload["evidence_message_ids"] *= 2
        payload["evidence_quotes"] *= 2
    elif corruption == "blank_explanation":
        payload["explanation"] = " "
    elif corruption == "blank_source":
        payload["source_interpretation"] = " "
    elif corruption == "missing_verdict":
        payload.pop("verdict")
    else:
        payload["verdict"] = "APPROVED"
    with pytest.raises(ValueError, match=expected_error):
        experiment.parse_assessment(json.dumps(payload), case["thread"], case["candidate"])


def test_scores_report_acceptance_rejection_failures_and_every_exact_mismatch(benchmark):
    cases, expected, _ = benchmark
    results = [{"case_id": case["case_id"], "status": "OK", "assessment": reviewed_response(case, expected)} for case in cases]
    perfect = experiment.score_results(results, expected)
    assert perfect["metrics"]["faithful_acceptance"] == {"correct": 4, "total": 4, "rate": 1.0}
    assert perfect["metrics"]["incorrect_rejection"] == {"correct": 4, "total": 4, "rate": 1.0}
    assert perfect["mismatches"] == []
    by_id = {row["case_id"]: row for row in results}
    by_id["case_01"]["assessment"]["verdict"] = "UNSUPPORTED"
    by_id["case_02"]["assessment"]["verdict"] = "SUPPORTED"
    by_id["case_03"]["status"] = "INVALID_RESPONSE"
    by_id["case_04"]["assessment"]["verdict"] = "UNCERTAIN"
    by_id["case_06"]["assessment"]["verdict"] = "UNSUPPORTED"
    by_id["case_07"]["status"] = "REQUEST_FAILED"
    scored = experiment.score_results(results, expected)
    assert scored["metrics"]["faithful_acceptance"] == {"correct": 2, "total": 4, "rate": 0.5}
    assert scored["metrics"]["incorrect_rejection"] == {"correct": 1, "total": 4, "rate": 0.25}
    assert scored["metrics"]["exact_verdict_agreement"]["correct"] == 2
    assert {row["case_id"] for row in scored["mismatches"]} == {"case_01", "case_02", "case_03", "case_04", "case_06", "case_07"}
    subtype = next(row for row in scored["mismatches"] if row["case_id"] == "case_06")
    assert subtype["acceptance_or_rejection_correct"] is True


def test_uncertain_is_not_a_correct_incorrect_candidate_rejection(benchmark):
    cases, expected, _ = benchmark
    results = [{"case_id": case["case_id"], "status": "OK", "assessment": reviewed_response(case, expected)} for case in cases]
    results[1]["assessment"]["verdict"] = "UNCERTAIN"
    assert experiment.score_results(results, expected)["metrics"]["incorrect_rejection"]["correct"] == 3
    with pytest.raises(ValueError, match="exactly one result"):
        experiment.score_results(results[:-1], expected)
    with pytest.raises(ValueError, match="exactly one result"):
        experiment.score_results([results[0], *results[:-1]], expected)


@pytest.mark.parametrize("flags", [[], ["--dry-run"]])
def test_dry_run_writes_eight_exact_requests_without_credentials_calls_or_scores(tmp_path, monkeypatch, flags):
    output = tmp_path / "preview"
    monkeypatch.setattr(experiment, "get_api_key", lambda _: pytest.fail("Dry run requested credentials"))
    monkeypatch.setattr(experiment, "send_once", lambda *a: pytest.fail("Dry run made an HTTP request"))
    assert experiment.main([*flags, "--output-dir", str(output)]) == 0
    manifest = experiment.read_json(output / "manifest.json")
    assert len(manifest["request_sha256"]) == 8
    for case_id, digest in manifest["request_sha256"].items():
        assert experiment.sha256((output / case_id / "request.json").read_bytes()) == digest
    report = experiment.read_json(output / "report.json")
    assert report["model_calls"] == 0 and report["metrics"] is None
    assert len(experiment.read_json(output / "results.json")) == 8
    assert not list(output.glob("*/response.raw.bin"))
    with pytest.raises(SystemExit, match="2"):
        experiment.main(["--run", "--output-dir", str(output)])


def test_live_mode_with_mocked_http_sends_saved_bytes_once_per_case_and_scores(benchmark, tmp_path, monkeypatch):
    cases, expected, _ = benchmark
    output = tmp_path / "mock_live"
    monkeypatch.setenv("THREADSENSE_VERIFIER_MODEL", "openrouter/openai/gpt-4o-mini")
    monkeypatch.setattr(experiment, "get_api_key", lambda name: "offline-key" if name == "OPENROUTER_API_KEY" else pytest.fail("Wrong provider key"))
    sent = []

    def send(endpoint, body, key):
        case = cases[len(sent)]
        assert endpoint == "https://openrouter.ai/api/v1/chat/completions"
        assert key == "offline-key"
        assert body == (output / case["case_id"] / "request.json").read_bytes()
        assert json.loads(body)["model"] == "openai/gpt-4o-mini"
        assert (output / case["case_id"] / "started.json").exists()
        sent.append(body)
        return 200, response_envelope(json.dumps(reviewed_response(case, expected)))

    monkeypatch.setattr(experiment, "send_once", send)
    assert experiment.main(["--run", "--output-dir", str(output)]) == 0
    assert len(sent) == len(set(sent)) == 8
    report = experiment.read_json(output / "report.json")
    assert report["model_calls"] == 8
    assert report["metrics"]["faithful_acceptance"]["correct"] == 4
    assert report["metrics"]["incorrect_rejection"]["correct"] == 4
    assert report["mismatches"] == []
    assert len(list(output.glob("*/assessment.raw.txt"))) == 8
    assert "offline-key" not in "".join(path.read_text() for path in output.rglob("*.json"))


def test_failures_and_invalid_raw_outputs_are_retained_without_retries(benchmark, tmp_path, monkeypatch):
    cases, expected, _ = benchmark
    output = tmp_path / "failed_live"
    monkeypatch.setattr(experiment, "get_api_key", lambda _: "offline-key")
    responses, calls = {}, []

    def send(endpoint, body, key):
        case = cases[len(calls)]
        case_id = case["case_id"]
        calls.append(case_id)
        payload = reviewed_response(case, expected)
        status = 200
        if case_id == "case_02":
            status, raw = 429, b'{"error":"rate limit"}'
        elif case_id == "case_03":
            raw = b"not JSON"
        elif case_id == "case_04":
            payload["evidence_quotes"][0] = "Invented approval quote."
            raw = response_envelope(json.dumps(payload))
        elif case_id == "case_06":
            raw = response_envelope(None)
        elif case_id == "case_07":
            raise OSError("offline-key connection failure")
        else:
            raw = response_envelope(json.dumps(payload))
        responses[case_id] = raw
        return status, raw

    monkeypatch.setattr(experiment, "send_once", send)
    assert experiment.main(["--run", "--output-dir", str(output)]) == 2
    assert len(calls) == len(set(calls)) == 8
    results = experiment.read_json(output / "results.json")
    assert len(results) == 8
    for row in results:
        assert (output / row["case_id"] / "response.raw.bin").read_bytes() == responses.get(row["case_id"], b"")
    assert "Invented approval quote" in (output / "case_04/assessment.raw.txt").read_text()
    assert "offline-key" not in json.dumps(results)
    assert {row["case_id"] for row in experiment.read_json(output / "report.json")["mismatches"]} == {
        "case_02", "case_03", "case_04", "case_06", "case_07",
    }


def test_interruption_retains_unattempted_cases_and_cannot_resume_paid_calls(benchmark, tmp_path, monkeypatch):
    output = tmp_path / "interrupted"
    monkeypatch.setattr(experiment, "get_api_key", lambda _: "offline-key")
    send = Mock(side_effect=KeyboardInterrupt())
    monkeypatch.setattr(experiment, "send_once", send)
    assert experiment.main(["--run", "--output-dir", str(output)]) == 130
    assert send.call_count == 1
    results = experiment.read_json(output / "results.json")
    assert len(results) == 8
    assert results[0]["status"] == "REQUEST_FAILED"
    assert all(row["status"] == "NOT_RUN" for row in results[1:])
    with pytest.raises(SystemExit, match="2"):
        experiment.main(["--run", "--output-dir", str(output)])
    assert send.call_count == 1


@pytest.mark.parametrize("status", [200, 429, 500, 307])
def test_http_transport_posts_exact_body_once_and_does_not_retry_or_redirect(monkeypatch, status):
    connection = Mock()
    connection.getresponse.return_value.status = status
    connection.getresponse.return_value.read.return_value = b"raw response"
    factory = Mock(return_value=connection)
    monkeypatch.setattr(experiment.http.client, "HTTPSConnection", factory)
    result = experiment.send_once("https://api.openai.com/v1/chat/completions", b"exact bytes", "offline-key")
    assert result == (status, b"raw response")
    factory.assert_called_once_with("api.openai.com", timeout=120)
    connection.request.assert_called_once_with("POST", "/v1/chat/completions", body=b"exact bytes", headers={
        "Content-Type": "application/json", "Authorization": "Bearer offline-key",
    })
    connection.close.assert_called_once()


def test_transport_exception_is_not_retried(monkeypatch):
    connection = Mock()
    connection.request.side_effect = TimeoutError("No response")
    monkeypatch.setattr(experiment.http.client, "HTTPSConnection", Mock(return_value=connection))
    with pytest.raises(TimeoutError, match="No response"):
        experiment.send_once("https://api.openai.com/v1/chat/completions", b"body", "offline-key")
    assert connection.request.call_count == 1
    connection.close.assert_called_once()


def test_partial_response_is_retained_without_retry(tmp_path, monkeypatch):
    connection = Mock()
    connection.getresponse.return_value.status = 200
    connection.getresponse.return_value.read.side_effect = experiment.http.client.IncompleteRead(b'{"partial":', 10)
    monkeypatch.setattr(experiment.http.client, "HTTPSConnection", Mock(return_value=connection))
    monkeypatch.setattr(experiment, "get_api_key", lambda _: "offline-key")
    output = tmp_path / "partial"
    assert experiment.main(["--run", "--output-dir", str(output)]) == 2
    assert connection.request.call_count == 8  # One attempt per case; none retried.
    for result in experiment.read_json(output / "results.json"):
        assert result["status"] == "REQUEST_FAILED"
        assert result["http_status"] == 200
        assert (output / result["case_id"] / "response.raw.bin").read_bytes() == b'{"partial":'


def test_input_and_production_directories_cannot_receive_experiment_outputs():
    for base in (experiment.PILOT, experiment.BENCHMARK, experiment.ROOT / "src", experiment.ROOT / "data/fixtures"):
        with pytest.raises(ValueError, match="separate from code, inputs, and pilot data"):
            experiment.check_output((base / "new_experiment").resolve())


def test_benchmark_cannot_exceed_eight_requests(benchmark, tmp_path, monkeypatch):
    inputs = experiment.read_json(experiment.BENCHMARK / "cases.json")
    expected = experiment.read_json(experiment.BENCHMARK / "expected.json")
    inputs["cases"].append({**inputs["cases"][0], "case_id": "case_09"})
    (tmp_path / "cases.json").write_bytes(experiment.json_bytes(inputs))
    (tmp_path / "expected.json").write_bytes(experiment.json_bytes(expected))
    monkeypatch.setattr(experiment, "BENCHMARK", tmp_path)
    with pytest.raises(ValueError, match="Exactly eight unique neutral"):
        experiment.load_benchmark()
