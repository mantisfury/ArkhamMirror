"""
Audit logging service for SHATTERED.

Provides functions to log and query security-relevant events.
"""

import json
import logging
from datetime import datetime
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# --- Pydantic Schemas ---

class AuditEventCreate(BaseModel):
    """Data for creating an audit event."""
    event_type: str
    action: str
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    details: dict = {}


class AuditEventRead(BaseModel):
    """Audit event response model."""
    id: UUID
    tenant_id: Optional[UUID] = None
    user_id: Optional[UUID] = None
    user_email: Optional[str] = None
    event_type: str
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    action: str
    details: dict
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class AuditListResponse(BaseModel):
    """Paginated audit event list."""
    events: List[AuditEventRead]
    total: int
    limit: int
    offset: int


class AuditStats(BaseModel):
    """Audit statistics."""
    total_events: int
    events_today: int
    events_this_week: int
    failed_logins_today: int
    top_event_types: List[dict]
    recent_users: List[dict]


# --- Service Functions ---

async def log_audit_event(
    session: AsyncSession,
    event_type: str,
    action: str,
    tenant_id: Optional[UUID] = None,
    user_id: Optional[UUID] = None,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    details: Optional[dict] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> None:
    """
    Log an audit event to the database.

    Args:
        session: Database session
        event_type: Type of event (e.g., "auth.login.success")
        action: Action performed (e.g., "authenticate", "create", "update")
        tenant_id: Tenant the event belongs to
        user_id: User who performed the action
        target_type: Type of target (e.g., "user", "document")
        target_id: ID of the target resource
        details: Additional context as JSON
        ip_address: Client IP address
        user_agent: Client user agent string
    """
    try:
        await session.execute(
            text("""
                INSERT INTO arkham_auth.audit_events
                (tenant_id, user_id, event_type, target_type, target_id, action, details, ip_address, user_agent)
                VALUES (:tenant_id, :user_id, :event_type, :target_type, :target_id, :action, :details, :ip_address, :user_agent)
            """),
            {
                "tenant_id": str(tenant_id) if tenant_id else None,
                "user_id": str(user_id) if user_id else None,
                "event_type": event_type,
                "target_type": target_type,
                "target_id": target_id,
                "action": action,
                "details": json.dumps(details or {}),
                "ip_address": ip_address,
                "user_agent": user_agent,
            }
        )
        await session.commit()
        logger.debug(f"Audit event logged: {event_type} by user {user_id}")
    except Exception as e:
        logger.error(f"Failed to log audit event: {e}")
        # Don't raise - audit logging should not break main operations


async def get_audit_events(
    session: AsyncSession,
    tenant_id: UUID,
    event_type: Optional[str] = None,
    user_id: Optional[UUID] = None,
    target_type: Optional[str] = None,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[List[AuditEventRead], int]:
    """
    Query audit events with filters.

    Returns:
        Tuple of (events, total_count)
    """
    # Build dynamic WHERE clause
    conditions = ["a.tenant_id = :tenant_id"]
    params = {"tenant_id": str(tenant_id), "limit": limit, "offset": offset}

    if event_type:
        if event_type.endswith("*"):
            # Wildcard match
            conditions.append("a.event_type LIKE :event_type")
            params["event_type"] = event_type.replace("*", "%")
        else:
            conditions.append("a.event_type = :event_type")
            params["event_type"] = event_type

    if user_id:
        conditions.append("a.user_id = :user_id")
        params["user_id"] = str(user_id)

    if target_type:
        conditions.append("a.target_type = :target_type")
        params["target_type"] = target_type

    if from_date:
        conditions.append("a.created_at >= :from_date")
        params["from_date"] = from_date

    if to_date:
        conditions.append("a.created_at <= :to_date")
        params["to_date"] = to_date

    where_clause = " AND ".join(conditions)

    # Get total count
    count_result = await session.execute(
        text(f"SELECT COUNT(*) FROM arkham_auth.audit_events a WHERE {where_clause}"),
        params
    )
    total = count_result.scalar() or 0

    # Get events with user email join
    query = text(f"""
        SELECT
            a.id, a.tenant_id, a.user_id, a.event_type, a.target_type,
            a.target_id, a.action, a.details, a.ip_address, a.user_agent,
            a.created_at, u.email as user_email
        FROM arkham_auth.audit_events a
        LEFT JOIN arkham_auth.users u ON a.user_id = u.id
        WHERE {where_clause}
        ORDER BY a.created_at DESC
        LIMIT :limit OFFSET :offset
    """)

    result = await session.execute(query, params)
    rows = result.fetchall()

    events = []
    for row in rows:
        events.append(AuditEventRead(
            id=row.id,
            tenant_id=row.tenant_id,
            user_id=row.user_id,
            user_email=row.user_email,
            event_type=row.event_type,
            target_type=row.target_type,
            target_id=row.target_id,
            action=row.action,
            details=row.details if isinstance(row.details, dict) else json.loads(row.details or "{}"),
            ip_address=row.ip_address,
            user_agent=row.user_agent,
            created_at=row.created_at,
        ))

    return events, total


async def get_audit_stats(
    session: AsyncSession,
    tenant_id: UUID,
) -> AuditStats:
    """Get audit statistics for a tenant."""

    # Total events
    total_result = await session.execute(
        text("SELECT COUNT(*) FROM arkham_auth.audit_events WHERE tenant_id = :tid"),
        {"tid": str(tenant_id)}
    )
    total_events = total_result.scalar() or 0

    # Events today
    today_result = await session.execute(
        text("""
            SELECT COUNT(*) FROM arkham_auth.audit_events
            WHERE tenant_id = :tid AND created_at >= CURRENT_DATE
        """),
        {"tid": str(tenant_id)}
    )
    events_today = today_result.scalar() or 0

    # Events this week
    week_result = await session.execute(
        text("""
            SELECT COUNT(*) FROM arkham_auth.audit_events
            WHERE tenant_id = :tid AND created_at >= CURRENT_DATE - INTERVAL '7 days'
        """),
        {"tid": str(tenant_id)}
    )
    events_this_week = week_result.scalar() or 0

    # Failed logins today
    failed_result = await session.execute(
        text("""
            SELECT COUNT(*) FROM arkham_auth.audit_events
            WHERE tenant_id = :tid
            AND event_type = 'auth.login.failure'
            AND created_at >= CURRENT_DATE
        """),
        {"tid": str(tenant_id)}
    )
    failed_logins_today = failed_result.scalar() or 0

    # Top event types (last 7 days)
    top_types_result = await session.execute(
        text("""
            SELECT event_type, COUNT(*) as count
            FROM arkham_auth.audit_events
            WHERE tenant_id = :tid AND created_at >= CURRENT_DATE - INTERVAL '7 days'
            GROUP BY event_type
            ORDER BY count DESC
            LIMIT 10
        """),
        {"tid": str(tenant_id)}
    )
    top_event_types = [
        {"event_type": row.event_type, "count": row.count}
        for row in top_types_result.fetchall()
    ]

    # Recent active users
    recent_users_result = await session.execute(
        text("""
            SELECT u.email, COUNT(*) as event_count, MAX(a.created_at) as last_activity
            FROM arkham_auth.audit_events a
            JOIN arkham_auth.users u ON a.user_id = u.id
            WHERE a.tenant_id = :tid AND a.created_at >= CURRENT_DATE - INTERVAL '7 days'
            GROUP BY u.email
            ORDER BY last_activity DESC
            LIMIT 10
        """),
        {"tid": str(tenant_id)}
    )
    recent_users = [
        {"email": row.email, "event_count": row.event_count, "last_activity": row.last_activity.isoformat()}
        for row in recent_users_result.fetchall()
    ]

    return AuditStats(
        total_events=total_events,
        events_today=events_today,
        events_this_week=events_this_week,
        failed_logins_today=failed_logins_today,
        top_event_types=top_event_types,
        recent_users=recent_users,
    )


async def export_audit_events(
    session: AsyncSession,
    tenant_id: UUID,
    format: str = "csv",
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
) -> str:
    """
    Export audit events as CSV or JSON.

    Returns:
        Formatted string (CSV or JSON)
    """
    events, _ = await get_audit_events(
        session,
        tenant_id=tenant_id,
        from_date=from_date,
        to_date=to_date,
        limit=10000,  # Max export size
        offset=0,
    )

    if format == "json":
        return json.dumps(
            [e.model_dump(mode="json") for e in events],
            indent=2,
            default=str
        )

    # CSV format
    import csv
    import io

    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        "Timestamp", "Event Type", "Action", "User Email", "User ID",
        "Target Type", "Target ID", "IP Address", "Details"
    ])

    # Rows
    for event in events:
        writer.writerow([
            event.created_at.isoformat(),
            event.event_type,
            event.action,
            event.user_email or "",
            str(event.user_id) if event.user_id else "",
            event.target_type or "",
            event.target_id or "",
            event.ip_address or "",
            json.dumps(event.details),
        ])

    return output.getvalue()


