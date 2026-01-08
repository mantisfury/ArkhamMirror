"""Authentication routes."""

import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from fastapi_users.password import PasswordHelper

from .dependencies import (
    fastapi_users,
    auth_backend,
    current_active_user,
    require_admin,
    get_async_session,
)
from .models import User, Tenant
from .schemas import (
    UserRead,
    UserCreate,
    UserUpdate,
    TenantRead,
    TenantCreate,
    SetupRequest,
    SetupResponse,
)
from .audit import (
    log_audit_event,
    get_audit_events,
    get_audit_stats,
    export_audit_events,
    ensure_audit_schema,
    AuditListResponse,
    AuditStats,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

# Include FastAPI-Users authentication routes (login/logout)
router.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix="/jwt",
)

# Include user management routes (for admins)
router.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate),
    prefix="/users",
)


# --- Current User Endpoints ---

@router.get("/me", response_model=UserRead)
async def get_current_user(user: User = Depends(current_active_user)):
    """Get current authenticated user."""
    return user


@router.get("/me/tenant", response_model=TenantRead)
async def get_current_tenant(user: User = Depends(current_active_user)):
    """Get current user's tenant."""
    return user.tenant


@router.patch("/me", response_model=UserRead)
async def update_current_user(
    update: UserUpdate,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """Update current user's profile (display name only, not role)."""
    if update.display_name is not None:
        user.display_name = update.display_name
    # Don't allow self-role change
    await session.commit()
    await session.refresh(user)
    return user


# --- Setup Endpoints ---

@router.get("/setup-required")
async def check_setup_required(session: AsyncSession = Depends(get_async_session)):
    """Check if initial setup is needed (no tenants exist)."""
    result = await session.execute(select(func.count(Tenant.id)))
    count = result.scalar()
    return {"setup_required": count == 0}


@router.post("/setup", response_model=SetupResponse)
async def initial_setup(
    http_request: Request,
    request: SetupRequest,
    session: AsyncSession = Depends(get_async_session),
):
    """
    Initial setup - creates first tenant and admin user.

    This endpoint only works when no tenants exist yet.
    """
    # Check if setup already completed
    result = await session.execute(select(func.count(Tenant.id)))
    if result.scalar() > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Setup already completed"
        )

    # Check if slug is valid
    existing_slug = await session.execute(
        select(Tenant).where(Tenant.slug == request.tenant_slug)
    )
    if existing_slug.scalar():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tenant slug already exists"
        )

    # Create tenant
    tenant = Tenant(
        name=request.tenant_name,
        slug=request.tenant_slug,
    )
    session.add(tenant)
    await session.flush()  # Get tenant ID

    # Create admin user
    password_helper = PasswordHelper()
    admin = User(
        email=request.admin_email,
        hashed_password=password_helper.hash(request.admin_password),
        tenant_id=tenant.id,
        display_name=request.admin_display_name or "Admin",
        role="admin",
        is_active=True,
        is_superuser=True,
        is_verified=True,
    )
    session.add(admin)

    await session.commit()
    await session.refresh(tenant)

    logger.info(f"Initial setup completed: tenant={tenant.slug}, admin={admin.email}")

    # Ensure audit table exists and log setup
    await ensure_audit_schema(session)
    await log_audit_event(
        session,
        event_type="tenant.created",
        action="create",
        tenant_id=tenant.id,
        user_id=admin.id,
        target_type="tenant",
        target_id=str(tenant.id),
        details={"tenant_name": tenant.name, "tenant_slug": tenant.slug, "admin_email": admin.email},
        ip_address=http_request.client.host if http_request.client else None,
        user_agent=http_request.headers.get("user-agent"),
    )

    return SetupResponse(
        tenant=TenantRead.model_validate(tenant),
        message="Setup complete. Please log in.",
    )


# --- Tenant Management (Admin only) ---

