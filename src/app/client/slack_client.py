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
    ) -> Iterator[list[dict[str, Any]]]:
        next_cursor = cursor
        while True:
            res = self._client.conversations_history(
                channel=channel_id,
                cursor=next_cursor,
                limit=limit,
            )

            messages: list[dict[str, Any]] = res.get("messages", [])
            yield messages

            next_cursor = res.get("response_metadata", {}).get("next_cursor")
            if not next_cursor:
                break
