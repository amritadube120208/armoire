from datetime import timedelta
import pytest
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    verify_password,
)


def test_password_hashing():
    raw_pass = "MySecretPassword123!"
    hashed = get_password_hash(raw_pass)

    assert hashed != raw_pass
    assert verify_password(raw_pass, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False


def test_access_token_creation_and_decoding():
    user_id = "11111111-2222-3333-4444-555555555555"
    token = create_access_token(user_id)
    payload = decode_token(token)

    assert payload is not None
    assert payload["sub"] == user_id
    assert payload["type"] == "access"
    assert "exp" in payload


def test_refresh_token_creation():
    user_id = "11111111-2222-3333-4444-555555555555"
    token = create_refresh_token(user_id)
    payload = decode_token(token)

    assert payload is not None
    assert payload["sub"] == user_id
    assert payload["type"] == "refresh"


def test_expired_token():
    user_id = "11111111-2222-3333-4444-555555555555"
    expired_token = create_access_token(user_id, expires_delta=timedelta(seconds=-10))
    payload = decode_token(expired_token)

    assert payload is None
