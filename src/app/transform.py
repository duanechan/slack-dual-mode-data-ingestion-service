from datetime import UTC, datetime, timedelta
from typing import Any

_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


def _ts_to_datetime(ts: str) -> datetime:
    seconds, _, micros = ts.partition(".")
    return _EPOCH + timedelta(seconds=int(seconds), microseconds=int(micros or 0))


def message_to_row(message: dict[str, Any], channel_id: str) -> dict[str, Any]:
    ts = message["ts"]
    edited_ts = (message.get("edited") or {}).get("ts")

    return {
        "channel_id": channel_id,
        "ts": ts,
        "event_type": "edited" if edited_ts else "created",
        "version_ts": edited_ts or ts,
        "message_time": _ts_to_datetime(ts),
        "thread_ts": message.get("thread_ts"),
        "user_id": message.get("user"),
        "text": message.get("text"),
        "subtype": message.get("subtype"),
        "edited_ts": edited_ts,
    }
