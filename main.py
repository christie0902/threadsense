from threadsense.adapters.mock_slack import MockSlackAdapter


adapter = MockSlackAdapter(
    fixture_dir="data/fixtures/slack/channels",
    users_file="data/fixtures/slack/users.json",
)

threads = adapter.get_threads("C_RP_GENERAL")


for thread in threads:
    print("=" * 70)

    print(
        f"Project: {thread.project_id}\n"
        f"Channel: {thread.channel_name}\n"
        f"Messages: {thread.message_count}"
    )

    print()

    for message in thread.messages:
        print(
            f"{message.author_name} "
            f"({message.author_role.value}):"
        )

        print(message.text)

        if message.reactions:
            print(
                f"Reactions: {', '.join(message.reactions)}"
            )

        print()