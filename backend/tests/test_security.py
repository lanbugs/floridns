"""Unit tests for core security utilities."""
import time

import pytest

from app.core.security import (
    create_access_token,
    create_refresh_token,
    create_totp_challenge_token,
    decode_token,
    hash_password,
    verify_password,
)


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

def test_hash_password_produces_bcrypt_hash() -> None:
    h = hash_password("secret")
    assert h.startswith("$2")


def test_verify_password_correct() -> None:
    h = hash_password("correct")
    assert verify_password("correct", h) is True


def test_verify_password_wrong() -> None:
    h = hash_password("correct")
    assert verify_password("wrong", h) is False


def test_hash_is_unique_per_call() -> None:
    h1 = hash_password("same")
    h2 = hash_password("same")
    assert h1 != h2


# ---------------------------------------------------------------------------
# Access token
# ---------------------------------------------------------------------------

def test_create_access_token_decodable() -> None:
    token = create_access_token("user-123")
    payload = decode_token(token)
    assert payload is not None
    assert payload["sub"] == "user-123"
    assert payload["type"] == "access"


def test_access_token_has_expiry() -> None:
    token = create_access_token("user-123")
    payload = decode_token(token)
    assert payload is not None
    assert "exp" in payload
    assert payload["exp"] > time.time()


# ---------------------------------------------------------------------------
# Refresh token
# ---------------------------------------------------------------------------

def test_create_refresh_token_decodable() -> None:
    token = create_refresh_token("user-456")
    payload = decode_token(token)
    assert payload is not None
    assert payload["sub"] == "user-456"
    assert payload["type"] == "refresh"


def test_refresh_token_longer_lived_than_access() -> None:
    access = create_access_token("u")
    refresh = create_refresh_token("u")
    access_exp = decode_token(access)["exp"]  # type: ignore[index]
    refresh_exp = decode_token(refresh)["exp"]  # type: ignore[index]
    assert refresh_exp > access_exp


# ---------------------------------------------------------------------------
# TOTP challenge token
# ---------------------------------------------------------------------------

def test_totp_challenge_token_type() -> None:
    token = create_totp_challenge_token("user-789")
    payload = decode_token(token)
    assert payload is not None
    assert payload["type"] == "totp_challenge"
    assert payload["sub"] == "user-789"


# ---------------------------------------------------------------------------
# decode_token edge cases
# ---------------------------------------------------------------------------

def test_decode_invalid_token_is_falsy() -> None:
    result = decode_token("not.a.token")
    assert not result


def test_decode_empty_string_is_falsy() -> None:
    result = decode_token("")
    assert not result


def test_decode_garbage_is_falsy() -> None:
    result = decode_token("eyJhbGciOiJIUzI1NiJ9.garbage.sig")
    assert not result
