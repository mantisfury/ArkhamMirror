"""
Notification Service - Email and webhook notifications.

Provides notification capabilities for system events,
alerts, and user communications.
"""

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Try to import optional dependencies
try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False
    logger.warning("aiohttp not installed - webhook notifications disabled")

try:
    import aiosmtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    SMTP_AVAILABLE = True
except ImportError:
    SMTP_AVAILABLE = False
    logger.warning("aiosmtplib not installed - email notifications disabled")


# ============================================
# Exceptions
# ============================================

class NotificationError(Exception):
    """Base exception for notification errors."""
    pass


class DeliveryError(NotificationError):
    """Failed to deliver notification."""
    pass


class ConfigurationError(NotificationError):
    """Invalid notification configuration."""
    pass


class ChannelNotFoundError(NotificationError):
    """Notification channel not found."""
    pass


# ============================================
# Enums and Types
# ============================================

class NotificationType(str, Enum):
    """Types of notifications."""
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    ALERT = "alert"


class ChannelType(str, Enum):
    """Notification channel types."""
    EMAIL = "email"
    WEBHOOK = "webhook"
    LOG = "log"


class DeliveryStatus(str, Enum):
    """Notification delivery status."""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRYING = "retrying"


@dataclass
class Notification:
    """A notification to be sent."""
    id: str
    type: NotificationType
    title: str
    message: str
    recipient: str
    channel: ChannelType
    created_at: datetime = field(default_factory=datetime.utcnow)
    sent_at: Optional[datetime] = None
    status: DeliveryStatus = DeliveryStatus.PENDING
    metadata: Dict[str, Any] = field(default_factory=dict)
    retry_count: int = 0
    max_retries: int = 3


@dataclass
class ChannelConfig:
    """Configuration for a notification channel."""
    name: str
    type: ChannelType
    enabled: bool = True
    config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EmailConfig:
    """Email channel configuration."""
    smtp_host: str
    smtp_port: int = 587
    username: Optional[str] = None
    password: Optional[str] = None
    from_address: str = "noreply@arkham.local"
    from_name: str = "ArkhamMirror"
    use_tls: bool = True
    timeout: int = 30


@dataclass
class WebhookConfig:
    """Webhook channel configuration."""
    url: str
    method: str = "POST"
    headers: Dict[str, str] = field(default_factory=dict)
    auth_token: Optional[str] = None
    timeout: int = 30
    verify_ssl: bool = True


# ============================================
# Channel Handlers
# ============================================

class NotificationChannel(ABC):
    """Abstract base class for notification channels."""

    @property
    @abstractmethod
    def channel_type(self) -> ChannelType:
        """Return the channel type."""
        pass

    @abstractmethod
    async def send(self, notification: Notification) -> bool:
        """
        Send a notification through this channel.

        Args:
            notification: Notification to send

        Returns:
            True if sent successfully

        Raises:
            DeliveryError: If delivery fails
        """
        pass


class LogChannel(NotificationChannel):
    """Log notifications to the application log."""

    @property
    def channel_type(self) -> ChannelType:
        return ChannelType.LOG

    async def send(self, notification: Notification) -> bool:
        """Log the notification."""
        log_level = {
            NotificationType.INFO: logging.INFO,
            NotificationType.SUCCESS: logging.INFO,
            NotificationType.WARNING: logging.WARNING,
            NotificationType.ERROR: logging.ERROR,
            NotificationType.ALERT: logging.CRITICAL,
        }.get(notification.type, logging.INFO)

        logger.log(
            log_level,
            f"[NOTIFICATION] {notification.title}: {notification.message} "
            f"(recipient: {notification.recipient})"
        )
        return True


