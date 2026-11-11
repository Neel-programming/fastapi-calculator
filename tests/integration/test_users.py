"""Integration tests for the user registration endpoint against a real database."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.database import SessionLocal, engine
from main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_users():
    """Remove all users before and after each test so tests do not interfere."""
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM users"))
    yield
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM users"))


def register(username="neel", email="neel@example.com", password="supersecret123"):
    """Send a registration request and return the response."""
    return client.post("/users", json={
        "username": username,
        "email": email,
        "password": password,
    })


def test_register_returns_created():
    """A valid registration returns 201 with the new user."""
    response = register()
    assert response.status_code == 201
    body = response.json()
    assert body["username"] == "neel"
    assert body["email"] == "neel@example.com"
    assert body["id"] > 0


def test_response_never_contains_password():
    """Neither the raw password nor the hash appears in the response."""
    body = register().json()
    assert "password" not in body
    assert "password_hash" not in body


def test_password_is_hashed_in_the_database():
    """The stored value is a bcrypt hash, not the plain password."""
    register()
    session = SessionLocal()
    try:
        stored = session.execute(
            text("SELECT password_hash FROM users WHERE username = 'neel'")
        ).scalar_one()
    finally:
        session.close()
    assert stored != "supersecret123"
    assert stored.startswith("$2b$")


def test_duplicate_username_is_rejected():
    """Registering the same username twice returns 400."""
    register()
    response = register(email="different@example.com")
    assert response.status_code == 400
    assert "already registered" in response.json()["error"]


def test_duplicate_email_is_rejected():
    """Registering the same email twice returns 400."""
    register()
    response = register(username="different")
    assert response.status_code == 400
    assert "already registered" in response.json()["error"]


@pytest.mark.parametrize("field, value", [
    ("username", "ab"),
    ("email", "not-an-email"),
    ("password", "short"),
])
def test_invalid_input_is_rejected(field, value):
    """Malformed registration data returns 400 and saves nothing."""
    payload = {"username": "neel", "email": "neel@example.com", "password": "supersecret123"}
    payload[field] = value
    response = client.post("/users", json=payload)
    assert response.status_code == 400

    session = SessionLocal()
    try:
        count = session.execute(text("SELECT COUNT(*) FROM users")).scalar_one()
    finally:
        session.close()
    assert count == 0


def test_two_different_users_can_register():
    """Distinct usernames and emails both succeed."""
    assert register().status_code == 201
    assert register(username="other", email="other@example.com").status_code == 201