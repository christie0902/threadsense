
import argparse
import json
import os
from pathlib import Path
from getpass import getpass
from threadsense.agents.severity import SeverityLevel

from crewai import Crew, Process

from threadsense.agents.contracts import TopicAnalysis
from threadsense.agents.topic_analyst import (
    create_topic_analyst,
    create_topic_task,
)

ROOT = Path(__file__).resolve().parents[1]

INPUT = ROOT / "data/processed/agent2_sample/group_input.json"
OUTPUT = ROOT / "data/processed/agent2_sample/topic_analysis.json"


def validate_input(payload):
    members = payload["members"]
    ids = [m["thread_id"] for m in members]

    if not members or len(ids) != len(set(ids)):
        raise ValueError("Empty input or duplicate threads")

    for member in members:
        original = member["original_thread"]
        interpretation = member["agent1_interpretation"]

        if original["thread_id"] != member["thread_id"]:
            raise ValueError("Original thread ID mismatch")

        if interpretation["thread_id"] != member["thread_id"]:
            raise ValueError("Agent 1 thread ID mismatch")

        if original["project_id"] != payload["project_id"]:
            raise ValueError("Project mismatch")

        if original["batch_id"] != payload["batch_id"]:
            raise ValueError("Batch mismatch")

    return members


def validate_output(payload, analysis: TopicAnalysis):
    # 1. Check original group identity.
    for field in ("candidate_group_id", "project_id", "batch_id"):
        if getattr(analysis, field) != payload[field]:
            raise ValueError(f"Output mismatch: {field}")

    members = {
        m["thread_id"]: m
        for m in payload["members"]
    }

    # 2. Every thread must appear exactly once.
    assigned = [
        tid
        for topic in analysis.topics
        for tid in topic.thread_ids
    ]

    if sorted(assigned) != sorted(members):
        raise ValueError("Missing, duplicated, or unknown thread IDs")

    # 3. Check severity and Slack evidence references.
    for topic in analysis.topics:
        if not isinstance(topic.severity, SeverityLevel):
            raise ValueError("Invalid severity")

        valid_messages = {
            message["message_id"]
            for tid in topic.thread_ids
            for message in members[tid]["original_thread"]["messages"]
        }

        evidence = topic.evidence_message_ids

        invalid_ids = sorted(set(evidence) - valid_messages)

        if not evidence or invalid_ids:
            raise ValueError(
                f"Topic: {topic.topic_name}\n"
                f"Evidence supplied: {evidence}\n"
                f"Invalid IDs: {invalid_ids}\n"
                f"Valid message IDs: {sorted(valid_messages)}"
            )

    # 4. Check split consistency.
    if analysis.is_coherent and len(analysis.topics) > 1:
        raise ValueError("Coherent group cannot have multiple topics")

    if (
        not analysis.is_coherent
        and len(analysis.topics) == 1
        and not analysis.needs_human_review
    ):
        raise ValueError("Unresolved coherence requires review")

    if analysis.needs_human_review and not analysis.review_reason:
        raise ValueError("Review reason is required")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--run",
        action="store_true",
        help="Call the LLM to analyze this sample",
    )
    args = parser.parse_args()

    payload = json.loads(INPUT.read_text(encoding="utf-8"))
    members = validate_input(payload)

    print(f"Input OK: {len(members)} threads")
    print(f"Candidate group: {payload['candidate_group_id']}")

    if not args.run:
        print("Preflight passed. No API calls made.")
        return

    if OUTPUT.exists():
        raise FileExistsError(
            "Agent 2 output already exists. Inspect it before rerunning."
        )

    
    if not os.getenv("OPENAI_API_KEY", "").strip():
        key = getpass("OPENAI_API_KEY (input hidden): ").strip()

        if not key:
            raise RuntimeError("OPENAI_API_KEY is required")

        os.environ["OPENAI_API_KEY"] = key


    agent = create_topic_analyst()
    task = create_topic_task(agent)

    crew = Crew(
        agents=[agent],
        tasks=[task],
        process=Process.sequential,
        memory=False,
        verbose=False,
    )

    response = crew.kickoff(
        inputs={
            "group_json": json.dumps(payload, ensure_ascii=False)
        }
    )

    if response.pydantic is None:
        raise ValueError("CrewAI did not return structured output")

    analysis = TopicAnalysis.model_validate(response.pydantic)

    draft = OUTPUT.with_name("topic_analysis_unvalidated.json")
    draft.write_text(
        analysis.model_dump_json(indent=2),
        encoding="utf-8",
    )

    validate_output(payload, analysis)

    OUTPUT.write_text(
        analysis.model_dump_json(indent=2),
        encoding="utf-8",
    )

    print(f"Analysis saved: {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