class EmailChannel(NotificationChannel):
    """Send notifications via email."""

    def __init__(self, config: EmailConfig):
        self.config = config

    @property
    def channel_type(self) -> ChannelType:
        return ChannelType.EMAIL

    async def send(self, notification: Notification) -> bool:
        """Send email notification."""
        if not SMTP_AVAILABLE:
            raise DeliveryError("aiosmtplib not installed")

        try:
            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = notification.title
            msg["From"] = f"{self.config.from_name} <{self.config.from_address}>"
            msg["To"] = notification.recipient

            # Add plain text and HTML versions
            text_part = MIMEText(notification.message, "plain")
            html_part = MIMEText(self._to_html(notification), "html")

            msg.attach(text_part)
            msg.attach(html_part)

            # Send email
            await aiosmtplib.send(
                msg,
                hostname=self.config.smtp_host,
                port=self.config.smtp_port,
                username=self.config.username,
                password=self.config.password,
                start_tls=self.config.use_tls,
                timeout=self.config.timeout,
            )

            logger.info(f"Email sent to {notification.recipient}")
            return True

        except Exception as e:
            logger.error(f"Email delivery failed: {e}")
            raise DeliveryError(f"Failed to send email: {e}") from e

    def _to_html(self, notification: Notification) -> str:
        """Convert notification to HTML email."""
        color = {
            NotificationType.INFO: "#17a2b8",
            NotificationType.SUCCESS: "#28a745",
            NotificationType.WARNING: "#ffc107",
            NotificationType.ERROR: "#dc3545",
            NotificationType.ALERT: "#dc3545",
        }.get(notification.type, "#6c757d")

        return f"""
        <html>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <div style="border-left: 4px solid {color}; padding-left: 20px;">
                <h2 style="color: {color}; margin-top: 0;">{notification.title}</h2>
                <p>{notification.message}</p>
                <hr style="border: none; border-top: 1px solid #eee;">
                <p style="color: #666; font-size: 12px;">
                    Sent by ArkhamMirror at {notification.created_at.strftime("%Y-%m-%d %H:%M:%S")}
                </p>
            </div>
        </body>
        </html>
        """


class WebhookChannel(NotificationChannel):
    """Send notifications via webhook."""

    def __init__(self, config: WebhookConfig):
        self.config = config

    @property
    def channel_type(self) -> ChannelType:
        return ChannelType.WEBHOOK

    async def send(self, notification: Notification) -> bool:
        """Send webhook notification."""
        if not AIOHTTP_AVAILABLE:
            raise DeliveryError("aiohttp not installed")

        try:
            # Prepare headers
            headers = {
                "Content-Type": "application/json",
                **self.config.headers,
            }
            if self.config.auth_token:
                headers["Authorization"] = f"Bearer {self.config.auth_token}"

            # Prepare payload
            payload = {
                "id": notification.id,
                "type": notification.type.value,
                "title": notification.title,
                "message": notification.message,
                "recipient": notification.recipient,
                "timestamp": notification.created_at.isoformat(),
                "metadata": notification.metadata,
            }

            # Send request
            timeout = aiohttp.ClientTimeout(total=self.config.timeout)
            connector = aiohttp.TCPConnector(ssl=self.config.verify_ssl)

            async with aiohttp.ClientSession(
                timeout=timeout,
                connector=connector,
            ) as session:
                method = getattr(session, self.config.method.lower())
                async with method(
                    self.config.url,
                    json=payload,
                    headers=headers,
                ) as response:
                    if response.status >= 400:
                        text = await response.text()
                        raise DeliveryError(
                            f"Webhook returned {response.status}: {text}"
                        )

            logger.info(f"Webhook sent to {self.config.url}")
            return True

        except aiohttp.ClientError as e:
            logger.error(f"Webhook delivery failed: {e}")
            raise DeliveryError(f"Failed to send webhook: {e}") from e


# ============================================
# Notification Service
# ============================================

