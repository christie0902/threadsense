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

    assert len(threads) == 3

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

def test_message_without_replies_becomes_thread():
    adapter = make_adapter()

    threads = adapter.get_threads(
        "C_RP_GENERAL"
    )

    standalone_threads = [
        thread
        for thread in threads
        if thread.thread_id == "1790880012.001400"
    ]

    assert len(standalone_threads) == 1

    thread = standalone_threads[0]

    assert thread.message_count == 1
    assert thread.messages[0].text == (
        "Reminder: queue closes at 6 PM today."
    )

def test_language_metadata_is_preserved():
    adapter = make_adapter()

    threads = adapter.get_threads(
        "C_RP_GENERAL"
    )

    target_thread = next(
        thread
        for thread in threads
        if thread.thread_id == "1790877012.001300"
    )

    assert target_thread.language == "en"

def test_missing_language_defaults_to_none():
    adapter = make_adapter()

    threads = adapter.get_threads(
        "C_RP_GENERAL"
    )

    target_thread = next(
        thread
        for thread in threads
        if thread.thread_id == "1790873412.001200"
    )

    assert target_thread.language is None

def test_multilingual_channel_loads_correctly():
    adapter = make_adapter()

    threads = adapter.get_threads(
        "C_MULTI_GENERAL"
    )

    assert len(threads) == 2

    languages = {
        thread.language
        for thread in threads
    }

    assert languages == {"ko", "vi"}

def test_korean_thread_metadata():
    adapter = make_adapter()

    threads = adapter.get_threads(
        "C_MULTI_GENERAL"
    )

    korean_thread = next(
        thread
        for thread in threads
        if thread.language == "ko"
    )

    assert korean_thread.project_id == "multilingual_eval"
    assert korean_thread.channel_name == "multilingual-eval-general"
    assert korean_thread.message_count == 4

def test_multilingual_thread_contains_team_lead():
    adapter = make_adapter()

    threads = adapter.get_threads(
        "C_MULTI_GENERAL"
    )

    team_lead_messages = [
        message
        for thread in threads
        for message in thread.messages
        if message.author_role == Role.TEAM_LEAD
    ]

    assert len(team_lead_messages) > 0

def test_safety_channel_loads_correctly():
    adapter = make_adapter()

    threads = adapter.get_threads(
        "C_SAFETY_GENERAL"
    )

    assert len(threads) == 2
    assert all(
        thread.project_id == "safety_classification"
        for thread in threads
    )

def test_safety_first_thread_has_team_lead_resolution():
    adapter = make_adapter()

    threads = adapter.get_threads(
        "C_SAFETY_GENERAL"
    )

    first_thread = threads[0]

    team_lead_messages = [
        message
        for message in first_thread.messages
        if message.author_role == Role.TEAM_LEAD
    ]

    assert len(team_lead_messages) == 1

def test_audio_channel_loads_correctly():
    adapter = make_adapter()

    threads = adapter.get_threads(
        "C_AUDIO_GENERAL"
    )

    assert len(threads) == 2

    assert all(
        thread.project_id == "audio_multimodal"
        for thread in threads
    )

def test_audio_unresolved_thread_has_no_team_lead():
    adapter = make_adapter()

    threads = adapter.get_threads(
        "C_AUDIO_GENERAL"
    )

    target_thread = next(
        thread
        for thread in threads
        if thread.thread_id == "1790899012.002000"
    )

    team_lead_messages = [
        message
        for message in target_thread.messages
        if message.author_role == Role.TEAM_LEAD
    ]

    assert len(team_lead_messages) == 0