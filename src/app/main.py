# src/app/main.py
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from minio import Minio
from slack_sdk import WebClient
from slack_sdk.http_retry.builtin_handlers import RateLimitErrorRetryHandler

from app.client.slack_client import SlackClient
from app.jobs import JobManager
from app.routes import router
from app.services.ingestion_service import IngestionService
from app.settings import Settings
from app.storage.checkpoint_store import CheckpointStore
from app.storage.minio_client import MinioClient


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    settings = Settings()  # pyright: ignore[reportCallIssue]
    slack = SlackClient(
        client=WebClient(
            token=settings.SLACK_BOT_TOKEN.get_secret_value(),
            retry_handlers=[RateLimitErrorRetryHandler(max_retry_count=3)],
        )
    )
    minio_client = Minio(
        endpoint=settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY.get_secret_value(),
        secret_key=settings.MINIO_SECRET_KEY.get_secret_value(),
        secure=settings.MINIO_SECURE,
    )
    service = IngestionService(
        slack,
        MinioClient(client=minio_client, bucket=settings.MINIO_BUCKET),
        CheckpointStore(minio_client, settings.MINIO_BUCKET),
    )
    app.state.jobs = JobManager(service)
    yield
    app.state.jobs.shutdown()


app = FastAPI(title="slack-dual-mode-data-ingestion-service", lifespan=lifespan)
app.include_router(router, prefix="/api")
