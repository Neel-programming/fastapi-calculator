"""Unit tests for the calculation factory, schemas, and model helpers. No database needed."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from app.calculation_factory import (
    AddOperation,
    CalculationFactory,
    DivideOperation,
    MultiplyOperation,
    Operation,
    SubOperation,
    build_calculation,
)
from app.models import Calculation, User
from app.schemas import CalculationCreate, CalculationRead, CalculationType


# ---------- Factory ----------

@pytest.mark.parametrize("calc_type, expected_class", [
    (CalculationType.ADD, AddOperation),
    (CalculationType.SUB, SubOperation),
    (CalculationType.MULTIPLY, MultiplyOperation),
    (CalculationType.DIVIDE, DivideOperation),
])
def test_factory_returns_correct_operation(calc_type, expected_class):
    """The factory hands back the operation class that matches each type."""
    assert isinstance(CalculationFactory.create(calc_type), expected_class)


@pytest.mark.parametrize("calc_type", list(CalculationType))
def test_factory_supports_every_type(calc_type):
    """Every type in the enum has an operation, so a new type without one fails here."""
    assert isinstance(CalculationFactory.create(calc_type), Operation)


def test_factory_accepts_plain_strings():
    """The database stores types as strings, so the factory accepts 'Divide' too."""
    assert isinstance(CalculationFactory.create("Divide"), DivideOperation)


@pytest.mark.parametrize("bad_type", ["Modulus", "add", "", None])
def test_factory_rejects_unknown_types(bad_type):
    """Types outside the enum raise a clear error."""
    with pytest.raises(ValueError, match="Unsupported calculation type"):
        CalculationFactory.create(bad_type)


def test_operation_base_class_is_abstract():
    """Operation is an interface and cannot be created directly."""
    with pytest.raises(TypeError):
        Operation()


# ---------- Operations ----------

@pytest.mark.parametrize("calc_type, a, b, expected", [
    ("Add", 2, 3, 5),
    ("Add", -2, -3, -5),
    ("Sub", 10, 4, 6),
    ("Sub", 0, 5, -5),
    ("Multiply", 4, 5, 20),
    ("Multiply", 2.5, 4, 10),
    ("Divide", 10, 4, 2.5),
    ("Divide", -9, 3, -3),
])
def test_operation_computes_correct_result(calc_type, a, b, expected):
    """Each operation returns the right answer, including negatives and decimals."""
    operation = CalculationFactory.create(calc_type)
    assert operation.compute(a, b) == pytest.approx(expected)


def test_divide_operation_rejects_zero():
    """Division by zero raises even if the schema check is skipped."""
    with pytest.raises(ValueError, match="divide by zero"):
        DivideOperation().compute(10, 0)


# ---------- CalculationCreate ----------

def test_calculation_create_accepts_valid_data():
    """A well-formed calculation passes validation."""
    data = CalculationCreate(a=10, b=5, type="Add")
    assert data.a == 10.0
    assert data.b == 5.0
    assert data.type is CalculationType.ADD


@pytest.mark.parametrize("raw_type, expected", [
    ("add", CalculationType.ADD),
    ("SUB", CalculationType.SUB),
    ("  Multiply  ", CalculationType.MULTIPLY),
    ("dIvIdE", CalculationType.DIVIDE),
])
def test_type_ignores_case_and_spaces(raw_type, expected):
    """'add', 'SUB', and padded strings match the right type."""
    assert CalculationCreate(a=10, b=5, type=raw_type).type is expected


@pytest.mark.parametrize("calc_type", ["Add", "Sub", "Multiply"])
def test_zero_divisor_is_only_rejected_for_divide(calc_type):
    """b = 0 is fine for every type except Divide."""
    assert CalculationCreate(a=10, b=0, type=calc_type).b == 0


def test_zero_numerator_is_allowed_for_divide():
    """0 divided by a number is valid."""
    assert CalculationCreate(a=0, b=5, type="Divide").a == 0


@pytest.mark.parametrize("payload, message", [
    ({"a": 10, "b": 5, "type": "Modulus"}, "Input should be 'Add'"),
    ({"a": 10, "b": 5, "type": 3}, "Input should be 'Add'"),
    ({"a": 10, "b": 0, "type": "Divide"}, "Cannot divide by zero"),
    ({"a": "ten", "b": 5, "type": "Add"}, "valid number"),
    ({"a": "10", "b": 5, "type": "Add"}, "valid number"),
    ({"a": True, "b": 5, "type": "Add"}, "valid number"),
    ({"a": float("nan"), "b": 5, "type": "Add"}, "finite number"),
    ({"a": 10, "b": float("inf"), "type": "Add"}, "finite number"),
    ({"b": 5, "type": "Add"}, "Field required"),
    ({"a": 10, "b": 5}, "Field required"),
])
def test_calculation_create_rejects_invalid_data(payload, message):
    """Bad types, zero divisors, non-numbers, and missing fields are rejected."""
    with pytest.raises(ValidationError, match=message):
        CalculationCreate(**payload)


# ---------- CalculationRead ----------

def test_calculation_read_has_only_expected_fields():
    """The response schema exposes calculation data and nothing about the user."""
    assert set(CalculationRead.model_fields) == {
        "id", "a", "b", "type", "result", "user_id", "created_at",
    }


def test_calculation_read_never_leaks_the_owner_hash():
    """Serializing a Calculation that has a linked User leaves the user's hash out."""
    owner = User(id=7, username="neel", email="neel@example.com", password_hash="$2b$12$fakehash")
    calc = Calculation(id=1, a=10, b=4, type="Divide", result=2.5, user_id=7,
                       created_at=datetime(2026, 11, 17, 18, 0), user=owner)

    data = CalculationRead.model_validate(calc)

    assert data.type is CalculationType.DIVIDE
    assert data.result == 2.5
    json_text = data.model_dump_json()
    assert "password" not in json_text
    assert "$2b$" not in json_text


# ---------- build_calculation ----------

def test_build_calculation_fills_in_the_result():
    """build_calculation uses the factory's result and sets the owner, without saving."""
    calc = build_calculation(CalculationCreate(a=10, b=4, type="divide"), user_id=7)
    assert isinstance(calc, Calculation)
    assert (calc.a, calc.b, calc.result, calc.user_id) == (10, 4, 2.5, 7)
    assert calc.type == "Divide"  # stored as the enum's plain string value
    assert calc.id is None  # not saved to the database yet


# ---------- Model representations ----------

def test_calculation_repr_shows_the_expression():
    """repr() reads like the calculation itself."""
    calc = Calculation(id=1, a=2, b=3, type="Add", result=5)
    assert repr(calc) == "<Calculation id=1 2 Add 3 = 5>"


def test_user_repr_hides_the_password_hash():
    """repr() shows the username but never the hash."""
    user = User(id=1, username="neel", password_hash="$2b$12$fakehash")
    assert "neel" in repr(user)
    assert "$2b$" not in repr(user)