from datetime import UTC, date, datetime

import pytest

from app.storage.minio_client import build_object_name, group_rows_by_message_date


def test_rows_on_one_date_share_one_key():
    oct_2 = date(2026, 10, 2)
    a = {"ts": "a", "message_date": oct_2}
    b = {"ts": "b", "message_date": oct_2}

    groups = group_rows_by_message_date([a, b])

    assert groups == {oct_2: [a, b]}


def test_rows_are_grouped_by_message_date_in_input_order():
    oct_2 = date(2026, 10, 2)
    oct_3 = date(2026, 10, 3)
    a = {"ts": "a", "message_date": oct_2}
    b = {"ts": "b", "message_date": oct_3}
    c = {"ts": "c", "message_date": oct_2}

    groups = group_rows_by_message_date([a, b, c])

    assert groups == {oct_2: [a, c], oct_3: [b]}


def test_empty_rows_return_empty_dict():
    assert group_rows_by_message_date([]) == {}


def test_row_without_message_date_raises_error():
    with pytest.raises(KeyError, match="message_date"):
        group_rows_by_message_date(
            [
                {"ts": "a", "message_date": date(2026, 10, 2)},
                {"ts": "b"},
            ]
        )


@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        (
            "historical",
            "slack/historical/channel_id=C0C6AJHP204/message_date=2026-10-02/1790921528.903729_1790925160.657469_a1b2c3d4.parquet",
        ),
        (
            "realtime",
            "slack/realtime/channel_id=C0C6AJHP204/message_date=2026-10-02/1790921528.903729_1790925160.657469_a1b2c3d4.parquet",
        ),
    ],
)
def test_build_object_name(mode, expected):
    name = build_object_name(
        mode=mode,
        channel_id="C0C6AJHP204",
        message_date=date(2026, 10, 2),
        oldest_ts="1790921528.903729",
        newest_ts="1790925160.657469",
        content_hash="a1b2c3d4",
    )

    assert name == expected


def test_different_content_hash_gives_different_name():
    common = {
        "mode": "historical",
        "channel_id": "C0C6AJHP204",
        "message_date": date(2026, 10, 2),
        "oldest_ts": "1790921528.903729",
        "newest_ts": "1790925160.657469",
    }

    first = build_object_name(**common, content_hash="a1b2c3d4")
    second = build_object_name(**common, content_hash="e5f6a7b8")

    assert first != second


def test_datetime_message_date_still_gives_a_clean_path():
    name = build_object_name(
        mode="historical",
        channel_id="C0C6AJHP204",
        message_date=datetime(2026, 10, 2, 7, 12, tzinfo=UTC),
        oldest_ts="1790921528.903729",
        newest_ts="1790925160.657469",
        content_hash="a1b2c3d4",
    )

    assert "/message_date=2026-10-02/" in name
