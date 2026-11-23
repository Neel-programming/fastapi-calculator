"""User registration and login routes."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import DUMMY_HASH, create_access_token, hash_password, verify_password
from app.database import get_db
from app.models import User
from app.schemas import Token, UserCreate, UserLogin, UserRead

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["Users"])


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    responses={400: {"description": "Invalid data, or the username or email is taken"}},
)
def register(user: UserCreate, db: Session = Depends(get_db)):
    """Create an account. The password is stored only as a bcrypt hash."""
    new_user = User(
        username=user.username,
        email=user.email,
        password_hash=hash_password(user.password),
    )
    db.add(new_user)
    # EAFP: let the database enforce uniqueness rather than querying first
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        logger.warning("Duplicate registration attempt for %s", user.username)
        raise HTTPException(status_code=400, detail="Username or email already registered.")
    db.refresh(new_user)
    logger.info("User registered: %s", user.username)
    return new_user


@router.post(
    "/login",
    response_model=Token,
    responses={401: {"description": "Wrong username or password"}},
)
def login(credentials: UserLogin, db: Session = Depends(get_db)):
    """Check the password and return a JWT access token that lasts 30 minutes."""
    user = db.scalar(select(User).where(User.username == credentials.username))

    # Unknown usernames still run a bcrypt check, and both failures get the same
    # message, so an attacker cannot tell which usernames exist.
    stored_hash = user.password_hash if user else DUMMY_HASH
    if not verify_password(credentials.password, stored_hash) or user is None:
        logger.warning("Failed login for %s", credentials.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    logger.info("User logged in: %s", user.username)
    return Token(access_token=create_access_token(user.id))