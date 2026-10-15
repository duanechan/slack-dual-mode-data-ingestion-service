import json
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


def _ts_to_datetime(ts: str) -> datetime:
    seconds, _, micros = ts.partition(".")
    return _EPOCH + timedelta(seconds=int(seconds), microseconds=int(micros or 0))


def message_to_row(
    message: dict[str, Any],
    channel_id: str,
    *,
    ingested_at: datetime,
    source: Literal["historical", "realtime"],
) -> dict[str, Any]:
    ts = message["ts"]
    edited_ts = (message.get("edited") or {}).get("ts")
    message_time = _ts_to_datetime(ts)

    return {
        "channel_id": channel_id,
        "ts": ts,
        "event_type": "edited" if edited_ts else "created",
        "version_ts": edited_ts or ts,
        "message_time": message_time,
        "message_date": message_time.date(),
        "thread_ts": message.get("thread_ts"),
        "user_id": message.get("user"),
        "text": message.get("text"),
        "subtype": message.get("subtype"),
        "edited_ts": edited_ts,
        "raw_json": json.dumps(message, ensure_ascii=False, sort_keys=True),
        "ingested_at": ingested_at,
        "source": source,
    }


def user_to_row(user: dict[str, Any], *, ingested_at: datetime) -> dict[str, Any]:
    profile = user.get("profile") or {}
    return {
        "user_id": user["id"],
        "name": user.get("name"),
        "real_name": user.get("real_name") or profile.get("real_name"),
        "display_name": profile.get("display_name") or None,
        "is_bot": bool(user.get("is_bot")),
        "deleted": bool(user.get("deleted")),
        "tz": user.get("tz"),
        "raw_json": json.dumps(user, ensure_ascii=False, sort_keys=True),
        "ingested_at": ingested_at,
    }


def channel_to_row(channel: dict[str, Any], *, ingested_at: datetime) -> dict[str, Any]:
    created = channel.get("created")
    return {
        "channel_id": channel["id"],
        "name": channel.get("name"),
        "is_private": bool(channel.get("is_private")),
        "is_archived": bool(channel.get("is_archived")),
        "created_at": _EPOCH + timedelta(seconds=created) if created else None,
        "creator": channel.get("creator"),
        "topic": (channel.get("topic") or {}).get("value") or None,
        "purpose": (channel.get("purpose") or {}).get("value") or None,
        "num_members": channel.get("num_members"),
        "raw_json": json.dumps(channel, ensure_ascii=False, sort_keys=True),
        "ingested_at": ingested_at,
    }
