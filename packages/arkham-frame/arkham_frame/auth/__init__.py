"""Authentication module for ArkhamFrame."""

from .dependencies import (
    current_active_user,
    current_superuser,
    current_optional_user,
    require_role,
    require_permission,
    require_admin,
    require_analyst,
    require_write,
    require_delete,
    require_manage_users,
    get_async_session,
    create_db_and_tables,
)
from .models import User, Tenant, UserRole
from .schemas import UserRead, UserCreate, UserUpdate, TenantRead, TenantCreate
from .router import router as auth_router

__all__ = [
    # Dependencies
    "current_active_user",
    "current_superuser",
    "current_optional_user",
    "require_role",
    "require_permission",
    "require_admin",
    "require_analyst",
    "require_write",
    "require_delete",
    "require_manage_users",
    "get_async_session",
    "create_db_and_tables",
    # Models
    "User",
    "Tenant",
    "UserRole",
    # Schemas
    "UserRead",
    "UserCreate",
    "UserUpdate",
    "TenantRead",
    "TenantCreate",
    # Router
    "auth_router",
]
