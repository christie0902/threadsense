"""Offline batch safety, coverage, provenance, and resume regression tests."""

import importlib.util
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from threadsense.agents.contracts import ThreadInterpretation
from threadsense.agents.decision_evidence_audit import parse_audit_response
from threadsense.models import Thread


ROOT = Path(__file__).resolve().parents[1]


def make_entry(runner, thread_id):
    thread = Thread.model_validate({
        "thread_id": thread_id, "project_id": "project", "batch_id": "batch",
        "channel_id": "C_TEST", "channel_name": "test", "channel_type": "QA",
        "created_at": "2026-10-01T00:00:00+00:00",
        "messages": [{
            "message_id": thread_id, "author_id": "U1", "author_name": "Author",
            "author_role": "TUTOR", "timestamp": "2026-10-01T00:00:00+00:00",
            "text": "Should this item enter QN?",
        }],
    })
    interpretation = ThreadInterpretation(
        thread_id=thread_id, summary="An author asks whether an item should enter Quarantine.",
        central_question="Should this item enter Quarantine?", resolution_state="UNRESOLVED",
        resolution_rationale="No reply has answered the question.", confidence=0.7,
    )
    baseline = {
        "thread_id": thread_id, "channel_id": "C_TEST", "project_id": "project",
        "batch_id": "batch", "language": None, "model": "legacy-model",
        "run_config_sha256": "legacy-run", "created_at": "2026-10-01T00:00:00+00:00",
        "interpretation": interpretation.model_dump(mode="json"),
    }
    source = thread.model_dump(mode="json")
    return {
        "thread": thread, "baseline": baseline, "source": source,
        "source_sha256": runner.digest(source), "baseline_sha256": runner.digest(baseline),
        "key": runner.digest({"source": source, "baseline": baseline}),
    }


@pytest.fixture
def batch(monkeypatch, tmp_path):
    spec = importlib.util.spec_from_file_location(
        "test_verification_batch_runner", ROOT / "scripts/run_agent1_verification.py",
    )
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    entries = [make_entry(runner, "1.0"), make_entry(runner, "2.0")]
    monkeypatch.setattr(runner, "load_inputs", lambda: entries)
    monkeypatch.setattr(runner, "run_configuration", lambda values: {
        "pipeline_version": 3, "interpreter_model": "openai/test",
        "auditor_model": "openai/test", "source_count": len(values),
        "inputs": runner.digest([entry["baseline"] for entry in values]),
    })
    monkeypatch.setattr(runner, "get_api_key", lambda key: "offline-test-key")
    output = tmp_path / "verified_v1"
    return runner, entries, output


def verified_result(thread, original, *, on_raw_output, on_stage_start, on_artifact):
    from threadsense.agents.verification_pipeline import VerificationResult

    question = thread.messages[0].text
    audit = {
        "thread_id": thread.thread_id, "root_request_quote": question,
        "requested_decisions": [question], "reply_assessments": [],
        "decision_coverage": [{"requested_decision": question, "status": "UNANSWERED",
                               "answer_message_ids": [], "rationale": "No replies exist."}],
        "uncertainties": [], "interpretation_findings": [],
        # Explicit synthetic assessments of make_entry's three simple units.
        "prose_assessments": [{
            "unit_id": f"{field}:1", "candidate_text": original[field],
            "verdict": "SUPPORTED", "source_interpretation": meaning,
            "explanation": meaning, "evidence_message_ids": [thread.thread_id],
            "evidence_quotes": [question],
        } for field, meaning in (
            ("summary", "The author asks whether this item should enter Quarantine."),
            ("central_question", "The candidate preserves the root quarantine question."),
            ("resolution_rationale", "Only the root question exists; no reply answers it."),
        )],
    }
    # Cache fixtures must be valid under the same parser used for model output.
    parse_audit_response(thread, json.dumps(audit), original)
    on_stage_start("source_analysis")
    on_stage_start("prose_1")
    on_artifact("prose_1", "request.json", b'{"synthetic_cache_test": true}')
    on_raw_output("prose_1", json.dumps(audit))
    return VerificationResult.model_validate({
        "source_analysis": {key: value for key, value in audit.items()
                            if key not in {"prose_assessments", "interpretation_findings"}},
        "status": "VERIFIED", "interpretation": original,
        "original_interpretation": original, "revised_interpretation": None,
        "findings": [], "passes": [{
            "number": 1, "interpretation": original, "audit": audit,
            "findings": [], "error": None,
        }],
        "revision_count": 0, "revision_error": None,
        "provisional_fields": [], "review_reason": None, "effective_attempt": "original",
    })


