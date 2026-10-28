import json
from datetime import datetime, timezone
from pathlib import Path

from threadsense.adapters.base import DataAdapter
from threadsense.routing import slack_datetime, slack_time
from threadsense.models import (
    ChannelType,
    Message,
    Reaction,
    MessageSource,
    Role,
    Thread,
)


class MockSlackAdapter(DataAdapter):

    def __init__(self, fixture_dir: str, users_file: str):
        self.fixture_dir = Path(fixture_dir)

        with open(users_file, encoding="utf-8") as f:
            users_data = json.load(f)

        if isinstance(users_data, dict):
            users = users_data["users"]
        else:
            users = users_data

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

            timestamp=slack_datetime(raw["ts"]),

            text=raw.get("text", ""),

            source=MessageSource(
                raw.get("source", "USER")
            ),

            reactions=self._convert_reactions(
                raw.get("reactions", [])
            ),
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
                batch_id=channel.get("batch_id"),
                
                channel_id=channel["id"],
                channel_name=channel["name"],

                channel_type=ChannelType(
                    channel["channel_type"]
                ),

                language=root_message.get(
                    "language"
                ),

                created_at=slack_datetime(thread_ts),

                messages=messages,
            )

            threads.append(thread)

        threads.sort(
            key=lambda thread: thread.created_at
        )

        return threads

    def get_source_threads(self, channel_id: str) -> list[dict]:
        """Lossless fixture ingestion for deterministic routing/extraction.

        Read exposed replies even when reply_count is stale; retain edit/approval
        metadata and unknown authors without inventing a role. This adapter can
        only expose the snapshot supplied by the caller, not Slack's edit history.
        """
        from copy import deepcopy
        fixture = self._load_channel(channel_id)
        channel = fixture['channel']
        roots = {m['ts']:m for m in fixture['history']}
        if len(roots)!=len(fixture['history']):
            raise ValueError('Duplicate source parent IDs; refusing silent source loss.')
        if set(fixture.get('replies',{}))-roots.keys():
            raise ValueError('Reply collection has no source parent; context is unavailable.')
        result=[]
        for tid, root in roots.items():
            messages={tid:deepcopy(root)}
            for reply in fixture.get('replies',{}).get(tid,[]):
                messages[reply['ts']]=deepcopy(reply)
            ordered=sorted(messages.values(), key=lambda m:slack_time(m['ts']))
            result.append({'workspace_id':fixture.get('workspace_id',channel.get('workspace_id')),
                'project_id':channel.get('project_id'),'batch_id':channel.get('batch_id'),
                'channel_id':channel['id'],'channel_type':channel.get('channel_type'),
                'thread_id':tid,'channel_metadata':deepcopy(channel),
                'messages':ordered,'users':{m.get('user'):deepcopy(self.users.get(m.get('user')))
                                           for m in ordered},
                'source_capture_at':fixture.get('captured_at')})
        return result

    def _convert_reactions(self, raw_reactions):
        converted = []

        for reaction in raw_reactions or []:

            # Support older sample fixtures
            if isinstance(reaction, str):
                converted.append(
                    Reaction(name=reaction)
                )
                continue

            reactor_ids = reaction.get("users") or []

            reactor_roles = {}

            for user_id in reactor_ids:
                user = self.users.get(user_id)

                if user:
                    reactor_roles[user_id] = Role(user["role"])

            converted.append(
                Reaction(
                    name=reaction["name"],
                    users=reactor_ids,
                    count=reaction.get("count"),
                    reactor_roles=reactor_roles,
                )
            )

        return converted
