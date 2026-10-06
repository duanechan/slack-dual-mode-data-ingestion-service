from datetime import date
from typing import Any, Literal

from minio import Minio


def group_rows_by_message_date(
    rows: list[dict[str, Any]],
) -> dict[date, list[dict[str, Any]]]:
    grouped: dict[date, list[dict[str, Any]]] = {}
    for row in rows:
        message_date: date = row["message_date"]
        if message_date not in grouped:
            grouped[message_date] = [row]
        else:
            grouped[message_date].append(row)
    return grouped


def build_object_name(
    *,
    mode: Literal["historical", "realtime"],
    channel_id: str,
    message_date: date,
    oldest_ts: str,
    newest_ts: str,
    content_hash: str,
) -> str:
    folder = (
        f"slack/{mode}"
        + f"/channel_id={channel_id}"
        + f"/message_date={message_date.strftime('%Y-%m-%d')}"
    )
    return f"{folder}/{oldest_ts}_{newest_ts}_{content_hash}.parquet"


class MinioClient:
    def __init__(self, client: Minio, bucket: str) -> None:
        self._client = client
        self._bucket = bucket