async def ensure_audit_schema(session: AsyncSession) -> None:
    """Ensure audit table exists (idempotent)."""
    await session.execute(text("""
        CREATE TABLE IF NOT EXISTS arkham_auth.audit_events (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID REFERENCES arkham_auth.tenants(id) ON DELETE CASCADE,
            user_id UUID REFERENCES arkham_auth.users(id) ON DELETE SET NULL,
            event_type VARCHAR(100) NOT NULL,
            target_type VARCHAR(50),
            target_id VARCHAR(255),
            action VARCHAR(50) NOT NULL,
            details JSONB DEFAULT '{}',
            ip_address VARCHAR(45),
            user_agent TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """))

    # Create indexes if not exist
    await session.execute(text("CREATE INDEX IF NOT EXISTS idx_audit_tenant ON arkham_auth.audit_events(tenant_id)"))
    await session.execute(text("CREATE INDEX IF NOT EXISTS idx_audit_user ON arkham_auth.audit_events(user_id)"))
    await session.execute(text("CREATE INDEX IF NOT EXISTS idx_audit_type ON arkham_auth.audit_events(event_type)"))
    await session.execute(text("CREATE INDEX IF NOT EXISTS idx_audit_created ON arkham_auth.audit_events(created_at)"))
    await session.execute(text("CREATE INDEX IF NOT EXISTS idx_audit_target ON arkham_auth.audit_events(target_type, target_id)"))

    await session.commit()
    logger.info("Audit schema verified")
