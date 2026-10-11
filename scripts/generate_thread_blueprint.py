"""Step 23: expand ThreadSense's topic catalog into a 200-thread evaluation blueprint.

Run from the project root:
    python scripts/generate_thread_blueprint.py

Reads:
    data/evaluation/topic_catalog.json
    data/evaluation/thread_blueprint.json  (existing sample threads; not modified)

Writes:
    data/evaluation/thread_blueprint_200.json

The output is evaluation/generation metadata, NOT mock Slack messages. Never feed this
file to the runtime agents, RAG pipeline, or MCP research server.
"""

from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import random

ROOT = Path(__file__).resolve().parents[1]
EVAL_DIR = ROOT / "data" / "evaluation"
CATALOG_PATH = EVAL_DIR / "topic_catalog.json"
SAMPLES_PATH = EVAL_DIR / "thread_blueprint.json"
OUTPUT_PATH = EVAL_DIR / "thread_blueprint_200.json"

SEED = 2026  # Re-running with the same inputs produces the same dataset plan.
SNAPSHOT_START = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)
SNAPSHOT_SECONDS = 24 * 60 * 60

CHANNEL_PREFIX = {
    "response_preference": "C_RP",
    "safety_classification": "C_SAFETY",
    "audio_multimodal": "C_AUDIO",
    "multilingual_eval": "C_MULTI",
}

LANGUAGE_BY_TOPIC = {
    "korean_register_switching": "ko",
    "vietnamese_regional_variation": "vi",
    "japanese_honorific_consistency": "ja",
    "spanish_formality_preference": "es",
}


def read_json(path: Path):
    if not path.is_file():
        raise FileNotFoundError(f"Missing {path}. Check the file name and folder.")
    return json.loads(path.read_text(encoding="utf-8"))


def get_latent_topic(scenario: dict, index: int) -> str:
    """Each routine/outlier must have its own topic, not one giant noise cluster."""
    if scenario["topic_kind"] == "ROUTINE_OUTLIER":
        return scenario["individual_latent_topics"][index]["latent_topic"]
    return scenario["latent_topic"]


def choose_channel(scenario: dict, topic: str, rng: random.Random) -> str:
    if scenario["topic_kind"] == "ROUTINE_OUTLIER":
        return "ANNOUNCEMENTS" if any(
            term in topic for term in ("notice", "reminder", "schedule", "assignment", "resource", "training_link")
        ) else "GENERAL"
    # Most questions go into general or QA; a small fraction are announcement replies.
    return rng.choices(["GENERAL", "QA", "ANNOUNCEMENTS"], weights=[68, 27, 5])[0]


def suggested_terms(topic: str) -> list[str]:
    """Generation hints only. Dialogue writers must actually use these terms."""
    t = topic.lower()
    if any(word in t for word in ("platform", "player", "connection", "rendering")):
        return ["LT"]
    if any(word in t for word in ("quarantine", "_qn", "pii", "nsfw")):
        return ["QN", "QA"]
    if any(word in t for word in ("qa_", "scoring", "rating", "rubric", "tie")):
        return ["QA", "rubric"]
    if any(word in t for word in ("korean", "vietnamese", "spanish", "japanese", "language", "code_switch")):
        return ["QA", "align"]
    return ["queue"]


def allocate_exact_counts(records: list[dict], field: str, targets: dict, rng: random.Random):
    """Honor existing labels while filling exact overall class distributions."""
    counts = Counter(r[field] for r in records if r.get(field) is not None)
    for value, count in counts.items():
        if value not in targets or count > targets[value]:
            raise ValueError(f"Existing {field}={value!r} count {count} exceeds target {targets.get(value)}")

    missing = [r for r in records if r.get(field) is None]
    remaining = [value for value, target in targets.items() for _ in range(target - counts[value])]
    if len(missing) != len(remaining):
        raise ValueError(f"Cannot allocate {field}: {len(missing)} missing, {len(remaining)} slots")
    rng.shuffle(remaining)
    rng.shuffle(missing)
    for record, value in zip(missing, remaining):
        record[field] = value


