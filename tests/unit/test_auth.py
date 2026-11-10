"""Unit tests for password hashing and user schemas."""

import pytest
from pydantic import ValidationError

from app.auth import hash_password, verify_password
from app.schemas import UserCreate, UserRead


def test_hash_is_not_the_plain_password():
    """The stored hash never contains the original password."""
    hashed = hash_password("supersecret123")
    assert hashed != "supersecret123"
    assert "supersecret123" not in hashed


def test_hash_has_bcrypt_prefix():
    """Hashes are produced by bcrypt."""
    assert hash_password("supersecret123").startswith("$2b$")


def test_same_password_produces_different_hashes():
    """A random salt means identical passwords hash differently."""
    assert hash_password("supersecret123") != hash_password("supersecret123")


def test_verify_accepts_correct_password():
    """The correct password verifies against its hash."""
    hashed = hash_password("supersecret123")
    assert verify_password("supersecret123", hashed) is True


@pytest.mark.parametrize("wrong", ["wrongpassword", "SUPERSECRET123", "", "supersecret12"])
def test_verify_rejects_incorrect_password(wrong):
    """Any password other than the original fails verification."""
    hashed = hash_password("supersecret123")
    assert verify_password(wrong, hashed) is False


def test_verify_rejects_malformed_hash():
    """A hash that is not valid bcrypt returns False rather than raising."""
    assert verify_password("supersecret123", "not-a-real-hash") is False


def test_password_over_bcrypt_limit_is_rejected():
    """Passwords longer than 72 bytes raise rather than being truncated."""
    with pytest.raises(ValueError, match="at most 72 bytes"):
        hash_password("a" * 73)


def test_user_create_accepts_valid_data():
    """A well-formed registration passes validation."""
    user = UserCreate(username="neel", email="neel@example.com", password="supersecret123")
    assert user.username == "neel"
    assert user.password == "supersecret123"


@pytest.mark.parametrize("field, value", [
    ("username", "ab"),
    ("username", "a" * 51),
    ("email", "not-an-email"),
    ("email", "missing@domain"),
    ("password", "short"),
])
def test_user_create_rejects_invalid_data(field, value):
    """Invalid usernames, emails, and passwords are rejected."""
    data = {"username": "neel", "email": "neel@example.com", "password": "supersecret123"}
    data[field] = value
    with pytest.raises(ValidationError):
        UserCreate(**data)


def test_user_read_excludes_password_fields():
    """The response schema has no password or hash field."""
    fields = UserRead.model_fields.keys()
    assert "password" not in fields
    assert "password_hash" not in fields
    assert set(fields) == {"id", "username", "email", "created_at"}