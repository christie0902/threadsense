"""Historical replay and offline review binding; no new live accuracy claims."""

from copy import deepcopy
import importlib.util
import json
from pathlib import Path

import pytest

from threadsense.agents.verification_handoff import (
    apply_content_reviews, digest, file_hash, identity, load_content_reviews,
)


ROOT = Path(__file__).resolve().parents[1]
PILOT = ROOT / "data/processed/agent1_verified_pilot_v6"
from threadsense.metadata_paths import resolve_metadata
REVIEW = resolve_metadata(ROOT / "docs/agent1-pilot-content-review.json")


@pytest.fixture
def reconciler():
    spec = importlib.util.spec_from_file_location("offline_reconciler_test", ROOT / "scripts/reconcile_agent1_handoff.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_actual_v6_replay_exports_effective_status_without_changing_history(reconciler, tmp_path, monkeypatch):
    from threadsense.agents import verification_requests

    monkeypatch.setattr(verification_requests, "send_once", lambda *a, **k: pytest.fail("Paid call in offline replay"))
    monkeypatch.setattr(reconciler.runner, "verify_thread", lambda *a, **k: pytest.fail("Reverification in historical replay"))
    protected = [*PILOT.rglob("*"), REVIEW]
    before = {p: file_hash(p) for p in protected if p.is_file()}
    output = tmp_path / "handoff_v1"
    manifest = reconciler.reconcile(PILOT, output, [REVIEW], write=True)
    read = reconciler.runner.read_json
    records = read(output / "interpretations.json")
    queue = read(output / "review_queue.json")
    assert manifest["kind"] == "offline_reconciliation" and manifest["new_model_calls"] == 0
    assert manifest["counts"] == {"VERIFIED": 1, "CORRECTED": 1, "NEEDS_REVIEW": 2}
    historical = {identity(r): r for r in read(PILOT / "interpretations.json")}
    assert len({identity(row) for row in records}) == len(records) == 4
    assert queue == [row for row in records if row["verification_status"] == "NEEDS_REVIEW"]
    for row in records:
        original = historical[identity(row)]
        assert row["interpretation"] == original["interpretation"]
        assert row["automated_verification_status"] == original["verification_status"]
        assert row["verification_origin"] == "offline_reconciliation"
        assert row["candidate_sha256"] == digest(row["interpretation"])
        assert row["input_sha256"] == digest(read(output / row["lineage"]["source_file"]))
        assert (output / row["lineage"]["verification_file"]).is_file()
        assert row["content_reviews"]
        assert all(review["provenance"]["human_approval"] is False for review in row["content_reviews"])
        assert all(review["provenance"]["reviewer_identity"] is None and review["provenance"]["reviewed_at"] is None for review in row["content_reviews"])
    disputed = next(row for row in records if row["thread_id"] == "1790882197.000111")
    assert disputed["automated_verification_status"] == "CORRECTED"
    assert disputed["verification_status"] == "NEEDS_REVIEW"
    assert disputed["provisional_fields"] == ["summary"]
    assert "seems to have failed" in disputed["interpretation"]["summary"]
    assert disputed["review_reason"] and disputed["review_findings"][0]["evidence_message_ids"]
    replay = read(output / "replay_report.json")
    stages = [stage for record in replay for stage in record["stages"]]
    assert sum(stage["request_attempted"] for stage in stages) == 12
    assert sum(stage["status"] == "VALIDATED_SAVED_RESPONSE" for stage in stages) == 11
    assert sum(stage["status"] == "REQUEST_WITHOUT_RESPONSE" for stage in stages) == 1
    assert before == {path: file_hash(path) for path in before}
    with pytest.raises(ValueError, match="not a live verification cache"):
        reconciler.runner.inspect_cache(output, reconciler.runner.load_inputs(), {})
    # Current code cannot silently reuse the historical verification cache.
    entries = reconciler.runner.load_inputs()
    config = reconciler.runner.run_configuration(entries)
    config["source_count"] = len(entries)
    with pytest.raises(ValueError, match="changed"):
        reconciler.runner.inspect_cache(PILOT, entries, config)


def base_record(review):
    return {**{key: review[key] for key in ("project_id", "batch_id", "channel_id", "thread_id")},
            "input_sha256": review["source_sha256"], "candidate_sha256": review["candidate_sha256"],
            "verification_status": "CORRECTED", "automated_verification_status": "CORRECTED",
            "review_required": False, "provisional_fields": [], "review_reason": None,
            "review_reasons": [], "review_findings": [], "content_reviews": [], "review_applicability": []}


@pytest.fixture
def bound_review():
    reviews, diagnostics = load_content_reviews([REVIEW], ROOT)
    assert not diagnostics
    return next(review for review in reviews if review["thread_id"] == "1790882197.000111")


@pytest.mark.parametrize("field, expected", [
    ("project_id", "UNMATCHED_IDENTITY"), ("batch_id", "UNMATCHED_IDENTITY"),
    ("channel_id", "UNMATCHED_IDENTITY"), ("thread_id", "UNMATCHED_IDENTITY"),
    ("input_sha256", "STALE_SOURCE"), ("candidate_sha256", "STALE_CANDIDATE"),
])
def test_dispute_cannot_transfer_to_another_identity_source_or_candidate(bound_review, field, expected):
    record = base_record(bound_review)
    record[field] = "different"
    report = apply_content_reviews([record], [bound_review])
    assert report[0]["status"] == expected
    assert record["verification_status"] == "CORRECTED"
    assert record["content_reviews"] == []
    assert not record["review_required"]


def test_matching_negative_review_overrides_acceptance_and_positive_is_not_human_approval(bound_review):
    record = base_record(bound_review)
    positive = deepcopy(bound_review)
    positive.update(review_id="synthetic-positive-test-review", needs_review=False, findings=[],
                    disputed_fields=[], review_reason=None, source_review_outcome="PASS")
    report = apply_content_reviews([record], [bound_review, positive])
    assert [item["status"] for item in report] == ["APPLIED_DISPUTE", "MATCHED_NONAPPROVAL"]
    assert record["verification_status"] == "NEEDS_REVIEW"
    assert record["automated_verification_status"] == "CORRECTED"
    assert record["provisional_fields"] == ["summary"]
    assert record["review_findings"] and record["review_reasons"]
    assert not any(review["provenance"]["human_approval"] for review in record["content_reviews"])


@pytest.mark.parametrize("corruption", ["quote", "identity", "candidate", "hash", "missing_reference", "evaluation_reference"])
def test_invalid_review_bindings_are_reported_not_silently_applied(tmp_path, corruption):
    document = json.loads(REVIEW.read_text(encoding="utf-8"))
    row = deepcopy(document["reviews"][1])
    if corruption == "quote":
        row["findings"][0]["evidence_quotes"][0] = "Invented source statement."
    elif corruption == "identity":
        row["batch_id"] = "wrong-batch"
    elif corruption == "candidate":
        row["findings"][0]["candidate_text"] = "Claim absent from this interpretation."
    elif corruption == "hash":
        row["candidate_sha256"] = "0" * 64
    elif corruption == "evaluation_reference":
        row["source_file"] = "data/evaluation/do_not_read.json"
    else:
        row["source_file"] = "missing-source.json"
    path = tmp_path / "reviews.json"
    path.write_text(json.dumps({"review_type": document["review_type"], "reviews": [row]}), encoding="utf-8")
    # The explicit review file may be external; evidence references remain scoped to ROOT.
    reviews, diagnostics = load_content_reviews([path], ROOT)
    assert reviews == []
    assert diagnostics[0]["status"] == "INVALID_REVIEW"
    assert diagnostics[0]["reason"]


def test_reconciliation_dry_run_is_read_only_and_refuses_existing_output(reconciler, tmp_path):
    output = tmp_path / "handoff_v1"
    report = reconciler.reconcile(PILOT, output, [REVIEW])
    assert report["new_model_calls"] == 0
    assert not output.exists()
    output.mkdir()
    with pytest.raises(ValueError, match="new, separate"):
        reconciler.reconcile(PILOT, output, [REVIEW], write=True)
