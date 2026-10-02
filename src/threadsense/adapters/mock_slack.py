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

    