def test_default_and_explicit_dry_run_never_request_keys_or_write(batch, monkeypatch, capsys):
    runner, _, output = batch
    monkeypatch.setattr(runner, "get_api_key", lambda _: pytest.fail("Credentials requested offline"))
    monkeypatch.setattr(runner, "verify_thread", lambda *a, **k: pytest.fail("Paid call in dry run"))
    for flags in ([], ["--dry-run"]):
        assert runner.main([*flags, "--output-dir", str(output)]) == 0
        assert not output.exists()
    assert "Selected 1 of 2" in capsys.readouterr().out


def test_batch_preserves_each_source_and_reuses_completed_cache(batch, monkeypatch):
    runner, entries, output = batch
    calls = []

    def invoke(*args, **kwargs):
        calls.append(args[0].thread_id)
        return verified_result(*args, **kwargs)

    monkeypatch.setattr(runner, "verify_thread", invoke)
    flags = ["--run", "--limit", "0", "--output-dir", str(output)]
    assert runner.main(flags) == 0
    assert calls == ["1.0", "2.0"]
    records = runner.read_json(output / "interpretations.json")
    assert [record["thread_id"] for record in records] == ["1.0", "2.0"]
    assert all(record["verification_status"] == "VERIFIED" for record in records)
    assert all(record["lineage"]["baseline_run_config_sha256"] == "legacy-run" for record in records)
    assert len({record["run_config_sha256"] for record in records}) == 1
    assert records[0]["run_config_sha256"] != "legacy-run"
    assert len(list((output / "sources").glob("*.json"))) == len(entries)
    for record in records:
        source = runner.read_json(output / record["lineage"]["source_file"])
        assert source["thread_id"] == record["thread_id"]
        assert (output / record["lineage"]["verification_file"]).exists()
    monkeypatch.setattr(runner, "get_api_key", lambda _: pytest.fail("Cache-only resume needs no key"))
    monkeypatch.setattr(runner, "verify_thread", lambda *a, **k: pytest.fail("Completed calls repeated"))
    assert runner.main(flags) == 0
    manifest = runner.read_json(output / "manifest.json")
    assert manifest["counts"] == {"VERIFIED": 2, "CORRECTED": 0, "NEEDS_REVIEW": 0}
    assert manifest["attempted_this_run"] == 0
    assert manifest["coverage"] == "all_source_threads"


def test_interruption_preserves_raw_and_unprocessed_threads_then_resumes(batch, monkeypatch):
    runner, entries, output = batch

    def interrupted(thread, original, *, on_raw_output, on_stage_start, on_artifact):
        on_stage_start("prose_1")
        on_raw_output("prose_1", "invalid JSON output retained verbatim")
        raise KeyboardInterrupt()

    monkeypatch.setattr(runner, "verify_thread", interrupted)
    flags = ["--run", "--limit", "0", "--output-dir", str(output)]
    assert runner.main(flags) == 1
    records = runner.read_json(output / "interpretations.json")
    assert len(records) == 2
    assert all(record["verification_status"] == "NEEDS_REVIEW" for record in records)
    assert all(record["interpretation"] == entry["baseline"]["interpretation"] for record, entry in zip(records, entries))
    assert runner.read_json(output / "manifest.json")["unprocessed"] == 1
    assert (output / "records" / entries[0]["key"] / "prose_1.raw.txt").read_text() == "invalid JSON output retained verbatim"
    assert not (output / "records" / entries[1]["key"] / "started.json").exists()
    calls = []

    def resume(thread, original, **kwargs):
        calls.append(thread.thread_id)
        return verified_result(thread, original, **kwargs)

    monkeypatch.setattr(runner, "verify_thread", resume)
    assert runner.main(flags) == 0
    assert calls == ["2.0"]
    records = runner.read_json(output / "interpretations.json")
    assert [record["verification_status"] for record in records] == ["NEEDS_REVIEW", "VERIFIED"]
    assert runner.read_json(output / "manifest.json")["unprocessed"] == 0


