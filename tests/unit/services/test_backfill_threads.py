import io
from datetime import datetime
from typing import Any
from unittest.mock import Mock

import pyarrow.parquet as pq
import pytest
from minio.api import Minio
from slack_sdk import WebClient

from app.client.slack_client import SlackClient
from app.services.ingestion_service import IngestionService
from app.storage.minio_client import MinioClient

PARENT = {
    "ts": "1790921000.000100",
    "text": "parent",
    "user": "U1",
    "thread_ts": "1790921000.000100",
    "reply_count": 2,
}
PLAIN = {"ts": "1790921050.000200", "text": "no thread", "user": "U1"}
REPLY_1 = {
    "ts": "1790921100.000300",
    "text": "reply one",
    "user": "U2",
    "thread_ts": PARENT["ts"],
}
REPLY_2 = {
    "ts": "1790921200.000400",
    "text": "reply two",
    "user": "U1",
    "thread_ts": PARENT["ts"],
}


@pytest.fixture
def stored() -> dict[str, bytes]:
    return {}


@pytest.fixture
def service(
    stored: dict[str, bytes], checkpoints: Mock
) -> tuple[IngestionService, Mock]:
    web = Mock(spec=WebClient)
    web.conversations_history.return_value = {
        "messages": [PLAIN, PARENT],  # newest first
        "response_metadata": {"next_cursor": ""},
    }
    # conversations.replies returns the parent first, then the replies
    web.conversations_replies.return_value = {
        "messages": [PARENT, REPLY_1, REPLY_2],
        "response_metadata": {"next_cursor": ""},
    }

    def put_object(bucket_name, object_name, data, length):
        stored[object_name] = data.read()

    raw = Mock(spec=Minio)
    raw.put_object.side_effect = put_object
    return (
        IngestionService(
            SlackClient(client=web), MinioClient(client=raw, bucket="b"), checkpoints
        ),
        web,
    )


def landed_rows(stored: dict[str, bytes]) -> list[dict[str, Any]]:
    return [
        row
        for body in stored.values()
        for row in pq.read_table(io.BytesIO(body)).to_pylist()
    ]


def test_threaded_parents_get_their_replies_written(
    service: tuple[IngestionService, Mock],
    stored: dict[str, bytes],
    ingested_at: datetime,
):
    ingestion, web = service

    total = ingestion.backfill_channel("C1", ingested_at, limit=200)

    web.conversations_replies.assert_called_once()  # only the threaded parent
    assert web.conversations_replies.call_args.kwargs["ts"] == PARENT["ts"]
    rows = landed_rows(stored)
    assert total == len(rows) == 4
    assert len({r["ts"] for r in rows}) == 4  # the parent is not written twice
    assert {
        r["text"] for r in rows if r["ts"] != r["thread_ts"] and r["thread_ts"]
    } == {
        "reply one",
        "reply two",
    }


def test_checkpoint_moves_only_after_replies_landed(
    service: tuple[IngestionService, Mock],
    stored: dict[str, bytes],
    checkpoints: Mock,
    ingested_at: datetime,
):
    ingestion, _ = service

    ingestion.backfill_channel("C1", ingested_at, limit=200)

    checkpoints.save.assert_called_once_with(channel_id="C1", oldest_ts=PARENT["ts"])
    assert len(landed_rows(stored)) == 4


def test_failed_replies_fetch_leaves_the_checkpoint_alone(
    service: tuple[IngestionService, Mock],
    checkpoints: Mock,
    ingested_at: datetime,
):
    ingestion, web = service
    web.conversations_replies.side_effect = ConnectionError("slack down")

    with pytest.raises(ConnectionError):
        ingestion.backfill_channel("C1", ingested_at, limit=200)

    checkpoints.save.assert_not_called()  # the page is re-fetched on restart


def test_on_page_reports_parents_and_replies(
    service: tuple[IngestionService, Mock], ingested_at: datetime
):
    ingestion, _ = service
    seen: list[tuple[str, int]] = []

    ingestion.backfill_channel(
        "C1", ingested_at, limit=200, on_page=lambda c, n: seen.append((c, n))
    )

    assert seen == [("C1", 4)]
