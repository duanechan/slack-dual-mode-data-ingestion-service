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
