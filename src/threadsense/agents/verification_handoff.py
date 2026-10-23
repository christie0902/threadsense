"""Canonical, nonblocking Agent 1 handoff; no model calls or text repairs."""

import hashlib
import json
import os
from pathlib import Path

from threadsense.agents.contracts import ThreadInterpretation, VerificationFinding
from threadsense.models import Thread


IDENTITY_FIELDS = ("project_id", "batch_id", "channel_id", "thread_id")
HANDOFF_VERSION = 1


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def identity(record):
    return tuple(record.get(key) for key in IDENTITY_FIELDS)


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _reference(root, name):
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()) or path.is_relative_to((root / "data/evaluation").resolve()):
        raise ValueError("Review references must be repository evidence, excluding evaluation data.")
    return path


def load_content_reviews(paths, root):
    """Bind explicit reviews to their referenced historical source and candidate.

    Older reviews have references but no hashes. Compute observed bindings from
    those artifacts; never claim the reviewer supplied those hashes or a date.
    Optional supplied hashes must match. Invalid rows remain explicit diagnostics.
    """
    bound, diagnostics = [], []
    for path in dict.fromkeys(Path(p).resolve() for p in paths):
        if path.is_relative_to((root / "data/evaluation").resolve()):
            raise ValueError("Evaluation data cannot be used as runtime content reviews.")
        document = read_json(path)
        if not isinstance(document.get("reviews"), list):
            raise ValueError("Content-review documents require a reviews list.")
        for index, row in enumerate(document["reviews"]):
            provenance = {
                "review_file": str(path.relative_to(root.resolve()) if path.is_relative_to(root.resolve()) else path).replace("\\", "/"),
                "review_file_sha256": file_hash(path), "review_pointer": f"/reviews/{index}",
                "review_type": document.get("review_type"),
                "reviewer_identity": row.get("reviewer_identity") if isinstance(row, dict) else None,
                "reviewed_at": row.get("reviewed_at") if isinstance(row, dict) else None,
                "human_approval": False,
                "binding_method": "computed_from_referenced_evidence; not reviewer-attested",
            }
            review_id = digest({"file": provenance["review_file_sha256"], "pointer": provenance["review_pointer"]})
            try:
                if not isinstance(row, dict) or any(key not in row for key in IDENTITY_FIELDS):
                    raise ValueError("Review requires full project/batch/channel/thread identity.")
                if type(row.get("needs_review")) is not bool:
                    raise ValueError("Review needs_review must be an explicit boolean.")
                source_path = _reference(root, row["source_file"])
                result_path = _reference(root, row["verification_file"])
                source_payload, saved = read_json(source_path), read_json(result_path)
                thread = Thread.model_validate(source_payload)
                if identity(source_payload) != identity(row):
                    raise ValueError("Review identity does not match its source evidence.")
                if saved.get("result_sha256") != digest(saved.get("result")):
                    raise ValueError("Reviewed verification result checksum mismatch.")
                from threadsense.agents.verification_pipeline import VerificationResult
                result = VerificationResult.model_validate(saved["result"])
                candidate = result.interpretation.model_dump(mode="json")
                source_hash = digest(source_payload)
                if candidate["thread_id"] != thread.thread_id or saved["metadata"]["source_sha256"] != source_hash:
                    raise ValueError("Reviewed candidate/source identity or fingerprint mismatch.")
                candidate_hash = digest(candidate)
                bindings = {"source_sha256": source_hash, "candidate_sha256": candidate_hash,
                            "source_file_sha256": file_hash(source_path), "verification_file_sha256": file_hash(result_path)}
                if any(key in row and row[key] != value for key, value in bindings.items()):
                    raise ValueError("Supplied review binding does not match referenced evidence.")
                fields = set(row.get("disputed_fields", []))
                if fields - ThreadInterpretation.model_fields.keys():
                    raise ValueError("Review disputes unknown interpretation fields.")
                findings = []
                messages = {m.message_id: m for m in thread.messages}
                for item in row.get("findings", []):
                    finding = VerificationFinding.model_validate(item)
                    ids, quotes = finding.evidence_message_ids, finding.evidence_quotes
                    if not finding.explanation.strip() or not finding.disputed_fields or set(finding.disputed_fields) - ThreadInterpretation.model_fields.keys():
                        raise ValueError("Content finding needs a specific explanation and valid disputed fields.")
                    if not ids or len(ids) != len(quotes) or len(ids) != len(set(ids)):
                        raise ValueError("Content findings require unique source IDs and parallel exact quotations.")
                    if any(mid not in messages or not quote.strip() or quote not in messages[mid].text for mid, quote in zip(ids, quotes)):
                        raise ValueError("Content review has unknown evidence IDs or fabricated quotations.")
                    if item.get("candidate_text") and not any(item["candidate_text"] in str(candidate.get(field, "")) for field in finding.disputed_fields):
                        raise ValueError("Reviewed claim is absent from the referenced candidate fields.")
                    fields.update(finding.disputed_fields)
                    findings.append({**finding.model_dump(mode="json"), "candidate_text": item.get("candidate_text")})
                if row["needs_review"] and (not fields or not findings or not (row.get("review_reason") or "").strip()):
                    raise ValueError("Unresolved content disputes require fields, reasons, and evidence-backed findings.")
                if not row["needs_review"] and (findings or fields):
                    raise ValueError("Positive review cannot contain unresolved disputed fields/findings.")
                bound.append({
                    **{key: row[key] for key in IDENTITY_FIELDS}, "review_id": review_id,
                    **bindings, "needs_review": row["needs_review"], "disputed_fields": sorted(fields),
                    "review_reason": row.get("review_reason"), "findings": findings,
                    "source_review_outcome": row.get("source_review_outcome"),
                    "provenance": {**provenance, "source_file": row["source_file"],
                                   "verification_file": row["verification_file"], **bindings},
                })
            except (ValueError, KeyError, TypeError, OSError) as error:
                diagnostics.append({"review_id": review_id, "status": "INVALID_REVIEW", "reason": str(error),
                                    "provenance": provenance})
    return bound, diagnostics


