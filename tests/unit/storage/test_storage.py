from datetime import UTC, date, datetime

import pytest

from app.storage.storage import (
    build_object_name,
    content_hash,
    group_rows_by_message_date,
    ts_bounds,
)


def make_row(ts: str, message_time: datetime) -> dict:
    return {"ts": ts, "message_time": message_time}


def make_key_row(ts: str, event_type: str, version_ts: str) -> dict:
    return {
        "channel_id": "C0C6AJHP204",
        "ts": ts,
        "event_type": event_type,
        "version_ts": version_ts,
    }


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


def test_bounds_ignore_input_order():
    oldest = make_row(
        "1790921528.903729", datetime(2026, 10, 2, 6, 12, 8, 903729, tzinfo=UTC)
    )
    middle = make_row(
        "1790923000.000001", datetime(2026, 10, 2, 6, 36, 40, 1, tzinfo=UTC)
    )
    newest = make_row(
        "1790925160.657469", datetime(2026, 10, 2, 7, 12, 40, 657469, tzinfo=UTC)
    )

    # backfill pages arrive newest-first
    assert ts_bounds([newest, middle, oldest]) == (
        "1790921528.903729",
        "1790925160.657469",
    )


def test_bounds_compare_times_not_strings():
    # as strings "999999999.000001" sorts after "1000000000.000001"
    earlier = make_row(
        "999999999.000001", datetime(2001, 9, 9, 1, 46, 39, 1, tzinfo=UTC)
    )
    later = make_row(
        "1000000000.000001", datetime(2001, 9, 9, 1, 46, 40, 1, tzinfo=UTC)
    )

    assert ts_bounds([later, earlier]) == ("999999999.000001", "1000000000.000001")


def test_bounds_of_one_row_are_that_row():
    row = make_row(
        "1790925160.657469", datetime(2026, 10, 2, 7, 12, 40, 657469, tzinfo=UTC)
    )

    assert ts_bounds([row]) == ("1790925160.657469", "1790925160.657469")


def test_bounds_with_two_rows_sharing_a_ts():
    when = datetime(2026, 10, 2, 7, 12, 40, 657469, tzinfo=UTC)
    created = make_row("1790925160.657469", when)
    edited = make_row("1790925160.657469", when)

    assert ts_bounds([created, edited]) == ("1790925160.657469", "1790925160.657469")


def test_bounds_of_no_rows_raise_error():
    with pytest.raises(ValueError):
        ts_bounds([])


def test_hash_ignores_row_order():
    a = make_key_row("1790921528.903729", "created", "1790921528.903729")
    b = make_key_row("1790925160.657469", "created", "1790925160.657469")

    assert content_hash([a, b]) == content_hash([b, a])


def test_hash_differs_between_created_and_edited_versions():
    created = make_key_row("1790921528.903729", "created", "1790921528.903729")
    edited = make_key_row("1790921528.903729", "edited", "1790921538.000000")

    assert content_hash([created]) != content_hash([edited])


def test_hash_differs_between_two_edits_of_one_message():
    first_edit = make_key_row("1790921528.903729", "edited", "1790921538.000000")
    second_edit = make_key_row("1790921528.903729", "edited", "1790921599.000000")

    assert content_hash([first_edit]) != content_hash([second_edit])


def test_hash_has_a_fixed_known_value():
    rows = [
        make_key_row("1790921528.903729", "created", "1790921528.903729"),
        make_key_row("1790925160.657469", "created", "1790925160.657469"),
    ]

    # pinned: changing the algorithm changes every object name already written
    assert content_hash(rows) == "8a995707"
