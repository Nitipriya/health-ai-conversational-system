from datetime import datetime, timedelta, timezone
from typing import Literal

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

settings = get_settings()

# ── Password hashing ──────────────────────────────────────────────────────────
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    """Hash a plain password using bcrypt."""
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Check a plain password against its bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)


# ── JWT ───────────────────────────────────────────────────────────────────────
def _create_token(
    subject: str,
    token_type: Literal["access", "refresh"],
    expires_delta: timedelta,
) -> str:
    """
    Internal helper — builds a signed JWT.

    Payload fields:
      sub  → user UUID (as string)
      type → "access" or "refresh"
      exp  → expiry timestamp
      iat  → issued-at timestamp
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: str) -> str:
    """Create a short-lived access token (default 30 min)."""
    return _create_token(
        subject=user_id,
        token_type="access",
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )


def create_refresh_token(user_id: str) -> str:
    """Create a long-lived refresh token (default 7 days)."""
    return _create_token(
        subject=user_id,
        token_type="refresh",
        expires_delta=timedelta(days=settings.refresh_token_expire_days),
    )


def decode_token(token: str, expected_type: Literal["access", "refresh"]) -> str:
    """
    Decode and validate a JWT.

    Returns the user_id (sub) if valid.
    Raises ValueError with a clear message if anything is wrong.
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError as e:
        raise ValueError(f"Invalid token: {e}") from e

    # Check token type matches what we expect
    if payload.get("type") != expected_type:
        raise ValueError(f"Expected {expected_type} token, got {payload.get('type')}")

    user_id: str | None = payload.get("sub")
    if not user_id:
        raise ValueError("Token is missing subject (user id)")

    return user_id