def main():
    rng = random.Random(SEED)
    catalog = read_json(CATALOG_PATH)
    samples = read_json(SAMPLES_PATH)
    if not isinstance(samples, list):
        raise ValueError("thread_blueprint.json must contain a JSON list of sample thread records.")

    scenarios = catalog["topics"]
    by_project_topic = {}
    for scenario in scenarios:
        for i in range(scenario["thread_target"]):
            key = (scenario["project_id"], get_latent_topic(scenario, i))
            if key in by_project_topic and by_project_topic[key] is not scenario:
                raise ValueError(f"Duplicate scenario ownership for {key}")
            by_project_topic[key] = scenario

    grouped_samples = defaultdict(list)
    seen_ids = set()
    for sample in samples:
        key = (sample["project_id"], sample["latent_topic"])
        if key not in by_project_topic:
            raise ValueError(f"Sample {sample['thread_id']} has topic {key} missing from catalog")
        if sample["thread_id"] in seen_ids:
            raise ValueError(f"Duplicate sample thread_id {sample['thread_id']}")
        seen_ids.add(sample["thread_id"])
        grouped_samples[key].append(dict(sample))  # Copy: never alter original input.

    # Keep generated timestamps in the same 24-hour window as the original samples.
    window_start = int(SNAPSHOT_START.timestamp())
    occupied_seconds = {int(float(thread_id)) for thread_id in seen_ids}
    for thread_id in seen_ids:
        second = int(float(thread_id))
        if not window_start <= second < window_start + SNAPSHOT_SECONDS:
            raise ValueError(
                f"Sample thread_id {thread_id} is outside the Oct 1 noon–Oct 2 noon UTC fixture window. "
                "Adjust SNAPSHOT_START to your actual sample fixture window."
            )
    available_seconds = [window_start + s for s in range(SNAPSHOT_SECONDS)
                         if window_start + s not in occupied_seconds]
    rng.shuffle(available_seconds)

    records = []
    generated_count = 0
    for scenario in scenarios:
        project = scenario["project_id"]
        # For recurring issues, one scenario holds many threads; noise has one topic per item.
        topics = ([scenario["latent_topic"]] * scenario["thread_target"]
                  if scenario["topic_kind"] == "ISSUE"
                  else [item["latent_topic"] for item in scenario["individual_latent_topics"]])
        if len(topics) != scenario["thread_target"]:
            raise ValueError(f"Bad target/individual topic count in {scenario['scenario_id']}")

        for topic in dict.fromkeys(topics):
            existing = grouped_samples.pop((project, topic), [])
            capacity = topics.count(topic)
            if len(existing) > capacity:
                raise ValueError(f"Too many sample threads for {project}/{topic}: {len(existing)} > {capacity}")
            topic_rows = list(existing)
            for _ in range(capacity - len(existing)):
                second = available_seconds.pop()
                generated_count += 1
                thread_id = f"{second}.{generated_count:06d}"
                channel_type = choose_channel(scenario, topic, rng)
                row = {
                    "thread_id": thread_id,
                    "project_id": project,
                    "batch_id": scenario["batch_id"],
                    "channel_type": channel_type,
                    "latent_topic": topic,
                    "primary_issue_class": scenario["primary_issue_class"],
                    "secondary_issue_classes": scenario["secondary_issue_classes"].copy(),
                    "severity": scenario["default_severity"],
                    "resolution_state": "RESOLVED_IN_THREAD" if scenario["topic_kind"] == "ROUTINE_OUTLIER" else None,
                    "language": LANGUAGE_BY_TOPIC.get(topic),
                    "expected_action": scenario["expected_topic_action"],
                    "should_surface": scenario["should_surface"],
                    "cross_project_pattern": scenario["cross_project_pattern"],
                    "language_style": None,
                    "ambiguity_level": rng.choices(["LOW", "MEDIUM", "HIGH"], weights=[35, 50, 15])[0],
                    "domain_terms_used": [] if scenario["topic_kind"] == "ROUTINE_OUTLIER" else suggested_terms(topic),
                    "phrasing_variant_group": topic,
                    "expected_evidence_sources": scenario["expected_evidence_sources"].copy(),
                    "temporal_case": scenario["temporal_case"],
                }
                topic_rows.append(row)
            for row in topic_rows:
                # Preserve all supplied labels and thread IDs; fill only missing metadata.
                row.setdefault("batch_id", scenario["batch_id"])
                row.setdefault("channel_type", "GENERAL")
                row.setdefault("language", LANGUAGE_BY_TOPIC.get(topic))
                row.setdefault("primary_issue_class", scenario["primary_issue_class"])
                row.setdefault("secondary_issue_classes", scenario["secondary_issue_classes"].copy())
                row.setdefault("severity", scenario["default_severity"])
                row.setdefault("resolution_state", None)
                row.setdefault("expected_action", scenario["expected_topic_action"])
                row.setdefault("should_surface", scenario["should_surface"])
                row.setdefault("cross_project_pattern", scenario["cross_project_pattern"])
                row.setdefault("language_style", None)
                row.setdefault("ambiguity_level", "MEDIUM")
                row.setdefault("domain_terms_used", suggested_terms(topic))
                row.setdefault("phrasing_variant_group", topic)
                row.setdefault("expected_evidence_sources", scenario["expected_evidence_sources"].copy())
                row.setdefault("temporal_case", scenario["temporal_case"])
                row["scenario_id"] = scenario["scenario_id"]
                row["channel_id"] = CHANNEL_PREFIX[project] + "_" + row["channel_type"]
                if row["batch_id"] != scenario["batch_id"]:
                    raise ValueError(f"Batch mismatch for {row['thread_id']}: {row['batch_id']}")
                records.append(row)

    if grouped_samples:
        raise ValueError(f"Unassigned sample records: {list(grouped_samples)}")

    # Keep realistic non-issue announcements resolved even when seed records are sparse.
    resolution_targets = catalog["generation_guidelines"]["target_resolution_counts"]
    style_targets = catalog["generation_guidelines"]["language_style_target_counts"]
    allocate_exact_counts(records, "resolution_state", resolution_targets, rng)
    allocate_exact_counts(records, "language_style", style_targets, rng)

    expected_total = catalog["summary"]["planned_threads"]
    assert len(records) == expected_total, (len(records), expected_total)
    assert len({r["thread_id"] for r in records}) == expected_total, "Duplicate IDs"
    actual_project_counts = Counter(r["project_id"] for r in records)
    for project, info in catalog["projects"].items():
        assert actual_project_counts[project] == info["target_threads"]
        assert all(r["batch_id"] == info["batch_id"] for r in records if r["project_id"] == project)
    assert dict(Counter(r["resolution_state"] for r in records)) == resolution_targets
    assert dict(Counter(r["language_style"] for r in records)) == style_targets

    records.sort(key=lambda row: (row["project_id"], float(row["thread_id"])))
    OUTPUT_PATH.write_text(json.dumps(records, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"Saved {len(records)} records → {OUTPUT_PATH.relative_to(ROOT)}")
    print(f"Preserved {len(samples)} sample records; generated {generated_count} new records.")
    print("Projects:", dict(actual_project_counts))
    print("Resolution:", dict(Counter(r["resolution_state"] for r in records)))
    print("Language styles:", dict(Counter(r["language_style"] for r in records)))
    print("Temporal cases:", sum(r["temporal_case"] != "NONE" for r in records))
    print("Routine/no-action:", sum(r["primary_issue_class"] is None for r in records))
    print("Blueprint validation PASSED. No Slack conversations have been generated yet.")


if __name__ == "__main__":
    main()
