"""Offline reconciliation of archived verification evidence into a new handoff.

No model entry point is invoked. --write creates derived outputs in a new
directory; default --dry-run validates/replays evidence without writing.
"""

import argparse
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path

from threadsense.agents.decision_evidence_audit import build_prose_units
from threadsense.agents.prose_comparison import parse_source_response, parse_prose_response
from threadsense.agents.thread_interpreter import parse_interpretation_response
from threadsense.agents.verification_handoff import build_handoff, file_hash, load_content_reviews
from threadsense.terminology import get_terms


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("verification_runner_for_reconciliation", Path(__file__).with_name("run_agent1_verification.py"))
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def replay_record(directory, entry, result, config):
    """Use real parsers for archived responses, retaining missing-response facts."""
    checks = []
    source = None
    revision = None
    for stage in runner.STAGES:
        request_path = directory / f"{stage}.request.json"
        if not request_path.exists():
            if (directory / f"{stage}.call.json").exists():
                raise ValueError("Recorded call is missing its exact request.")
            continue
        request = runner.read_json(request_path)
        expected_model = config["interpreter_model"] if stage == "revision_1" else config["auditor_model"]
        if request["model"] != expected_model.partition("/")[2] or len(request["messages"]) != 2:
            raise ValueError("Historical request model/history mismatch.")
        inputs = json.loads(request["messages"][1]["content"])
        candidate = revision.model_dump(mode="json") if stage == "prose_2" and revision else result.original_interpretation
        if stage == "revision_1":
            if set(inputs) != {"revision_task"} or entry["thread"].model_dump_json() not in inputs["revision_task"]:
                raise ValueError("Historical revision request omits its actual source.")
        else:
            keys = {"original_conversation", "approved_glossary"}
            if stage.startswith("prose_"):
                keys.add("candidate_prose_units")
            if set(inputs) != keys or inputs["original_conversation"] != entry["source"] or inputs["approved_glossary"] != get_terms():
                raise ValueError("Historical request source/glossary/input boundary mismatch.")
            if stage == "prose_2" and revision is None:
                raise ValueError("Second prose request has no validated saved revision.")
            if stage.startswith("prose_") and inputs["candidate_prose_units"] != build_prose_units(candidate):
                raise ValueError("Historical request is bound to a different candidate.")
        item = {"stage": stage, "request_sha256": file_hash(request_path),
                "request_attempted": (directory / f"{stage}.call.json").exists()}
        response_path = directory / f"{stage}.response.raw.bin"
        if not response_path.exists():
            if result.status.value != "NEEDS_REVIEW":
                raise ValueError("An accepted historical result is missing a model response.")
            checks.append({**item, "status": "REQUEST_WITHOUT_RESPONSE", "provider_completion": "unknown"})
            continue
        response = runner.read_json(response_path)
        http = runner.read_json(directory / f"{stage}.response.json")
        if http["http_status"] != 200 or http.get("failure"):
            if result.status.value != "NEEDS_REVIEW":
                raise ValueError("Accepted historical result has a failed request.")
            checks.append({**item, "status": "FAILED_RESPONSE_RETAINED"})
            continue
        choices = response.get("choices", [])
        if len(choices) != 1 or choices[0].get("finish_reason") != "stop":
            raise ValueError("Historical response is incomplete.")
        raw = (directory / f"{stage}.raw.txt").read_text(encoding="utf-8")
        if raw != choices[0]["message"]["content"]:
            raise ValueError("Historical raw text differs from its HTTP response.")
        if stage == "source_analysis":
            source = parse_source_response(entry["thread"], raw)
            if result.source_analysis is not None and source != result.source_analysis:
                raise ValueError("Saved source analysis differs from its response.")
        elif stage == "revision_1":
            revision = parse_interpretation_response(entry["thread"], raw)
            if result.revised_interpretation is not None and revision != result.revised_interpretation:
                raise ValueError("Saved revision differs from its response.")
        else:
            comparison = parse_prose_response(entry["thread"], raw, candidate)
            attempt = next((p for p in result.passes if p.number == int(stage[-1])), None)
            if attempt and attempt.audit:
                if comparison.prose_assessments != attempt.audit.prose_assessments:
                    raise ValueError("Saved prose assessments differ from their response.")
                if source is None or any(getattr(attempt.audit, key) != value for key, value in source):
                    raise ValueError("Pass did not reuse the saved source analysis.")
        checks.append({**item, "status": "VALIDATED_SAVED_RESPONSE", "response_sha256": file_hash(response_path)})
    if sum(item["request_attempted"] for item in checks) > 4:
        raise ValueError("Historical record exceeds four request attempts.")
    return {"thread_id": entry["thread"].thread_id, "stages": checks}


