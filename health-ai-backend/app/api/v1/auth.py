from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.rate_limiter import limiter
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
    UserResponse,
)
from app.services.auth_service import login_user, refresh_tokens, register_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=RegisterResponse, status_code=201)
@limiter.limit("5/minute")   # strict limit — prevent spam account creation
async def register(
    request: Request,           # required by slowapi for rate limiting
    data: RegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new user account.

    - Email must be unique
    - Password needs 1 uppercase + 1 number + min 8 chars
    """
    user = await register_user(data, db)
    return user


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")  # prevent brute force
async def login(
    request: Request,
    data: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Login with email + password.
    Returns an access token (30 min) and a refresh token (7 days).
    """
    return await login_user(data, db)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    data: RefreshRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Exchange a refresh token for a new token pair.
    Use this when the access token expires instead of logging in again.
    """
    return await refresh_tokens(data.refresh_token, db)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """
    Get the currently logged-in user's profile.
    Requires a valid access token in the Authorization header.
    """
    return current_user
