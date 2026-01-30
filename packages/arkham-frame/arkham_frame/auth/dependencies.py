"""Authentication dependencies."""

import os
import uuid
from typing import AsyncGenerator, Optional

from fastapi import Depends, HTTPException, status
from fastapi_users import FastAPIUsers
from fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
    JWTStrategy,
)
from fastapi_users.db import SQLAlchemyUserDatabase
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from .models import User, UserRole, Base
from .manager import UserManager

# Configuration from environment
SECRET_KEY = os.environ.get("AUTH_SECRET_KEY", "CHANGE-ME-IN-PRODUCTION")
JWT_LIFETIME = int(os.environ.get("JWT_LIFETIME_SECONDS", "28800"))  # default 8 hours
DATABASE_URL = os.environ.get(
    "AUTH_DATABASE_URL",
    os.environ.get("DATABASE_URL", "postgresql+asyncpg://arkham:arkhampass@localhost/arkhamdb")
)

# Ensure async driver
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

# Async engine and session
engine = create_async_engine(DATABASE_URL, echo=False)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


async def create_db_and_tables():
    """Create auth database tables."""
    async with engine.begin() as conn:
        # Create schema if not exists
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS arkham_auth"))
        await conn.run_sync(Base.metadata.create_all)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Get async database session."""
    async with async_session_maker() as session:
        yield session


async def get_user_db(session: AsyncSession = Depends(get_async_session)):
    """Get user database adapter."""
    yield SQLAlchemyUserDatabase(session, User)


async def get_user_manager(user_db=Depends(get_user_db)):
    """Get user manager instance."""
    yield UserManager(user_db)


def get_jwt_strategy() -> JWTStrategy:
    """Create JWT strategy."""
    return JWTStrategy(secret=SECRET_KEY, lifetime_seconds=JWT_LIFETIME)


# Transport and backend
bearer_transport = BearerTransport(tokenUrl="api/auth/jwt/login")

auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)

# FastAPI Users instance
fastapi_users = FastAPIUsers[User, uuid.UUID](get_user_manager, [auth_backend])

# Dependency shortcuts
current_active_user = fastapi_users.current_user(active=True)
current_superuser = fastapi_users.current_user(active=True, superuser=True)
current_optional_user = fastapi_users.current_user(active=True, optional=True)


def require_role(required_role: str):
    """
    Dependency factory for role-based access control.

    Usage:
        @router.get("/admin-only")
        async def admin_endpoint(user: User = Depends(require_role("admin"))):
            ...
    """
    async def check_role(user: User = Depends(current_active_user)) -> User:
        hierarchy = UserRole.get_hierarchy()
        user_level = hierarchy.get(user.role, 0)
        required_level = hierarchy.get(required_role, 0)

        if user_level < required_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{required_role}' required"
            )
        return user

    return check_role


def require_permission(permission: str):
    """
    Dependency factory for permission-based access control.

    Usage:
        @router.post("/documents")
        async def create_doc(user: User = Depends(require_permission("write"))):
            ...
    """
    async def check_permission(user: User = Depends(current_active_user)) -> User:
        if not UserRole.has_permission(user.role, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission '{permission}' required"
            )
        return user

    return check_permission


# Pre-built role requirements
require_admin = require_role(UserRole.ADMIN)
require_analyst = require_role(UserRole.ANALYST)

# Pre-built permission requirements
require_write = require_permission("write")
require_delete = require_permission("delete")
require_manage_users = require_permission("manage_users")
