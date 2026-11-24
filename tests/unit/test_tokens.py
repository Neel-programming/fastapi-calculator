"""Unit tests for JWT access tokens and the login schemas. No database needed."""

from datetime import datetime, timedelta, timezone

import jwt
import pytest
from pydantic import ValidationError

from app.auth import (
    ALGORITHM,
    DUMMY_HASH,
    SECRET_KEY,
    create_access_token,
    decode_access_token,
    verify_password,
)
from app.schemas import Token, UserCreate, UserLogin


def make_token(payload, key=SECRET_KEY, algorithm=ALGORITHM):
    """Sign a custom payload, for building tokens the app would never issue."""
    return jwt.encode(payload, key, algorithm=algorithm)


def expires_in(minutes):
    """Return a datetime the given number of minutes from now."""
    return datetime.now(timezone.utc) + timedelta(minutes=minutes)


# ---------- Creating and decoding tokens ----------

def test_token_round_trip_returns_the_user_id():
    """A fresh token decodes back to the user it was made for."""
    assert decode_access_token(create_access_token(42)) == 42


def test_token_stores_id_as_string_and_expires_in_30_minutes():
    """The payload has the user id as 'sub' and an expiry about 30 minutes away."""
    payload = jwt.decode(create_access_token(7), SECRET_KEY, algorithms=[ALGORITHM])
    assert payload["sub"] == "7"
    minutes_left = (payload["exp"] - datetime.now(timezone.utc).timestamp()) / 60
    assert 29 < minutes_left <= 30


def test_expired_token_is_rejected():
    """A token past its expiry decodes to None."""
    token = create_access_token(42, expires_delta=timedelta(seconds=-1))
    assert decode_access_token(token) is None


@pytest.mark.parametrize("token", [
    make_token({"sub": "42", "exp": expires_in(30)}, key="a-completely-different-secret-key-123"),
    make_token({"sub": "42", "exp": expires_in(30)}, key=None, algorithm="none"),
    make_token({"sub": "42"}),
    make_token({"exp": expires_in(30)}),
    make_token({"sub": "not-a-number", "exp": expires_in(30)}),
    "not.a.token",
    "",
])
def test_invalid_tokens_are_rejected(token):
    """Wrong key, unsigned, missing claims, a non-numeric id, or garbage all decode to None."""
    assert decode_access_token(token) is None


def test_editing_a_token_breaks_its_signature():
    """Changing the payload without the secret key makes the token invalid."""
    header, payload, signature = create_access_token(42).split(".")
    forged_payload = jwt.utils.base64url_encode(
        b'{"sub": "1", "exp": 9999999999}'
    ).decode()
    assert decode_access_token(f"{header}.{forged_payload}.{signature}") is None


def test_dummy_hash_never_matches():
    """The hash used for unknown usernames does not accept ordinary passwords."""
    assert verify_password("supersecret123", DUMMY_HASH) is False


# ---------- Login and registration schemas ----------

def test_user_login_accepts_credentials():
    """Username and password are all login needs."""
    login = UserLogin(username="neel", password="supersecret123")
    assert login.username == "neel"


@pytest.mark.parametrize("payload", [
    {"username": "neel"},
    {"password": "supersecret123"},
    {"username": "", "password": "supersecret123"},
    {"username": "neel", "password": ""},
])
def test_user_login_rejects_missing_fields(payload):
    """Both fields are required and cannot be empty."""
    with pytest.raises(ValidationError):
        UserLogin(**payload)


def test_token_type_defaults_to_bearer():
    """Clients send the token back as 'Bearer <token>'."""
    assert Token(access_token="abc").token_type == "bearer"


def test_password_at_the_72_byte_limit_is_accepted():
    """72 ASCII characters is exactly 72 bytes, the most bcrypt can use."""
    user = UserCreate(username="neel", email="neel@example.com", password="a" * 72)
    assert len(user.password) == 72


@pytest.mark.parametrize("password", ["a" * 73, "é" * 40])
def test_password_over_72_bytes_is_rejected(password):
    """73 ASCII characters, or 40 two-byte characters (80 bytes), are too long for bcrypt."""
    with pytest.raises(ValidationError, match="72"):
        UserCreate(username="neel", email="neel@example.com", password=password)