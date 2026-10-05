from typing import Literal

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    APP_TITLE: str = "slack-dual-mode-data-ingestion-service"
    APP_VERSION: str = "0.1.0"
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    ENVIRONMENT: Literal["production", "dev", "stage"] = "dev"

    # JWT
    JWT_ACCESS_SECRET: SecretStr
    JWT_ALGORITHM: str
    JWT_EXPIRY_MINUTES: int

    # Slack
    SLACK_BOT_TOKEN: SecretStr

    # MinIO
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_SECURE: bool = False
    MINIO_ACCESS_KEY: SecretStr
    MINIO_SECRET_KEY: SecretStr
    MINIO_BUCKET: str = "slack-ingestion-service-dev"

    # ClickHouse
    CLICKHOUSE_HOST: str = "localhost"
    CLICKHOUSE_PORT: int = 8123
    CLICKHOUSE_USER: str = "default"
    CLICKHOUSE_PASSWORD: SecretStr
    CLICKHOUSE_DB: str = "slack"

    # Logging
    LOG_LEVEL: str
    LOG_FORMAT: str

    @field_validator(
        "JWT_ACCESS_SECRET",
        "SLACK_BOT_TOKEN",
        "MINIO_ACCESS_KEY",
        "MINIO_SECRET_KEY",
        "CLICKHOUSE_PASSWORD",
    )
    @classmethod
    def must_be_real_secret(cls, v: SecretStr) -> SecretStr:
        value = v.get_secret_value().strip()
        if value == "":
            raise ValueError("value cannot be empty")
        if "REPLACE_WITH_" in value:
            raise ValueError("placeholder value detected, set a real value in .env")
        return v

    @field_validator("SLACK_BOT_TOKEN")
    @classmethod
    def must_be_bot_token(cls, v: SecretStr) -> SecretStr:
        if not v.get_secret_value().startswith("xoxb-"):
            raise ValueError("expected a bot token starting with 'xoxb-'")
        return v

    @field_validator("LOG_LEVEL")
    @classmethod
    def must_be_valid_log_level(cls, v: str) -> str:
        valid_levels = ["info", "debug", "warn", "error", "critical"]
        level = v.strip().lower()
        if level not in valid_levels:
            raise ValueError(
                f"expected value to be exactly one of {', '.join(valid_levels)}"
            )
        return level

    @field_validator("LOG_FORMAT")
    @classmethod
    def must_be_valid_log_format(cls, v: str) -> str:
        valid_formats = ["text", "json"]
        format = v.strip().lower()
        if format not in valid_formats:
            raise ValueError(
                f"expected value to be exactly one of {', '.join(valid_formats)}"
            )
        return format

    @model_validator(mode="after")
    def require_secure_minio_in_production(self) -> Settings:
        if self.ENVIRONMENT == "production" and not self.MINIO_SECURE:
            raise ValueError("MINIO_SECURE must be true when ENVIRONMENT is production")
        return self
