from typing import Any

import pyarrow as pa

SCHEMA = pa.schema(
    [
        pa.field("channel_id", pa.string(), nullable=False),
        pa.field("ts", pa.string(), nullable=False),
        pa.field("event_type", pa.string(), nullable=False),
        pa.field("version_ts", pa.string(), nullable=False),
        pa.field("message_time", pa.timestamp("us", tz="UTC"), nullable=False),
        pa.field("message_date", pa.date32(), nullable=False),
        pa.field("thread_ts", pa.string()),
        pa.field("user_id", pa.string()),
        pa.field("text", pa.string()),
        pa.field("subtype", pa.string()),
        pa.field("edited_ts", pa.string()),
        pa.field("raw_json", pa.string(), nullable=False),
        pa.field("ingested_at", pa.timestamp("us", tz="UTC"), nullable=False),
        pa.field("source", pa.string(), nullable=False),
    ]
)


def rows_to_table(rows: list[dict[str, Any]]) -> pa.Table:
    return pa.Table.from_pylist(rows, schema=SCHEMA)
