from typing import List, Optional
from urllib.parse import urlsplit
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Smart Wardrobe & AI Recommendation System"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    API_V1_STR: str = "/api/v1"

    # Security
    # This development-only key is rejected when ENVIRONMENT=production.
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

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    @field_validator("ENVIRONMENT")
    @classmethod
    def validate_environment(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in {"development", "test", "staging", "production"}:
            raise ValueError("ENVIRONMENT must be development, test, staging, or production")
        return value

    @model_validator(mode="after")
    def validate_deployment_settings(self):
        if len(self.SECRET_KEY.encode("utf-8")) < 32:
            raise ValueError("SECRET_KEY must be at least 32 bytes")

        if self.STORAGE_BACKEND not in {"local", "s3"}:
            raise ValueError("STORAGE_BACKEND must be local or s3")

        if self.ENVIRONMENT == "production":
            if self.SECRET_KEY.startswith(("dev-", "gsk_", "REPLACE")):
                raise ValueError("Set a unique SECRET_KEY before starting in production")
            if self.DEBUG:
                raise ValueError("DEBUG must be false in production")
            if not self.DATABASE_URL.startswith("postgresql+asyncpg://") or not self.SYNC_DATABASE_URL.startswith("postgresql+psycopg2://"):
                raise ValueError("Production requires PostgreSQL for both database URLs")
            if self.STORAGE_BACKEND != "s3":
                raise ValueError("Production requires private S3-compatible object storage")
            if not self.S3_BUCKET_NAME.strip():
                raise ValueError("Production requires an S3_BUCKET_NAME")
            if self.S3_ENDPOINT_URL and not self.S3_ENDPOINT_URL.startswith("https://"):
                raise ValueError("Production S3_ENDPOINT_URL must use HTTPS")
            if any("REPLACE" in value for value in (self.DATABASE_URL, self.SYNC_DATABASE_URL)):
                raise ValueError("Replace the database URL placeholders before deployment")
            if self.S3_ENDPOINT_URL and ".example" in self.S3_ENDPOINT_URL:
                raise ValueError("Replace the S3 endpoint example before deployment")
            if bool(self.S3_ACCESS_KEY_ID) != bool(self.S3_SECRET_ACCESS_KEY):
                raise ValueError("Set both S3 credentials or use a workload identity")
            if (self.S3_ACCESS_KEY_ID or "").startswith("REPLACE") or (self.S3_SECRET_ACCESS_KEY or "").startswith("REPLACE"):
                raise ValueError("Replace the S3 credential placeholders before deployment")
            if not self.OPENWEATHER_API_KEY or self.OPENWEATHER_API_KEY.startswith("REPLACE"):
                raise ValueError("Production requires OPENWEATHER_API_KEY for live recommendations")
            if not self.BACKEND_CORS_ORIGINS:
                raise ValueError("Production requires an explicit frontend origin")
            for origin in self.BACKEND_CORS_ORIGINS:
                parsed = urlsplit(origin)
                if origin == "*" or parsed.scheme != "https" or not parsed.hostname or parsed.path not in {"", "/"} or parsed.query or parsed.fragment or ".example" in origin:
                    raise ValueError("Production CORS origins must be real, specific HTTPS origins")

        return self


settings = Settings()
