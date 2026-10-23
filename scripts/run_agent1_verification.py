"""Verify saved Agent 1 interpretations with at most one targeted revision.

Offline preflight is the default. Paid calls require --run. Run one process per
output directory. Completed results (including NEEDS_REVIEW) are never retried;
an interrupted started attempt is retained for review without repeating calls.
Exit codes: 0 completed/preflight (including review flags), 1 fatal/interrupted/incomplete,
2 invalid CLI/input/cache. Review flags never request a human-approval pause.
"""

import argparse
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

from threadsense.adapters.mock_slack import MockSlackAdapter
from threadsense.agents.contracts import ThreadInterpretation
from threadsense.config import get_api_key, get_model_settings
from threadsense.agents.verification_handoff import (
    build_handoff, digest, identity, load_content_reviews,
)
from threadsense.agents.verification_requests import EvidencePersistenceError, VerificationConfigurationError


ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "data/processed/agent1_authority_fix/interpretations.json"
FIXTURES = ROOT / "data/fixtures/slack_generated"
STAGES = ("source_analysis", "prose_1", "revision_1", "prose_2")
ARTIFACTS = ("request.json", "call.json", "response.raw.bin", "response.json", "failure.json")
PIPELINE_VERSION = 3
DEFAULT_CONTENT_REVIEW = ROOT / "docs/agent1-pilot-content-review.json"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, value: object, *, exclusive: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if exclusive:
        with path.open("x", encoding="utf-8") as handle:
            handle.write(text)
    else:
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(text, encoding="utf-8")
        temporary.replace(path)


def load_inputs() -> list[dict]:
    """Join the saved baseline to original Slack, independently of clustering."""
    baseline = read_json(BASELINE)
    if not isinstance(baseline, list) or not baseline:
        raise ValueError("Baseline must contain a nonempty list of interpretations.")
    adapter = MockSlackAdapter(str(FIXTURES / "channels"), str(FIXTURES / "users.json"))
    sources = {}
    for path in sorted((FIXTURES / "channels").glob("C_*.json")):
        for thread in adapter.get_threads(path.stem):
            key = identity(thread.model_dump())
            if key in sources:
                raise ValueError(f"Duplicate source thread: {key}")
            sources[key] = thread
    seen, entries = set(), []
    for record in baseline:
        if not isinstance(record, dict) or not isinstance(record.get("interpretation"), dict):
            raise ValueError("Every baseline record must contain an interpretation object.")
        key = identity(record)
        if key in seen or key not in sources:
            raise ValueError(f"Duplicate baseline or missing original Slack thread: {key}")
        seen.add(key)
        thread = sources[key]
        source = thread.model_dump(mode="json")
        entries.append({
            "thread": thread, "baseline": record, "source": source,
            "source_sha256": digest(source),
            "baseline_sha256": digest(record),
            "key": digest({"source": source, "baseline": record}),
        })
    if seen != set(sources):
        raise ValueError("Baseline and Slack source coverage differ; no threads may be omitted.")
    return entries


def run_configuration(entries: list[dict]) -> dict:
    from threadsense.agents.decision_evidence_audit import get_auditor_model_settings

    model, _ = get_model_settings()
    auditor_model, _ = get_auditor_model_settings()
    code_files = [
        "scripts/run_agent1_verification.py", "src/threadsense/config.py",
        "src/threadsense/models.py", "src/threadsense/terminology.py",
        "src/threadsense/adapters/mock_slack.py",
        *[f"src/threadsense/agents/{name}.py" for name in (
            "contracts", "thread_interpreter", "decision_evidence_audit",
            "interpretation_verifier", "interpretation_revision", "verification_pipeline",
            "prose_comparison", "verification_requests", "verification_handoff",
        )],
    ]
    return {
        "pipeline_version": PIPELINE_VERSION,
        "maximum_calls_per_thread": 4, "automatic_retries": 0,
        "interpreter_model": model,
        "auditor_model": auditor_model,
        "baseline_sha256": digest(read_json(BASELINE)),
        "source_sha256": digest([entry["source"] for entry in entries]),
        "glossary_sha256": hashlib.sha256(
            (ROOT / "data/knowledge/domain_lexicon.json").read_bytes()
        ).hexdigest(),
        "code_sha256": {
            name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in code_files
        },
        "packages": {name: version(name) for name in ("crewai", "litellm", "pydantic")},
    }


