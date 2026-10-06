from datetime import date

import pytest

from app.storage.minio_client import group_rows_by_message_date


def test_single_row_returns_one_key():
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
