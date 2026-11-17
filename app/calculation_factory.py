"""Factory pattern that picks the right calculation logic for each type."""

from abc import ABC, abstractmethod

from app.models import Calculation
from app.operations import add, divide, multiply, subtract
from app.schemas import CalculationCreate, CalculationType


class Operation(ABC):
    """The interface every calculation type implements."""

    @abstractmethod
    def compute(self, a: float, b: float) -> float:
        """Return the result of applying this operation to a and b."""


class AddOperation(Operation):
    """Adds two numbers."""

    def compute(self, a: float, b: float) -> float:
        return add(a, b)


class SubOperation(Operation):
    """Subtracts b from a."""

    def compute(self, a: float, b: float) -> float:
        return subtract(a, b)


class MultiplyOperation(Operation):
    """Multiplies two numbers."""

    def compute(self, a: float, b: float) -> float:
        return multiply(a, b)


class DivideOperation(Operation):
    """Divides a by b. Raises ValueError when b is zero."""

    def compute(self, a: float, b: float) -> float:
        return divide(a, b)


class CalculationFactory:
    """Creates the Operation object that matches a calculation type."""

    _operations = {
        CalculationType.ADD: AddOperation,
        CalculationType.SUB: SubOperation,
        CalculationType.MULTIPLY: MultiplyOperation,
        CalculationType.DIVIDE: DivideOperation,
    }

    @classmethod
    def create(cls, calc_type) -> Operation:
        """Return an Operation for a CalculationType or its string value, e.g. 'Add'."""
        # EAFP: let the enum reject unknown types instead of checking first
        try:
            calc_type = CalculationType(calc_type)
        except ValueError:
            raise ValueError(f"Unsupported calculation type: {calc_type!r}") from None
        return cls._operations[calc_type]()


def build_calculation(data: CalculationCreate, user_id: int) -> Calculation:
    """Compute the result with the factory and return an unsaved Calculation row."""
    operation = CalculationFactory.create(data.type)
    return Calculation(
        a=data.a,
        b=data.b,
        type=data.type.value,
        result=operation.compute(data.a, data.b),
        user_id=user_id,
    )