def reconcile(evidence, output, review_paths, *, write=False):
    evidence, output = Path(evidence).resolve(), Path(output).resolve()
    runner.check_output_directory(output)
    if output.exists() or output == evidence or output in evidence.parents or evidence in output.parents:
        raise ValueError("Use a new, separate directory for offline reconciliation.")
    snapshot = {p.relative_to(evidence).as_posix(): file_hash(p) for p in evidence.rglob("*") if p.is_file()}
    manifest = runner.read_json(evidence / "manifest.json")
    config = manifest["config"]
    entries = runner.load_inputs()
    if (config["baseline_sha256"] != runner.digest(runner.read_json(runner.BASELINE))
            or config["source_sha256"] != runner.digest([entry["source"] for entry in entries])
            or config["glossary_sha256"] != file_hash(ROOT / "data/knowledge/domain_lexicon.json")):
        raise ValueError("Historical source/baseline/glossary fingerprints no longer match available inputs.")
    # Explicit historical validation: its recorded code/model config is not
    # represented as the current version's verification cache.
    cached = runner.inspect_cache(evidence, entries, config, historical=True)
    retained = [e for e in entries if e["key"] in manifest["selection"]]
    if any(e["key"] not in cached or cached[e["key"]] is None for e in retained):
        raise ValueError("Historical records require explicit terminal retention before reconciliation.")
    replay = [replay_record(evidence / "records" / e["key"], e, cached[e["key"]], config) for e in retained]
    reviews, diagnostics = load_content_reviews(review_paths, ROOT)
    records, queue, counts, report = build_handoff(output, evidence, retained, cached, config, runner.BASELINE,
        reviews=reviews, diagnostics=diagnostics, origin="offline_reconciliation")
    if snapshot != {p.relative_to(evidence).as_posix(): file_hash(p) for p in evidence.rglob("*") if p.is_file()}:
        raise ValueError("Historical evidence changed during reconciliation.")
    derived = {
        "kind": "offline_reconciliation", "new_model_calls": 0,
        "historical_run_config_sha256": manifest["run_config_sha256"],
        "historical_pipeline_version": config["pipeline_version"],
        "historical_evidence_directory": str(evidence), "historical_artifact_sha256": snapshot,
        "handoff_config_sha256": report["config_sha256"], "reconciliation_code_sha256": file_hash(Path(__file__)),
        "retained": len(records), "counts": counts, "review_records": len(queue),
        "reconciled_at": datetime.now(timezone.utc).isoformat(),
        "note": "Derived handoff; not new live verification and not a resumable verification cache.",
    }
    if write:
        output.mkdir(parents=True, exist_ok=False)
        for name, payload in {"interpretations.json": records, "review_queue.json": queue,
                              "content_review_report.json": report, "replay_report.json": replay,
                              "manifest.json": derived}.items():
            runner.write_json(output / name, payload, exclusive=True)
    return derived


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-dir", type=Path, default=ROOT / "data/processed/agent1_verified_pilot_v6")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data/processed/agent1_handoff_reconciled_v1")
    parser.add_argument("--content-review", type=Path, action="append")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true", help="Write derived files; no model calls.")
    mode.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = reconcile(args.evidence_dir, args.output_dir,
                           args.content_review or [runner.DEFAULT_CONTENT_REVIEW], write=args.write)
    except (ValueError, KeyError, OSError) as error:
        parser.error(str(error))
    print(json.dumps({key: report[key] for key in ("kind", "new_model_calls", "retained", "counts", "review_records")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
