"""Pydantic request/response models for the auth module."""

import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------

_PASSWORD_PATTERN = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,}$")


def _validate_password(v: str) -> str:
    if not _PASSWORD_PATTERN.match(v):
        raise ValueError(
            "Password must be at least 8 characters with uppercase, lowercase, and digit"
        )
    return v


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return _validate_password(v)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    """Body is optional — refresh token comes from httpOnly cookie."""
    pass


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return _validate_password(v)


class VerifyEmailRequest(BaseModel):
    token: str


class CreateApiKeyRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    scopes: list[str] = Field(default_factory=list)
    rate_limit: int = Field(default=100, ge=1, le=10000)


class M2MTokenRequest(BaseModel):
    client_id: str
    client_secret: str


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    csrf_token: str | None = None


class UserResponse(BaseModel):
    id: UUID
    email: str
    first_name: str | None
    last_name: str | None
    role: str
    is_verified: bool
    permissions: list[str] = Field(default_factory=list)
    created_at: datetime


class SessionResponse(BaseModel):
    session_id: UUID
    device: str | None
    ip_address: str | None
    created_at: datetime


class UserContextResponse(BaseModel):
    user: UserResponse
    session: SessionResponse | None = None
    active_sessions_count: int
    auth_type: str = "jwt"


class ApiKeyResponse(BaseModel):
    id: UUID
    name: str
    scopes: list[str]
    rate_limit: int
    is_active: bool
    last_used_at: datetime | None
    created_at: datetime


class ApiKeyCreatedResponse(ApiKeyResponse):
    raw_key: str  # only returned once on creation


class MessageResponse(BaseModel):
    message: str


class ErrorResponse(BaseModel):
    error: str
    message: str
    details: dict | list | None = None