@router.get("/tenants", response_model=List[TenantRead])
async def list_tenants(
    user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_async_session),
):
    """List all tenants (superuser only)."""
    if not user.is_superuser:
        raise HTTPException(status_code=403, detail="Superuser required")

    result = await session.execute(select(Tenant))
    return result.scalars().all()


@router.post("/tenants", response_model=TenantRead)
async def create_tenant(
    data: TenantCreate,
    user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_async_session),
):
    """Create a new tenant (superuser only)."""
    if not user.is_superuser:
        raise HTTPException(status_code=403, detail="Superuser required")

    # Check slug uniqueness
    existing = await session.execute(
        select(Tenant).where(Tenant.slug == data.slug)
    )
    if existing.scalar():
        raise HTTPException(status_code=400, detail="Tenant slug already exists")

    tenant = Tenant(name=data.name, slug=data.slug)
    session.add(tenant)
    await session.commit()
    await session.refresh(tenant)

    return TenantRead.model_validate(tenant)


# --- User Management within Tenant ---

@router.get("/tenant/users", response_model=List[UserRead])
async def list_tenant_users(
    user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_async_session),
):
    """List users in current tenant."""
    result = await session.execute(
        select(User).where(User.tenant_id == user.tenant_id)
    )
    return result.scalars().all()


@router.post("/tenant/users", response_model=UserRead)
async def create_tenant_user(
    request: Request,
    data: UserCreate,
    user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_async_session),
):
    """Create a new user in current tenant."""
    # Check email uniqueness
    existing = await session.execute(
        select(User).where(User.email == data.email)
    )
    if existing.scalar():
        raise HTTPException(status_code=400, detail="Email already registered")

    # Check tenant user limit
    count_result = await session.execute(
        select(func.count(User.id)).where(User.tenant_id == user.tenant_id)
    )
    current_count = count_result.scalar()
    if current_count >= user.tenant.max_users:
        raise HTTPException(status_code=400, detail="Tenant user limit reached")

    # Create user
    password_helper = PasswordHelper()
    new_user = User(
        email=data.email,
        hashed_password=password_helper.hash(data.password),
        tenant_id=user.tenant_id,
        display_name=data.display_name,
        role=data.role if data.role in ["admin", "analyst", "viewer"] else "analyst",
        is_active=True,
        is_verified=True,
    )
    session.add(new_user)
    await session.commit()
    await session.refresh(new_user)

    logger.info(f"User {new_user.email} created in tenant {user.tenant_id}")

    # Audit log
    await log_audit_event(
        session,
        event_type="user.created",
        action="create",
        tenant_id=user.tenant_id,
        user_id=user.id,
        target_type="user",
        target_id=str(new_user.id),
        details={"email": new_user.email, "role": new_user.role},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    return UserRead.model_validate(new_user)


@router.patch("/tenant/users/{user_id}", response_model=UserRead)
async def update_tenant_user(
    request: Request,
    user_id: str,
    data: UserUpdate,
    user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_async_session),
):
    """Update a user in current tenant."""
    import uuid as uuid_mod

    try:
        target_id = uuid_mod.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID")

    result = await session.execute(
        select(User).where(User.id == target_id, User.tenant_id == user.tenant_id)
    )
    target_user = result.scalar()

    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    # Track changes for audit
    changes = {}
    old_role = target_user.role
    old_active = target_user.is_active

    # Update fields
    if data.display_name is not None:
        changes["display_name"] = data.display_name
        target_user.display_name = data.display_name
    if data.role is not None and data.role in ["admin", "analyst", "viewer"]:
        if data.role != old_role:
            changes["role"] = {"from": old_role, "to": data.role}
        target_user.role = data.role
    if data.is_active is not None:
        if data.is_active != old_active:
            changes["is_active"] = {"from": old_active, "to": data.is_active}
        target_user.is_active = data.is_active

    await session.commit()
    await session.refresh(target_user)

    # Audit log - different event types based on what changed
    if "role" in changes:
        await log_audit_event(
            session,
            event_type="user.role.changed",
            action="update",
            tenant_id=user.tenant_id,
            user_id=user.id,
            target_type="user",
            target_id=str(target_user.id),
            details={"email": target_user.email, **changes["role"]},
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )

    if "is_active" in changes:
        event_type = "user.reactivated" if data.is_active else "user.deactivated"
        await log_audit_event(
            session,
            event_type=event_type,
            action="update",
            tenant_id=user.tenant_id,
            user_id=user.id,
            target_type="user",
            target_id=str(target_user.id),
            details={"email": target_user.email},
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )

    if changes and "role" not in changes and "is_active" not in changes:
        await log_audit_event(
            session,
            event_type="user.updated",
            action="update",
            tenant_id=user.tenant_id,
            user_id=user.id,
            target_type="user",
            target_id=str(target_user.id),
            details={"email": target_user.email, "changes": changes},
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )

    return UserRead.model_validate(target_user)


