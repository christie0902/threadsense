
"""Test Agent 1 verification on one known problematic thread."""

import argparse
import json
import os
from getpass import getpass
from pathlib import Path

from threadsense.agents.contracts import ThreadInterpretation
from threadsense.agents.interpretation_verifier import verify_interpretation
from threadsense.config import get_model_settings
from threadsense.models import Thread
from threadsense.topic_inputs import load_candidate_payloads


ROOT = Path(__file__).resolve().parents[1]
TARGET_THREAD_ID = "1790915374.000127"

OUTPUT = (
    ROOT
    / "data/processed/agent1_verifier_sample"
    / f"{TARGET_THREAD_ID}.verifier_v2.json"
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--run",
        action="store_true",
        help="Execute the paid LLM verification",
    )
    args = parser.parse_args()

    # Locate the original thread and frozen Agent 1 result.
    matches = [
        (payload, member)
        for payload in load_candidate_payloads()
        for member in payload["members"]
        if member["thread_id"] == TARGET_THREAD_ID
    ]

    if len(matches) != 1:
        raise ValueError(
            f"Expected one target thread, found {len(matches)}"
        )

    payload, member = matches[0]

    thread = Thread.model_validate(member["original_thread"])
    interpretation = ThreadInterpretation.model_validate(
        member["agent1_interpretation"]
    )

    model, key_name = get_model_settings()
        
    verifier_model = (
        os.getenv("THREADSENSE_VERIFIER_MODEL", "").strip()
        or model
    )

    key_name = (
        "OPENROUTER_API_KEY"
        if verifier_model.startswith("openrouter/")
        else "OPENAI_API_KEY"
    )


    print("Thread:", thread.thread_id)
    print("Agent 1 model:", model)
    print("Verifier model:", verifier_model)
    print("Original question:", thread.messages[0].text)
    print("Agent 1 summary:", interpretation.summary)
    print("Resolution:", interpretation.resolution_state.value)

    if not args.run:
        print("\nPreflight complete. No API calls or file writes.")
        return

    # Never overwrite a completed verification.
    if OUTPUT.exists():
        raise FileExistsError(
            f"Verification result already exists: {OUTPUT}"
        )

    if not os.getenv(key_name, "").strip():
        key = getpass(f"{key_name} (input hidden): ").strip()

        if not key:
            raise RuntimeError(f"{key_name} is required")

        os.environ[key_name] = key

    print("\nRunning independent verification...")

    result = verify_interpretation(thread, interpretation)

    record = {
        "thread_id": thread.thread_id,
        "candidate_group_id": payload["candidate_group_id"],
        "model": verifier_model,
        "interpreter_model": model,
        "verification_version": "v2",
        "original_thread": thread.model_dump(mode="json"),
        "original_interpretation": interpretation.model_dump(
            mode="json"
        ),
        "verification": result.model_dump(mode="json"),
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT.open("x", encoding="utf-8") as file:
        json.dump(
            record,
            file,
            indent=2,
            ensure_ascii=False,
        )

    print("Verification status:", result.status.value)
    print("Findings:", len(result.findings))

    for finding in result.findings:
        print(f"- {finding.category.value}: {finding.explanation}")

    print("Saved:", OUTPUT)


if __name__ == "__main__":
    main()
