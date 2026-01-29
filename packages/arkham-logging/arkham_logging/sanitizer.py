"""Automatic data sanitization for logging."""

import re
from typing import Any, Dict, List, Optional, Set
from copy import deepcopy


class DataSanitizer:
    """Automatically sanitizes sensitive data before logging.
    
    Recursively scans all data structures (dicts, lists, nested structures)
    and redacts sensitive patterns including passwords, tokens, API keys,
    emails, credit cards, SSNs, IPs, and custom patterns.
    """
    
    # Sensitive key patterns (case-insensitive)
    SENSITIVE_KEYS = {
        "password", "passwd", "pwd", "secret", "token", "api_key", "apikey",
        "access_token", "refresh_token", "auth_token", "bearer", "credential",
        "private_key", "privatekey", "secret_key", "secretkey", "session_id",
        "sessionid", "cookie", "authorization", "x-api-key", "x-auth-token",
    }
    
    # Patterns for sensitive values
    EMAIL_PATTERN = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
    CREDIT_CARD_PATTERN = re.compile(r'\b(?:\d{4}[-\s]?){3}\d{4}\b')
    SSN_PATTERN = re.compile(r'\b\d{3}-\d{2}-\d{4}\b')
    PHONE_PATTERN = re.compile(r'\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b')
    IP_PATTERN = re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b')
    
    def __init__(
        self,
        redaction_string: str = "***",
        sanitize_emails: bool = True,
        sanitize_ips: bool = False,
        whitelist_keys: Optional[Set[str]] = None,
        custom_patterns: Optional[List[re.Pattern]] = None,
    ):
        """Initialize sanitizer.
        
        Args:
            redaction_string: String to use for redaction (default: "***")
            sanitize_emails: Whether to sanitize email addresses
            sanitize_ips: Whether to sanitize IP addresses
            whitelist_keys: Set of keys that should never be sanitized
            custom_patterns: Additional regex patterns to match and redact
        """
        self.redaction_string = redaction_string
        self.sanitize_emails = sanitize_emails
        self.sanitize_ips = sanitize_ips
        self.whitelist_keys = whitelist_keys or set()
        self.custom_patterns = custom_patterns or []
    
    def sanitize(self, data: Any, context: Optional[Dict] = None) -> Any:
        """Recursively sanitize data structure.
        
        Args:
            data: Data to sanitize (dict, list, str, or any other type)
            context: Optional context for tracking nested depth
            
        Returns:
            Sanitized copy of data (doesn't mutate original)
        """
        if context is None:
            context = {"depth": 0}
        
        # Prevent infinite recursion
        if context["depth"] > 50:
            return self.redaction_string
        
        context["depth"] += 1
        
        try:
            if isinstance(data, dict):
                return self._sanitize_dict(data, context)
            elif isinstance(data, list):
                return self._sanitize_list(data, context)
            elif isinstance(data, tuple):
                return tuple(self._sanitize_list(list(data), context))
            elif isinstance(data, str):
                return self._sanitize_string(data)
            elif isinstance(data, (int, float, bool, type(None))):
                return data  # Primitives are safe
            else:
                # For other types, convert to string and sanitize
                return self._sanitize_string(str(data))
        finally:
            context["depth"] -= 1
    
    def _sanitize_dict(self, data: Dict[str, Any], context: Dict) -> Dict[str, Any]:
        """Sanitize dictionary."""
        sanitized = {}
        
        for key, value in data.items():
            sanitized_key = key
            
            # Check if key itself is sensitive
            if self._is_sensitive_key(key):
                sanitized[sanitized_key] = self.redaction_string
            else:
                # Recursively sanitize value
                sanitized[sanitized_key] = self.sanitize(value, context)
        
        return sanitized
    
    def _sanitize_list(self, data: List[Any], context: Dict) -> List[Any]:
        """Sanitize list."""
        return [self.sanitize(item, context) for item in data]
    
    def _sanitize_string(self, value: str) -> str:
        """Sanitize string value."""
        if not isinstance(value, str) or len(value) == 0:
            return value
        
        sanitized = value
        
        # Check for sensitive patterns
        if self.sanitize_emails and self.EMAIL_PATTERN.search(sanitized):
            sanitized = self.EMAIL_PATTERN.sub(self.redaction_string, sanitized)
        
        if self.CREDIT_CARD_PATTERN.search(sanitized):
            sanitized = self.CREDIT_CARD_PATTERN.sub(self.redaction_string, sanitized)
        
        if self.SSN_PATTERN.search(sanitized):
            sanitized = self.SSN_PATTERN.sub(self.redaction_string, sanitized)
        
        if self.PHONE_PATTERN.search(sanitized):
            sanitized = self.PHONE_PATTERN.sub(self.redaction_string, sanitized)
        
        if self.sanitize_ips and self.IP_PATTERN.search(sanitized):
            sanitized = self.IP_PATTERN.sub(self.redaction_string, sanitized)
        
        # Apply custom patterns
        for pattern in self.custom_patterns:
            sanitized = pattern.sub(self.redaction_string, sanitized)
        
        return sanitized
    
    def _is_sensitive_key(self, key: str) -> bool:
        """Check if a key indicates sensitive data.
        
        Args:
            key: Dictionary key to check
            
        Returns:
            True if key is sensitive
        """
        if key in self.whitelist_keys:
            return False
        
        key_lower = key.lower()
        
        # Check exact match
        if key_lower in self.SENSITIVE_KEYS:
            return True
        
        # Check if key contains any sensitive pattern
        for sensitive in self.SENSITIVE_KEYS:
            if sensitive in key_lower:
                return True
        
        return False


# Global instance for convenience
_default_sanitizer = DataSanitizer()


def sanitize(data: Any, **kwargs) -> Any:
    """Convenience function to sanitize data.
    
    Args:
        data: Data to sanitize
        **kwargs: Options passed to DataSanitizer
        
    Returns:
        Sanitized data
    """
    if kwargs:
        sanitizer = DataSanitizer(**kwargs)
    else:
        sanitizer = _default_sanitizer
    
    return sanitizer.sanitize(data)
