import json
from pathlib import Path
from typing import Any

import pytest


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
