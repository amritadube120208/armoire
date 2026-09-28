import pytest
from pydantic import ValidationError
from app.core.config import Settings


def production_settings(**overrides):
    values = {
        "_env_file": None,
        "ENVIRONMENT": "production",
        "DEBUG": False,
        "SECRET_KEY": "a-production-signing-key-that-is-not-a-default-1234567890",
        "DATABASE_URL": "postgresql+asyncpg://armoire:strong-password@db:5432/armoire",
        "SYNC_DATABASE_URL": "postgresql+psycopg2://armoire:strong-password@db:5432/armoire",
        "STORAGE_BACKEND": "s3",
        "S3_BUCKET_NAME": "armoire-private-media",
        "OPENWEATHER_API_KEY": "weather-provider-key",
        "BACKEND_CORS_ORIGINS": ["https://armoire.app"],
    }
    values.update(overrides)
    return Settings(**values)


def test_valid_production_settings_are_accepted():
    assert production_settings().ENVIRONMENT == "production"


@pytest.mark.parametrize("overrides", [
    {"SECRET_KEY": "dev-insecure-development-secret-key-that-is-long-enough"},
    {"SECRET_KEY": "REPLACE_WITH_GENERATED_SECRET_KEY_1234567890123456789"},
    {"DEBUG": True},
    {"DATABASE_URL": "sqlite+aiosqlite:///./wardrobe.db"},
    {"STORAGE_BACKEND": "local"},
    {"OPENWEATHER_API_KEY": "REPLACE_WITH_OPENWEATHER_API_KEY"},
    {"BACKEND_CORS_ORIGINS": ["*"]},
    {"BACKEND_CORS_ORIGINS": ["http://armoire.example.org"]},
    {"BACKEND_CORS_ORIGINS": ["https://your-domain.example"]},
    {"S3_ACCESS_KEY_ID": "only-half-a-credential"},
])
def test_unsafe_or_unfinished_production_settings_fail_fast(overrides):
    with pytest.raises(ValidationError):
        production_settings(**overrides)
