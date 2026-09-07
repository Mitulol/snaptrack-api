"""Unit tests for password hashing and JWT helpers."""

from datetime import timedelta

import jwt
import pytest

from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_hash_is_salted_and_verifiable():
    h1 = hash_password("hunter2!!")
    h2 = hash_password("hunter2!!")
    assert h1 != h2  # random salt
    assert verify_password("hunter2!!", h1)
    assert not verify_password("wrong", h1)


def test_verify_password_handles_garbage_hash():
    assert verify_password("x", "not-a-bcrypt-hash") is False


def test_token_round_trips_subject():
    token = create_access_token(42)
    assert decode_access_token(token)["sub"] == "42"


def test_expired_token_raises():
    token = create_access_token(1, expires_delta=timedelta(seconds=-5))
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(token)


def test_tampered_token_raises():
    token = create_access_token(1) + "x"
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(token)
