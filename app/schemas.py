"""Pydantic schemas for request validation and response serialization."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


class UserCreate(BaseModel):
    """Incoming data for registering a new user."""

    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=72)

    @field_validator("password")
    @classmethod
    def fit_bcrypt_limit(cls, value: str) -> str:
        """bcrypt uses at most 72 bytes, and characters like é take 2 bytes each."""
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must be at most 72 bytes.")
        return value


class UserLogin(BaseModel):
    """Credentials for logging in."""

    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1, max_length=72)


class UserRead(BaseModel):
    """User data returned to clients. Never includes the password hash."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: EmailStr
    created_at: datetime


class Token(BaseModel):
    """The JWT returned by a successful login."""

    access_token: str
    token_type: str = "bearer"


class CalculationType(str, Enum):
    """The calculation types the application supports."""

    ADD = "Add"
    SUB = "Sub"
    MULTIPLY = "Multiply"
    DIVIDE = "Divide"


class CalculationCreate(BaseModel):
    """Incoming data for a new or edited calculation."""

    # strict=True accepts real numbers like 10 or 2.5 but rejects True and "10".
    # allow_inf_nan=False rejects NaN and infinity, which are not real operands.
    a: float = Field(..., strict=True, allow_inf_nan=False)
    b: float = Field(..., strict=True, allow_inf_nan=False)
    type: CalculationType

    @field_validator("type", mode="before")
    @classmethod
    def match_type_ignoring_case(cls, value):
        """Accept 'add', 'ADD', or ' Add ' as CalculationType.ADD."""
        if isinstance(value, str):
            for member in CalculationType:
                if member.value.lower() == value.strip().lower():
                    return member
        # Anything else falls through to the enum check, which rejects it.
        return value

    @model_validator(mode="after")
    def reject_zero_divisor(self):
        """Division by zero is not allowed. Runs after a, b, and type pass."""
        if self.type == CalculationType.DIVIDE and self.b == 0:
            raise ValueError("Cannot divide by zero.")
        return self


class CalculationRead(BaseModel):
    """Calculation data returned to clients. Has no link to the user's password hash."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    a: float
    b: float
    type: CalculationType
    result: float
    user_id: int
    created_at: datetime