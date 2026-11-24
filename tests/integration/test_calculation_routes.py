"""Integration tests for the calculation BREAD routes against a real database."""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.auth import create_access_token
from app.database import engine
from main import app

client = TestClient(app)


def empty_tables():
    """Delete every calculation and user."""
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM calculations"))
        connection.execute(text("DELETE FROM users"))


@pytest.fixture(autouse=True)
def clean_tables():
    """Start and finish every test with empty tables."""
    empty_tables()
    yield
    empty_tables()


def register_and_login(username):
    """Register a user through the API, log in, and return their auth header."""
    password = "supersecret123"
    client.post("/users/register", json={
        "username": username, "email": f"{username}@example.com", "password": password,
    })
    response = client.post("/users/login", json={"username": username, "password": password})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def auth():
    """Auth header for the main test user, neel."""
    return register_and_login("neel")


@pytest.fixture
def other_auth():
    """Auth header for a second user, to check that users cannot see each other's data."""
    return register_and_login("other")


def add(headers, a=10, b=4, calc_type="Divide"):
    """POST a calculation and return the response."""
    return client.post("/calculations", json={"a": a, "b": b, "type": calc_type}, headers=headers)


def db_row(calc_id):
    """Read a calculation straight from PostgreSQL, or None if it is gone."""
    with engine.connect() as connection:
        return connection.execute(
            text("SELECT a, b, type, result, user_id FROM calculations WHERE id = :id"),
            {"id": calc_id},
        ).one_or_none()


def db_user_id(username):
    """Look up a user's id straight from PostgreSQL."""
    with engine.connect() as connection:
        return connection.execute(
            text("SELECT id FROM users WHERE username = :u"), {"u": username}
        ).scalar_one()


def calculation_count():
    """Return how many calculations exist."""
    with engine.connect() as connection:
        return connection.execute(text("SELECT COUNT(*) FROM calculations")).scalar_one()


# ---------- Full lifecycle ----------

def test_create_read_update_delete(auth):
    """One calculation goes through Add, Read, Edit, and Delete."""
    created = add(auth, a=10, b=4, calc_type="Divide")
    assert created.status_code == 201
    calc_id = created.json()["id"]

    read = client.get(f"/calculations/{calc_id}", headers=auth)
    assert read.status_code == 200
    assert read.json()["result"] == 2.5

    edited = client.put(f"/calculations/{calc_id}", json={"a": 6, "b": 7, "type": "Multiply"},
                        headers=auth)
    assert edited.status_code == 200
    assert edited.json()["result"] == 42

    deleted = client.delete(f"/calculations/{calc_id}", headers=auth)
    assert deleted.status_code == 204
    assert client.get(f"/calculations/{calc_id}", headers=auth).status_code == 404


# ---------- Add ----------

@pytest.mark.parametrize("calc_type, a, b, expected", [
    ("Add", 2, 3, 5),
    ("Sub", 10, 4, 6),
    ("Multiply", 4, 5, 20),
    ("Divide", 10, 4, 2.5),
])
def test_add_computes_and_saves_each_type(auth, calc_type, a, b, expected):
    """POST returns 201 with the result, and PostgreSQL stores the same row for this user."""
    response = add(auth, a=a, b=b, calc_type=calc_type)
    assert response.status_code == 201
    body = response.json()
    assert body["result"] == pytest.approx(expected)
    assert body["user_id"] == db_user_id("neel")

    row = db_row(body["id"])
    assert (row.a, row.b, row.type) == (a, b, calc_type)
    assert row.result == pytest.approx(expected)
    assert row.user_id == body["user_id"]


def test_add_ignores_a_user_id_in_the_body(auth, other_auth):
    """The owner always comes from the token, so nobody can save into another account."""
    other_id = db_user_id("other")
    response = client.post(
        "/calculations",
        json={"a": 1, "b": 2, "type": "Add", "user_id": other_id},
        headers=auth,
    )
    assert response.status_code == 201
    assert response.json()["user_id"] == db_user_id("neel")


@pytest.mark.parametrize("payload, message", [
    ({"a": 10, "b": 5, "type": "Modulus"}, "type"),
    ({"a": 10, "b": 0, "type": "Divide"}, "Cannot divide by zero"),
    ({"a": "ten", "b": 5, "type": "Add"}, "valid number"),
    ({"a": True, "b": 5, "type": "Add"}, "valid number"),
    ({"b": 5, "type": "Add"}, "Field required"),
])
def test_add_rejects_invalid_data(auth, payload, message):
    """Invalid data returns 400 with an error message and saves nothing."""
    response = client.post("/calculations", json=payload, headers=auth)
    assert response.status_code == 400
    assert message in response.json()["error"]
    assert calculation_count() == 0


# ---------- Browse ----------

def test_browse_lists_only_my_calculations_in_order(auth, other_auth):
    """Browse returns the user's own calculations, oldest first, and none of anyone else's."""
    first = add(auth, a=1, b=2, calc_type="Add").json()
    second = add(auth, a=9, b=3, calc_type="Sub").json()
    add(other_auth, a=5, b=5, calc_type="Multiply")

    response = client.get("/calculations", headers=auth)
    assert response.status_code == 200
    assert [calc["id"] for calc in response.json()] == [first["id"], second["id"]]


def test_browse_is_empty_for_a_new_user(auth):
    """A user with no calculations gets an empty list, not an error."""
    response = client.get("/calculations", headers=auth)
    assert response.status_code == 200
    assert response.json() == []


