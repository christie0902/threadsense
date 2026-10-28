"""Step 27: group saved Agent 1 interpretations, without reading evaluation labels.

Install as scripts/run_thread_grouping.py and run from the ThreadSense project.
Needs numpy, scikit-learn >= 1.2, sentence-transformers >= 3.
No API key. The first embedding run downloads the pinned local model.
Run one process per output directory. Input files are never modified.
"""

import argparse
import csv
import hashlib
import io
import json
import math
import os
import tempfile
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL = "sentence-transformers/all-MiniLM-L6-v2"
MODEL_REVISION = "b9db1e8a0d3a51769172ba8546f282a73f066e47"
STATES = {"UNRESOLVED", "PARTIALLY_RESOLVED", "RESOLVED_IN_THREAD"}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     allow_nan=False).encode("utf-8")).hexdigest()


def write_text(path, text):
    """Write a complete temporary file, then replace with bounded lock retries."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="",
                                     dir=path.parent, prefix=path.name + ".",
                                     suffix=".tmp", delete=False) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    for attempt in range(6):
        try:
            os.replace(temporary, path)
            return
        except PermissionError:
            if attempt == 5:
                raise PermissionError(
                    f"Cannot replace {path}. Close file previews and other runs. "
                    f"The completed temporary file is retained at {temporary}."
                ) from None
            time.sleep(0.5 * (attempt + 1))


def write_json(path, value):
    write_text(path, json.dumps(value, ensure_ascii=False, indent=2,
                                allow_nan=False) + "\n")


def load_records(path, *, historical=False):
    records = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(records, list) or not records:
        raise ValueError("Input must be a nonempty list of saved interpretations.")
    seen, configs = set(), set()
    for r in records:
        for key in ("thread_id", "project_id", "channel_id", "run_config_sha256"):
            if not isinstance(r.get(key), str) or not r[key].strip():
                raise ValueError(f"Missing/invalid record field: {key}")
        if r.get("batch_id") is not None and not isinstance(r["batch_id"], str):
            raise ValueError("batch_id must be a string or null.")
        identity = (r["project_id"], r.get("batch_id"), r["channel_id"], r["thread_id"])
        if identity in seen:
            raise ValueError(f"Duplicate thread: {identity}")
        seen.add(identity)
        configs.add(r["run_config_sha256"])
        a = r.get("interpretation")
        if not isinstance(a, dict) or a.get("thread_id") != r["thread_id"]:
            raise ValueError(f"Invalid interpretation identity: {identity}")
        if not isinstance(a.get("summary"), str) or not a["summary"].strip():
            raise ValueError(f"Missing summary: {identity}")
        if "central_question" not in a or (a["central_question"] is not None and not isinstance(a["central_question"], str)):
            raise ValueError(f"Invalid central question: {identity}")
        if a.get("resolution_state") not in STATES:
            raise ValueError(f"Invalid resolution: {identity}")
        evidence = a.get("authority_evidence_message_ids")
        if not isinstance(evidence, list) or any(not isinstance(i, str) for i in evidence):
            raise ValueError(f"Invalid authority evidence list: {identity}")
        if type(a.get("authoritative_response_present")) is not bool or a["authoritative_response_present"] != bool(evidence):
            raise ValueError(f"Inconsistent authority flag: {identity}")
    if len(configs) != 1:
        raise ValueError("Input mixes Agent 1 configurations. Use one completed run.")
    # Stable input order avoids arbitrary changes from file ordering.
    if not historical:
        from threadsense.routing import partition
        records, _, _ = partition(records)
    return sorted(records, key=lambda r: (r["project_id"], r.get("batch_id") or "",
                                          r["channel_id"], r["thread_id"]))


def embedding_text(record):
    """Use meaning-bearing text, not confidence, authority or resolution labels."""
    a = record["interpretation"]
    question = (a.get("central_question") or "").strip()
    summary = a["summary"].strip()
    return f"Question: {question}\nSummary: {summary}" if question else f"Summary: {summary}"


def package_versions():
    result = {}
    for name in ("numpy", "scikit-learn", "sentence-transformers", "transformers", "torch"):
        try:
            result[name] = version(name)
        except PackageNotFoundError:
            result[name] = "not-installed"
    return result


def validate_vectors(values, rows):
    import numpy as np
    vectors = np.asarray(values, dtype=np.float32)
    if vectors.ndim != 2 or vectors.shape[0] != rows or vectors.shape[1] == 0:
        raise ValueError("Embedding cache has invalid dimensions.")
    if not np.isfinite(vectors).all():
        raise ValueError("Embeddings contain non-finite values.")
    lengths = np.linalg.norm(vectors, axis=1, keepdims=True)
    if (lengths <= 0).any():
        raise ValueError("Embeddings contain a zero vector.")
    return vectors / lengths


def get_embeddings(records, cache_dir, packages):
    texts = [embedding_text(r) for r in records]
    # Threshold is intentionally absent: changing it reuses the same vectors.
    config = {"model": MODEL, "revision": MODEL_REVISION, "device": "cpu",
              "text_format": 1, "long_text_policy": "model_truncation_with_report",
              "packages": {k: packages[k] for k in
                           ("sentence-transformers", "transformers", "torch", "numpy")}}
    key = digest({"config": config, "texts": texts})
    path = cache_dir / f"{key}.json"
    if path.exists():
        cached = json.loads(path.read_text(encoding="utf-8"))
        if cached["cache_key"] != key or cached["config"] != config:
            raise ValueError(f"Embedding cache metadata mismatch: {path}")
        if digest(cached["vectors"]) != cached["vectors_sha256"]:
            raise ValueError(f"Embedding cache checksum mismatch: {path}")
        vectors = validate_vectors(cached["vectors"], len(records))
        print(f"Embeddings: reused {len(records)} cached vectors.")
        return vectors, key, cached["truncated_input_indices"], config

    from sentence_transformers import SentenceTransformer
    print("Loading the local embedding model (first use downloads model files)...", flush=True)
    model = SentenceTransformer(MODEL, revision=MODEL_REVISION, device="cpu",
                               trust_remote_code=False)
    # Long inputs are reported, never silently counted as fully represented.
    token_lengths = [len(model.tokenizer.encode(t, truncation=False)) for t in texts]
    truncated = [i for i, length in enumerate(token_lengths) if length > model.max_seq_length]
    values = model.encode(texts, batch_size=32, show_progress_bar=True,
                          convert_to_numpy=True, normalize_embeddings=True)
    vectors = validate_vectors(values, len(records))
    values = vectors.tolist()
    write_json(path, {"cache_key": key, "config": config,
                      "vectors": values, "vectors_sha256": digest(values),
                      "truncated_input_indices": truncated})
    print(f"Embeddings: computed and cached {len(records)} vectors.")
    return vectors, key, truncated, config


def group_records(records, vectors, threshold):
    from threadsense.routing import require_discussion
    for record in records:
        require_discussion(record)
    import numpy as np
    from sklearn.cluster import AgglomerativeClustering
    vectors = validate_vectors(vectors, len(records))
    scopes = defaultdict(list)
    for i, r in enumerate(records):
        scopes[(r["project_id"], r.get("batch_id"))].append(i)
    groups = []
    for (project, batch), indices in sorted(scopes.items(), key=lambda x: (x[0][0], x[0][1] or "")):
        if len(indices) == 1:
            labels = [0]
        else:
            labels = AgglomerativeClustering(
                n_clusters=None, metric="cosine", linkage="complete",
                distance_threshold=threshold, compute_full_tree=True,
            ).fit_predict(vectors[indices])
        members_by_label = defaultdict(list)
        for i, label in zip(indices, labels):
            members_by_label[int(label)].append(i)
        for member_indices in members_by_label.values():
            member_indices.sort(key=lambda i: (records[i]["channel_id"], records[i]["thread_id"]))
            members = [records[i] for i in member_indices]
            similarities = np.clip(vectors[member_indices] @ vectors[member_indices].T, -1, 1)
            # The medoid is the member with greatest mean similarity to its group.
            representative = members[int(np.argmax(similarities.mean(axis=1)))]
            pairs = similarities[np.triu_indices(len(members), k=1)]
            identities = [[r["channel_id"], r["thread_id"]] for r in members]
            groups.append({
                "cluster_id": "cluster_" + digest([project, batch, identities])[:16],
                "project_id": project, "batch_id": batch, "thread_count": len(members),
                "is_singleton": len(members) == 1,
                "representative_thread_id": representative["thread_id"],
                "representative_channel_id": representative["channel_id"],
                "representative_question": representative["interpretation"]["central_question"],
                "representative_summary": representative["interpretation"]["summary"],
                "mean_pairwise_similarity": round(float(pairs.mean()), 4) if len(pairs) else None,
                "minimum_pairwise_similarity": round(float(pairs.min()), 4) if len(pairs) else None,
                "resolution_counts": dict(Counter(r["interpretation"]["resolution_state"] for r in members)),
                "threads": [{k: r.get(k) for k in
                             ("thread_id", "channel_id", "language", "interpretation")} for r in members],
            })
    groups.sort(key=lambda g: (g["project_id"], g["batch_id"] or "", -g["thread_count"], g["cluster_id"]))
    assigned = [(m["channel_id"], m["thread_id"]) for g in groups for m in g["threads"]]
    expected = {(r["channel_id"], r["thread_id"]) for r in records}
    if len(assigned) != len(records) or len(set(assigned)) != len(assigned) or set(assigned) != expected:
        raise ValueError("Grouping failed the one-assignment-per-thread check.")
    return groups


def review_csv(groups):
    stream = io.StringIO(newline="")
    fields = ["cluster_id", "project_id", "batch_id", "thread_count", "thread_id",
              "channel_id", "central_question", "summary", "resolution_state"]
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    for g in groups:
        for m in g["threads"]:
            row = {k: g[k] for k in fields[:4]}
            row.update({k: m[k] for k in ("thread_id", "channel_id")})
            row.update({k: m["interpretation"][k] for k in fields[6:]})
            # Avoid spreadsheet interpretation of text as formulas.
            row = {k: ("'" + v if isinstance(v, str) and v.lstrip().startswith(("=", "+", "-", "@")) else v)
                   for k, v in row.items()}
            writer.writerow(row)
    return "\ufeff" + stream.getvalue()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=PROJECT_ROOT / "data/processed/agent1_authority_fix/interpretations.json")
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "data/processed/grouping")
    parser.add_argument("--distance-threshold", type=float, default=0.35)
    parser.add_argument("--check-input", action="store_true", help="Validate input without downloading or loading a model.")
    args = parser.parse_args()
    if not math.isfinite(args.distance_threshold) or not 0 < args.distance_threshold < 2:
        parser.error("--distance-threshold must be between 0 and 2, exclusive.")
    source = args.input.resolve()
    from threadsense.routing import partition
    records, announcements, routing = partition(load_records(source, historical=True))
    print(f"Routing: {routing['input_threads']} source threads; {len(records)} discussions; {len(announcements)} announcements retained outside clustering.")
    print(f"Input: {len(records)} threads across {len({r['project_id'] for r in records})} projects.")
    if args.check_input:
        print("Input checks passed. No embeddings computed or files written.")
        return 0
    packages = package_versions()
    if any(packages[k] == "not-installed" for k in packages):
        parser.error('Install dependencies: python -m pip install "sentence-transformers>=3" "scikit-learn>=1.2" numpy')
    output = args.output_dir.resolve()
    if output.exists():
        parser.error('Use a fresh grouping directory; historical inputs and results are immutable.')
    if source in {output / "clusters.json", output / "cluster_review.csv"}:
        parser.error("Choose an output directory that will not overwrite the input.")
    vectors, cache_key, truncated, embedding_config = get_embeddings(records, output / "embedding_cache", packages)
    if truncated:
        print(f"Note: {len(truncated)} embedding inputs exceeded the model token limit; IDs are recorded in clusters.json.")
    groups = group_records(records, vectors, args.distance_threshold)
    report = {
        "format_version": 1, "created_at": datetime.now(timezone.utc).isoformat(),
        "routing_manifest": routing,
        "input_path": str(source), "input_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "agent1_run_config_sha256": records[0]["run_config_sha256"],
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "config": {"embedding": embedding_config, "algorithm": "agglomerative",
                   "linkage": "complete", "metric": "cosine", "scope": "project_and_batch",
                   "distance_threshold": args.distance_threshold, "packages": packages},
        "embedding_cache_key": cache_key,
        "truncated_embedding_inputs": [{"channel_id": records[i]["channel_id"], "thread_id": records[i]["thread_id"]} for i in truncated],
        "thread_count": len(records), "cluster_count": len(groups),
        "singleton_count": sum(g["is_singleton"] for g in groups), "clusters": groups,
    }
    write_json(output / "clusters.json", report)
    write_text(output / "cluster_review.csv", review_csv(groups))
    for project in sorted({g["project_id"] for g in groups}):
        subset = [g for g in groups if g["project_id"] == project]
        print(f"{project}: {sum(g['thread_count'] for g in subset)} threads, "
              f"{len(subset)} groups, {sum(g['is_singleton'] for g in subset)} singletons")
    print(f"Done: {len(records)} threads assigned exactly once to {len(groups)} groups.")
    print(f"Next-agent input: {output / 'clusters.json'}")
    print(f"Human review: {output / 'cluster_review.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