@router.delete("/tenant/users/{user_id}")
async def delete_tenant_user(
    request: Request,
    user_id: str,
    user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_async_session),
):
    """Delete a user from current tenant."""
    import uuid as uuid_mod

    try:
        target_id = uuid_mod.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID")

    # Can't delete yourself
    if target_id == user.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")

    result = await session.execute(
        select(User).where(User.id == target_id, User.tenant_id == user.tenant_id)
    )
    target_user = result.scalar()

    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    # Store info for audit before deletion
    deleted_email = target_user.email
    deleted_id = str(target_user.id)

    await session.delete(target_user)
    await session.commit()

    logger.info(f"User {deleted_email} deleted from tenant {user.tenant_id}")

    # Audit log
    await log_audit_event(
        session,
        event_type="user.deleted",
        action="delete",
        tenant_id=user.tenant_id,
        user_id=user.id,
        target_type="user",
        target_id=deleted_id,
        details={"email": deleted_email},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    return {"status": "deleted", "user_id": user_id}


# --- Audit Logging Endpoints ---

@router.get("/audit", response_model=AuditListResponse)
async def list_audit_events(
    request: Request,
    event_type: Optional[str] = None,
    user_id: Optional[str] = None,
    target_type: Optional[str] = None,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    limit: int = Query(50, le=500),
    offset: int = 0,
    user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_async_session),
):
    """
    List audit events for current tenant.

    Requires admin role. Supports filtering by event type, user, target, and date range.
    """
    import uuid as uuid_mod

    target_user_id = None
    if user_id:
        try:
            target_user_id = uuid_mod.UUID(user_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid user ID format")

    events, total = await get_audit_events(
        session,
        tenant_id=user.tenant_id,
        event_type=event_type,
        user_id=target_user_id,
        target_type=target_type,
        from_date=from_date,
        to_date=to_date,
        limit=limit,
        offset=offset,
    )

    return AuditListResponse(
        events=events,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/audit/stats", response_model=AuditStats)
async def audit_statistics(
    user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_async_session),
):
    """Get audit event statistics for current tenant."""
    return await get_audit_stats(session, user.tenant_id)


@router.get("/audit/export")
async def export_audit(
    format: str = Query("csv", pattern="^(csv|json)$"),
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Export audit events as CSV or JSON.

    Use query parameters to filter by date range.
    """
    content = await export_audit_events(
        session,
        tenant_id=user.tenant_id,
        format=format,
        from_date=from_date,
        to_date=to_date,
    )

    if format == "json":
        return Response(
            content=content,
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=audit_events.json"}
        )

    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit_events.csv"}
    )


@router.get("/audit/event-types")
async def list_event_types(
    user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_async_session),
):
    """Get list of unique event types in audit log."""
    from sqlalchemy import text

    result = await session.execute(
        text("""
            SELECT DISTINCT event_type
            FROM arkham_auth.audit_events
            WHERE tenant_id = :tid
            ORDER BY event_type
        """),
        {"tid": str(user.tenant_id)}
    )

    return {"event_types": [row[0] for row in result.fetchall()]}
