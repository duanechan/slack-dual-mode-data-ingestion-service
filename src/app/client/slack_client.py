from collections.abc import Iterator
from typing import Any

from slack_sdk import WebClient


class SlackClient:
    def __init__(self, client: WebClient) -> None:
        self._client = client

    def iter_channel_messages(
        self,
        channel_id: str,
        cursor: str | None = None,
        limit: int | None = None,
        latest: str | None = None,
        oldest: str | None = None,
    ) -> Iterator[list[dict[str, Any]]]:
        next_cursor = cursor
        while True:
            res = self._client.conversations_history(
                channel=channel_id,
                cursor=next_cursor,
                limit=limit,
                latest=latest,
                oldest=oldest,
                inclusive=False,
            )

            messages: list[dict[str, Any]] = res.get("messages", [])
            yield messages

            next_cursor = res.get("response_metadata", {}).get("next_cursor")
            if not next_cursor:
                break

    def iter_users(self, limit: int = 200) -> Iterator[list[dict[str, Any]]]:
        cursor: str | None = None
        while True:
            res = self._client.users_list(cursor=cursor, limit=limit)
            yield res.get("members", [])
            cursor = res.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break

    def iter_channels(self, limit: int = 200) -> Iterator[list[dict[str, Any]]]:
        cursor: str | None = None
        while True:
            res = self._client.conversations_list(
                cursor=cursor,
                limit=limit,
                types="public_channel",
                exclude_archived=False,
            )
            yield res.get("channels", [])
            cursor = res.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break
