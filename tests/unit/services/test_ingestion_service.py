from datetime import datetime
from unittest.mock import Mock

from minio.api import Minio
from slack_sdk import WebClient

from app.client.slack_client import SlackClient
from app.services.ingestion_service import IngestionService
from app.storage.minio_client import MinioClient


def test_backfill_channel(ingested_at: datetime):
    web = Mock(spec=WebClient)
    web.conversations_history.side_effect = [
        {
            "messages": [{"ts": "100", "text": "First"}],
            "response_metadata": {"next_cursor": "cursor-2"},
        },
        {
            "messages": [{"ts": "200", "text": "Second"}],
            "response_metadata": {"next_cursor": ""},
        },
    ]

    slack = SlackClient(client=web)
    minio = MinioClient(client=Mock(spec=Minio), bucket="b")

    ingestion = IngestionService(slack, minio)
    assert (
        ingestion.backfill_channel(
            channel_id="#TEST-CHANNEL-ID",
            ingested_at=ingested_at,
            limit=2,
        )
        == 2
    )


import io
from datetime import timedelta

import pyarrow.parquet as pq
import pytest


def test_backfill_recovers_from_crash_between_objects(ingested_at: datetime):
    web = Mock(spec=WebClient)
    web.conversations_history.return_value = {
        "messages": [
            {"ts": "1700086400.000200", "text": "day 2"},
            {"ts": "1700000000.000100", "text": "day 1"},
        ],
        "response_metadata": {"next_cursor": ""},
    }

    stored: dict[str, bytes] = {}
    calls = 0
    fail_on_call: int | None = 2

    def put_object(bucket_name, object_name, data, length):
        nonlocal calls
        calls += 1
        if calls == fail_on_call:
            raise ConnectionError("simulated crash")
        stored[object_name] = data.read()

    raw = Mock(spec=Minio)
    raw.put_object.side_effect = put_object

    def run(at: datetime) -> int:
        service = IngestionService(
            SlackClient(client=web), MinioClient(client=raw, bucket="b")
        )
        return service.backfill_channel(channel_id="C1", ingested_at=at, limit=2)

    with pytest.raises(ConnectionError):
        run(ingested_at)
    assert len(stored) == 1

    fail_on_call = None
    run(ingested_at + timedelta(minutes=5))

    assert len(stored) == 2

    seen = {
        ts
        for body in stored.values()
        for ts in pq.read_table(io.BytesIO(body)).column("ts").to_pylist()
    }
    assert seen == {"1700000000.000100", "1700086400.000200"}
