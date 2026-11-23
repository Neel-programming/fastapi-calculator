"""Password hashing, JWT access tokens, and the logged-in-user dependency."""

import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User

# bcrypt truncates input beyond 72 bytes, so reject longer passwords
# rather than silently ignoring the extra characters.
MAX_PASSWORD_BYTES = 72

# Set JWT_SECRET_KEY in production. The default is only for development and tests.
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-only-secret-key-change-me-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Adds the Authorize button to /docs. auto_error=False lets get_current_user
# send its own 401 response instead of FastAPI's default.
bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    """Return a bcrypt hash of the given plain-text password."""
    # LBYL: check the length before bcrypt silently truncates it
    encoded = password.encode("utf-8")
    if len(encoded) > MAX_PASSWORD_BYTES:
        raise ValueError(f"Password must be at most {MAX_PASSWORD_BYTES} bytes.")
    return bcrypt.hashpw(encoded, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Return True if the plain-text password matches the stored hash."""
    # EAFP: let bcrypt reject a malformed hash rather than parsing it first
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


# Login checks this hash when the username does not exist, so a wrong username
# takes as long as a wrong password and response times reveal nothing.
DUMMY_HASH = hash_password("placeholder-password-never-matches")


def create_access_token(user_id: int, expires_delta: timedelta | None = None) -> str:
    """Return a signed JWT that identifies the user and expires after 30 minutes."""
    lifetime = expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),  # JWT subjects must be strings
        "exp": datetime.now(timezone.utc) + lifetime,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> int | None:
    """Return the user id inside a valid token, or None if it is invalid or expired."""
    # EAFP: let PyJWT reject bad signatures, expired tokens, and garbage
    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],  # never accept unsigned "none" tokens
            options={"require": ["exp", "sub"]},  # a token without exp would never expire
        )
        return int(payload["sub"])
    except (jwt.InvalidTokenError, ValueError):
        return None


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Return the user who owns the Bearer token, or raise 401."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = decode_access_token(credentials.credentials)
    # A deleted user's token is rejected too, even if it has not expired yet.
    user = db.get(User, user_id) if user_id is not None else None
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user