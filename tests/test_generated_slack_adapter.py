"""Verify MockSlackAdapter ingests the 200-thread Slack dataset.

Install at: tests/test_generated_slack_adapter.py
Run at project root: uv run --locked --extra dev python -m pytest -q tests/test_generated_slack_adapter.py

Reads only agent-visible data/fixtures/slack_generated, not evaluation labels.
"""
from collections import Counter
from pathlib import Path
import json

import pytest

from threadsense.adapters.mock_slack import MockSlackAdapter
from threadsense.models import Role

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "data" / "fixtures" / "slack_generated"
CHANNELS = FIXTURES / "channels"
PROJECT_COUNTS = {
    "response_preference": 55,
    "safety_classification": 50,
    "audio_multimodal": 45,
    "multilingual_eval": 50,
}
BATCH_IDS = {
    "response_preference": "rp_batch_15",
    "safety_classification": "safety_batch_08",
    "audio_multimodal": "audio_batch_06",
    "multilingual_eval": "multi_batch_11",
}


@pytest.fixture(scope="module")
def corpus():
    assert (FIXTURES / "users.json").exists()
    channel_files = sorted(CHANNELS.glob("C_*.json"))
    assert len(channel_files) == 12

    users = json.loads((FIXTURES / "users.json").read_text(encoding="utf-8"))["users"]
    roles = {u["id"]: u["role"] for u in users}
    adapter = MockSlackAdapter(
        fixture_dir=str(CHANNELS), users_file=str(FIXTURES / "users.json")
    )
    by_channel = {p.stem: adapter.get_threads(p.stem) for p in channel_files}
    raw_channels = {
        p.stem: json.loads(p.read_text(encoding="utf-8")) for p in channel_files
    }
    threads = [thread for group in by_channel.values() for thread in group]
    return adapter, by_channel, raw_channels, roles, threads


def test_thread_counts_batches_and_channels(corpus):
    _, by_channel, _, _, threads = corpus
    assert len(threads) == 200
    assert Counter(t.project_id for t in threads) == PROJECT_COUNTS
    assert len({t.thread_id for t in threads}) == 200
    for channel_id, group in by_channel.items():
        for thread in group:
            assert thread.channel_id == channel_id
            assert thread.batch_id == BATCH_IDS[thread.project_id]
            assert thread.messages
            assert thread.created_at == thread.messages[0].timestamp
            times = [message.timestamp for message in thread.messages]
            assert times == sorted(times)
            assert all(ts.tzinfo is not None for ts in times)


def test_every_raw_reaction_survives_ingestion(corpus):
    _, by_channel, raw_channels, roles, _ = corpus
    checked = 0
    for channel_id, threads in by_channel.items():
        raw = raw_channels[channel_id]
        root_by_id = {str(r["ts"]): r for r in raw["history"]}
        for thread in threads:
            root = root_by_id[thread.thread_id]
            raw_messages = raw["replies"].get(thread.thread_id) or [root]
            assert len(thread.messages) == len(raw_messages), thread.thread_id
            for message, raw_message in zip(thread.messages, raw_messages):
                assert message.timestamp.timestamp() == pytest.approx(float(raw_message["ts"]), abs=0.00001)
                raw_reactions = raw_message.get("reactions", [])
                assert len(message.reactions) == len(raw_reactions), (thread.thread_id, raw_message["ts"])
                for reaction, expected in zip(message.reactions, raw_reactions):
                    if isinstance(expected, str):
                        assert reaction.name == expected
                        assert not reaction.users
                        assert not reaction.reactor_roles
                        continue
                    assert reaction.name == expected["name"]
                    assert reaction.users == expected.get("users", [])
                    assert reaction.count == expected.get("count")
                    for uid in expected.get("users", []):
                        assert uid in reaction.reactor_roles, (thread.thread_id, uid)
                        assert reaction.reactor_roles[uid] == Role(roles[uid])
                    checked += 1
    assert checked > 0, "No structured emoji reactions were checked"


def test_tl_endorsements_target_substantive_replies(corpus):
    _, _, _, _, threads = corpus
    approval_counts = Counter()
    for thread in threads:
        for index, message in enumerate(thread.messages):
            for reaction in message.reactions:
                if reaction.name in {"this", "agree", "white_check_mark"} and (
                    Role.TEAM_LEAD in reaction.reactor_roles.values()
                ):
                    assert index > 0, f"TL approved a root question: {thread.thread_id}"
                    assert message.author_role in {Role.TUTOR, Role.QA_TUTOR}
                    assert len(message.text.strip()) > 20
                    approval_counts[reaction.name] += 1
    assert approval_counts == {
        "this": 6,
        "agree": 6,
        "white_check_mark": 6,
    }


def test_tl_eyes_are_distinct_from_approvals(corpus):
    _, _, _, _, threads = corpus
    found = [
        (thread.thread_id, reaction.name)
        for thread in threads
        for message in thread.messages
        for reaction in message.reactions
        if reaction.name == "eyes" and Role.TEAM_LEAD in reaction.reactor_roles.values()
    ]
    assert found, "Expected TL acknowledgement reactions (:eyes:)"
    assert not any(name in {"this", "agree", "white_check_mark"} for _, name in found)


def test_history_cursor_pagination(corpus):
    adapter, by_channel, _, _, _ = corpus
    channel_id = max(by_channel, key=lambda c: len(by_channel[c]))
    expected = {thread.thread_id for thread in by_channel[channel_id]}
    cursor = None
    seen = []
    while True:
        page = adapter.fetch_history(channel_id, cursor=cursor, limit=7)
        assert len(page["messages"]) <= 7
        seen.extend(str(m["ts"]) for m in page["messages"])
        cursor = page.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break
    assert len(seen) == len(set(seen))
    assert set(seen) == expected
