import uuid

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import UnauthorizedException
from app.core.security import decode_token
from app.db.models.user import User
from app.db.session import get_db
from app.services.auth_service import get_user_by_id

# Extracts the Bearer token from the Authorization header automatically
bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Dependency that protects any route requiring authentication.

    Usage in a route:
        async def my_route(current_user: User = Depends(get_current_user)):
            ...

    What it does:
    1. Reads the Authorization: Bearer <token> header
    2. Decodes and validates the JWT
    3. Loads the user from DB
    4. Returns the User object — or raises 401 if anything fails
    """
    if not credentials:
        raise UnauthorizedException("No authorization token provided")

    try:
        user_id = decode_token(credentials.credentials, expected_type="access")
    except ValueError as e:
        raise UnauthorizedException(str(e)) from e

    user = await get_user_by_id(uuid.UUID(user_id), db)

    if not user.is_active:
        raise UnauthorizedException("Account is disabled")

    return user
