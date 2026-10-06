from datetime import date
from typing import Any

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


def build_object_name_from_channel(channel_id: str) -> str:
    return ""


class MinioClient:
    def __init__(self, client: Minio, bucket: str) -> None:
        self._client = client
        self._bucket = bucket