class NotificationService:
    """
    Service for sending notifications.

    Provides:
    - Multi-channel notifications (email, webhook, log)
    - Event-driven notifications
    - Retry logic for failed deliveries
    - Notification history
    """

    def __init__(
        self,
        event_bus=None,
        template_service=None,
        max_history: int = 1000,
    ):
        """
        Initialize the notification service.

        Args:
            event_bus: Optional event bus for event-driven notifications
            template_service: Optional template service for message formatting
            max_history: Maximum notifications to keep in history
        """
        self._event_bus = event_bus
        self._templates = template_service
        self._max_history = max_history

        self._channels: Dict[str, NotificationChannel] = {
            "log": LogChannel(),
        }
        self._history: List[Notification] = []
        self._notification_counter = 0

        # Subscriptions for event-driven notifications
        self._event_subscriptions: Dict[str, List[Dict]] = {}

        logger.info("NotificationService initialized")

    def configure_email(
        self,
        name: str,
        smtp_host: str,
        smtp_port: int = 587,
        username: Optional[str] = None,
        password: Optional[str] = None,
        from_address: str = "noreply@arkham.local",
        from_name: str = "ArkhamMirror",
        use_tls: bool = True,
    ) -> None:
        """
        Configure an email channel.

        Args:
            name: Channel name
            smtp_host: SMTP server hostname
            smtp_port: SMTP server port
            username: SMTP username
            password: SMTP password
            from_address: Sender email address
            from_name: Sender name
            use_tls: Use TLS for connection
        """
        if not SMTP_AVAILABLE:
            raise ConfigurationError("aiosmtplib not installed")

        config = EmailConfig(
            smtp_host=smtp_host,
            smtp_port=smtp_port,
            username=username,
            password=password,
            from_address=from_address,
            from_name=from_name,
            use_tls=use_tls,
        )
        self._channels[name] = EmailChannel(config)
        logger.info(f"Configured email channel: {name}")

    def configure_webhook(
        self,
        name: str,
        url: str,
        method: str = "POST",
        headers: Optional[Dict[str, str]] = None,
        auth_token: Optional[str] = None,
        verify_ssl: bool = True,
    ) -> None:
        """
        Configure a webhook channel.

        Args:
            name: Channel name
            url: Webhook URL
            method: HTTP method (POST, PUT, etc.)
            headers: Custom headers
            auth_token: Bearer token for authentication
            verify_ssl: Verify SSL certificates
        """
        if not AIOHTTP_AVAILABLE:
            raise ConfigurationError("aiohttp not installed")

        # Validate URL
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            raise ConfigurationError(f"Invalid webhook URL: {url}")

        config = WebhookConfig(
            url=url,
            method=method,
            headers=headers or {},
            auth_token=auth_token,
            verify_ssl=verify_ssl,
        )
        self._channels[name] = WebhookChannel(config)
        logger.info(f"Configured webhook channel: {name}")

    def list_channels(self) -> List[str]:
        """List all configured channels."""
        return list(self._channels.keys())

    def remove_channel(self, name: str) -> bool:
        """
        Remove a notification channel.

        Args:
            name: Channel name

        Returns:
            True if removed, False if not found
        """
        if name == "log":
            logger.warning("Cannot remove default log channel")
            return False

        if name in self._channels:
            del self._channels[name]
            logger.info(f"Removed channel: {name}")
            return True
        return False

    async def send(
        self,
        title: str,
        message: str,
        recipient: str,
        channel: str = "log",
        type: NotificationType = NotificationType.INFO,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Notification:
        """
        Send a notification.

        Args:
            title: Notification title
            message: Notification message
            recipient: Recipient (email address, webhook name, etc.)
            channel: Channel name to use
            type: Notification type
            metadata: Additional metadata

        Returns:
            Notification object with delivery status

        Raises:
            ChannelNotFoundError: If channel not configured
            DeliveryError: If delivery fails after retries
        """
        if channel not in self._channels:
            raise ChannelNotFoundError(f"Channel not found: {channel}")

        # Create notification
        self._notification_counter += 1
        notification = Notification(
            id=f"notif-{self._notification_counter:06d}",
            type=type,
            title=title,
            message=message,
            recipient=recipient,
            channel=self._channels[channel].channel_type,
            metadata=metadata or {},
        )

        # Attempt delivery with retries
        channel_handler = self._channels[channel]

        while notification.retry_count <= notification.max_retries:
            try:
                await channel_handler.send(notification)
                notification.status = DeliveryStatus.SENT
                notification.sent_at = datetime.utcnow()
                break
            except DeliveryError as e:
                notification.retry_count += 1
                if notification.retry_count > notification.max_retries:
                    notification.status = DeliveryStatus.FAILED
                    notification.metadata["error"] = str(e)
                    logger.error(f"Notification failed after {notification.max_retries} retries: {e}")
                else:
                    notification.status = DeliveryStatus.RETRYING
                    logger.warning(f"Notification delivery failed, retry {notification.retry_count}")
                    await asyncio.sleep(2 ** notification.retry_count)  # Exponential backoff

        # Add to history
        self._history.append(notification)
        if len(self._history) > self._max_history:
            self._history.pop(0)

        # Publish event if event bus available
        if self._event_bus:
            await self._event_bus.publish(
                "notification.sent",
                {
                    "id": notification.id,
                    "type": notification.type.value,
                    "status": notification.status.value,
                    "channel": channel,
                }
            )

        return notification

    async def send_batch(
        self,
        notifications: List[Dict[str, Any]],
        channel: str = "log",
    ) -> List[Notification]:
        """
        Send multiple notifications.

        Args:
            notifications: List of notification dicts (title, message, recipient, etc.)
            channel: Default channel if not specified per notification

        Returns:
            List of Notification objects
        """
        results = []

        for notif_data in notifications:
            try:
                result = await self.send(
                    title=notif_data["title"],
                    message=notif_data["message"],
                    recipient=notif_data.get("recipient", "system"),
                    channel=notif_data.get("channel", channel),
                    type=NotificationType(notif_data.get("type", "info")),
                    metadata=notif_data.get("metadata"),
                )
                results.append(result)
            except Exception as e:
                logger.error(f"Batch notification failed: {e}")

        return results

    def subscribe_to_event(
        self,
        event_pattern: str,
        channel: str,
        recipient: str,
        title_template: str = "{{ event_name }}",
        message_template: str = "{{ event_data }}",
        type: NotificationType = NotificationType.INFO,
    ) -> None:
        """
        Subscribe to events for automatic notifications.

        Args:
            event_pattern: Event name pattern (e.g., "document.*")
            channel: Channel to send notifications to
            recipient: Recipient for notifications
            title_template: Template for notification title
            message_template: Template for notification message
            type: Notification type
        """
        subscription = {
            "channel": channel,
            "recipient": recipient,
            "title_template": title_template,
            "message_template": message_template,
            "type": type,
        }

        if event_pattern not in self._event_subscriptions:
            self._event_subscriptions[event_pattern] = []

        self._event_subscriptions[event_pattern].append(subscription)
        logger.info(f"Added notification subscription for: {event_pattern}")

    def get_history(
        self,
        limit: int = 100,
        status: Optional[DeliveryStatus] = None,
        type: Optional[NotificationType] = None,
    ) -> List[Notification]:
        """
        Get notification history.

        Args:
            limit: Maximum entries to return
            status: Filter by delivery status
            type: Filter by notification type

        Returns:
            List of Notification objects
        """
        result = self._history

        if status:
            result = [n for n in result if n.status == status]

        if type:
            result = [n for n in result if n.type == type]

        return result[-limit:]

    def clear_history(self) -> None:
        """Clear notification history."""
        self._history = []

    def get_stats(self) -> Dict[str, Any]:
        """Get notification statistics."""
        by_status = {}
        by_type = {}
        by_channel = {}

        for notif in self._history:
            by_status[notif.status.value] = by_status.get(notif.status.value, 0) + 1
            by_type[notif.type.value] = by_type.get(notif.type.value, 0) + 1
            by_channel[notif.channel.value] = by_channel.get(notif.channel.value, 0) + 1

        return {
            "total": len(self._history),
            "by_status": by_status,
            "by_type": by_type,
            "by_channel": by_channel,
            "channels_configured": len(self._channels),
        }
