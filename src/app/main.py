from datetime import UTC, datetime

from minio import Minio
from slack_sdk import WebClient

from app.client.slack_client import SlackClient
from app.services.ingestion_service import IngestionService
from app.settings import Settings
from app.storage.checkpoint_store import CheckpointStore
from app.storage.minio_client import MinioClient


def main() -> None:
    settings = Settings()  # pyright: ignore[reportCallIssue]
    slack_web_client = WebClient(token=settings.SLACK_BOT_TOKEN.get_secret_value())
    slack = SlackClient(client=slack_web_client)
    minio_client = Minio(
        endpoint=settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY.get_secret_value(),
        secret_key=settings.MINIO_SECRET_KEY.get_secret_value(),
        secure=settings.MINIO_SECURE,
    )
    minio = MinioClient(client=minio_client, bucket=settings.MINIO_BUCKET)
    checkpoints = CheckpointStore(minio_client, settings.MINIO_BUCKET)
    ingestion_service = IngestionService(slack, minio, checkpoints)

    total = ingestion_service.backfill_channel(
        channel_id="C0C6AJHP204",
        ingested_at=datetime.now(UTC),
        limit=200,
    )
    print(f"Result: {total}")


if __name__ == "__main__":
    main()
