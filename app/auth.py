"""Password hashing and verification."""

import bcrypt

# bcrypt truncates input beyond 72 bytes, so reject longer passwords
# rather than silently ignoring the extra characters.
MAX_PASSWORD_BYTES = 72


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