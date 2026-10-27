# tests/e2e/test_e2e.py
"""End-to-end tests driving the calculator through a real browser."""

import pytest
from playwright.sync_api import expect

BASE_URL = "http://localhost:8000"


@pytest.mark.e2e
def test_hello_world(page, fastapi_server):
    """The homepage loads and shows its heading."""
    page.goto(BASE_URL)
    assert page.inner_text("h1") == "Hello World"


@pytest.mark.e2e
@pytest.mark.parametrize("a, b, button, expected", [
    ("10", "5", "Add", "Calculation Result: 15"),
    ("10", "5", "Subtract", "Calculation Result: 5"),
    ("10", "5", "Multiply", "Calculation Result: 50"),
    ("10", "5", "Divide", "Calculation Result: 2"),
])
def test_calculator_operations(page, fastapi_server, a, b, button, expected):
    """Each calculator button produces the correct result in the browser."""
    page.goto(BASE_URL)
    page.fill("#a", a)
    page.fill("#b", b)
    page.click(f'button:text("{button}")')
    expect(page.locator("#result")).to_have_text(expected)


@pytest.mark.e2e
def test_calculator_decimals(page, fastapi_server):
    """The calculator handles decimal input."""
    page.goto(BASE_URL)
    page.fill("#a", "2.5")
    page.fill("#b", "4")
    page.click('button:text("Multiply")')
    expect(page.locator("#result")).to_have_text("Calculation Result: 10")


@pytest.mark.e2e
def test_calculator_negative_numbers(page, fastapi_server):
    """The calculator handles negative operands."""
    page.goto(BASE_URL)
    page.fill("#a", "-8")
    page.fill("#b", "3")
    page.click('button:text("Add")')
    expect(page.locator("#result")).to_have_text("Calculation Result: -5")


@pytest.mark.e2e
def test_calculator_divide_by_zero(page, fastapi_server):
    """Dividing by zero shows an error instead of a result."""
    page.goto(BASE_URL)
    page.fill("#a", "10")
    page.fill("#b", "0")
    page.click('button:text("Divide")')
    expect(page.locator("#result")).to_have_text("Error: Cannot divide by zero!")