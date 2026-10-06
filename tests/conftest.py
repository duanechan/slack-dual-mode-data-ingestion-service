import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from app.transform import message_to_row


@pytest.fixture
def load_json():
    def load_json_fixture(filename: str) -> dict[str, Any]:
        path = Path(__file__).parent / "fixtures" / filename
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    return load_json_fixture


@pytest.fixture
def valid_settings() -> dict[str, Any]:
    return {
        "JWT_ACCESS_SECRET": "test-jwt-secret",
        "JWT_ALGORITHM": "HS256",
        "JWT_EXPIRY_MINUTES": 30,
        "SLACK_BOT_TOKEN": "xoxb-test-token",
        "MINIO_ACCESS_KEY": "test-access-key",
        "MINIO_SECRET_KEY": "test-secret-key",
        "CLICKHOUSE_PASSWORD": "test-password",
        "LOG_LEVEL": "info",
        "LOG_FORMAT": "json",
    }


@pytest.fixture
def ingested_at() -> datetime:
    return datetime(2026, 10, 5, 12, 0, tzinfo=UTC)


@pytest.fixture
def rows(load_json, ingested_at):
    messages = load_json("conversations-replies.json")["messages"]
    return [
        message_to_row(
            message, "C0C6AJHP204", ingested_at=ingested_at, source="historical"
        )
        for message in messages[:2]
    ]
