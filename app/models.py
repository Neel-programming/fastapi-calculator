"""SQLAlchemy models."""

from datetime import datetime

from sqlalchemy import CheckConstraint, Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
    """A registered user of the calculator application."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.now, nullable=False)

    # One user has many calculations. passive_deletes lets PostgreSQL's
    # ON DELETE CASCADE remove them when the user is deleted.
    calculations = relationship(
        "Calculation",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        """Return a readable representation without exposing the hash."""
        return f"<User id={self.id} username={self.username!r}>"


class Calculation(Base):
    """One calculation owned by a user. The result is computed once and stored."""

    __tablename__ = "calculations"

    # The database rejects bad rows itself, even if code skips the Pydantic schemas.
    # Keep the type list in sync with CalculationType in app/schemas.py.
    __table_args__ = (
        CheckConstraint(
            "type IN ('Add', 'Sub', 'Multiply', 'Divide')",
            name="ck_calculations_valid_type",
        ),
        CheckConstraint(
            "NOT (type = 'Divide' AND b = 0)",
            name="ck_calculations_no_zero_divisor",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    a = Column(Float, nullable=False)
    b = Column(Float, nullable=False)
    type = Column(String(20), nullable=False)
    result = Column(Float, nullable=False)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at = Column(DateTime, default=datetime.now, nullable=False)

    user = relationship("User", back_populates="calculations")

    def __repr__(self) -> str:
        """Return a readable representation of the calculation."""
        return f"<Calculation id={self.id} {self.a} {self.type} {self.b} = {self.result}>"