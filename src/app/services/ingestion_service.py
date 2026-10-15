import threading
from collections.abc import Callable
from datetime import datetime

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
            oldest_ts, _ = ts_bounds(rows)
            self._checkpoints.save(channel_id=channel_id, oldest_ts=oldest_ts)
            total += len(rows)
            if on_page is not None:
                on_page(channel_id, len(rows))
            if running is not None:
                running.wait()
        return total

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
