from datetime import datetime

from app.client.slack_client import SlackClient
from app.storage.minio_client import MinioClient
from app.transform import message_to_row


class IngestionService:
    def __init__(
        self,
        slack: SlackClient,
        minio: MinioClient,
    ) -> None:
        self._slack = slack
        self._minio = minio

    def backfill_channel(
        self,
        channel_id: str,
        ingested_at: datetime,
        limit: int,
    ) -> int:
        total = 0
        for messages in self._slack.iter_channel_messages(
            channel_id=channel_id, limit=limit
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
            self._minio.write_page(mode="historical", rows=rows)
            # <-- CHECKPOINT GOES HERE, and only here:
            #     after write_page has returned without raising.
            #     (the oldest ts in this page becomes the resume point)
            total += len(rows)
        return total
