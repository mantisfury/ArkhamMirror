"""Tenant user helpers for use by shards (e.g. projects)."""

from typing import List, Optional
from uuid import UUID

from sqlalchemy import select

from .dependencies import async_session_maker
from .models import User


async def get_tenant_admin_user_ids(tenant_id: Optional[UUID]) -> List[str]:
    """Return user ids for all users with role 'admin' in the given tenant."""
    if not tenant_id:
        return []
    async with async_session_maker() as session:
        result = await session.execute(
            select(User.id).where(
                User.tenant_id == tenant_id,
                User.role == "admin",
            )
        )
        return [str(row[0]) for row in result.all()]
