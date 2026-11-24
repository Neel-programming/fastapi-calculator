"""Integration tests for the register and login routes against a real database."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.auth import decode_access_token
from app.database import engine
from main import app

client = TestClient(app)

PASSWORD = "supersecret123"


@pytest.fixture(autouse=True)
def clean_users():
    """Remove all users (and, by cascade, their calculations) around each test."""
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM users"))
    yield
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM users"))


def register(username="neel", email="neel@example.com", password=PASSWORD):
    """Send a registration request and return the response."""
    return client.post("/users/register", json={
        "username": username,
        "email": email,
        "password": password,
    })


def login(username="neel", password=PASSWORD):
    """Send a login request and return the response."""
    return client.post("/users/login", json={"username": username, "password": password})


def db_user(username="neel"):
    """Read a user straight from PostgreSQL, or None if there is no such user."""
    with engine.connect() as connection:
        return connection.execute(
            text("SELECT id, username, email, password_hash FROM users WHERE username = :u"),
            {"u": username},
        ).one_or_none()


def user_count():
    """Return how many users exist."""
    with engine.connect() as connection:
        return connection.execute(text("SELECT COUNT(*) FROM users")).scalar_one()


# ---------- Register ----------

def test_register_returns_created_user():
    """A valid registration returns 201 with the new user's public fields."""
    response = register()
    assert response.status_code == 201
    body = response.json()
    assert body["username"] == "neel"
    assert body["email"] == "neel@example.com"
    assert body["id"] > 0
    assert set(body) == {"id", "username", "email", "created_at"}


def test_register_saves_the_user_in_the_database():
    """The row exists, matches the response, and stores a bcrypt hash, not the password."""
    body = register().json()
    row = db_user()
    assert row.id == body["id"]
    assert row.email == "neel@example.com"
    assert row.password_hash != PASSWORD
    assert row.password_hash.startswith("$2b$")


def test_register_response_never_contains_password():
    """Neither the raw password nor the hash appears in the response."""
    response = register()
    assert "password" not in response.text
    assert "$2b$" not in response.text


@pytest.mark.parametrize("duplicate", [
    {"email": "different@example.com"},  # same username
    {"username": "different"},           # same email
])
def test_duplicate_username_or_email_is_rejected(duplicate):
    """Reusing a username or email returns 400 and keeps only the first user."""
    register()
    response = register(**duplicate)
    assert response.status_code == 400
    assert "already registered" in response.json()["error"]
    assert user_count() == 1


@pytest.mark.parametrize("field, value", [
    ("username", "ab"),
    ("email", "not-an-email"),
    ("password", "short"),
    ("password", "é" * 40),  # 40 characters but 80 bytes, over bcrypt's limit
])
def test_invalid_registration_is_rejected(field, value):
    """Malformed registration data returns 400 and saves nothing."""
    payload = {"username": "neel", "email": "neel@example.com", "password": PASSWORD}
    payload[field] = value
    response = client.post("/users/register", json=payload)
    assert response.status_code == 400
    assert field in response.json()["error"]
    assert user_count() == 0


def test_two_different_users_can_register():
    """Distinct usernames and emails both succeed."""
    assert register().status_code == 201
    assert register(username="other", email="other@example.com").status_code == 201
    assert user_count() == 2


# ---------- Login ----------

def test_login_returns_a_bearer_token_for_the_user():
    """Correct credentials return a JWT that identifies the registered user."""
    user_id = register().json()["id"]
    response = login()
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert decode_access_token(body["access_token"]) == user_id


def test_login_token_unlocks_protected_routes():
    """The token from login is accepted by the calculation routes."""
    register()
    token = login().json()["access_token"]
    response = client.get("/calculations", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.parametrize("username, password", [
    ("neel", "wrongpassword"),   # wrong password
    ("nobody", PASSWORD),        # unknown username
    ("NEEL", PASSWORD),          # usernames are case-sensitive
])
def test_bad_credentials_get_the_same_401(username, password):
    """Wrong passwords and unknown users get an identical response."""
    register()
    response = login(username, password)
    assert response.status_code == 401
    assert response.json() == {"error": "Invalid username or password."}
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("payload", [
    {"username": "neel"},
    {"password": PASSWORD},
    {},
])
def test_login_with_missing_fields_is_rejected(payload):
    """Login data is validated by the UserLogin schema."""
    register()
    response = client.post("/users/login", json=payload)
    assert response.status_code == 400
    assert "Field required" in response.json()["error"]