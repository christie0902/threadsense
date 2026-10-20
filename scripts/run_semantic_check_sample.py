
"""Test independent answer checking on one Slack thread."""

import argparse
import json
import os
from getpass import getpass
from pathlib import Path

from threadsense.agents.contracts import DecisionEvidenceAudit
from threadsense.agents.decision_evidence_audit import (
    validate_decision_evidence_audit,
)
from threadsense.agents.semantic_resolution_check import (
    check_answer_independently,
    compare_answer_checks,
)
from threadsense.config import get_model_settings
from threadsense.models import Thread


ROOT = Path(__file__).resolve().parents[1]
TARGET = "1790882197.000111"

AUDIT_FILE = (
    ROOT
    / "data/processed/agent1_decision_audit_sample"
    / f"{TARGET}.audit_v1.json"
)

OUTPUT_DIR = (
    ROOT / "data/processed/agent1_semantic_check_sample"
)

OUTPUT = OUTPUT_DIR / f"{TARGET}.check_v1.json"
RAW_OUTPUT = OUTPUT_DIR / f"{TARGET}.check_v1.raw.txt"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--run",
        action="store_true",
        help="Execute one paid independent verification",
    )
    args = parser.parse_args()

    # Read the saved original Slack evidence.
    record = json.loads(
        AUDIT_FILE.read_text(encoding="utf-8")
    )

    thread = Thread.model_validate(
        record["original_thread"]
    )

    audit = DecisionEvidenceAudit.model_validate(
        record["audit"]
    )

    validate_decision_evidence_audit(thread, audit)

    if thread.thread_id != TARGET:
        raise ValueError("Unexpected thread ID.")

    default_model, _ = get_model_settings()

    model = (
        os.getenv("THREADSENSE_VERIFIER_MODEL", "").strip()
        or default_model
    )

    key_name = (
        "OPENROUTER_API_KEY"
        if model.startswith("openrouter/")
        else "OPENAI_API_KEY"
    )

    print("Thread:", thread.thread_id)
    print("Model:", model)
    print("Original messages:", len(thread.messages))
    print("Existing audit: Validated")

    if not args.run:
        print("\nPreflight complete. No API calls or file writes.")
        return

    if OUTPUT.exists() or RAW_OUTPUT.exists():
        raise FileExistsError(
            "A previous result already exists. "
            "Inspect it before another paid call."
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

    print("\nRunning independent answer check...")

    try:
        # Only the original thread is sent to the LLM.
        check = check_answer_independently(
            thread,
            on_raw_output=preserve_raw,
        )

        # Compare outputs only AFTER independent analysis.
        agreement = compare_answer_checks(
            thread,
            audit,
            check,
        )

    except Exception:
        if RAW_OUTPUT.exists():
            print("Raw response preserved:", RAW_OUTPUT)
        raise

    result = {
        "thread_id": TARGET,
        "model": model,
        "first_audit_file": AUDIT_FILE.name,
        "independent_check": check.model_dump(mode="json"),
        "agreement_status": agreement.value,
        "raw_output_file": RAW_OUTPUT.name,
    }

    with OUTPUT.open("x", encoding="utf-8") as file:
        json.dump(
            result,
            file,
            indent=2,
            ensure_ascii=False,
        )

    print("\nIndependent reply assessments:")

    for reply in check.replies:
        print(
            f"- {reply.message_id}: {reply.verdict.value}"
        )

    print("\nAgreement:", agreement.value)
    print("Saved:", OUTPUT)


if __name__ == "__main__":
    main()