def test_incomplete_started_attempt_becomes_review_without_repeating_calls(batch, monkeypatch):
    runner, entries, output = batch
    monkeypatch.setattr(runner, "verify_thread", verified_result)
    flags = ["--run", "--output-dir", str(output)]
    assert runner.main(flags) == 0
    (output / "records" / entries[0]["key"] / "result.json").unlink()
    monkeypatch.setattr(runner, "verify_thread", lambda *a, **k: pytest.fail("Interrupted call repeated"))
    monkeypatch.setattr(runner, "get_api_key", lambda _: pytest.fail("Interrupted recovery needs no key"))
    assert runner.main(flags) == 0
    record = runner.read_json(output / "interpretations.json")[0]
    assert record["verification_status"] == "NEEDS_REVIEW"
    assert "previous attempt was interrupted" in record["review_reason"]


@pytest.mark.parametrize("target", ["raw", "result", "source", "started", "stage", "request"])
def test_corrupt_cache_is_rejected_before_any_paid_call(batch, monkeypatch, target):
    runner, entries, output = batch
    monkeypatch.setattr(runner, "verify_thread", verified_result)
    flags = ["--run", "--output-dir", str(output)]
    assert runner.main(flags) == 0
    directory = output / "records" / entries[0]["key"]
    paths = {
        "raw": directory / "prose_1.raw.txt", "result": directory / "result.json",
        "source": output / "sources" / f"{entries[0]['source_sha256']}.json",
        "started": directory / "started.json",
        "stage": directory / "prose_1.started.json",
        "request": directory / "prose_1.request.json",
    }
    paths[target].write_text("{}", encoding="utf-8")
    monkeypatch.setattr(runner, "verify_thread", lambda *a, **k: pytest.fail("Corrupt cache caused a paid call"))
    with pytest.raises(SystemExit) as error:
        runner.main([*flags, "--limit", "0"])
    assert error.value.code == 2


def test_changed_input_cannot_reuse_existing_cache(batch, monkeypatch):
    runner, entries, output = batch
    monkeypatch.setattr(runner, "verify_thread", verified_result)
    flags = ["--run", "--output-dir", str(output)]
    assert runner.main(flags) == 0
    entries[0]["baseline"]["interpretation"]["summary"] = "Changed baseline"
    monkeypatch.setattr(runner, "verify_thread", lambda *a, **k: pytest.fail("Changed cache used"))
    with pytest.raises(SystemExit, match="2"):
        runner.main(flags)


def test_foreign_output_and_protected_output_rejected(batch, monkeypatch):
    runner, _, output = batch
    output.mkdir()
    (output / "legacy.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(runner, "verify_thread", lambda *a, **k: pytest.fail("Unsafe output used"))
    with pytest.raises(SystemExit, match="2"):
        runner.main(["--run", "--output-dir", str(output)])
    protected_child = ROOT / "data/processed/agent1_authority_fix/new_v1"
    with pytest.raises(SystemExit, match="2"):
        runner.main(["--dry-run", "--output-dir", str(protected_child)])
    assert not protected_child.exists()


def test_cli_rejects_conflicting_modes_and_negative_limit(batch):
    runner, _, _ = batch
    for flags in (["--run", "--dry-run"], ["--limit", "-1"]):
        with pytest.raises(SystemExit, match="2"):
            runner.main(flags)


def test_real_subprocess_dry_run_needs_no_credentials_or_files(tmp_path):
    output = tmp_path / "subprocess_v1"
    environment = dict(os.environ)
    environment.update({
        "PYTHONPATH": str(ROOT / "src"), "OPENAI_API_KEY": "",
        "OPENROUTER_API_KEY": "", "THREADSENSE_MODEL": "openai/offline-test",
        "THREADSENSE_VERIFIER_MODEL": "openai/offline-test",
    })
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/run_agent1_verification.py"),
         "--dry-run", "--limit", "1", "--output-dir", str(output)],
        cwd=tmp_path, env=environment, capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Selected 1 of 178" in result.stdout
    assert "200 source threads; 22 announcements excluded" in result.stdout
    assert "Dry run" in result.stdout
    assert not output.exists()


