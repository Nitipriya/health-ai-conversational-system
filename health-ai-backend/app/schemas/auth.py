import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator


# ── Register ──────────────────────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)
    age: int | None = Field(None, ge=1, le=120)
    health_conditions: str | None = Field(
        None,
        description="Comma-separated e.g. 'diabetes, hypertension'",
    )

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one number")
        return v


class RegisterResponse(BaseModel):
    id: uuid.UUID
    full_name: str
    email: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Login ─────────────────────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int          # seconds until access token expires


# ── Refresh ───────────────────────────────────────────────────────────────────
class RefreshRequest(BaseModel):
    refresh_token: str


# ── Current user ──────────────────────────────────────────────────────────────
class UserResponse(BaseModel):
    id: uuid.UUID
    full_name: str
    email: str
    age: int | None
    health_conditions: str | None
    is_active: bool
    is_verified: bool
    created_at: datetime

    model_config = {"from_attributes": True}
