
"""Agent 2 batch runner — dry-run foundation."""

import argparse
import hashlib
import json
import os
from pathlib import Path

from threadsense.agents.contracts import TopicAnalysis
from threadsense.topic_inputs import load_candidate_payloads

from run_agent2_sample import validate_output


ROOT = Path(__file__).resolve().parents[1]

CACHE_DIR = ROOT / "data/processed/agent2_batch/cache"

CACHE_VERSION = 1

MODEL = os.getenv(
    "THREADSENSE_MODEL",
    "openai/gpt-4o-mini-2024-07-18",
)

# Files whose changes may affect Agent 2 results.
DEPENDENCIES = [
    "src/threadsense/agents/topic_analyst.py",
    "src/threadsense/agents/contracts.py",
    "src/threadsense/agents/severity.py",
    "src/threadsense/agents/thread_interpreter.py",
    "src/threadsense/terminology.py",
    "data/knowledge/domain_lexicon.json",
]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def configuration_fingerprint() -> dict:
    """Fingerprint the current agent configuration."""

    files = {}

    for relative_path in DEPENDENCIES:
        path = ROOT / relative_path
        files[relative_path] = sha256(path.read_bytes())

    return {
        "cache_version": CACHE_VERSION,
        "model": MODEL,
        "dependencies": files,
    }


def input_fingerprint(payload: dict, config: dict) -> str:
    """Identify this exact input and configuration."""

    content = {
        "payload": payload,
        "config": config,
    }

    serialized = json.dumps(
        content,
        sort_keys=True,
        ensure_ascii=False,
    )

    return sha256(serialized.encode("utf-8"))


def check_cache(payload: dict, fingerprint: str) -> str:
    """Check whether an existing result can be reused."""

    cluster_id = payload["candidate_group_id"]
    path = CACHE_DIR / f"{cluster_id}.json"

    if not path.exists():
        return "NEW"

    try:
        cached = json.loads(path.read_text(encoding="utf-8"))

        if cached.get("fingerprint") != fingerprint:
            return "STALE"

        analysis = TopicAnalysis.model_validate(
            cached["analysis"]
        )

        validate_output(payload, analysis)

        return "REUSABLE"

    except (ValueError, KeyError, TypeError):
        return "INVALID"


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Number of groups to inspect",
    )

    args = parser.parse_args()

    if args.limit < 1:
        parser.error("--limit must be at least 1")

    payloads = load_candidate_payloads()
    config = configuration_fingerprint()

    selected = payloads[:args.limit]

    print(f"Model: {MODEL}")
    print(f"Total groups: {len(payloads)}")
    print(f"Inspecting: {len(selected)}")
    print()

    for payload in selected:
        fingerprint = input_fingerprint(payload, config)
        status = check_cache(payload, fingerprint)

        print(
            f"{payload['candidate_group_id']} | "
            f"{len(payload['members'])} threads | "
            f"{status} | "
            f"{fingerprint[:12]}"
        )

    print()
    print("Dry-run complete. No API calls or file writes.")


if __name__ == "__main__":
    main()
