import io
from datetime import UTC, datetime

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from app.parquet import SCHEMA, rows_to_table


def test_rows_become_a_table_with_the_declared_schema(rows):
    table = rows_to_table(rows)

    assert table.schema == SCHEMA
    assert table.num_rows == 2


def test_values_survive_the_round_trip(rows):
    table = rows_to_table(rows)

    assert table.to_pylist() == rows
    assert table.to_pylist()[1]["message_time"] == datetime(
        2026, 10, 2, 7, 12, 40, 657469, tzinfo=UTC
    )


def test_missing_key_column_is_rejected_when_writing(rows):
    del rows[0]["version_ts"]
    table = rows_to_table(rows)

    with pytest.raises(pa.ArrowInvalid, match="version_ts"):
        pq.write_table(table, io.BytesIO())


def test_schema_survives_a_parquet_file(rows):
    buffer = io.BytesIO()
    pq.write_table(rows_to_table(rows), buffer)
    buffer.seek(0)

    assert pq.read_table(buffer).schema == SCHEMA
