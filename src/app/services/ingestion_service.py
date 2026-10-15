import threading
from collections.abc import Callable
from datetime import datetime
from typing import Any

from app.client.slack_client import SlackClient
from app.storage.checkpoint_store import CheckpointStore
from app.storage.minio_client import MinioClient
from app.storage.storage import ts_bounds
from app.transform import channel_to_row, message_to_row, user_to_row


class IngestionService:
    def __init__(
        self,
        slack: SlackClient,
        minio: MinioClient,
        checkpoints: CheckpointStore,
    ) -> None:
        self._slack = slack
        self._minio = minio
        self._checkpoints = checkpoints

    def backfill_channel(
        self,
        channel_id: str,
        ingested_at: datetime,
        limit: int,
        running: threading.Event | None = None,
        on_page: Callable[[str, int], None] | None = None,
    ) -> int:
        total = 0
        latest = self._checkpoints.load(channel_id)
        for messages in self._slack.iter_channel_messages(
            channel_id=channel_id, limit=limit, latest=latest
        ):
            rows = [
                message_to_row(
                    message=message,
                    channel_id=channel_id,
                    ingested_at=ingested_at,
                    source="historical",
                )
                for message in messages
            ]
            if not rows:
                continue
            self._minio.write_page(mode="historical", rows=rows)
            reply_count = self._backfill_replies(channel_id, messages, ingested_at)
            oldest_ts, _ = ts_bounds(rows)
            self._checkpoints.save(channel_id=channel_id, oldest_ts=oldest_ts)
            total += len(rows) + reply_count
            if on_page is not None:
                on_page(channel_id, len(rows) + reply_count)
            if running is not None:
                running.wait()
        return total

    def _backfill_replies(
        self,
        channel_id: str,
        messages: list[dict[str, Any]],
        ingested_at: datetime,
    ) -> int:
        """Write the replies of every threaded parent on this page.

        conversations.history returns parents only. This runs before the page
        checkpoint is saved, so a crash re-fetches the page with its replies.
        """
        written = 0
        for message in messages:
            if not message.get("reply_count"):
                continue
            thread_ts = message.get("thread_ts", message["ts"])
            for replies in self._slack.iter_thread_replies(channel_id, thread_ts):
                rows = [
                    message_to_row(
                        message=reply,
                        channel_id=channel_id,
                        ingested_at=ingested_at,
                        source="historical",
                    )
                    for reply in replies
                    if reply["ts"] != thread_ts  # the parent comes back too
                ]
                if rows:
                    self._minio.write_page(mode="historical", rows=rows)
                    written += len(rows)
        return written

    def sync_metadata(self, ingested_at: datetime) -> dict[str, int]:
        users = [
            user_to_row(user, ingested_at=ingested_at)
            for page in self._slack.iter_users()
            for user in page
        ]
        channels = [
            channel_to_row(channel, ingested_at=ingested_at)
            for page in self._slack.iter_channels()
            for channel in page
        ]
        snapshot_date = ingested_at.date()
        self._minio.write_snapshot("users", users, snapshot_date)
        self._minio.write_snapshot("channels", channels, snapshot_date)
        return {"users": len(users), "channels": len(channels)}
