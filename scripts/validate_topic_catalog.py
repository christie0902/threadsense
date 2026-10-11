import json
from pathlib import Path
from collections import Counter

path = Path("data/evaluation/topic_catalog.json")

with open(path, encoding="utf-8") as f:
    catalog = json.load(f)

counts = Counter()

for topic in catalog["topics"]:
    counts[topic["project_id"]] += topic["thread_target"]

print("Threads per project:")

for project, count in counts.items():
    print(f"{project}: {count}")

total = sum(counts.values())

assert total == 200, f"Expected 200, got {total}"

print(f"\nTotal: {total}")
print("Catalog validation passed!")