def test_later_subset_keeps_prior_results_in_the_aggregate(batch, monkeypatch):
    runner, _, output = batch
    calls = []

    def invoke(thread, original, **kwargs):
        calls.append(thread.thread_id)
        return verified_result(thread, original, **kwargs)

    monkeypatch.setattr(runner, "verify_thread", invoke)
    for thread_id in ("1.0", "2.0", "1.0"):
        assert runner.main(["--run", "--thread-id", thread_id, "--output-dir", str(output)]) == 0
    records = runner.read_json(output / "interpretations.json")
    assert [row["thread_id"] for row in records] == ["1.0", "2.0"]
    assert calls == ["1.0", "2.0"]
    manifest = runner.read_json(output / "manifest.json")
    assert manifest["selected"] == 1
    assert manifest["retained"] == 2
    assert manifest["counts"]["VERIFIED"] == 2


def test_subset_resume_keeps_previously_selected_unstarted_threads(batch, monkeypatch):
    runner, _, output = batch

    def interrupted(thread, original, *, on_raw_output, on_stage_start, on_artifact):
        on_stage_start("prose_1")
        raise KeyboardInterrupt()

    monkeypatch.setattr(runner, "verify_thread", interrupted)
    assert runner.main(["--run", "--limit", "0", "--output-dir", str(output)]) == 1
    monkeypatch.setattr(runner, "verify_thread", lambda *a, **k: pytest.fail("Cached thread retried"))
    assert runner.main(["--run", "--thread-id", "1.0", "--output-dir", str(output)]) == 1
    assert len(runner.read_json(output / "interpretations.json")) == 2
    manifest = runner.read_json(output / "manifest.json")
    assert manifest["unprocessed"] == 1
    assert manifest["state"] == "incomplete"


def test_interrupted_revision_is_counted_without_a_raw_response(batch, monkeypatch):
    runner, entries, output = batch

    def interrupted(thread, original, *, on_raw_output, on_stage_start, on_artifact):
        on_stage_start("prose_1")
        on_raw_output("prose_1", "first audit")
        on_stage_start("revision_1")
        raise KeyboardInterrupt()

    monkeypatch.setattr(runner, "verify_thread", interrupted)
    flags = ["--run", "--output-dir", str(output)]
    assert runner.main(flags) == 1
    record = runner.read_json(output / "interpretations.json")[0]
    assert record["revision_count"] == 1
    directory = output / "records" / entries[0]["key"]
    assert not (directory / "revision_1.raw.txt").exists()
    # Simulate an abrupt exit before result.json was durably saved.
    (directory / "result.json").unlink()
    monkeypatch.setattr(runner, "verify_thread", lambda *a, **k: pytest.fail("Revision repeated"))
    assert runner.main(flags) == 0
    assert runner.read_json(output / "interpretations.json")[0]["revision_count"] == 1


@pytest.mark.parametrize("original_invalid", [False, True])
def test_interrupted_recovery_preserves_saved_revision_and_prefers_valid_candidate(batch, tmp_path, original_invalid):
    runner, entries, _ = batch
    entry = entries[0]
    revision = dict(entry["baseline"]["interpretation"], summary="Synthetic saved revision awaiting its check.")
    if original_invalid:
        entry["baseline"]["interpretation"]["summary"] = None
    path = tmp_path / "revision_1.raw.txt"
    path.write_text(json.dumps(revision), encoding="utf-8")
    raw_before = path.read_bytes()
    result = runner.provisional_result(entry, "Interrupted during fresh prose check.",
                                       revision_attempted=True, directory=tmp_path)
    assert result.status.value == "NEEDS_REVIEW"
    assert result.revision_count == 1 and result.review_reason and result.provisional_fields
    assert result.revised_interpretation.model_dump(mode="json") == revision
    assert result.original_interpretation == entry["baseline"]["interpretation"]
    assert result.effective_attempt == ("revision" if original_invalid else "original")
    expected = revision if original_invalid else entry["baseline"]["interpretation"]
    assert result.interpretation.model_dump(mode="json") == expected
    assert path.read_bytes() == raw_before


