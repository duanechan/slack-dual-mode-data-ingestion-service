import io
import json
from typing import Any

from minio import Minio
from minio.error import S3Error

_HIGH_WATER_PREFIX = "_state/realtime/channel_id="


class CheckpointStore:
    def __init__(self, client: Minio, bucket: str) -> None:
        self._client = client
        self._bucket = bucket

    def _put(self, key: str, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self._client.put_object(
            bucket_name=self._bucket,
            object_name=key,
            data=io.BytesIO(body),
            length=len(body),
        )

    def _get(self, key: str) -> dict[str, Any] | None:
        try:
            res = self._client.get_object(self._bucket, key)
        except S3Error as e:
            if e.code == "NoSuchKey":
                return None
            raise
        try:
            return json.loads(res.read())
        finally:
            res.close()
            res.release_conn()

    # Historical backfill: oldest ts reached so far (resume with `latest=`).
    def _key(self, channel_id: str) -> str:
        return f"_state/historical/channel_id={channel_id}.json"

    def save(self, channel_id: str, oldest_ts: str) -> None:
        self._put(self._key(channel_id), {"oldest_ts": oldest_ts})

    def load(self, channel_id: str) -> str | None:
        data = self._get(self._key(channel_id))
        return None if data is None else data["oldest_ts"]

    # Real-time: newest ts written so far (catch up from here with `oldest=`).
    def save_high_water(self, channel_id: str, newest_ts: str) -> None:
        self._put(f"{_HIGH_WATER_PREFIX}{channel_id}.json", {"newest_ts": newest_ts})

    def load_high_water(self, channel_id: str) -> str | None:
        data = self._get(f"{_HIGH_WATER_PREFIX}{channel_id}.json")
        return None if data is None else data["newest_ts"]

    def high_water_channels(self) -> list[str]:
        names = (
            obj.object_name
            for obj in self._client.list_objects(
                self._bucket, prefix=_HIGH_WATER_PREFIX
            )
        )
        return [
            n.removeprefix(_HIGH_WATER_PREFIX).removesuffix(".json") for n in names if n
        ]
