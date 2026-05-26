import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AlreadyExistsException,
    BadRequestException,
    UnauthorizedException,
)
from app.core.logging import get_logger
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.db.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse

logger = get_logger(__name__)


async def register_user(data: RegisterRequest, db: AsyncSession) -> User:
    """
    Create a new user account.
    Raises AlreadyExistsException if email is taken.
    """
    # Check email isn't already registered
    result = await db.execute(select(User).where(User.email == data.email))
    existing = result.scalar_one_or_none()
    if existing:
        raise AlreadyExistsException("Email")

    user = User(
        full_name=data.full_name,
        email=data.email,
        hashed_password=hash_password(data.password),
        age=data.age,
        health_conditions=data.health_conditions,
    )
    db.add(user)
    await db.flush()   # flush to get the generated ID without committing yet

    logger.info(f"New user registered: {user.email} (id={user.id})")
    return user


async def login_user(data: LoginRequest, db: AsyncSession) -> TokenResponse:
    """
    Authenticate a user and return access + refresh tokens.
    Raises UnauthorizedException on bad credentials.
    """
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()

    # Use the same error for both "user not found" and "wrong password"
    # so attackers can't tell which one it is
    if not user or not verify_password(data.password, user.hashed_password):
        raise UnauthorizedException("Incorrect email or password")

    if not user.is_active:
        raise UnauthorizedException("Account is disabled")

    user_id = str(user.id)
    logger.info(f"User logged in: {user.email}")

    return TokenResponse(
        access_token=create_access_token(user_id),
        refresh_token=create_refresh_token(user_id),
        expires_in=30 * 60,   # 30 minutes in seconds
    )


async def refresh_tokens(refresh_token: str, db: AsyncSession) -> TokenResponse:
    """
    Exchange a valid refresh token for a new access + refresh token pair.
    """
    try:
        user_id = decode_token(refresh_token, expected_type="refresh")
    except ValueError as e:
        raise UnauthorizedException(str(e)) from e

    # Make sure the user still exists and is active
    result = await db.execute(
        select(User).where(User.id == uuid.UUID(user_id))
    )
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise UnauthorizedException("User not found or disabled")

    return TokenResponse(
        access_token=create_access_token(user_id),
        refresh_token=create_refresh_token(user_id),
        expires_in=30 * 60,
    )


async def get_user_by_id(user_id: uuid.UUID, db: AsyncSession) -> User:
    """Fetch a user by their UUID. Raises UnauthorizedException if not found."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise UnauthorizedException("User not found")
    return user