def test_all_200_real_threads_survive_mocked_model_failures_and_inputs_are_unchanged(batch, monkeypatch):
    runner, _, output = batch
    # Load actual production inputs; no evaluation labels enter the pipeline.
    spec = importlib.util.spec_from_file_location("real_verification_inputs", ROOT / "scripts/run_agent1_verification.py")
    real_runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(real_runner)
    entries = real_runner.load_inputs()
    assert len(entries) == 200
    monkeypatch.setattr(runner, "load_inputs", lambda: entries)
    protected = [ROOT / "data/processed/agent1_authority_fix/interpretations.json",
                 ROOT / "data/processed/grouping/clusters.json", ROOT / "data/knowledge/domain_lexicon.json"]
    for folder in (ROOT / "data/fixtures/slack_generated", ROOT / "data/evaluation"):
        protected.extend(path for path in folder.rglob("*") if path.is_file())
    before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in protected}
    calls = []

    def failed_models(thread, original, **callbacks):
        from threadsense.agents.verification_pipeline import verify_and_revise

        def unavailable(*args, on_raw_output, **kwargs):
            calls.append(thread.thread_id)
            on_raw_output("Malformed output retained for review")
            raise ValueError("Offline simulated invalid model response")

        def source_stub_for_failure_retention(thread, **kwargs):
            # Synthetic source classifications exercise retention only, not model accuracy.
            calls.append(thread.thread_id)
            root = next(m for m in thread.messages if m.message_id == thread.thread_id)
            return {
                "thread_id": thread.thread_id, "root_request_quote": root.text,
                "requested_decisions": [root.text], "uncertainties": [],
                "reply_assessments": [{"message_id": m.message_id, "contribution": "OTHER",
                    "evidence_quote": m.text, "explanation": "Synthetic orchestration fixture."}
                    for m in thread.messages if m.message_id != thread.thread_id],
                "decision_coverage": [{"requested_decision": root.text, "status": "UNANSWERED",
                    "answer_message_ids": [], "rationale": "Synthetic orchestration fixture."}],
            }
        return verify_and_revise(thread, original, source_analyzer=source_stub_for_failure_retention,
                                 comparator=unavailable, reviser=unavailable, **callbacks)

    monkeypatch.setattr(runner, "verify_thread", failed_models)
    flags = ["--run", "--limit", "0", "--output-dir", str(output)]
    assert runner.main(flags) == 0
    records = runner.read_json(output / "interpretations.json")
    assert len(records) == len({runner.identity(record) for record in records}) == 178
    routed = runner.read_json(output / "routing_manifest.json")
    assert len(routed["announcement_sources"]) == 22
    assert {runner.identity(record) for record in records}.isdisjoint({runner.identity(r) for r in routed["announcement_sources"]})
    assert {runner.identity(record) for record in records} | {runner.identity(r) for r in routed["announcement_sources"]} == {runner.identity(entry["baseline"]) for entry in entries}
    assert all(row["verification_status"] == "NEEDS_REVIEW" and row["revision_count"] == 1 for row in records)
    assert len(calls) == 534  # One source, failed prose, failed revision per thread; no second prose.
    assert len(runner.read_json(output / "review_queue.json")) == 178
    assert runner.read_json(output / "manifest.json")["unprocessed"] == 0
    for row in records:
        assert (output / row["lineage"]["verification_file"]).is_file()
    monkeypatch.setattr(runner, "verify_thread", lambda *a, **k: pytest.fail("Terminal failures retried"))
    assert runner.main(flags) == 0
    assert before == {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in protected}


