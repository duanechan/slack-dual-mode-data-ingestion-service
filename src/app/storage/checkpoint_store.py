import io
import json

from minio import Minio
from minio.error import S3Error


class CheckpointStore:
    def __init__(self, client: Minio, bucket: str) -> None:
        self._client = client
        self._bucket = bucket

    def _key(self, channel_id: str) -> str:
        return f"_state/historical/channel_id={channel_id}.json"

    def save(self, channel_id: str, oldest_ts: str) -> None:
        body = json.dumps({"oldest_ts": oldest_ts}).encode("utf-8")
        self._client.put_object(
            bucket_name=self._bucket,
            object_name=self._key(channel_id),
            data=io.BytesIO(body),
            length=len(body),
        )

    def load(self, channel_id: str) -> str | None:
        try:
            res = self._client.get_object(self._bucket, self._key(channel_id))
        except S3Error as e:
            if e.code == "NoSuchKey":
                return None
            raise
        try:
            return json.loads(res.read())["oldest_ts"]
        finally:
            res.close()
            res.release_conn()
