"""Authentication routes."""

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
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

    return UserRead.model_validate(new_user)


@router.patch("/tenant/users/{user_id}", response_model=UserRead)
async def update_tenant_user(
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

    # Update fields
    if data.display_name is not None:
        target_user.display_name = data.display_name
    if data.role is not None and data.role in ["admin", "analyst", "viewer"]:
        target_user.role = data.role
    if data.is_active is not None:
        target_user.is_active = data.is_active

    await session.commit()
    await session.refresh(target_user)

    return UserRead.model_validate(target_user)


@router.delete("/tenant/users/{user_id}")
async def delete_tenant_user(
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

    await session.delete(target_user)
    await session.commit()

    logger.info(f"User {target_user.email} deleted from tenant {user.tenant_id}")

    return {"status": "deleted", "user_id": user_id}
