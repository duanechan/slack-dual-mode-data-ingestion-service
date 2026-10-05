import pytest
from pydantic import ValidationError

from app.settings import Settings


def test_valid_settings_load(valid_settings):
    settings = Settings.model_validate(valid_settings)

    assert settings.ENVIRONMENT == "dev"


def test_log_level_is_lowercased(valid_settings):
    settings = Settings.model_validate({**valid_settings, "LOG_LEVEL": "INFO"})

    assert settings.LOG_LEVEL == "info"


def test_unknown_environment_is_rejected(valid_settings):
    with pytest.raises(ValidationError, match="ENVIRONMENT"):
        Settings.model_validate({**valid_settings, "ENVIRONMENT": "prod"})
