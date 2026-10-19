
"""Prepare one cluster for Agent 2. No API calls."""

import json
from pathlib import Path

from threadsense.adapters.mock_slack import MockSlackAdapter

ROOT = Path(__file__).resolve().parents[1]
CLUSTER_ID = "cluster_5ac8046a34862c06"

# 1. Load the existing cluster
path = ROOT / "data/processed/grouping/clusters.json"
grouping = json.loads(path.read_text(encoding="utf-8"))

assert grouping["config"]["distance_threshold"] == 0.50

cluster = next(
    c for c in grouping["clusters"]
    if c["cluster_id"] == CLUSTER_ID
)

# 2. Load original Slack threads using the adapter
fixtures = ROOT / "data/fixtures/slack_generated"

adapter = MockSlackAdapter(
    str(fixtures / "channels"),
    str(fixtures / "users.json"),
)

threads_by_key = {}

for channel_id in {m["channel_id"] for m in cluster["threads"]}:
    for thread in adapter.get_threads(channel_id):
        key = (
            thread.project_id,
            thread.batch_id,
            thread.channel_id,
            thread.thread_id,
        )
        threads_by_key[key] = thread

# 3. Match cluster members to original Slack threads
members = []

for member in cluster["threads"]:
    key = (
        cluster["project_id"],
        cluster["batch_id"],
        member["channel_id"],
        member["thread_id"],
    )

    thread = threads_by_key[key]

    assert member["interpretation"]["thread_id"] == thread.thread_id

    members.append({
        "thread_id": thread.thread_id,
        "channel_id": thread.channel_id,
        "agent1_interpretation": member["interpretation"],
        "original_thread": thread.model_dump(mode="json"),
    })

# 4. Assemble and save the input
payload = {
    "candidate_group_id": cluster["cluster_id"],
    "project_id": cluster["project_id"],
    "batch_id": cluster["batch_id"],
    "members": members,
}

output = ROOT / "data/processed/agent2_sample/group_input.json"
output.parent.mkdir(parents=True, exist_ok=True)

output.write_text(
    json.dumps(payload, indent=2, ensure_ascii=False),
    encoding="utf-8",
)

print(f"Prepared {len(members)} threads")
for member in members:
    count = len(member["original_thread"]["messages"])
    print(f"  {member['thread_id']}: {count} messages")

print(f"Saved: {output.relative_to(ROOT)}")
