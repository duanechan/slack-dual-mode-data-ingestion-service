import io
from typing import Any, Literal

import pyarrow.parquet as pq
from minio import Minio

from app.parquet import rows_to_table
from app.storage.storage import (
    build_object_name,
    content_hash,
    group_rows_by_message_date,
    ts_bounds,
)


class MinioClient:
    def __init__(self, client: Minio, bucket: str) -> None:
        self._client = client
        self._bucket = bucket

    def write_page(
        self,
        mode: Literal["historical", "realtime"],
        rows: list[dict[str, Any]],
    ) -> list[str]:
        if not rows:
            return []

        channel_ids = {row["channel_id"] for row in rows}
        if len(channel_ids) != 1:
            raise ValueError(
                f"page must belong to one channel, got {sorted(channel_ids)}"
            )
        sources = {row["source"] for row in rows}
        if sources != {mode}:
            raise ValueError(f"rows have source {sorted(sources)} but mode is {mode!r}")
        channel_id = channel_ids.pop()

        written: list[str] = []
        for message_date, group in group_rows_by_message_date(rows).items():
            oldest_ts, newest_ts = ts_bounds(group)
            object_name = build_object_name(
                mode=mode,
                channel_id=channel_id,
                message_date=message_date,
                oldest_ts=oldest_ts,
                newest_ts=newest_ts,
                content_hash=content_hash(group),
            )

            buffer = io.BytesIO()
            pq.write_table(rows_to_table(group), buffer)
            size = buffer.getbuffer().nbytes
            buffer.seek(0)

            self._client.put_object(
                bucket_name=self._bucket,
                object_name=object_name,
                data=buffer,
                length=size,
            )
            written.append(object_name)

        return written
