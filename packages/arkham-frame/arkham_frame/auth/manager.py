"""User manager for FastAPI-Users."""

import os
import uuid
from datetime import datetime
from typing import Optional

from fastapi import Request
from fastapi_users import BaseUserManager, UUIDIDMixin
import logging

from .models import User

logger = logging.getLogger(__name__)

SECRET_KEY = os.environ.get("AUTH_SECRET_KEY", "CHANGE-ME-IN-PRODUCTION")


class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    """Custom user manager with tenant awareness."""

    reset_password_token_secret = SECRET_KEY
    verification_token_secret = SECRET_KEY

    async def on_after_register(self, user: User, request: Optional[Request] = None):
        """Called after a user registers."""
        logger.info(f"User {user.email} registered for tenant {user.tenant_id}")

    async def on_after_login(
        self,
        user: User,
        request: Optional[Request] = None,
        response=None,
    ):
        """Called after a user logs in."""
        # Update last_login timestamp
        user.last_login = datetime.utcnow()
        logger.info(f"User {user.email} logged in")

    async def on_after_forgot_password(
        self,
        user: User,
        token: str,
        request: Optional[Request] = None,
    ):
        """Called after password reset token is generated."""
        logger.info(f"Password reset requested for {user.email}")
        # In production, send email with token

    async def on_after_reset_password(
        self,
        user: User,
        request: Optional[Request] = None,
    ):
        """Called after password is reset."""
        logger.info(f"Password reset completed for {user.email}")

    async def on_after_request_verify(
        self,
        user: User,
        token: str,
        request: Optional[Request] = None,
    ):
        """Called after verification token is generated."""
        logger.info(f"Verification requested for {user.email}")
        # In production, send verification email

    async def on_after_verify(
        self,
        user: User,
        request: Optional[Request] = None,
    ):
        """Called after user is verified."""
        logger.info(f"User {user.email} verified")
