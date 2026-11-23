"""Database connection and session management."""

import os

from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

# Falls back to localhost so the app runs outside Docker during development.
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/fastapi_db",
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Any fixed number works. Every worker asks PostgreSQL for the same lock.
TABLE_SETUP_LOCK_ID = 601


def init_db():
    """Create any missing tables, one worker at a time.

    The Docker image starts 4 workers at once. Without the lock, they all try
    to create the same tables at the same moment, and the losers crash with
    "already exists" errors. The lock is released when the transaction ends.
    """
    from app import models  # noqa: F401  (registers User and Calculation on Base)

    with engine.begin() as connection:
        connection.execute(text("SELECT pg_advisory_xact_lock(:id)"), {"id": TABLE_SETUP_LOCK_ID})
        Base.metadata.create_all(bind=connection)


def get_db():
    """Yield a database session and close it when the request finishes."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        