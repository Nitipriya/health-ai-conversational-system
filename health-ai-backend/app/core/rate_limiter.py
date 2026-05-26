from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import get_settings

settings = get_settings()


def get_user_identifier(request: Request) -> str:
    """
    Use the authenticated user's ID as the rate limit key if available,
    otherwise fall back to IP address.

    This means:
    - Logged-in users: limited by their user ID (fair per-user limiting)
    - Unauthenticated requests: limited by IP (protects login/register endpoints)
    """
    user = getattr(request.state, "user", None)
    if user:
        return str(user.id)
    return get_remote_address(request)


# The limiter instance — attach this to the FastAPI app in main.py
limiter = Limiter(key_func=get_user_identifier)

# Reusable limit string built from settings
# e.g. "30/minute"
default_limit = f"{settings.rate_limit_per_minute}/minute"
