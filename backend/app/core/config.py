from typing import List, Optional, Union
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from pydantic import AnyHttpUrl, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Smart Wardrobe & AI Recommendation System"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    API_V1_STR: str = "/api/v1"

    # Security
    SECRET_KEY: str = "dev-secret-key-smart-wardrobe-backend-mvp-super-safe-32-chars"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALGORITHM: str = "HS256"

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
    ]

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./wardrobe.db"
    SYNC_DATABASE_URL: str = "sqlite:///./wardrobe.db"

    # Redis & Celery
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # Storage
    STORAGE_BACKEND: str = "local"  # "local" or "s3"
    STORAGE_LOCAL_DIR: str = "./storage_data"
    S3_ENDPOINT_URL: Optional[str] = None
    S3_ACCESS_KEY_ID: Optional[str] = None
    S3_SECRET_ACCESS_KEY: Optional[str] = None
    S3_BUCKET_NAME: str = "smart-wardrobe-media"
    S3_REGION: str = "auto"

    # Quality Gate Thresholds
    MAX_UPLOAD_SIZE_MB: int = 15
    MIN_IMAGE_WIDTH: int = 200
    MIN_IMAGE_HEIGHT: int = 200
    BLUR_THRESHOLD_GOOD: float = 100.0
    BLUR_THRESHOLD_BORDERLINE: float = 50.0
    BRIGHTNESS_MIN: float = 40.0
    BRIGHTNESS_MAX: float = 220.0

    # External APIs
    OPENWEATHER_API_KEY: Optional[str] = None
    REPLICATE_API_TOKEN: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def normalize_database_urls(cls, values):
        """Adapt standard Neon URLs to SQLAlchemy's async and sync drivers."""
        if not isinstance(values, dict):
            return values
        async_url = values.get("DATABASE_URL")
        if not isinstance(async_url, str) or not async_url.startswith(("postgres://", "postgresql://")):
            return values

        sync_url = async_url.replace("postgres://", "postgresql://", 1)
        if "SYNC_DATABASE_URL" not in values:
            values["SYNC_DATABASE_URL"] = sync_url.replace("postgresql://", "postgresql+psycopg2://", 1)
        parsed = urlsplit(async_url)
        async_query = []
        for key, value in parse_qsl(parsed.query, keep_blank_values=True):
            if key.lower() == "channel_binding":
                # Neon adds this libpq option to copied URLs; asyncpg doesn't accept it.
                continue
            if key.lower() == "sslmode" and value.lower() == "require":
                key = "ssl"
            async_query.append((key, value))
        values["DATABASE_URL"] = urlunsplit(
            parsed._replace(scheme="postgresql+asyncpg", query=urlencode(async_query))
        )
        return values

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )


settings = Settings()
