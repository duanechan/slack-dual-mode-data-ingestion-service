import io
from datetime import UTC, date, datetime
from unittest.mock import Mock

import pyarrow.parquet as pq
import pytest
from minio import Minio

from app.parquet import SCHEMA
from app.storage.minio_client import MinioClient
from app.storage.storage import content_hash

OCT_2_PREFIX = (
    "slack/historical/channel_id=C0C6AJHP204/message_date=2026-10-02/"
    "1790921528.903729_1790925160.657469_"
)
OCT_3_PREFIX = (
    "slack/historical/channel_id=C0C6AJHP204/message_date=2026-10-03/"
    "1791000000.000001_1791000000.000001_"
)


@pytest.fixture
def two_date_rows(rows):
    next_day = {
        **rows[1],
        "ts": "1791000000.000001",
        "version_ts": "1791000000.000001",
        "message_time": datetime(2026, 10, 3, 4, 40, 0, 1, tzinfo=UTC),
        "message_date": date(2026, 10, 3),
    }
    return [*rows, next_day]


def object_names(minio: Mock) -> list[str]:
    return [call.kwargs["object_name"] for call in minio.put_object.call_args_list]


def test_one_object_is_written_per_message_date(two_date_rows):
    minio = Mock(spec=Minio)
    client = MinioClient(minio, bucket="slack-ingestion-service-dev")

    written = client.write_page("historical", two_date_rows)

    names = object_names(minio)
    assert names == written
    assert len(names) == 2
    assert names[0] == OCT_2_PREFIX + content_hash(two_date_rows[:2]) + ".parquet"
    assert names[1] == OCT_3_PREFIX + content_hash(two_date_rows[2:]) + ".parquet"
    assert (
        minio.put_object.call_args_list[0].kwargs["bucket_name"]
        == "slack-ingestion-service-dev"
    )


def test_uploaded_bytes_are_a_valid_file_with_the_declared_schema(two_date_rows):
    minio = Mock(spec=Minio)
    client = MinioClient(minio, bucket="b")

    client.write_page("historical", two_date_rows)

    first = minio.put_object.call_args_list[0].kwargs
    content = first["data"].read()
    table = pq.read_table(io.BytesIO(content))
    assert first["length"] == len(content)
    assert table.schema == SCHEMA
    assert table.to_pylist() == two_date_rows[:2]


def test_empty_page_writes_nothing():
    minio = Mock(spec=Minio)
    client = MinioClient(minio, bucket="b")

    assert client.write_page("historical", []) == []
    minio.put_object.assert_not_called()


def test_failed_upload_reaches_the_caller(rows):
    minio = Mock(spec=Minio)
    minio.put_object.side_effect = ConnectionError("minio is down")
    client = MinioClient(minio, bucket="b")

    with pytest.raises(ConnectionError):
        client.write_page("historical", rows)


def test_retry_after_a_partial_failure_uses_the_same_object_names(two_date_rows):
    flaky = Mock(spec=Minio)
    flaky.put_object.side_effect = [None, ConnectionError("dropped")]
    with pytest.raises(ConnectionError):
        MinioClient(flaky, bucket="b").write_page("historical", two_date_rows)

    retry = Mock(spec=Minio)
    MinioClient(retry, bucket="b").write_page("historical", two_date_rows)

    assert object_names(retry) == object_names(flaky)


def test_page_from_two_channels_is_rejected_before_any_upload(rows):
    minio = Mock(spec=Minio)
    mixed = [rows[0], {**rows[1], "channel_id": "C0000000002"}]

    with pytest.raises(ValueError, match="one channel"):
        MinioClient(minio, bucket="b").write_page("historical", mixed)

    minio.put_object.assert_not_called()


def test_rows_from_another_mode_are_rejected_before_any_upload(rows):
    minio = Mock(spec=Minio)

    with pytest.raises(ValueError, match="source"):
        MinioClient(minio, bucket="b").write_page("realtime", rows)

    minio.put_object.assert_not_called()