def check_output_directory(output: Path) -> None:
    if not re.search(r"_v[1-9][0-9]*$", output.name):
        raise ValueError("Use a NEW versioned output directory ending in _v1, _v2, etc.")
    protected = [
        FIXTURES.resolve(), BASELINE.parent.resolve(),
        (ROOT / "data/processed/grouping").resolve(),
        (ROOT / "data/knowledge").resolve(), (ROOT / "data/evaluation").resolve(),
    ]
    if any(output == path or output in path.parents or path in output.parents for path in protected):
        raise ValueError("Output directory overlaps protected inputs or historical artifacts.")


def metadata(entry: dict, config_hash: str, *, pipeline_version=PIPELINE_VERSION) -> dict:
    return {
        "pipeline_version": pipeline_version, "run_config_sha256": config_hash,
        "source_sha256": entry["source_sha256"],
        "baseline_sha256": entry["baseline_sha256"], "key": entry["key"],
    }


def raw_files(directory: Path) -> dict[str, str]:
    return {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for stage in STAGES if (path := directory / f"{stage}.raw.txt").exists()
    }


def artifact_files(directory: Path) -> dict[str, str]:
    return {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for stage in STAGES for suffix in ARTIFACTS
        if (path := directory / f"{stage}.{suffix}").exists()
    }


def stage_files(directory: Path) -> dict[str, str]:
    return {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for stage in STAGES if (path := directory / f"{stage}.started.json").exists()
    }


def validate_result(entry: dict, payload: dict):
    from threadsense.agents.verification_pipeline import VerificationResult
    from threadsense.agents.decision_evidence_audit import validate_source_analysis, validate_decision_evidence_audit
    from threadsense.agents.interpretation_verifier import verify_interpretation

    result = VerificationResult.model_validate(payload)
    if result.interpretation.thread_id != entry["thread"].thread_id:
        raise ValueError("Cached final interpretation has the wrong thread ID.")
    if result.original_interpretation != entry["baseline"]["interpretation"]:
        raise ValueError("Cached original interpretation does not match the baseline.")
    if result.revision_count not in (0, 1) or len(result.passes) > 2:
        raise ValueError("Cached result exceeds the bounded verification workflow.")
    if result.source_analysis is not None:
        validate_source_analysis(entry["thread"], result.source_analysis)
    for attempt in result.passes:
        if attempt.audit is not None:
            validate_decision_evidence_audit(entry["thread"], attempt.audit, attempt.interpretation)
        if attempt.passed and verify_interpretation(
            entry["thread"], ThreadInterpretation.model_validate(attempt.interpretation), attempt.audit,
        ):
            raise ValueError("Cached passing audit fails deterministic verification.")
    if result.status.value != "NEEDS_REVIEW" and result.interpretation.model_dump(mode="json") != result.passes[-1].interpretation:
        raise ValueError("Cached passing interpretation does not match its assessed candidate.")
    return result


