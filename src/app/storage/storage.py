import hashlib
import json
from datetime import date
from typing import Any, Literal


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


def ts_bounds(rows: list[dict[str, Any]]) -> tuple[str, str]:
    oldest = min(rows, key=lambda row: row["message_time"])
    newest = max(rows, key=lambda row: row["message_time"])
    return oldest["ts"], newest["ts"]


def content_hash(rows: list[dict[str, Any]]) -> str:
    keys = sorted(
        (row["channel_id"], row["ts"], row["event_type"], row["version_ts"])
        for row in rows
    )
    payload = json.dumps(keys).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:8]
