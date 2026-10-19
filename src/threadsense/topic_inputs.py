
import json
from pathlib import Path

from threadsense.adapters.mock_slack import MockSlackAdapter


ROOT = Path(__file__).resolve().parents[2]


def load_candidate_payloads() -> list[dict]:
    """Prepare all frozen candidate groups for Agent 2."""

    # 1. Load frozen semantic groups.
    path = ROOT / "data/processed/grouping/clusters.json"
    grouping = json.loads(path.read_text(encoding="utf-8"))

    if grouping["config"]["distance_threshold"] != 0.50:
        raise ValueError("Unexpected grouping threshold")

    clusters = grouping["clusters"]

    # 2. Load original Slack threads once per channel.
    fixtures = ROOT / "data/fixtures/slack_generated"

    adapter = MockSlackAdapter(
        str(fixtures / "channels"),
        str(fixtures / "users.json"),
    )

    channel_ids = {
        member["channel_id"]
        for cluster in clusters
        for member in cluster["threads"]
    }

    threads_by_key = {}

    for channel_id in sorted(channel_ids):
        for thread in adapter.get_threads(channel_id):
            key = (
                thread.project_id,
                thread.batch_id,
                thread.channel_id,
                thread.thread_id,
            )

            if key in threads_by_key:
                raise ValueError(f"Duplicate Slack thread: {key}")

            threads_by_key[key] = thread

    # 3. Join each cluster with original Slack evidence.
    payloads = []
    seen = set()

    for cluster in clusters:
        members = []

        for member in cluster["threads"]:
            key = (
                cluster["project_id"],
                cluster["batch_id"],
                member["channel_id"],
                member["thread_id"],
            )

            if key in seen:
                raise ValueError(f"Duplicate assignment: {key}")

            if key not in threads_by_key:
                raise ValueError(f"Missing original thread: {key}")

            thread = threads_by_key[key]
            interpretation = member["interpretation"]

            if interpretation["thread_id"] != thread.thread_id:
                raise ValueError(f"Interpretation mismatch: {key}")

            members.append({
                "thread_id": thread.thread_id,
                "channel_id": thread.channel_id,
                "agent1_interpretation": interpretation,
                "original_thread": thread.model_dump(mode="json"),
            })

            seen.add(key)

        if not members:
            raise ValueError("Empty candidate cluster")

        payloads.append({
            "candidate_group_id": cluster["cluster_id"],
            "project_id": cluster["project_id"],
            "batch_id": cluster["batch_id"],
            "members": members,
        })

    # 4. Check complete coverage.
    if len(payloads) != 91 or len(seen) != 200:
        raise ValueError(
            f"Unexpected coverage: {len(payloads)} groups, "
            f"{len(seen)} threads"
        )

    return payloads