# ---------- Read ----------

def test_read_returns_the_calculation(auth):
    """GET by id returns exactly what POST created."""
    created = add(auth).json()
    response = client.get(f"/calculations/{created['id']}", headers=auth)
    assert response.status_code == 200
    assert response.json() == created


def test_read_rejects_a_non_integer_id(auth):
    """The id in the URL must be an integer."""
    response = client.get("/calculations/abc", headers=auth)
    assert response.status_code == 400
    assert "calc_id" in response.json()["error"]


# ---------- Edit ----------

def test_edit_recomputes_and_saves_the_result(auth):
    """PUT replaces a, b, and type, recomputes the result, and updates PostgreSQL."""
    calc_id = add(auth, a=2, b=3, calc_type="Add").json()["id"]

    response = client.put(f"/calculations/{calc_id}", json={"a": 10, "b": 4, "type": "sub"},
                          headers=auth)
    assert response.status_code == 200
    assert response.json()["result"] == 6
    assert response.json()["type"] == "Sub"

    row = db_row(calc_id)
    assert (row.a, row.b, row.type, row.result) == (10, 4, "Sub", 6)


@pytest.mark.parametrize("payload, message", [
    ({"a": 10, "b": 0, "type": "Divide"}, "Cannot divide by zero"),
    ({"a": 10, "b": 2, "type": "Power"}, "type"),
    ({"a": 10, "type": "Add"}, "Field required"),
])
def test_edit_rejects_invalid_data_and_keeps_the_old_values(auth, payload, message):
    """A bad edit returns 400 and the stored calculation does not change."""
    calc_id = add(auth, a=2, b=3, calc_type="Add").json()["id"]

    response = client.put(f"/calculations/{calc_id}", json=payload, headers=auth)
    assert response.status_code == 400
    assert message in response.json()["error"]

    row = db_row(calc_id)
    assert (row.a, row.b, row.type, row.result) == (2, 3, "Add", 5)


# ---------- Delete ----------

def test_delete_removes_the_row(auth):
    """DELETE returns 204 with no body, and the row is gone from PostgreSQL."""
    calc_id = add(auth).json()["id"]

    response = client.delete(f"/calculations/{calc_id}", headers=auth)
    assert response.status_code == 204
    assert response.content == b""
    assert db_row(calc_id) is None


def test_deleting_twice_returns_404(auth):
    """A calculation that is already gone cannot be deleted again."""
    calc_id = add(auth).json()["id"]
    client.delete(f"/calculations/{calc_id}", headers=auth)
    assert client.delete(f"/calculations/{calc_id}", headers=auth).status_code == 404


# ---------- Ownership ----------

@pytest.mark.parametrize("method", ["GET", "PUT", "DELETE"])
def test_other_users_calculations_are_hidden(auth, other_auth, method):
    """Reading, editing, or deleting someone else's calculation returns 404 and changes nothing."""
    calc_id = add(other_auth, a=2, b=3, calc_type="Add").json()["id"]

    body = {"a": 100, "b": 1, "type": "Add"} if method == "PUT" else None
    response = client.request(method, f"/calculations/{calc_id}", json=body, headers=auth)
    assert response.status_code == 404
    assert response.json() == {"error": "Calculation not found."}

    row = db_row(calc_id)
    assert (row.a, row.b, row.result) == (2, 3, 5)


@pytest.mark.parametrize("method", ["GET", "PUT", "DELETE"])
def test_missing_calculation_returns_404(auth, method):
    """An id that does not exist returns 404."""
    body = {"a": 1, "b": 2, "type": "Add"} if method == "PUT" else None
    response = client.request(method, "/calculations/999999", json=body, headers=auth)
    assert response.status_code == 404


# ---------- Authentication ----------

ROUTES = [
    ("GET", "/calculations"),
    ("POST", "/calculations"),
    ("GET", "/calculations/1"),
    ("PUT", "/calculations/1"),
    ("DELETE", "/calculations/1"),
]


def call(method, url, headers=None):
    """Call a route, sending a valid body to POST and PUT."""
    body = {"a": 1, "b": 2, "type": "Add"} if method in ("POST", "PUT") else None
    return client.request(method, url, json=body, headers=headers)


@pytest.mark.parametrize("method, url", ROUTES)
def test_every_route_requires_a_token(method, url):
    """Without a token, every calculation route returns 401."""
    response = call(method, url)
    assert response.status_code == 401
    assert response.json() == {"error": "Not authenticated."}
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("method, url", ROUTES)
def test_garbage_token_is_rejected(method, url):
    """A token that is not a valid JWT returns 401 on every route."""
    response = call(method, url, headers={"Authorization": "Bearer not-a-real-token"})
    assert response.status_code == 401
    assert response.json() == {"error": "Invalid or expired token."}


def test_expired_token_is_rejected(auth):
    """A correctly signed token that has expired returns 401."""
    expired = create_access_token(db_user_id("neel"), expires_delta=timedelta(seconds=-1))
    response = client.get("/calculations", headers={"Authorization": f"Bearer {expired}"})
    assert response.status_code == 401


def test_deleted_users_token_is_rejected(auth):
    """A valid token stops working once its user is deleted."""
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM users WHERE username = 'neel'"))
    response = client.get("/calculations", headers=auth)
    assert response.status_code == 401


# ---------- Health ----------

def test_health_check():
    """The Docker health check endpoint reports ok."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}