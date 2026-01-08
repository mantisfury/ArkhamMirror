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
from .audit import (
    log_audit_event,
    get_audit_events,
    get_audit_stats,
    export_audit_events,
    ensure_audit_schema,
    AuditEventCreate,
    AuditEventRead,
    AuditListResponse,
    AuditStats,
)

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
    # Audit
    "log_audit_event",
    "get_audit_events",
    "get_audit_stats",
    "export_audit_events",
    "ensure_audit_schema",
    "AuditEventCreate",
    "AuditEventRead",
    "AuditListResponse",
    "AuditStats",
]