def inspect_cache(output: Path, entries: list[dict], config: dict, *, historical=False) -> dict:
    """Check every cached record before any paid request, including unselected rows."""
    manifest = output / "manifest.json"
    if not output.exists():
        return {}
    if not manifest.exists():
        if any(path.name != ".running.lock" for path in output.iterdir()):
            raise ValueError("Output contains files without this pipeline's manifest. Choose a new directory.")
        return {}
    saved = read_json(manifest)
    if saved.get("kind") == "offline_reconciliation":
        raise ValueError("Offline handoff reconciliation is not a live verification cache.")
    if historical and config.get("pipeline_version") not in (2, 3):
        raise ValueError("Unsupported historical evidence contract.")
    config_hash = digest(config)
    if saved.get("config") != config or saved.get("run_config_sha256") != config_hash:
        raise ValueError("Inputs, models, glossary, code, or packages changed. Choose a new output directory.")
    by_key = {entry["key"]: entry for entry in entries}
    selection = saved.get("selection", [])
    if (not isinstance(selection, list) or any(not isinstance(key, str) for key in selection)
            or len(selection) != len(set(selection)) or set(selection) - by_key.keys()):
        raise ValueError("Cached manifest contains an invalid thread selection.")
    allowed_output = {"manifest.json", "interpretations.json", "review_queue.json",
                      "sources", "records", ".running.lock", "content_review_report.json", "content_review_report.json.tmp",
                      "manifest.json.tmp", "interpretations.json.tmp", "review_queue.json.tmp"}
    if any(path.name not in allowed_output for path in output.iterdir()):
        raise ValueError("Output directory contains files from another workflow.")
    cached = {}
    records_dir = output / "records"
    for directory in records_dir.iterdir() if records_dir.exists() else []:
        if not directory.is_dir() or directory.name not in by_key:
            raise ValueError(f"Unknown cache record: {directory.name}")
        entry = by_key[directory.name]
        expected = metadata(entry, config_hash, pipeline_version=config["pipeline_version"] if historical else PIPELINE_VERSION)
        started = directory / "started.json"
        allowed = {"started.json", "result.json", "result.json.tmp",
                   *[f"{s}.raw.txt" for s in STAGES], *[f"{s}.started.json" for s in STAGES],
                   *[f"{s}.{suffix}" for s in STAGES for suffix in ARTIFACTS]}
        if any(path.name not in allowed for path in directory.iterdir()):
            raise ValueError(f"Unexpected cache files: {directory.name}")
        if not started.exists() or read_json(started).get("metadata") != expected:
            raise ValueError(f"Missing or mismatched started-attempt record: {directory.name}")
        source_path = output / "sources" / f"{entry['source_sha256']}.json"
        if not source_path.exists() or digest(read_json(source_path)) != entry["source_sha256"]:
            raise ValueError(f"Cached source is missing or modified: {directory.name}")
        result_path = directory / "result.json"
        if not result_path.exists():
            cached[directory.name] = None  # Started, never silently retry it.
            continue
        record = read_json(result_path)
        if record.get("metadata") != expected or record.get("result_sha256") != digest(record.get("result")):
            raise ValueError(f"Cached result metadata/checksum mismatch: {directory.name}")
        if record.get("raw_files") != raw_files(directory):
            raise ValueError(f"Cached raw response is missing or modified: {directory.name}")
        if record.get("stage_files") != stage_files(directory):
            raise ValueError(f"Cached stage marker is missing or modified: {directory.name}")
        if record.get("artifact_files") != artifact_files(directory):
            raise ValueError(f"Cached request/response artifact is missing or modified: {directory.name}")
        cached[directory.name] = validate_result(entry, record["result"])
    return cached


def provisional_result(entry: dict, reason: str, *, revision_attempted: bool = False, directory: Path | None = None):
    from threadsense.agents.verification_pipeline import retain_for_review

    result = retain_for_review(
        entry["thread"], entry["baseline"]["interpretation"], reason,
        revision_count=int(revision_attempted),
    )
    if directory is not None:
        # Preserve an actual saved revision even if interruption prevented its
        # final check. Never reconstruct missing model output or retry a call.
        from threadsense.agents.thread_interpreter import parse_interpretation_response
        path = directory / "revision_1.raw.txt"
        if path.exists():
            try:
                revision = parse_interpretation_response(entry["thread"], path.read_text(encoding="utf-8"))
                result.revised_interpretation = revision
                result.revision_count = 1
                if result.effective_attempt == "fallback":
                    result.interpretation = revision
                    result.effective_attempt = "revision"
            except (ValueError, RuntimeError, TypeError) as error:
                result.revision_error = redact_error(error)
    return result


def save_result(output: Path, entry: dict, config_hash: str, result) -> None:
    directory = output / "records" / entry["key"]
    payload = result.model_dump(mode="json")
    validate_result(entry, payload)
    write_json(directory / "result.json", {
        "metadata": metadata(entry, config_hash), "result": payload,
        "result_sha256": digest(payload), "raw_files": raw_files(directory),
        "stage_files": stage_files(directory), "artifact_files": artifact_files(directory),
    })


def write_reports(output, retained, config, results, *, selected, state, attempted, unprocessed,
                  reviews=(), review_diagnostics=()):
    records, queue, counts, review_report = build_handoff(
        output, output, retained, results, config, BASELINE,
        reviews=reviews, diagnostics=review_diagnostics,
    )
    if state == "complete" and counts["NEEDS_REVIEW"]:
        state = "complete_with_review"
    config_hash = digest(config)
    write_json(output / "interpretations.json", records)
    write_json(output / "review_queue.json", queue)
    write_json(output / "content_review_report.json", review_report)
    write_json(output / "manifest.json", {
        "config": config, "run_config_sha256": config_hash,
        "handoff_config_sha256": review_report["config_sha256"],
        "updated_at": datetime.now(timezone.utc).isoformat(), "state": state,
        "selected": len(selected), "counts": counts,
        "retained": len(retained),
        "attempted_this_run": attempted, "unprocessed": unprocessed,
        "model_calls_recorded": sum(1 for _ in (output / "records").glob("*/*.call.json")),
        "selection": [entry["key"] for entry in retained],
        "requested_selection": [entry["key"] for entry in selected],
        "coverage": "all_source_threads" if len(retained) == config["source_count"] else "selected_subset",
    })
    return counts