def test_200_mixed_mocked_outcomes_continue_after_flagged_and_failed_middle_records(batch, monkeypatch):
    """Synthetic single-question threads test orchestration, not live accuracy."""
    from threadsense.agents.decision_evidence_audit import build_prose_units
    from threadsense.agents.prose_comparison import parse_source_response, parse_prose_response
    from threadsense.agents.verification_pipeline import verify_and_revise

    runner, _, output = batch
    entries = []
    for i in range(200):
        entry = make_entry(runner, f"{i}.0")
        if i % 4 in (1, 2):
            entry["baseline"]["interpretation"]["summary"] = "An author asks whether an item should receive a quality note (QN)."
        entry["baseline_sha256"] = runner.digest(entry["baseline"])
        entry["key"] = runner.digest({"source": entry["source"], "baseline": entry["baseline"]})
        entries.append(entry)
    monkeypatch.setattr(runner, "load_inputs", lambda: entries)
    invoked, stages = [], {}

    def model_mocks(thread, original, **callbacks):
        i = int(thread.thread_id.split(".")[0])
        invoked.append(i)
        stages[i] = []
        if i % 4 == 3:
            callbacks["on_stage_start"]("source_analysis")
            stages[i].append("source_analysis")
            raise TimeoutError("Synthetic interrupted per-thread request")
        question = thread.messages[0].text

        def source(current, **kwargs):
            stages[i].append("source_analysis")
            payload = {"thread_id": current.thread_id, "root_request_quote": question,
                "requested_decisions": [question], "reply_assessments": [], "uncertainties": [],
                "decision_coverage": [{"requested_decision": question, "status": "UNANSWERED",
                    "answer_message_ids": [], "rationale": "The single root has no reply."}]}
            raw = json.dumps(payload)
            kwargs["on_raw_output"](raw)
            return parse_source_response(current, raw)

        def compare(current, *, interpretation, **kwargs):
            stages[i].append("prose")
            assessments = []
            for unit in build_prose_units(interpretation):
                wrong = "quality note" in unit["candidate_text"]
                meaning = ("QN means Quarantine, not quality note." if wrong else
                           "The author asks whether this item should enter Quarantine; there are no replies.")
                assessments.append({"unit_id": unit["unit_id"], "candidate_text": unit["candidate_text"],
                    "verdict": "CONTRADICTED" if wrong else "SUPPORTED", "source_interpretation": meaning,
                    "explanation": meaning, "evidence_message_ids": [current.thread_id], "evidence_quotes": [question]})
            raw = json.dumps({"prose_assessments": assessments})
            kwargs["on_raw_output"](raw)
            return parse_prose_response(current, raw, interpretation)

        def revise(current, previous, findings, analysis, **kwargs):
            stages[i].append("revision")
            assert findings and analysis.thread_id == current.thread_id
            corrected = previous.model_copy(deep=True)
            if i % 4 == 1:
                corrected.summary = "An author asks whether an item should enter Quarantine."
            kwargs["on_raw_output"](corrected.model_dump_json())
            return corrected

        return verify_and_revise(thread, original, source_analyzer=source, comparator=compare, reviser=revise, **callbacks)

    monkeypatch.setattr(runner, "verify_thread", model_mocks)
    flags = ["--run", "--limit", "0", "--output-dir", str(output)]
    assert runner.main(flags) == 0  # Completed review flags do not block downstream work.
    assert invoked == list(range(200))
    records = runner.read_json(output / "interpretations.json")
    queue = runner.read_json(output / "review_queue.json")
    assert len(records) == len({runner.identity(row) for row in records}) == 200
    assert queue == [row for row in records if row["review_required"]]
    assert len(queue) == 100
    assert runner.read_json(output / "manifest.json")["counts"] == {"VERIFIED": 50, "CORRECTED": 50, "NEEDS_REVIEW": 100}
    assert runner.read_json(output / "manifest.json")["state"] == "complete_with_review"
    assert runner.read_json(output / "manifest.json")["unprocessed"] == 0
    for row in records:
        assert row["candidate_sha256"] == runner.digest(row["interpretation"])
        assert (output / row["lineage"]["source_file"]).is_file()
        saved = runner.read_json(output / row["lineage"]["verification_file"])["result"]
        if row["verification_status"] == "CORRECTED":
            assert saved["passes"][0]["findings"] and not saved["passes"][1]["findings"]
            assert row["review_reasons"] == [] and row["provisional_fields"] == []
        elif row["review_required"]:
            assert row["review_reason"] and row["provisional_fields"]
    assert all(len(calls) <= 4 and calls.count("source_analysis") == 1 and calls.count("revision") <= 1 for calls in stages.values())
    monkeypatch.setattr(runner, "verify_thread", lambda *a, **k: pytest.fail("Terminal records retried"))
    assert runner.main(flags) == 0


@pytest.mark.parametrize("failure_type", ["configuration", "persistence"])
def test_fatal_failure_stops_run_and_is_not_reported_as_success(batch, monkeypatch, failure_type):
    from threadsense.agents.verification_requests import EvidencePersistenceError, VerificationConfigurationError

    runner, _, output = batch
    error_type = VerificationConfigurationError if failure_type == "configuration" else EvidencePersistenceError
    calls = []

    def fail(thread, original, **kwargs):
        calls.append(thread.thread_id)
        raise error_type("Synthetic fatal failure")

    monkeypatch.setattr(runner, "verify_thread", fail)
    assert runner.main(["--run", "--limit", "0", "--output-dir", str(output)]) == 1
    assert calls == ["1.0"]
    manifest = runner.read_json(output / "manifest.json")
    assert manifest["state"] == "failed" and manifest["unprocessed"] == 1
    assert len(runner.read_json(output / "interpretations.json")) == 2
