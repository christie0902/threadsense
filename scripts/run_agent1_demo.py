import argparse
from pathlib import Path

from threadsense.adapters.mock_slack import MockSlackAdapter


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inspect or interpret one mock Slack thread."
    )
    parser.add_argument("--channel", default="C_AUDIO_GENERAL")
    parser.add_argument("--thread-id", default="1790921338.000134")
    parser.add_argument("--inspect", action="store_true")
    parser.add_argument('--cutoff',help='Timezone-aware daily cutoff; required outside read-only inspection.')
    parser.add_argument(
        "--list",
        action="store_true",
        help="Display channel conversations without calling the model.",
    )

    args = parser.parse_args()

    fixture_root = PROJECT_ROOT / "data" / "fixtures" / "slack_generated"

    adapter = MockSlackAdapter(
        fixture_dir=str(fixture_root / "channels"),
        users_file=str(fixture_root / "users.json"),
    )

    if not (args.inspect or args.list):
        if not args.cutoff:
            parser.error('Processing requires an explicit timezone-aware --cutoff.')
        from threadsense.source_ingestion import fixture_routes, interpretation_threads, existing_canonical_members
        from threadsense.knowledge_sources import extract_announcement, store_source
        from threadsense.routing import IDENTITY
        _, announcements, routing = fixture_routes(fixture_root, cutoff=args.cutoff, channels=[args.channel])
        announcement = next((s for s in announcements if s['thread_id']==args.thread_id), None)
        if announcement is not None:
            member = next((m for m in existing_canonical_members()
                if all(m[k]==announcement.get(k) for k in IDENTITY)), None)
            print(store_source(extract_announcement(announcement, canonical_member=member),
                PROJECT_ROOT/'data/knowledge/decisions'))
            print('Announcement extracted; zero interpretation/model calls.')
            return
        threads, _, _ = interpretation_threads(fixture_root, cutoff=args.cutoff, channels=[args.channel])
    else:
        threads = adapter.get_threads(args.channel)
    if args.list:
        for item in threads:
            print(f"\nTHREAD: {item.thread_id}")

            for message in item.messages:
                print(f"  {message.message_id}: {message.text}")

                for reaction in message.reactions:
                    print(f"    Reaction: {reaction.model_dump_json()}")

        return
    thread = next(
        (item for item in threads if item.thread_id == args.thread_id),
        None,
    )

    if thread is None:
        raise ValueError(
            f"Thread {args.thread_id} was not found in {args.channel}. "
            "Check the channel fixture and thread ID."
        )

    if args.inspect:
        print(thread.model_dump_json(indent=2))
        return

    # Import after inspection mode so inspecting needs no CrewAI startup.
    from threadsense.agents.thread_interpreter import (
        get_model_settings,
        interpret_thread,
    )

    try:
        model, _ = get_model_settings()
    except ValueError as exc:
        parser.error(str(exc))

    print(f"Interpreting with {model}...")

    try:
        result = interpret_thread(thread)
    except RuntimeError as exc:
        parser.exit(1, f"{exc}\n")

    print("\nValidated interpretation:")
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
