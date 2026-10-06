import json
from datetime import UTC, date, datetime

from app.transform import message_to_row


def test_thread_reply_becomes_created_row(load_json, ingested_at):
    message = load_json("conversations-replies.json")["messages"][1]
    expected = {
        "channel_id": "C0C6AJHP204",
        "ts": "1790925160.657469",
        "event_type": "created",
        "version_ts": "1790925160.657469",
        "message_time": datetime(2026, 10, 2, 7, 12, 40, 657469, tzinfo=UTC),
        "message_date": date(2026, 10, 2),
        "thread_ts": "1790921528.903729",
        "user_id": "U0C6AEJKELC",
        "text": "Goated song",
        "subtype": None,
        "edited_ts": None,
        "ingested_at": ingested_at,
        "source": "historical",
    }

    actual = message_to_row(
        message, "C0C6AJHP204", ingested_at=ingested_at, source="historical"
    )

    assert {k: actual[k] for k in expected} == expected
    assert json.loads(actual["raw_json"]) == message


def test_edited_thread_parent_becomes_edited_row(load_json, ingested_at):
    message = load_json("conversations-replies.json")["messages"][0]
    expected = {
        "channel_id": "C0C6AJHP204",
        "ts": "1790921528.903729",
        "event_type": "edited",
        "version_ts": "1790921538.000000",
        "message_time": datetime(2026, 10, 2, 6, 12, 8, 903729, tzinfo=UTC),
        "message_date": date(2026, 10, 2),
        "thread_ts": "1790921528.903729",
        "user_id": "U0C6AEJKELC",
        "text": "Life's A Bitch by Nas",
        "subtype": None,
        "edited_ts": "1790921538.000000",
        "ingested_at": ingested_at,
        "source": "realtime",
    }

    actual = message_to_row(
        message, "C0C6AJHP204", ingested_at=ingested_at, source="realtime"
    )

    assert {k: actual[k] for k in expected} == expected
    assert json.loads(actual["raw_json"]) == message


def test_raw_json_does_not_depend_on_key_order(ingested_at):
    first = {"ts": "1.000001", "text": "it’s fine 👍"}
    second = {"text": "it’s fine 👍", "ts": "1.000001"}

    row_one = message_to_row(first, "C1", ingested_at=ingested_at, source="historical")
    row_two = message_to_row(second, "C1", ingested_at=ingested_at, source="historical")

    assert row_one["raw_json"] == row_two["raw_json"]
    assert "👍" in row_one["raw_json"]
