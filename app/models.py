"""SQLAlchemy models."""

from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String

from app.database import Base


class User(Base):
    """A registered user of the calculator application."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.now, nullable=False)

    def __repr__(self) -> str:
        """Return a readable representation without exposing the hash."""
        return f"<User id={self.id} username={self.username!r}>"