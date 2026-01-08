"""Authentication schemas."""

from datetime import datetime
from typing import Optional
import uuid

from fastapi_users import schemas
from pydantic import BaseModel, Field


class UserRead(schemas.BaseUser[uuid.UUID]):
    """User read schema."""
    tenant_id: uuid.UUID
    display_name: Optional[str] = None
    role: str = "analyst"
    created_at: datetime
    last_login: Optional[datetime] = None


class UserCreate(schemas.BaseUserCreate):
    """User create schema."""
    display_name: Optional[str] = None
    role: str = "analyst"
    tenant_id: Optional[uuid.UUID] = None  # Set by system for tenant-scoped registration


class UserUpdate(schemas.BaseUserUpdate):
    """User update schema."""
    display_name: Optional[str] = None
    role: Optional[str] = None


class TenantRead(BaseModel):
    """Tenant read schema."""
    id: uuid.UUID
    name: str
    slug: str
    is_active: bool
    max_users: int
    max_documents: int
    created_at: datetime

    class Config:
        from_attributes = True


class TenantCreate(BaseModel):
    """Tenant create schema."""
    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")


class SetupRequest(BaseModel):
    """Initial setup request - creates first tenant and admin."""
    tenant_name: str = Field(..., min_length=1, max_length=255)
    tenant_slug: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")
    admin_email: str = Field(..., min_length=5)
    admin_password: str = Field(..., min_length=8)
    admin_display_name: Optional[str] = None


class SetupResponse(BaseModel):
    """Setup response."""
    tenant: TenantRead
    message: str = "Setup complete. Please log in."


class LoginRequest(BaseModel):
    """Login request schema."""
    username: str  # email
    password: str


class TokenResponse(BaseModel):
    """Token response schema."""
    access_token: str
    token_type: str = "bearer"
