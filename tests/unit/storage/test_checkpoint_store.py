import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from minio.error import S3Error

from app.storage.checkpoint_store import CheckpointStore


def fake_s3_error(code: str) -> S3Error:
    return S3Error(
        code=code,
        message=code,
        resource="r",
        request_id="req",
        host_id="host",
        response=Mock(),
    )


class FakeMinio:
    """Just enough of the MinIO SDK for CheckpointStore: a dict of objects."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put_object(self, bucket_name, object_name, data, length):
        self.objects[object_name] = data.read()

    def get_object(self, bucket_name, object_name):
        if object_name not in self.objects:
            raise fake_s3_error("NoSuchKey")
        return _Response(self.objects[object_name])

    def list_objects(self, bucket_name, prefix):
        return [
            SimpleNamespace(object_name=name)
            for name in sorted(self.objects)
            if name.startswith(prefix)
        ]


class _Response:
    def __init__(self, body: bytes) -> None:
        self._body = body
        self.closed = False

    def read(self) -> bytes:
        return self._body

    def close(self) -> None:
        self.closed = True

    def release_conn(self) -> None:
        pass


@pytest.fixture
def minio() -> FakeMinio:
    return FakeMinio()


@pytest.fixture
def store(minio: FakeMinio) -> CheckpointStore:
    return CheckpointStore(minio, "b")  # type: ignore[arg-type]


def test_load_returns_none_when_nothing_saved(store: CheckpointStore):
    assert store.load("C1") is None
    assert store.load_high_water("C1") is None


def test_save_then_load_round_trips_and_overwrites(store: CheckpointStore):
    store.save("C1", "200.000001")
    store.save("C1", "100.000001")
    assert store.load("C1") == "100.000001"


def test_other_s3_errors_are_not_swallowed(store: CheckpointStore, minio: FakeMinio):
    minio.get_object = Mock(side_effect=fake_s3_error("AccessDenied"))
    with pytest.raises(S3Error):
        store.load("C1")


def test_state_lives_outside_the_slack_prefix(store: CheckpointStore, minio: FakeMinio):
    store.save("C1", "100.000001")
    store.save_high_water("C1", "300.000001")
    assert all(name.startswith("_state/") for name in minio.objects)
    assert json.loads(minio.objects["_state/historical/channel_id=C1.json"]) == {
        "oldest_ts": "100.000001"
    }


def test_historical_and_realtime_marks_are_independent(store: CheckpointStore):
    store.save("C1", "100.000001")
    store.save_high_water("C1", "300.000001")
    assert store.load("C1") == "100.000001"
    assert store.load_high_water("C1") == "300.000001"


def test_high_water_channels_lists_only_realtime_marks(store: CheckpointStore):
    store.save("HIST_ONLY", "1.000001")
    store.save_high_water("C1", "2.000001")
    store.save_high_water("C2", "3.000001")
    assert store.high_water_channels() == ["C1", "C2"]
