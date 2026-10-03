from threadsense.adapters.mock_slack import MockSlackAdapter
from threadsense.models import Role


def make_adapter():
    return MockSlackAdapter(
        fixture_dir="data/fixtures/slack/channels",
        users_file="data/fixtures/slack/users.json",
    )

def test_adapter_builds_threads():
    adapter = make_adapter()

    threads = adapter.get_threads(
        "C_RP_GENERAL"
    )

    assert len(threads) == 2

def test_first_thread_contains_replies():
    adapter = make_adapter()

    threads = adapter.get_threads(
        "C_RP_GENERAL"
    )

    first_thread = threads[0]

    assert first_thread.message_count == 4

def test_roles_are_preserved():
    adapter = make_adapter()

    threads = adapter.get_threads(
        "C_RP_GENERAL"
    )

    qa_messages = [
        message
        for thread in threads
        for message in thread.messages
        if message.author_role == Role.QA_TUTOR
    ]

    assert len(qa_messages) > 0

def test_threads_are_chronological():
    adapter = make_adapter()

    threads = adapter.get_threads(
        "C_RP_GENERAL"
    )

    timestamps = [
        thread.created_at
        for thread in threads
    ]

    assert timestamps == sorted(timestamps)

def test_messages_are_chronological():
    adapter = make_adapter()

    threads = adapter.get_threads(
        "C_RP_GENERAL"
    )

    for thread in threads:
        timestamps = [
            message.timestamp
            for message in thread.messages
        ]

        assert timestamps == sorted(timestamps)

def test_pagination_returns_multiple_pages():
    adapter = make_adapter()

    items = [
        {"id": i}
        for i in range(45)
    ]

    first_page = adapter._paginate(
        items=items,
        cursor=None,
        limit=20,
    )

    assert len(first_page["messages"]) == 20
    assert first_page["response_metadata"]["next_cursor"] == "20"

    second_page = adapter._paginate(
        items=items,
        cursor="20",
        limit=20,
    )

    assert len(second_page["messages"]) == 20
    assert second_page["response_metadata"]["next_cursor"] == "40"

    third_page = adapter._paginate(
        items=items,
        cursor="40",
        limit=20,
    )

    assert len(third_page["messages"]) == 5
    assert third_page["response_metadata"]["next_cursor"] == ""