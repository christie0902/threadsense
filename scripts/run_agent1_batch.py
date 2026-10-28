"""Interpret fixture threads once and save resumable inputs for clustering.

Install this file as scripts/run_agent1_batch.py. Run one process per output
folder. This uses ordinary sequential calls, not the OpenAI Batch API.
Rejected thread IDs and errors go to review_required.json; --retry-failed retries
them once per invocation. Exit codes: 0 complete, 1 stopped, 2 review needed.
"""

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import time


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def fingerprint(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def write_json(path: Path, value: object) -> None:
    """Replace only after the complete JSON file has been written."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    for attempt in range(6):
        try:
            temporary.replace(path)
            return
        except PermissionError:
            if attempt == 5:
                raise
            time.sleep(0.5 * (attempt + 1))


def load_threads(fixture_root: Path, channels: list[str] | None, *, cutoff=None, with_routing=False):
    from threadsense.source_ingestion import interpretation_threads
    result=interpretation_threads(fixture_root,cutoff=cutoff,channels=channels)
    return result if with_routing else result[0]


def package_versions() -> dict:
    versions = {}
    for name in ("crewai", "litellm", "pydantic"):
        try:
            versions[name] = version(name)
        except PackageNotFoundError:
            versions[name] = "not-installed"
    return versions


def output_failure_rule(exc: Exception) -> str | None:
    """Recognize only rejection messages emitted by the current interpreter.

    Do not classify arbitrary ValueErrors or provider failures as bad outputs.
    Keeping this in the runner preserves the interpreter's existing cache hash.
    """
    message = str(exc)
    if isinstance(exc, ValueError):
        rules = {
            "The output thread_id does not match the input.": "THREAD_ID_MISMATCH",
            "The output cites unknown message IDs:": "UNKNOWN_EVIDENCE_ID",
            "Authority flag and authority evidence list are inconsistent.": "AUTHORITY_INCONSISTENT",
            "The model cited authority evidence without an eligible author": "AUTHORITY_INELIGIBLE",
        }
        for prefix, rule in rules.items():
            if message.startswith(prefix):
                return rule
    if isinstance(exc, RuntimeError) and message.startswith(
        "The model did not return valid ThreadInterpretation JSON."
    ):
        return "INVALID_OUTPUT_JSON"
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--channel", action="append", help="Repeat to select channels.")
    parser.add_argument("--thread-id", action="append", help="Repeat to select threads.")
    parser.add_argument("--limit", type=int, default=10, help="Selected threads; 0 means all.")
    parser.add_argument("--dry-run", action="store_true", help="List selection; no API calls or writes.")
    parser.add_argument('--cutoff',help='Timezone-aware end of the daily window; required for live processing.')
    parser.add_argument(
        "--retry-failed", action="store_true",
        help="Retry each previously rejected output once; completed results stay cached.",
    )
    parser.add_argument(
        "--output-dir", type=Path,
        default=PROJECT_ROOT / "data" / "processed" / "agent1",
    )
    args = parser.parse_args(argv)
    if args.limit < 0:
        parser.error("--limit must be zero or positive")

    fixture_root = PROJECT_ROOT / "data" / "fixtures" / "slack_generated"
    if not args.dry_run and not args.cutoff:
        parser.error('Live processing requires an explicit timezone-aware --cutoff.')
    threads, announcements, routing = load_threads(fixture_root, args.channel, cutoff=args.cutoff, with_routing=True)
    from threadsense.source_ingestion import extraction_report, existing_canonical_members
    routed_threads=list(threads)
    existing_members=existing_canonical_members()
    extraction = extraction_report(routed_threads, announcements, routing,canonical_members=existing_members)
    print(f"Routing: {routing['input_threads']} threads; {routing['eligible_threads']} eligible; {len(announcements)} announcements; {routing['source_messages_in_window']} activity messages.")
    if args.thread_id:
        requested = set(args.thread_id)
        missing = requested - {thread.thread_id for thread in threads}
        if missing:
            parser.error(f"Thread IDs not found in selected channels: {sorted(missing)}")
        threads = [thread for thread in threads if thread.thread_id in requested]
    if args.limit:
        threads = threads[:args.limit]
    if not threads and args.dry_run:
        print('No eligible interpretation threads. Announcements remain on the extraction route.')
        return int(extraction['state']=='complete_with_failures')

    print(f"Selected {len(threads)} thread(s).")
    if args.dry_run:
        for thread in threads:
            print(f"  {thread.channel_id}: {thread.thread_id}")
        print("Dry run: no API calls and no output files written.")
        return int(extraction['state']=='complete_with_failures')

    from threadsense.agents import thread_interpreter as ti

    model, key_name = ti.get_model_settings()
    if not model.startswith(("openai/", "openrouter/")):
        parser.error("This runner supports openai/ and openrouter/ model routes.")
    output_dir = args.output_dir.resolve()
    manifest_path = output_dir / "run_config.json"
    config = {
        "format_version": 1,
        "routing_version":routing['routing_version'],
        "routing_rules_sha256":routing['rules_sha256'],
        "extraction_window":routing['window'],
        "model": model,
        "interpreter_sha256": fingerprint(Path(ti.__file__).read_text(encoding="utf-8")),
        "contract_sha256": fingerprint(ti.ThreadInterpretation.model_json_schema()),
        "packages": package_versions(),
    }
    if manifest_path.exists():
        previous = json.loads(manifest_path.read_text(encoding="utf-8"))
        if previous != config:
            parser.error("Model, code, contract, or packages changed. Choose a new --output-dir.")
    elif output_dir.exists() and any(output_dir.iterdir()):
        parser.error("Output folder contains files without run_config.json. Choose a new folder.")

    # Check all cached records before any paid calls; never silently trust bad cache data.
    selected = []
    completed = []
    rejected = {}
    config_hash = fingerprint(config)
    for thread in threads:
        input_hash = fingerprint(thread.model_dump(mode="json"))
        cache_path = output_dir / "records" / f"{input_hash}.json"
        record = None
        if cache_path.exists():
            record = json.loads(cache_path.read_text(encoding="utf-8"))
            if record["input_sha256"] != input_hash or record["run_config_sha256"] != fingerprint(config):
                parser.error(f"Cache metadata mismatch: {cache_path.name}")
            result = ti.ThreadInterpretation.model_validate(record["interpretation"])
            ti.validate_interpretation_references(thread, result)
            completed.append(record)
        else:
            failure_path = output_dir / "failures" / f"{input_hash}.json"
            if failure_path.exists():
                failure = json.loads(failure_path.read_text(encoding="utf-8"))
                if failure["input_sha256"] != input_hash or failure["run_config_sha256"] != config_hash:
                    parser.error(f"Failure metadata mismatch: {failure_path.name}")
                rejected[input_hash] = failure
        selected.append((thread, input_hash, cache_path, record))

    pending = len(threads) - len(completed) - (0 if args.retry_failed else len(rejected))
    print(f"Model: {model}")
    print(f"Cached: {len(completed)} | New interpretations needed: {pending}")
    if rejected:
        action = "retrying once" if args.retry_failed else "keeping for review"
        print(f"Previously rejected: {len(rejected)} ({action})")
    if pending:
        try:
            ti.get_api_key(key_name)
        except RuntimeError as exc:
            parser.error(str(exc))

    write_json(manifest_path, config)
    # Persist the separate source route before interpreting eligible discussions.
    extraction = extraction_report(routed_threads, announcements, routing,
        destination=PROJECT_ROOT/'data/knowledge/decisions',canonical_members=existing_members)
    write_json(output_dir/'routing_manifest.json', extraction)
    export_path = output_dir / "interpretations.json"
    review_path = output_dir / "review_required.json"
    status_path = output_dir / "batch_status.json"

    def write_reports(state: str, stopped_error: str | None = None) -> None:
        # Aggregates describe this selection; per-thread records survive other runs.
        write_json(export_path, completed)
        write_json(review_path, list(rejected.values()))
        write_json(status_path, {
            "state": state,
            "selected": len(threads),
            "valid": len(completed),
            "needs_review": len(rejected),
            "unprocessed": len(threads) - len(completed) - len(rejected),
            "all_selected_have_valid_interpretations": len(completed) == len(threads),
            "stopped_error": stopped_error,
        })

    write_reports("running")
    saved = 0
    reused = len(completed)
    for index, (thread, input_hash, cache_path, cached) in enumerate(selected, 1):
        if cached is not None:
            print(f"[{index}/{len(threads)}] cached {thread.thread_id}")
            continue
        if input_hash in rejected and not args.retry_failed:
            print(f"[{index}/{len(threads)}] review pending {thread.thread_id}")
            continue
        try:
            result = ti.interpret_thread(thread)
        except Exception as exc:
            detail = str(exc)
            api_key = os.getenv(key_name, "")
            if api_key:
                detail = detail.replace(api_key, "[redacted]")
            rule = output_failure_rule(exc)
            if rule is not None:
                failure = {
                    "thread_id": thread.thread_id,
                    "channel_id": thread.channel_id,
                    "project_id": thread.project_id,
                    "batch_id": thread.batch_id,
                    "model": model,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "input_sha256": input_hash,
                    "run_config_sha256": config_hash,
                    "rule": rule,
                    "error": detail[:1000],
                    "attempts": rejected.get(input_hash, {}).get("attempts", 0) + 1,
                }
                write_json(output_dir / "failures" / f"{input_hash}.json", failure)
                rejected[input_hash] = failure
                write_reports("running")
                print(f"[{index}/{len(threads)}] needs review {thread.thread_id}: {rule}")
                continue
            write_reports("stopped", detail[:1000])
            print(f"Stopped at {thread.channel_id}/{thread.thread_id}: {detail[:1000]}")
            print("Earlier results are saved. Rerun the same command after fixing the error.")
            return 1
        record = {
            "thread_id": thread.thread_id,
            "channel_id": thread.channel_id,
            "project_id": thread.project_id,
            "batch_id": thread.batch_id,
            "language": thread.language,
            "model": model,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "input_sha256": input_hash,
            "run_config_sha256": fingerprint(config),
            "interpretation": result.model_dump(mode="json"),
        }
        write_json(cache_path, record)
        rejected.pop(input_hash, None)
        (output_dir / "failures" / f"{input_hash}.json").unlink(missing_ok=True)
        completed.append(record)
        write_reports("running")
        saved += 1
        print(f"[{index}/{len(threads)}] saved {thread.thread_id}")

    write_reports("complete_with_review" if rejected else "complete")
    print(f"Done: {saved} new, {reused} reused, {len(rejected)} need review.")
    print(f"Clustering input: {export_path}")
    if rejected:
        print(f"Rejected threads: {review_path}")
        print("Coverage is partial. Rejected threads have no accepted interpretation.")
        print("To retry them once, rerun with --retry-failed.")
    return 2 if rejected or extraction['state']=='complete_with_failures' else 0


if __name__ == "__main__":
    raise SystemExit(main())
