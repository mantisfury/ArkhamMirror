"""Authentication models."""

from datetime import datetime
from typing import Optional
import uuid

from fastapi_users_db_sqlalchemy import SQLAlchemyBaseUserTableUUID
from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, DeclarativeBase


class Base(DeclarativeBase):
    """Base class for auth models."""
    pass


class Tenant(Base):
    """Tenant/Organization for multi-tenancy."""
    __tablename__ = "tenants"
    __table_args__ = {"schema": "arkham_auth"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    max_users = Column(Integer, default=100)
    max_documents = Column(Integer, default=10000)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    settings = Column(Text, default="{}")

    users = relationship("User", back_populates="tenant")


class User(SQLAlchemyBaseUserTableUUID, Base):
    """User model with tenant association."""
    __tablename__ = "users"
    __table_args__ = {"schema": "arkham_auth"}

    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("arkham_auth.tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tenant = relationship("Tenant", back_populates="users")

    display_name = Column(String(255), nullable=True)
    role = Column(String(50), default="analyst", nullable=False)  # admin, analyst, viewer
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)


class UserRole:
    """Role constants and permissions."""
    ADMIN = "admin"
    ANALYST = "analyst"
    VIEWER = "viewer"

    PERMISSIONS = {
        "admin": ["read", "write", "delete", "admin", "manage_users"],
        "analyst": ["read", "write", "delete"],
        "viewer": ["read"],
    }

    @classmethod
    def has_permission(cls, role: str, permission: str) -> bool:
        """Check if a role has a specific permission."""
        return permission in cls.PERMISSIONS.get(role, [])

    @classmethod
    def get_hierarchy(cls) -> dict:
        """Get role hierarchy values (higher = more permissions)."""
        return {cls.VIEWER: 0, cls.ANALYST: 1, cls.ADMIN: 2}
