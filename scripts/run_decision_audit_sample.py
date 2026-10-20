
"""Run one independent decision-evidence audit."""

import argparse
import json
import os
from getpass import getpass
from pathlib import Path

from threadsense.agents.decision_evidence_audit import (
    audit_thread_decisions,
)
from threadsense.config import get_model_settings
from threadsense.models import Thread
from threadsense.topic_inputs import load_candidate_payloads


ROOT = Path(__file__).resolve().parents[1]
TARGET_THREAD_ID = "1790882197.000111"

OUTPUT_DIR = (
    ROOT / "data/processed/agent1_decision_audit_sample"
)

OUTPUT = OUTPUT_DIR / f"{TARGET_THREAD_ID}.audit_v1.json"
RAW_OUTPUT = OUTPUT_DIR / f"{TARGET_THREAD_ID}.audit_v1.raw.txt"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--run",
        action="store_true",
        help="Execute one paid LLM audit",
    )
    args = parser.parse_args()

    matches = [
        member
        for group in load_candidate_payloads()
        for member in group["members"]
        if member["thread_id"] == TARGET_THREAD_ID
    ]

    if len(matches) != 1:
        raise ValueError(
            f"Expected one matching thread, found {len(matches)}"
        )

    # Original Slack only. No Agent 1 interpretation is used.
    thread = Thread.model_validate(
        matches[0]["original_thread"]
    )

    default_model, _ = get_model_settings()

    audit_model = (
        os.getenv("THREADSENSE_VERIFIER_MODEL", "").strip()
        or default_model
    )

    key_name = (
        "OPENROUTER_API_KEY"
        if audit_model.startswith("openrouter/")
        else "OPENAI_API_KEY"
    )

    print("Thread:", thread.thread_id)
    print("Auditor model:", audit_model)
    print("Original request:", next(
        m.text
        for m in thread.messages
        if m.message_id == thread.thread_id
    ))
    print("Number of replies:", len(thread.messages) - 1)

    if not args.run:
        print("\nPreflight complete. No API calls or file writes.")
        return

    if OUTPUT.exists() or RAW_OUTPUT.exists():
        raise FileExistsError(
            "A previous audit or raw response already exists. "
            "Inspect it before another API call."
        )

    if not os.getenv(key_name, "").strip():
        key = getpass(f"{key_name} (input hidden): ").strip()

        if not key:
            raise RuntimeError(f"{key_name} is required")

        os.environ[key_name] = key

    def preserve_raw(raw: str) -> None:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        with RAW_OUTPUT.open("x", encoding="utf-8") as file:
            file.write(raw)

    print("\nRunning independent decision-evidence audit...")

    try:
        audit = audit_thread_decisions(
            thread,
            on_raw_output=preserve_raw,
        )
    except Exception:
        if RAW_OUTPUT.exists():
            print("Raw audit preserved:", RAW_OUTPUT)
        raise

    record = {
        "thread_id": thread.thread_id,
        "model": audit_model,
        "original_thread": thread.model_dump(mode="json"),
        "audit": audit.model_dump(mode="json"),
        "raw_output_file": RAW_OUTPUT.name,
    }

    with OUTPUT.open("x", encoding="utf-8") as file:
        json.dump(
            record,
            file,
            indent=2,
            ensure_ascii=False,
        )

    print("\nRequested decisions:")
    for decision in audit.requested_decisions:
        print("-", decision)

    print("\nReply assessments:")
    for item in audit.reply_assessments:
        print(
            f"- {item.message_id}: "
            f"{item.contribution.value}"
        )
        print(f"  Evidence: {item.evidence_quote}")

    print("\nValidated audit saved:", OUTPUT)


if __name__ == "__main__":
    main()
