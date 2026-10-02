from datetime import UTC, datetime

from app.transform import message_to_row


def test_thread_reply_becomes_created_row(load_json):
    message = load_json("conversations-replies.json")["messages"][1]
    expected = {
        "channel_id": "C0C6AJHP204",
        "ts": "1790925160.657469",
        "event_type": "created",
        "version_ts": "1790925160.657469",
        "message_time": datetime(2026, 10, 2, 7, 12, 40, 657469, tzinfo=UTC),
        "thread_ts": "1790921528.903729",
        "user_id": "U0C6AEJKELC",
        "text": "Goated song",
        "subtype": None,
        "edited_ts": None,
    }

    actual = message_to_row(message, "C0C6AJHP204")

    assert {k: actual[k] for k in expected} == expected
