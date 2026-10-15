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

USER_SCHEMA = pa.schema(
    [
        pa.field("user_id", pa.string(), nullable=False),
        pa.field("name", pa.string()),
        pa.field("real_name", pa.string()),
        pa.field("display_name", pa.string()),
        pa.field("is_bot", pa.bool_(), nullable=False),
        pa.field("deleted", pa.bool_(), nullable=False),
        pa.field("tz", pa.string()),
        pa.field("raw_json", pa.string(), nullable=False),
        pa.field("ingested_at", pa.timestamp("us", tz="UTC"), nullable=False),
    ]
)

CHANNEL_SCHEMA = pa.schema(
    [
        pa.field("channel_id", pa.string(), nullable=False),
        pa.field("name", pa.string()),
        pa.field("is_private", pa.bool_(), nullable=False),
        pa.field("is_archived", pa.bool_(), nullable=False),
        pa.field("created_at", pa.timestamp("us", tz="UTC")),
        pa.field("creator", pa.string()),
        pa.field("topic", pa.string()),
        pa.field("purpose", pa.string()),
        pa.field("num_members", pa.int32()),
        pa.field("raw_json", pa.string(), nullable=False),
        pa.field("ingested_at", pa.timestamp("us", tz="UTC"), nullable=False),
    ]
)


def rows_to_table(rows: list[dict[str, Any]], schema: pa.Schema = SCHEMA) -> pa.Table:
    return pa.Table.from_pylist(rows, schema=schema)
