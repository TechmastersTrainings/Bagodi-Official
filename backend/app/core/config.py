from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Bagodi Platform API"
    app_env: str = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    database_url: str
    cors_origins: str = ""

    # Authentication & JWT configuration
    jwt_secret_key: str = "BAGODI_DEV_INSECURE_SECRET_KEY_REPLACE_IN_PRODUCTION_32CHARS"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7

    # OTP security & throttling configuration
    otp_expire_seconds: int = 300
    otp_resend_cooldown_seconds: int = 60
    otp_max_hourly_requests: int = 5
    otp_max_attempts: int = 3
    otp_provider: str = "console"

    # Payment Gateway Configuration
    payment_gateway_provider: str = "mock"
    payment_mock_secret: str = "BAGODI_DEV_PAYMENT_SECRET_KEY_32CHARS"
    payment_webhook_secret: str = "BAGODI_DEV_PAYMENT_WEBHOOK_SECRET_KEY_32CHARS"
    payment_webhook_timestamp_tolerance_seconds: int = 300

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