def apply_content_reviews(records, reviews, diagnostics=()):
    """Open matching disputes override acceptance; positive reviews never clear flags."""
    reports = list(diagnostics)
    by_identity = {identity(row): row for row in records}
    if len(by_identity) != len(records):
        raise ValueError("Canonical handoff contains duplicate full identities.")
    for review in reviews:
        row = by_identity.get(identity(review))
        if row is None:
            status = "UNMATCHED_IDENTITY"
        elif row["input_sha256"] != review["source_sha256"]:
            status = "STALE_SOURCE"
        elif row["candidate_sha256"] != review["candidate_sha256"]:
            status = "STALE_CANDIDATE"
        else:
            status = "APPLIED_DISPUTE" if review["needs_review"] else "MATCHED_NONAPPROVAL"
            row["content_reviews"].append(review)
            if review["needs_review"]:
                row["verification_status"] = "NEEDS_REVIEW"
                row["review_required"] = True
                row["provisional_fields"] = sorted(set(row["provisional_fields"]) | set(review["disputed_fields"]))
                row["review_reasons"] = list(dict.fromkeys([*row["review_reasons"], review["review_reason"]]))
                row["review_findings"].extend({**item, "origin": "content_review", "review_id": review["review_id"]} for item in review["findings"])
                row["review_reason"] = "; ".join(row["review_reasons"])
        report = {"review_id": review["review_id"], "status": status,
                  **{key: review[key] for key in IDENTITY_FIELDS}, "provenance": review["provenance"]}
        reports.append(report)
        if row is not None:
            row["review_applicability"].append(report)
    return reports


def build_handoff(output, evidence_root, retained, results, config, baseline_file, *,
                  reviews=(), diagnostics=(), origin="bounded_verification"):
    """One shared export implementation for live results and offline reconciliation."""
    output, evidence_root = Path(output).resolve(), Path(evidence_root).resolve()
    reference = lambda path: Path(os.path.relpath(path, output)).as_posix()
    records = []
    for entry in retained:
        result, baseline = results[entry["key"]], entry["baseline"]
        candidate = result.interpretation.model_dump(mode="json")
        result_path = evidence_root / "records" / entry["key"] / "result.json"
        result_ref = reference(result_path) if result_path.exists() else None
        records.append({
            **{key: baseline.get(key) for key in (*IDENTITY_FIELDS, "language")},
            "model": config["interpreter_model"], "run_config_sha256": digest(config),
            "handoff_version": HANDOFF_VERSION, "verification_origin": origin,
            "input_sha256": entry["source_sha256"], "candidate_sha256": digest(candidate),
            "source_message_ids": [m.message_id for m in entry["thread"].messages],
            "interpretation": candidate, "automated_verification_status": result.status.value,
            "verification_status": result.status.value, "review_required": result.status.value == "NEEDS_REVIEW",
            "revision_count": result.revision_count, "provisional_fields": list(result.provisional_fields),
            "review_reason": result.review_reason, "review_reasons": [result.review_reason] if result.review_reason else [],
            "review_findings": [{**item.model_dump(mode="json"), "origin": "automated_verification"} for item in result.findings],
            "content_reviews": [], "review_applicability": [],
            "lineage": {
                "baseline_file": str(baseline_file), "baseline_record_sha256": entry["baseline_sha256"],
                "baseline_run_config_sha256": baseline.get("run_config_sha256"),
                "baseline_model": baseline.get("model"), "baseline_created_at": baseline.get("created_at"),
                "source_file": reference(evidence_root / "sources" / f"{entry['source_sha256']}.json"),
                "verification_file": result_ref, "effective_attempt": result.effective_attempt,
                "original_candidate_sha256": digest(result.original_interpretation),
                "revised_candidate_sha256": digest(result.revised_interpretation.model_dump(mode="json")) if result.revised_interpretation else None,
                "effective_candidate_sha256": digest(candidate),
                "original_candidate_reference": f"{result_ref}#/result/original_interpretation" if result_ref else None,
                "revised_candidate_reference": f"{result_ref}#/result/revised_interpretation" if result_ref and result.revised_interpretation else None,
                "audit_history_reference": f"{result_ref}#/result/passes" if result_ref else None,
            },
        })
    reports = apply_content_reviews(records, reviews, diagnostics)
    # The queue carries the exact same effective records, avoiding divergent flags.
    queue = [row for row in records if row["review_required"]]
    counts = {status: sum(row["verification_status"] == status for row in records)
              for status in ("VERIFIED", "CORRECTED", "NEEDS_REVIEW")}
    export_config = {"handoff_version": HANDOFF_VERSION, "origin": origin,
                     "exporter_sha256": file_hash(Path(__file__)), "reviews": list(reviews), "diagnostics": list(diagnostics)}
    return records, queue, counts, {"config": export_config, "config_sha256": digest(export_config), "reviews": reports}
