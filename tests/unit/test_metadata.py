import io
from datetime import UTC, date, datetime
from unittest.mock import Mock

import pyarrow.parquet as pq
from minio.api import Minio

from app.client.slack_client import SlackClient
from app.services.ingestion_service import IngestionService
from app.storage.minio_client import MinioClient
from app.transform import channel_to_row, user_to_row

NOW = datetime(2026, 10, 15, 8, 0, tzinfo=UTC)


def test_user_to_row_flattens_profile_and_flags():
    row = user_to_row(
        {
            "id": "U1",
            "name": "ana",
            "profile": {"real_name": "Ana Reyes", "display_name": ""},
            "is_bot": True,
        },
        ingested_at=NOW,
    )
    assert row["user_id"] == "U1"
    assert row["real_name"] == "Ana Reyes"  # falls back to the profile
    assert row["display_name"] is None  # empty string becomes NULL
    assert (row["is_bot"], row["deleted"]) == (True, False)
    assert row["ingested_at"] == NOW


def test_channel_to_row_converts_created_and_nested_text(load_json):
    channel = load_json("conversations-list.json")["channels"][0]

    row = channel_to_row(channel, ingested_at=NOW)

    assert row["channel_id"] == channel["id"]
    assert row["created_at"] == datetime.fromtimestamp(channel["created"], tz=UTC)
    assert row["topic"] == (channel["topic"]["value"] or None)
    assert isinstance(row["is_private"], bool)


def test_write_snapshot_is_one_file_per_day_and_empty_writes_nothing():
    put = Mock()
    minio = MinioClient(client=Mock(spec=Minio, put_object=put), bucket="b")
    rows = [user_to_row({"id": "U1", "name": "ana"}, ingested_at=NOW)]

    first = minio.write_snapshot("users", rows, date(2026, 10, 15))
    again = minio.write_snapshot("users", rows, date(2026, 10, 15))

    assert first == again == "slack/users/2026-10-15.parquet"  # overwrite, not append
    assert minio.write_snapshot("users", [], date(2026, 10, 15)) is None
    assert put.call_count == 2
    body = put.call_args.kwargs["data"].read()
    assert pq.read_table(io.BytesIO(body)).column("user_id").to_pylist() == ["U1"]


def test_sync_metadata_writes_both_snapshots_and_counts():
    slack = Mock(spec=SlackClient)
    slack.iter_users.return_value = iter([[{"id": "U1"}, {"id": "U2"}]])
    slack.iter_channels.return_value = iter([[{"id": "C1", "name": "general"}]])
    minio = Mock(spec=MinioClient)
    service = IngestionService(slack, minio, Mock())

    counts = service.sync_metadata(NOW)

    assert counts == {"users": 2, "channels": 1}
    kinds = [c.args[0] for c in minio.write_snapshot.call_args_list]
    assert kinds == ["users", "channels"]
    assert {c.args[2] for c in minio.write_snapshot.call_args_list} == {
        date(2026, 10, 15)
    }
