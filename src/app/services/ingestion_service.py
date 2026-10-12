from datetime import datetime

from app.client.slack_client import SlackClient
from app.storage.checkpoint_store import CheckpointStore
from app.storage.minio_client import MinioClient
from app.storage.storage import ts_bounds
from app.transform import message_to_row


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
        return total
