import json
from datetime import datetime, timezone
from pathlib import Path

from threadsense.adapters.base import DataAdapter
from threadsense.models import (
    ChannelType,
    Message,
    MessageSource,
    Role,
    Thread,
)


class MockSlackAdapter(DataAdapter):

    def __init__(
        self,
        fixture_dir: str,
        users_file: str,
    ):
        self.fixture_dir = Path(fixture_dir)

        with open(users_file, encoding="utf-8") as f:
            users = json.load(f)

        self.users = {
            user["id"]: user
            for user in users
        }

    def _load_channel(
        self,
        channel_id: str,
    ) -> dict:

        path = self.fixture_dir / f"{channel_id}.json"

        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def _paginate(
        self,
        items: list[dict],
        cursor: str | None,
        limit: int,
    ) -> dict:

        offset = int(cursor) if cursor else 0

        page = items[offset:offset + limit]

        next_offset = offset + limit

        if next_offset < len(items):
            next_cursor = str(next_offset)
        else:
            next_cursor = ""

        return {
            "ok": True,
            "messages": page,
            "response_metadata": {
                "next_cursor": next_cursor
            }
        }
    
    def fetch_history(
        self,
        channel_id: str,
        cursor: str | None = None,
        limit: int = 20,
    ) -> dict:

        fixture = self._load_channel(channel_id)

        return self._paginate(
            fixture["history"],
            cursor,
            limit,
        )

    def fetch_replies(
        self,
        channel_id: str,
        thread_ts: str,
        cursor: str | None = None,
        limit: int = 20,
    ) -> dict:

        fixture = self._load_channel(channel_id)

        replies = fixture["replies"].get(
            thread_ts,
            [],
    )

        return self._paginate(
            replies,
            cursor,
            limit,
     )

    def _convert_message(
        self,
        raw: dict,
    ) -> Message:

        user_id = raw["user"]

        user = self.users[user_id]

        reactions = [
            reaction["name"]
            for reaction in raw.get("reactions", [])
    ]

        return Message(
            message_id=raw["ts"],
            author_id=user_id,
            author_name=user["name"],
            author_role=Role(user["role"]),

            timestamp=datetime.fromtimestamp(
                float(raw["ts"]),
                tz=timezone.utc,
            ),

            text=raw.get("text", ""),

            source=MessageSource(
                raw.get("source", "USER")
            ),

            reactions=reactions,
        )

    def get_threads(
        self,
        channel_id: str,
    ) -> list[Thread]:

        fixture = self._load_channel(channel_id)
        channel = fixture["channel"]

        history_messages = []

        cursor = None

        while True:
            response = self.fetch_history(
                channel_id=channel_id,
                cursor=cursor,
                limit=20,
            )

            history_messages.extend(
                response["messages"]
            )

            cursor = response[
                "response_metadata"
            ]["next_cursor"]

            if not cursor:
                break

            threads = []

            for root_message in history_messages:

                thread_ts = root_message["ts"]

                raw_messages = []

                if root_message.get("reply_count", 0) > 0:

                    reply_cursor = None

                    while True:

                        response = self.fetch_replies(
                            channel_id=channel_id,
                            thread_ts=thread_ts,
                            cursor=reply_cursor,
                            limit=20,
                        )

                        raw_messages.extend(
                            response["messages"]
                        )

                        reply_cursor = response[
                            "response_metadata"
                        ]["next_cursor"]

                        if not reply_cursor:
                            break
                else:
                    raw_messages = [
                        root_message
                    ]

                messages = [
                    self._convert_message(message)
                    for message in raw_messages
                ]

                messages.sort(
                    key=lambda message: message.timestamp
                )

                thread = Thread(
                    thread_id=thread_ts,

                    project_id=channel["project_id"],

                    channel_id=channel["id"],
                    channel_name=channel["name"],

                    channel_type=ChannelType(
                        channel["channel_type"]
                    ),

                    language=root_message.get(
                        "language"
                    ),

                    created_at=datetime.fromtimestamp(
                        float(thread_ts),
                        tz=timezone.utc,
                    ),

                    messages=messages,
                )

                threads.append(thread)

            threads.sort(
                key=lambda thread: thread.created_at
            )
            return threads