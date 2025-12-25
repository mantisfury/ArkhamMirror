"""
Notification API endpoints.

Provides REST API for sending notifications and managing channels.
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional

router = APIRouter()


class SendNotificationRequest(BaseModel):
    """Request body for sending a notification."""
    title: str = Field(..., description="Notification title")
    message: str = Field(..., description="Notification message")
    recipient: str = Field(..., description="Recipient identifier")
    channel: str = Field("log", description="Notification channel name")
    type: str = Field("info", description="Notification type: info, success, warning, error, alert")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class BatchNotificationRequest(BaseModel):
    """Request body for batch notifications."""
    notifications: List[Dict[str, Any]] = Field(..., description="List of notifications")
    default_channel: str = Field("log", description="Default channel if not specified")


class ConfigureEmailRequest(BaseModel):
    """Request body for configuring email channel."""
    name: str = Field(..., description="Channel name")
    smtp_host: str = Field(..., description="SMTP server hostname")
    smtp_port: int = Field(587, description="SMTP server port")
    username: Optional[str] = Field(None, description="SMTP username")
    password: Optional[str] = Field(None, description="SMTP password")
    from_address: str = Field("noreply@arkham.local", description="Sender email address")
    from_name: str = Field("ArkhamMirror", description="Sender name")
    use_tls: bool = Field(True, description="Use TLS")


class ConfigureWebhookRequest(BaseModel):
    """Request body for configuring webhook channel."""
    name: str = Field(..., description="Channel name")
    url: str = Field(..., description="Webhook URL")
    method: str = Field("POST", description="HTTP method")
    headers: Optional[Dict[str, str]] = Field(None, description="Custom headers")
    auth_token: Optional[str] = Field(None, description="Bearer token")
    verify_ssl: bool = Field(True, description="Verify SSL certificates")


@router.get("/channels")
async def list_channels() -> Dict[str, Any]:
    """List configured notification channels."""
    from ..main import get_frame

    frame = get_frame()
    notification_service = frame.get_service("notifications")

    if not notification_service:
        raise HTTPException(status_code=503, detail="Notification service not available")

    channels = notification_service.list_channels()

    return {
        "channels": channels,
        "count": len(channels),
    }


@router.post("/channels/email")
async def configure_email_channel(request: ConfigureEmailRequest) -> Dict[str, Any]:
    """Configure an email notification channel."""
    from ..main import get_frame
    from ..services.notifications import ConfigurationError

    frame = get_frame()
    notification_service = frame.get_service("notifications")

    if not notification_service:
        raise HTTPException(status_code=503, detail="Notification service not available")

    try:
        notification_service.configure_email(
            name=request.name,
            smtp_host=request.smtp_host,
            smtp_port=request.smtp_port,
            username=request.username,
            password=request.password,
            from_address=request.from_address,
            from_name=request.from_name,
            use_tls=request.use_tls,
        )

        return {
            "channel": request.name,
            "type": "email",
            "configured": True,
        }

    except ConfigurationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/channels/webhook")
async def configure_webhook_channel(request: ConfigureWebhookRequest) -> Dict[str, Any]:
    """Configure a webhook notification channel."""
    from ..main import get_frame
    from ..services.notifications import ConfigurationError

    frame = get_frame()
    notification_service = frame.get_service("notifications")

    if not notification_service:
        raise HTTPException(status_code=503, detail="Notification service not available")

    try:
        notification_service.configure_webhook(
            name=request.name,
            url=request.url,
            method=request.method,
            headers=request.headers,
            auth_token=request.auth_token,
            verify_ssl=request.verify_ssl,
        )

        return {
            "channel": request.name,
            "type": "webhook",
            "configured": True,
        }

    except ConfigurationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/channels/{name}")
async def remove_channel(name: str) -> Dict[str, Any]:
    """Remove a notification channel."""
    from ..main import get_frame

    frame = get_frame()
    notification_service = frame.get_service("notifications")

    if not notification_service:
        raise HTTPException(status_code=503, detail="Notification service not available")

    if not notification_service.remove_channel(name):
        raise HTTPException(status_code=404, detail=f"Channel '{name}' not found")

    return {"removed": name}


@router.post("/send")
async def send_notification(request: SendNotificationRequest) -> Dict[str, Any]:
    """Send a notification."""
    from ..main import get_frame
    from ..services.notifications import (
        NotificationType,
        ChannelNotFoundError,
        DeliveryError,
    )

    frame = get_frame()
    notification_service = frame.get_service("notifications")

    if not notification_service:
        raise HTTPException(status_code=503, detail="Notification service not available")

    try:
        notification_type = NotificationType(request.type.lower())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid notification type: {request.type}",
        )

    try:
        notification = await notification_service.send(
            title=request.title,
            message=request.message,
            recipient=request.recipient,
            channel=request.channel,
            type=notification_type,
            metadata=request.metadata,
        )

        return {
            "id": notification.id,
            "status": notification.status.value,
            "channel": notification.channel.value,
            "sent_at": notification.sent_at.isoformat() if notification.sent_at else None,
        }

    except ChannelNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except DeliveryError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/send/batch")
async def send_batch_notifications(request: BatchNotificationRequest) -> Dict[str, Any]:
    """Send multiple notifications."""
    from ..main import get_frame

    frame = get_frame()
    notification_service = frame.get_service("notifications")

    if not notification_service:
        raise HTTPException(status_code=503, detail="Notification service not available")

    results = await notification_service.send_batch(
        notifications=request.notifications,
        channel=request.default_channel,
    )

    return {
        "sent": len([r for r in results if r.status.value == "sent"]),
        "failed": len([r for r in results if r.status.value == "failed"]),
        "total": len(results),
        "notifications": [
            {
                "id": r.id,
                "status": r.status.value,
            }
            for r in results
        ],
    }


@router.get("/history")
async def get_notification_history(
    limit: int = Query(100, le=1000),
    status: Optional[str] = Query(None, description="Filter by status"),
    type: Optional[str] = Query(None, description="Filter by type"),
) -> Dict[str, Any]:
    """Get notification history."""
    from ..main import get_frame
    from ..services.notifications import DeliveryStatus, NotificationType

    frame = get_frame()
    notification_service = frame.get_service("notifications")

    if not notification_service:
        raise HTTPException(status_code=503, detail="Notification service not available")

    filter_status = None
    filter_type = None

    if status:
        try:
            filter_status = DeliveryStatus(status.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    if type:
        try:
            filter_type = NotificationType(type.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid type: {type}")

    history = notification_service.get_history(
        limit=limit,
        status=filter_status,
        type=filter_type,
    )

    return {
        "history": [
            {
                "id": n.id,
                "type": n.type.value,
                "title": n.title,
                "recipient": n.recipient,
                "channel": n.channel.value,
                "status": n.status.value,
                "created_at": n.created_at.isoformat(),
                "sent_at": n.sent_at.isoformat() if n.sent_at else None,
            }
            for n in history
        ],
        "count": len(history),
    }


@router.get("/stats")
async def get_notification_stats() -> Dict[str, Any]:
    """Get notification statistics."""
    from ..main import get_frame

    frame = get_frame()
    notification_service = frame.get_service("notifications")

    if not notification_service:
        raise HTTPException(status_code=503, detail="Notification service not available")

    return notification_service.get_stats()
