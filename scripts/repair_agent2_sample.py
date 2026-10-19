
import json
import os
from getpass import getpass

from crewai import Crew, Process, Task

from run_agent2_sample import (
    INPUT,
    OUTPUT,
    validate_input,
    validate_output,
)
from threadsense.agents.contracts import TopicAnalysis
from threadsense.agents.topic_analyst import create_topic_analyst
from threadsense.agents.severity import SEVERITY_RUBRIC


DRAFT = OUTPUT.with_name("topic_analysis_unvalidated.json")
REPAIRED_DRAFT = OUTPUT.with_name(
    "topic_analysis_repair_unvalidated.json"
)


def main():
    # 1. Read the original input and failed analysis.
    payload = json.loads(INPUT.read_text(encoding="utf-8"))
    validate_input(payload)

    draft = TopicAnalysis.model_validate_json(
        DRAFT.read_text(encoding="utf-8")
    )

    # 2. Confirm the draft really failed validation.
    try:
        validate_output(payload, draft)
    except ValueError as error:
        validation_error = str(error)
    else:
        raise RuntimeError("Draft already valid. No repair needed.")

    if OUTPUT.exists():
        raise FileExistsError("Validated output already exists.")

    required_ids = {
        member["thread_id"] for member in payload["members"]
    }
    assigned_ids = [
        tid for topic in draft.topics for tid in topic.thread_ids
    ]
    missing_ids = sorted(required_ids - set(assigned_ids))

    print(f"Missing thread IDs: {missing_ids}")

    # 3. Configure API key without storing it.
    if not os.getenv("OPENAI_API_KEY", "").strip():
        key = getpass("OPENAI_API_KEY (input hidden): ").strip()
        if not key:
            raise RuntimeError("API key required")
        os.environ["OPENAI_API_KEY"] = key

    rubric = "\n".join(
        f"{level.value}: {details['definition']}"
        for level, details in SEVERITY_RUBRIC.items()
    )

    # 4. Ask Agent 2 to repair its analysis ONCE.
    agent = create_topic_analyst()

    task = Task(
        description="""
Repair a previous invalid TopicAnalysis.

Validation failure:
{validation_error}

All required thread IDs:
{required_ids}

Previously missing thread IDs:
{missing_ids}

Original candidate group:
{group_json}

Previous invalid analysis:
{draft_json}

Severity standard:
{severity_rubric}

Instructions:
1. Reanalyze ALL original Slack threads.
2. Produce a complete, new TopicAnalysis.
3. Assign every original thread exactly once.
4. Do not create overlapping or duplicate topics.
5. Split substantively different operational issues.
6. Cite real message IDs belonging to assigned threads.
7. Apply the severity standard using observed evidence.
8. Preserve project, batch and candidate group IDs.
9. Do not fabricate policies or historical information.
10. Do not merely patch thread IDs into existing topics
    without checking their actual meaning.
""",
        expected_output=(
            "A complete, corrected TopicAnalysis with valid "
            "thread assignments and supporting evidence."
        ),
        agent=agent,
        output_pydantic=TopicAnalysis,
    )

    crew = Crew(
        agents=[agent],
        tasks=[task],
        process=Process.sequential,
        memory=False,
        verbose=False,
    )

    response = crew.kickoff(
        inputs={
            "validation_error": validation_error,
            "required_ids": json.dumps(sorted(required_ids)),
            "missing_ids": json.dumps(missing_ids),
            "group_json": json.dumps(payload, ensure_ascii=False),
            "draft_json": draft.model_dump_json(),
            "severity_rubric": rubric,
        }
    )

    if response.pydantic is None:
        raise ValueError("Repair did not return structured output")

    repaired = TopicAnalysis.model_validate(response.pydantic)

    # 5. Always preserve the repair attempt before validation.
    REPAIRED_DRAFT.write_text(
        repaired.model_dump_json(indent=2),
        encoding="utf-8",
    )

    validate_output(payload, repaired)

    OUTPUT.write_text(
        repaired.model_dump_json(indent=2),
        encoding="utf-8",
    )

    print("Agent 2 repair passed validation!")
    print(f"Topics: {len(repaired.topics)}")


if __name__ == "__main__":
    main()
