"""Integration tests for the Calculation model against a real PostgreSQL database."""

import pytest
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.auth import hash_password
from app.calculation_factory import build_calculation
from app.database import Base, SessionLocal, engine
from app.models import Calculation, User
from app.schemas import CalculationCreate, CalculationRead


def empty_tables():
    """Delete every calculation and user."""
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM calculations"))
        connection.execute(text("DELETE FROM users"))


@pytest.fixture(scope="module", autouse=True)
def create_tables():
    """Make sure both tables exist, even when this file runs on its own."""
    Base.metadata.create_all(bind=engine)


@pytest.fixture(autouse=True)
def clean_tables():
    """Start and finish every test with empty tables so tests do not interfere."""
    empty_tables()
    yield
    empty_tables()


@pytest.fixture
def db():
    """A database session that is closed after the test."""
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def user(db):
    """A saved user who owns the test calculations."""
    owner = User(username="neel", email="neel@example.com",
                 password_hash=hash_password("supersecret123"))
    db.add(owner)
    db.commit()
    db.refresh(owner)
    return owner


def save(db, user_id, **payload):
    """Validate the payload, build the row with the factory, and commit it."""
    calc = build_calculation(CalculationCreate(**payload), user_id)
    db.add(calc)
    db.commit()
    db.refresh(calc)
    return calc


def count_calculations(db):
    """Return how many calculation rows exist."""
    return db.execute(text("SELECT COUNT(*) FROM calculations")).scalar_one()


# ---------- Storing calculations ----------

@pytest.mark.parametrize("calc_type, a, b, expected", [
    ("Add", 2, 3, 5),
    ("Sub", 10, 4, 6),
    ("Multiply", 4, 5, 20),
    ("Divide", 10, 4, 2.5),
])
def test_calculation_is_stored_correctly(db, user, calc_type, a, b, expected):
    """Each type is saved with its operands, computed result, owner, and timestamp."""
    calc = save(db, user.id, a=a, b=b, type=calc_type)

    # Read the row back with plain SQL to see exactly what PostgreSQL stored.
    row = db.execute(
        text("SELECT a, b, type, result, user_id, created_at FROM calculations WHERE id = :id"),
        {"id": calc.id},
    ).one()

    assert (row.a, row.b, row.type) == (a, b, calc_type)
    assert row.result == pytest.approx(expected)
    assert row.user_id == user.id
    assert row.created_at is not None


def test_type_is_stored_in_standard_form(db, user):
    """'divide' from a client is saved as 'Divide', the form the database allows."""
    calc = save(db, user.id, a=9, b=3, type="divide")
    stored = db.execute(
        text("SELECT type FROM calculations WHERE id = :id"), {"id": calc.id}
    ).scalar_one()
    assert stored == "Divide"


def test_saved_row_serializes_with_calculation_read(db, user):
    """A row loaded from PostgreSQL converts to CalculationRead with no user details."""
    calc = save(db, user.id, a=6, b=7, type="Multiply")
    data = CalculationRead.model_validate(calc).model_dump()

    assert data["result"] == 42
    assert data["user_id"] == user.id
    assert set(data) == {"id", "a", "b", "type", "result", "user_id", "created_at"}


# ---------- Relationship and foreign key ----------

def test_user_and_calculations_are_linked(db, user):
    """The relationship works in both directions."""
    first = save(db, user.id, a=1, b=2, type="Add")
    save(db, user.id, a=5, b=3, type="Sub")
    db.refresh(user)

    assert len(user.calculations) == 2
    assert first.user.username == "neel"


def test_deleting_a_user_deletes_their_calculations(db, user):
    """ON DELETE CASCADE removes a user's calculations along with the user."""
    save(db, user.id, a=1, b=2, type="Add")
    save(db, user.id, a=8, b=2, type="Divide")
    assert count_calculations(db) == 2

    db.execute(text("DELETE FROM users WHERE id = :id"), {"id": user.id})
    db.commit()

    assert count_calculations(db) == 0


def test_unknown_user_id_is_rejected(db):
    """user_id must point to a real user, so the foreign key rejects id 999999."""
    db.add(build_calculation(CalculationCreate(a=1, b=2, type="Add"), user_id=999999))
    with pytest.raises(IntegrityError, match="foreign key"):
        db.commit()


# ---------- Error cases ----------

@pytest.mark.parametrize("calc_type, b, constraint", [
    ("Modulus", 2, "ck_calculations_valid_type"),
    ("Divide", 0, "ck_calculations_no_zero_divisor"),
])
def test_database_rejects_rows_that_skip_validation(db, user, calc_type, b, constraint):
    """Even without the schema, PostgreSQL refuses an invalid type or a zero divisor."""
    db.add(Calculation(a=10, b=b, type=calc_type, result=0, user_id=user.id))
    with pytest.raises(IntegrityError, match=constraint):
        db.commit()


@pytest.mark.parametrize("payload", [
    {"a": 10, "b": 5, "type": "Modulus"},
    {"a": 10, "b": 0, "type": "Divide"},
    {"a": "ten", "b": 5, "type": "Add"},
])
def test_invalid_input_saves_nothing(db, user, payload):
    """Validation fails before anything is written, so the table stays empty."""
    with pytest.raises(ValidationError):
        save(db, user.id, **payload)
    assert count_calculations(db) == 0