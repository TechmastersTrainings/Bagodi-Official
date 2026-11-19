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

    # Notification & Customer Communication Configuration
    notification_default_provider: str = "mock"
    notification_webhook_secret: str = "BAGODI_DEV_NOTIFICATION_WEBHOOK_SECRET_32CHARS"
    notification_max_retries: int = 3
    notification_base_retry_delay_seconds: int = 30
    notification_outbox_batch_size: int = 50

    # Cloudflare R2 Object Storage
    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket_name: str = "bagodi-assets"
    r2_public_domain: str = ""  # e.g. "https://assets.bagodi.in" or "https://pub-xxxx.r2.dev"
    allow_mock_providers_in_production: bool = False

    @property
    def r2_endpoint_url(self) -> str:
        if self.r2_account_id:
            return f"https://{self.r2_account_id}.r2.cloudflarestorage.com"
        return ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        configured = [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
        defaults = [
            "https://bagodi-store.vercel.app",
            "https://bagodi-merchant.vercel.app",
            "https://bagodi-super-admin.vercel.app",
            "http://localhost:3000",
            "http://localhost:3001",
            "http://localhost:3002",
            "http://localhost:5173",
            "http://localhost:5180",
        ]
        return list(dict.fromkeys(configured + defaults))

    def validate_production_configuration(self) -> None:
        """
        Validates that production environment is never started with
        insecure dev secrets, mock providers, or debug flags.
        Raises ValueError if production invariants are violated.
        """
        if self.app_env.lower() == "production":
            violations = []
            if (
                "DEV" in self.jwt_secret_key.upper()
                or "INSECURE" in self.jwt_secret_key.upper()
                or len(self.jwt_secret_key) < 32
            ):
                violations.append(
                    "jwt_secret_key must be an authentic random secret >= 32 chars without DEV/INSECURE markers"
                )
            if not self.allow_mock_providers_in_production:
                if self.payment_gateway_provider.lower() == "mock":
                    violations.append("payment_gateway_provider cannot be 'mock' in production")
                if (
                    "DEV" in self.payment_mock_secret.upper()
                    or "DEV" in self.payment_webhook_secret.upper()
                ):
                    violations.append(
                        "Payment webhook secrets cannot use default dev keys in production"
                    )
                if self.notification_default_provider.lower() == "mock":
                    violations.append("notification_default_provider cannot be 'mock' in production")
                if "DEV" in self.notification_webhook_secret.upper():
                    violations.append(
                        "Notification webhook secrets cannot use default dev keys in production"
                    )
                if self.otp_provider.lower() == "console":
                    violations.append("otp_provider cannot be 'console' in production")
            if self.debug:
                violations.append("debug mode must be disabled in production")
            if violations:
                raise ValueError(
                    "CRITICAL PRODUCTION CONFIGURATION VIOLATION:\n"
                    + "\n".join(f"- {v}" for v in violations)
                )


@lru_cache
def get_settings() -> Settings:
    return Settings()