def verify_thread(thread, original, *, on_raw_output, on_stage_start, on_artifact):
    from threadsense.agents.verification_pipeline import verify_and_revise

    return verify_and_revise(thread, original, on_raw_output=on_raw_output, on_stage_start=on_stage_start, on_artifact=on_artifact)


def redact_error(error: BaseException) -> str:
    text = str(error) or type(error).__name__
    for name in ("OPENAI_API_KEY", "OPENROUTER_API_KEY"):
        if key := os.getenv(name, "").strip():
            text = text.replace(key, "[redacted]")
    return text[:1000]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Offline preflight; no calls or writes (default).")
    mode.add_argument("--run", action="store_true", help="Authorize paid audit/revision calls for this selection.")
    parser.add_argument("--limit", type=int, default=1, help="Small pilot by default; 0 selects all.")
    parser.add_argument("--thread-id", action="append", help="Select specific thread IDs (repeatable).")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data/processed/agent1_verified_v3")
    parser.add_argument("--content-review", type=Path, action="append",
                        help="Source/candidate-bound content reviews; repeatable. Defaults to the saved review registry.")
    args = parser.parse_args(argv)
    if args.limit < 0:
        parser.error("--limit must be zero or positive")
    try:
        entries = load_inputs()
        selected = entries
        if args.thread_id:
            requested = set(args.thread_id)
            missing = requested - {entry["thread"].thread_id for entry in entries}
            if missing:
                raise ValueError(f"Unknown thread IDs: {sorted(missing)}")
            selected = [entry for entry in entries if entry["thread"].thread_id in requested]
        if args.limit:
            selected = selected[:args.limit]
        output = args.output_dir.resolve()
        check_output_directory(output)
        config = run_configuration(entries)
        config["source_count"] = len(entries)
        cached = inspect_cache(output, entries, config)
        reviews, review_diagnostics = load_content_reviews(args.content_review or [DEFAULT_CONTENT_REVIEW], ROOT)
    except (ValueError, OSError, KeyError) as error:
        parser.error(str(error))
    print(f"Selected {len(selected)} of {len(entries)} source threads.")
    for entry in selected:
        state = "cached" if cached.get(entry["key"]) is not None else "interrupted; review" if entry["key"] in cached else "new"
        print(f"  {entry['thread'].channel_id}/{entry['thread'].thread_id}: {state}")
    pending = [entry for entry in selected if entry["key"] not in cached]
    print(f"Compatible cached records: {len(selected) - len(pending)}; unstarted records: {len(pending)}.")
    print(f"Content reviews loaded: {len(reviews)}; invalid reviews: {len(review_diagnostics)}.")
    for diagnostic in review_diagnostics:
        print(f"  INVALID_REVIEW: {diagnostic['reason']}")
    print(f"Maximum new model tasks: {4 * len(pending)} (source analysis, prose, optional revision and fresh prose).")
    if not args.run:
        print("Dry run: no API calls, credentials required, or output files written.")
        return 0
    if pending:
        try:
            from threadsense.agents.decision_evidence_audit import get_auditor_model_settings
            get_api_key(get_model_settings()[1])
            get_api_key(get_auditor_model_settings()[1])
        except (ValueError, RuntimeError) as error:
            parser.error(str(error))
    output.mkdir(parents=True, exist_ok=True)
    lock = output / ".running.lock"
    try:
        with lock.open("x", encoding="utf-8") as handle:
            handle.write(f"PID {os.getpid()}\n")
    except FileExistsError:
        parser.error("Another run or stale lock exists. Confirm that no process is running before removing .running.lock.")
    config_hash = digest(config)
    results = {}
    attempted = 0
    interrupted = False
    fatal = False
    try:
        # Recheck under the lock in case another process finished after preflight.
        cached = inspect_cache(output, entries, config)
        pending = [entry for entry in selected if entry["key"] not in cached]
        prior_selection = read_json(output / "manifest.json")["selection"] if (output / "manifest.json").exists() else []
        retained_keys = {entry["key"] for entry in selected} | set(cached) | set(prior_selection)
        retained = [entry for entry in entries if entry["key"] in retained_keys]
        unprocessed = len(retained_keys - cached.keys())
        for entry in retained:
            source_path = output / "sources" / f"{entry['source_sha256']}.json"
            if source_path.exists():
                if digest(read_json(source_path)) != entry["source_sha256"]:
                    raise ValueError("Saved original Slack source was modified.")
            else:
                write_json(source_path, entry["source"], exclusive=True)
            result = cached.get(entry["key"])
            if result is None:
                reason = (
                    "A previous attempt was interrupted. Preserved responses require review; paid calls were not repeated."
                    if entry["key"] in cached else
                    "Not processed in this run yet; original interpretation is provisional."
                )
                directory = output / "records" / entry["key"]
                result = provisional_result(entry, reason, revision_attempted=(directory / "revision_1.started.json").exists(), directory=directory)
                if entry["key"] in cached:
                    save_result(output, entry, config_hash, result)
            results[entry["key"]] = result
        write_reports(output, retained, config, results, selected=selected, state="running", attempted=0, unprocessed=unprocessed,
                      reviews=reviews, review_diagnostics=review_diagnostics)
        for entry in pending:
            directory = output / "records" / entry["key"]
            write_json(directory / "started.json", {
                "metadata": metadata(entry, config_hash),
                "started_at": datetime.now(timezone.utc).isoformat(),
            }, exclusive=True)
            attempted += 1

            def preserve_stage(stage: str) -> None:
                if stage not in STAGES:
                    raise ValueError(f"Unknown pipeline stage: {stage}")
                write_json(directory / f"{stage}.started.json", {
                    "stage": stage, "started_at": datetime.now(timezone.utc).isoformat(),
                }, exclusive=True)

            def preserve_raw(stage: str, raw: str) -> None:
                if stage not in STAGES:
                    raise ValueError(f"Unknown pipeline stage: {stage}")
                with (directory / f"{stage}.raw.txt").open("x", encoding="utf-8") as handle:
                    handle.write(raw)

            def preserve_artifact(stage: str, name: str, body: bytes) -> None:
                if stage not in STAGES or name not in ARTIFACTS:
                    raise ValueError("Unknown verification artifact.")
                with (directory / f"{stage}.{name}").open("xb") as handle:
                    handle.write(body)

            try:
                result = verify_thread(entry["thread"], entry["baseline"]["interpretation"],
                                       on_raw_output=preserve_raw, on_stage_start=preserve_stage,
                                       on_artifact=preserve_artifact)
            except (Exception, KeyboardInterrupt) as error:
                result = provisional_result(
                    entry, f"Verification interrupted: {redact_error(error)}. Preserved outputs require review; calls will not repeat.",
                    revision_attempted=(directory / "revision_1.started.json").exists(), directory=directory,
                )
                fatal = isinstance(error, (EvidencePersistenceError, VerificationConfigurationError))
                interrupted = fatal or isinstance(error, KeyboardInterrupt)
            save_result(output, entry, config_hash, result)
            results[entry["key"]] = result
            unprocessed -= 1
            write_reports(output, retained, config, results, selected=selected,
                          state="failed" if fatal else "interrupted" if interrupted else "running",
                          attempted=attempted, unprocessed=unprocessed,
                          reviews=reviews, review_diagnostics=review_diagnostics)
            print(f"{entry['thread'].thread_id}: {result.status.value}")
            if interrupted:
                break
        counts = write_reports(output, retained, config, results, selected=selected,
                               state="failed" if fatal else "interrupted" if interrupted else "incomplete" if unprocessed else "complete_with_review" if any(r.status.value == "NEEDS_REVIEW" for r in results.values()) else "complete",
                               attempted=attempted, unprocessed=unprocessed,
                          reviews=reviews, review_diagnostics=review_diagnostics)
    finally:
        lock.unlink(missing_ok=True)
    print(" | ".join(f"{status}: {count}" for status, count in counts.items()))
    print(f"Unprocessed: {unprocessed}. Results: {output / 'interpretations.json'}")
    return 1 if interrupted or unprocessed else 0


if __name__ == "__main__":
    raise SystemExit(main())
