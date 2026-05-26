from fastapi import HTTPException, status


# ── Auth exceptions ───────────────────────────────────────────────────────────
class UnauthorizedException(HTTPException):
    def __init__(self, detail: str = "Not authenticated"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


class ForbiddenException(HTTPException):
    def __init__(self, detail: str = "You do not have permission to do this"):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


# ── Resource exceptions ───────────────────────────────────────────────────────
class NotFoundException(HTTPException):
    def __init__(self, resource: str = "Resource"):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{resource} not found",
        )


class AlreadyExistsException(HTTPException):
    def __init__(self, resource: str = "Resource"):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{resource} already exists",
        )


# ── Validation exceptions ─────────────────────────────────────────────────────
class BadRequestException(HTTPException):
    def __init__(self, detail: str = "Bad request"):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


# ── AI exceptions ─────────────────────────────────────────────────────────────
class AIProviderException(HTTPException):
    def __init__(self, detail: str = "AI provider error, please try again"):
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=detail,
        )


class SafetyException(HTTPException):
    """Raised when a message is blocked by the safety classifier."""
    def __init__(self, detail: str = "Message blocked for safety reasons"):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
        )


# ── Rate limit ────────────────────────────────────────────────────────────────
class RateLimitException(HTTPException):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests — slow down and try again in a minute",
        )
