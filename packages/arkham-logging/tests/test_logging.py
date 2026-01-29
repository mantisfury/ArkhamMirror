"""Comprehensive tests for arkham-logging."""

import pytest
import tempfile
import os
import time
import json
import logging
from pathlib import Path
from unittest.mock import patch, MagicMock

from arkham_logging import (
    LoggingManager,
    get_logger,
    create_wide_event,
    log_operation,
    LoggingConfig,
    load_config,
)
from arkham_logging.manager import initialize
from arkham_logging.sanitizer import DataSanitizer, sanitize
from arkham_logging.tracing import TracingContext, get_trace_id, set_trace_id, generate_trace_id
from arkham_logging.sampling import SamplingStrategy
from arkham_logging.handlers import AsyncFileHandler, RotatingFileHandlerWithRetention
from arkham_logging.wide_event import WideEvent


class TestConfig:
    """Test configuration loading."""
    
    def test_default_config(self):
        """Test default configuration."""
        config = LoggingConfig()
        assert config.console.enabled is True
        assert config.file.enabled is True
        assert config.wide_events.enabled is True
        assert config.file.path == "logs/arkham.log"
        assert config.file.max_bytes == 100_000_000
    
    def test_load_from_dict(self):
        """Test loading config from dictionary."""
        data = {
            "console": {"enabled": False},
            "file": {"path": "custom.log"},
        }
        config = LoggingConfig.from_dict(data)
        assert config.console.enabled is False
        assert config.file.path == "custom.log"
    
    def test_load_from_env(self):
        """Test loading config from environment variables."""
        with patch.dict(os.environ, {
            "ARKHAM_LOG_LEVEL": "DEBUG",
            "ARKHAM_LOG_CONSOLE_ENABLED": "false",
            "ARKHAM_LOG_FILE_PATH": "test.log",
        }):
            config = LoggingConfig.from_env()
            assert config.global_level == "DEBUG"
            assert config.console.enabled is False
            assert config.file.path == "test.log"
    
    def test_config_priority(self):
        """Test that env vars override YAML config."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("""
frame:
  logging:
    console:
      enabled: true
      level: INFO
    file:
      path: yaml.log
""")
            yaml_path = f.name
        
        try:
            with patch.dict(os.environ, {
                "ARKHAM_LOG_CONSOLE_ENABLED": "false",
                "ARKHAM_LOG_FILE_PATH": "env.log",
            }):
                config = LoggingConfig.load(yaml_path)
                # Env vars should override YAML
                assert config.console.enabled is False
                assert config.file.path == "env.log"
        finally:
            os.unlink(yaml_path)


class TestSanitizer:
    """Test data sanitization."""
    
    def test_sanitize_password(self):
        """Test password sanitization."""
        sanitizer = DataSanitizer()
        data = {"password": "secret123", "username": "user"}
        sanitized = sanitizer.sanitize(data)
        assert sanitized["password"] == "***"
        assert sanitized["username"] == "user"
    
    def test_sanitize_token(self):
        """Test token sanitization."""
        sanitizer = DataSanitizer()
        data = {"api_key": "sk-1234567890", "token": "bearer_token_123"}
        sanitized = sanitizer.sanitize(data)
        assert sanitized["api_key"] == "***"
        assert sanitized["token"] == "***"
    
    def test_sanitize_email(self):
        """Test email sanitization."""
        sanitizer = DataSanitizer(sanitize_emails=True)
        data = {"email": "user@example.com", "contact": "admin@test.org"}
        sanitized = sanitizer.sanitize(data)
        assert sanitized["email"] == "***"
        assert sanitized["contact"] == "***"
    
    def test_sanitize_email_disabled(self):
        """Test email sanitization can be disabled."""
        sanitizer = DataSanitizer(sanitize_emails=False)
        data = {"email": "user@example.com"}
        sanitized = sanitizer.sanitize(data)
        assert sanitized["email"] == "user@example.com"
    
    def test_sanitize_credit_card(self):
        """Test credit card sanitization."""
        sanitizer = DataSanitizer()
        data = {"card": "1234-5678-9012-3456"}
        sanitized = sanitizer.sanitize(data)
        assert "***" in sanitized["card"]
    
    def test_sanitize_ssn(self):
        """Test SSN sanitization."""
        sanitizer = DataSanitizer()
        data = {"ssn": "123-45-6789"}
        sanitized = sanitizer.sanitize(data)
        assert sanitized["ssn"] == "***"
    
    def test_sanitize_phone(self):
        """Test phone number sanitization."""
        sanitizer = DataSanitizer()
        data = {"phone": "555-123-4567"}
        sanitized = sanitizer.sanitize(data)
        assert "***" in sanitized["phone"]
    
    def test_sanitize_ip(self):
        """Test IP address sanitization."""
        sanitizer = DataSanitizer(sanitize_ips=True)
        data = {"ip": "192.168.1.1"}
        sanitized = sanitizer.sanitize(data)
        assert sanitized["ip"] == "***"
    
    def test_sanitize_nested(self):
        """Test nested structure sanitization."""
        sanitizer = DataSanitizer()
        data = {
            "user": {
                "password": "secret",
                "api_key": "key123",
                "nested": {
                    "token": "nested_token"
                }
            },
            "items": ["item1", "item2"],
        }
        sanitized = sanitizer.sanitize(data)
        assert sanitized["user"]["password"] == "***"
        assert sanitized["user"]["api_key"] == "***"
        assert sanitized["user"]["nested"]["token"] == "***"
        assert sanitized["items"] == ["item1", "item2"]
    
    def test_sanitize_list(self):
        """Test list sanitization."""
        sanitizer = DataSanitizer()
        data = [
            {"password": "secret1"},
            {"password": "secret2"},
        ]
        sanitized = sanitizer.sanitize(data)
        assert sanitized[0]["password"] == "***"
        assert sanitized[1]["password"] == "***"
    
    def test_sanitize_whitelist(self):
        """Test whitelist functionality."""
        sanitizer = DataSanitizer(whitelist_keys={"password"})
        data = {"password": "secret123", "token": "token123"}
        sanitized = sanitizer.sanitize(data)
        assert sanitized["password"] == "secret123"  # Not sanitized
        assert sanitized["token"] == "***"  # Still sanitized
    
    def test_sanitize_string_with_email(self):
        """Test string sanitization with embedded email."""
        sanitizer = DataSanitizer(sanitize_emails=True)
        text = "Contact user@example.com for details"
        sanitized = sanitizer.sanitize(text)
        assert "***" in sanitized
        assert "user@example.com" not in sanitized
    
    def test_sanitize_custom_pattern(self):
        """Test custom pattern sanitization."""
        import re
        custom_pattern = re.compile(r'\b\d{4}-\d{4}-\d{4}-\d{4}\b')
        sanitizer = DataSanitizer(custom_patterns=[custom_pattern])
        data = {"custom": "1234-5678-9012-3456"}
        sanitized = sanitizer.sanitize(data)
        assert sanitized["custom"] == "***"
    
    def test_sanitize_preserves_structure(self):
        """Test that sanitization preserves data structure."""
        sanitizer = DataSanitizer()
        original = {
            "user": {"id": "123", "password": "secret"},
            "items": [1, 2, 3],
        }
        sanitized = sanitizer.sanitize(original)
        # Original should not be modified
        assert original["user"]["password"] == "secret"
        # Sanitized should be modified
        assert sanitized["user"]["password"] == "***"
        assert sanitized["user"]["id"] == "123"
        assert sanitized["items"] == [1, 2, 3]
    
    def test_sanitize_convenience_function(self):
        """Test convenience sanitize function."""
        data = {"password": "secret"}
        sanitized = sanitize(data)
        assert sanitized["password"] == "***"


class TestTracing:
    """Test distributed tracing."""
    
    def test_generate_trace_id(self):
        """Test trace_id generation."""
        tracing = TracingContext()
        trace_id = tracing.generate_trace_id()
        assert trace_id.startswith("trace_")
        assert len(trace_id) > 10
        # Should be set in context
        assert tracing.get_trace_id() == trace_id
    
    def test_set_get_trace_id(self):
        """Test setting and getting trace_id."""
        tracing = TracingContext()
        tracing.set_trace_id("trace_test123")
        assert tracing.get_trace_id() == "trace_test123"
    
    def test_extract_from_headers_x_trace_id(self):
        """Test trace_id extraction from X-Trace-ID header."""
        tracing = TracingContext()
        headers = {"X-Trace-ID": "trace_abc123"}
        trace_id = tracing.extract_from_headers(headers)
        assert trace_id == "trace_abc123"
    
    def test_extract_from_headers_traceparent(self):
        """Test trace_id extraction from traceparent header."""
        tracing = TracingContext()
        headers = {"traceparent": "00-trace_abc123def456-parent-01"}
        trace_id = tracing.extract_from_headers(headers)
        assert trace_id == "trace_abc123def456"
    
    def test_extract_from_headers_case_insensitive(self):
        """Test case-insensitive header extraction."""
        tracing = TracingContext()
        headers = {"x-trace-id": "trace_lowercase"}
        trace_id = tracing.extract_from_headers(headers)
        assert trace_id == "trace_lowercase"
    
    def test_propagate_to_headers(self):
        """Test header propagation."""
        tracing = TracingContext()
        tracing.set_trace_id("trace_abc123")
        headers = tracing.propagate_to_headers()
        assert headers["X-Trace-ID"] == "trace_abc123"
        assert "traceparent" in headers
        assert headers["traceparent"].startswith("00-trace_abc123")
    
    def test_propagate_to_existing_headers(self):
        """Test propagation updates existing headers."""
        tracing = TracingContext()
        tracing.set_trace_id("trace_abc123")
        existing = {"Authorization": "Bearer token"}
        headers = tracing.propagate_to_headers(existing)
        assert headers["X-Trace-ID"] == "trace_abc123"
        assert headers["Authorization"] == "Bearer token"
    
    def test_clear_trace_id(self):
        """Test clearing trace_id."""
        tracing = TracingContext()
        tracing.set_trace_id("trace_test")
        tracing.clear()
        assert tracing.get_trace_id() is None
    
    def test_global_functions(self):
        """Test global convenience functions."""
        set_trace_id("trace_global")
        assert get_trace_id() == "trace_global"
        
        new_id = generate_trace_id()
        assert new_id.startswith("trace_")
        assert get_trace_id() == new_id


class TestWideEvents:
    """Test wide event logging."""
    
    def test_create_wide_event(self):
        """Test creating wide event."""
        event_builder = create_wide_event("test_service")
        assert event_builder._service == "test_service"
        assert event_builder._trace_id is not None
    
    def test_create_wide_event_with_trace_id(self):
        """Test creating wide event with trace_id."""
        event_builder = create_wide_event("test_service", trace_id="trace_custom")
        assert event_builder._trace_id == "trace_custom"
    
    def test_wide_event_builder_input(self):
        """Test wide event builder input."""
        event_builder = create_wide_event("test_service")
        event_builder.input(document_id="doc_123", filename="test.pdf")
        event = event_builder.success()
        
        assert event.input["document_id"] == "doc_123"
        assert event.input["filename"] == "test.pdf"
    
    def test_wide_event_builder_user(self):
        """Test wide event builder user context."""
        event_builder = create_wide_event("test_service")
        event_builder.user(id="user_456", subscription="premium")
        event = event_builder.success()
        
        assert event.user["id"] == "user_456"
        assert event.user["subscription"] == "premium"
    
    def test_wide_event_builder_output(self):
        """Test wide event builder output."""
        event_builder = create_wide_event("test_service")
        event_builder.output(page_count=10, success=True)
        event = event_builder.success()
        
        assert event.output["page_count"] == 10
        assert event.output["success"] is True
    
    def test_wide_event_builder_dependency(self):
        """Test wide event builder dependency tracking."""
        event_builder = create_wide_event("test_service")
        event_builder.dependency("api_call", duration_ms=450, status_code=200)
        event = event_builder.success()
        
        assert "api_call" in event.dependencies
        assert event.dependencies["api_call"]["duration_ms"] == 450
        assert event.dependencies["api_call"]["status_code"] == 200
    
    def test_wide_event_builder_context(self):
        """Test wide event builder custom context."""
        event_builder = create_wide_event("test_service")
        event_builder.context("feature_flag", "new_flow")
        event_builder.context("deployment_id", "deploy_123")
        event = event_builder.success()
        
        assert event.extra["feature_flag"] == "new_flow"
        assert event.extra["deployment_id"] == "deploy_123"
    
    def test_wide_event_status_code(self):
        """Test wide event status code."""
        event_builder = create_wide_event("test_service")
        event_builder.status_code(201)
        event = event_builder.success()
        
        assert event.status_code == 201
    
    def test_wide_event_success(self):
        """Test wide event success."""
        event_builder = create_wide_event("test_service")
        event_builder.input(document_id="doc_123")
        event_builder.user(id="user_456")
        event = event_builder.success()
        
        assert event.service == "test_service"
        assert event.outcome == "success"
        assert event.duration_ms >= 0
    
    def test_wide_event_error(self):
        """Test wide event error handling."""
        event_builder = create_wide_event("test_service")
        event_builder.input(document_id="doc_123")
        event = event_builder.error("TestError", "Test message")
        
        assert event.outcome == "error"
        assert event.error["code"] == "TestError"
        assert event.error["message"] == "Test message"
    
    def test_wide_event_error_with_exception(self):
        """Test wide event error with exception."""
        event_builder = create_wide_event("test_service")
        try:
            raise ValueError("Test exception")
        except ValueError as e:
            event = event_builder.error("ValueError", str(e), exception=e)
        
        assert event.outcome == "error"
        assert event.error["type"] == "ValueError"
        assert "traceback" in event.error
    
    def test_wide_event_sanitization(self):
        """Test that wide events automatically sanitize data."""
        event_builder = create_wide_event("test_service")
        event_builder.input(password="secret123", document_id="doc_123")
        event_builder.user(api_key="key123", id="user_456")
        event = event_builder.success()
        
        # Sensitive data should be sanitized
        assert event.input["password"] == "***"
        assert event.user["api_key"] == "***"
        # Non-sensitive data should remain
        assert event.input["document_id"] == "doc_123"
        assert event.user["id"] == "user_456"
    
    def test_wide_event_to_dict(self):
        """Test wide event to_dict conversion."""
        event_builder = create_wide_event("test_service")
        event_builder.input(test="value")
        event = event_builder.success()
        
        event_dict = event.to_dict()
        assert event_dict["service"] == "test_service"
        assert event_dict["outcome"] == "success"
        assert event_dict["input"]["test"] == "value"
        assert "timestamp" in event_dict
        assert "operation_id" in event_dict
        assert "trace_id" in event_dict


class TestSampling:
    """Test sampling strategies."""
    
    def test_always_sample_errors(self):
        """Test that errors are always sampled."""
        config = LoggingConfig()
        config.wide_events.always_sample_errors = True
        sampler = SamplingStrategy(config.wide_events)
        
        event = WideEvent(
            timestamp="2025-01-15T10:23:45Z",
            operation_id="op_123",
            trace_id="trace_123",
            service="test",
            duration_ms=100,
            outcome="error",
        )
        
        assert sampler.should_sample(event) is True
    
    def test_always_sample_status_500(self):
        """Test that HTTP 500 errors are always sampled."""
        config = LoggingConfig()
        config.wide_events.always_sample_errors = True
        sampler = SamplingStrategy(config.wide_events)
        
        event = WideEvent(
            timestamp="2025-01-15T10:23:45Z",
            operation_id="op_123",
            trace_id="trace_123",
            service="test",
            duration_ms=100,
            outcome="success",
            status_code=500,
        )
        
        assert sampler.should_sample(event) is True
    
    def test_sample_slow_requests(self):
        """Test that slow requests are always sampled."""
        config = LoggingConfig()
        config.wide_events.always_sample_slow = True
        config.wide_events.slow_threshold_ms = 2000
        sampler = SamplingStrategy(config.wide_events)
        
        event = WideEvent(
            timestamp="2025-01-15T10:23:45Z",
            operation_id="op_123",
            trace_id="trace_123",
            service="test",
            duration_ms=3000,  # Above threshold
            outcome="success",
        )
        
        assert sampler.should_sample(event) is True
    
    def test_sample_vip_users(self):
        """Test that VIP users are always sampled."""
        config = LoggingConfig()
        config.wide_events.always_sample_users = ["user_vip"]
        sampler = SamplingStrategy(config.wide_events)
        
        event = WideEvent(
            timestamp="2025-01-15T10:23:45Z",
            operation_id="op_123",
            trace_id="trace_123",
            service="test",
            duration_ms=100,
            outcome="success",
            user={"id": "user_vip"},
        )
        
        assert sampler.should_sample(event) is True
    
    def test_sample_vip_projects(self):
        """Test that VIP projects are always sampled."""
        config = LoggingConfig()
        config.wide_events.always_sample_projects = ["project_vip"]
        sampler = SamplingStrategy(config.wide_events)
        
        event = WideEvent(
            timestamp="2025-01-15T10:23:45Z",
            operation_id="op_123",
            trace_id="trace_123",
            service="test",
            duration_ms=100,
            outcome="success",
            project_id="project_vip",
        )
        
        assert sampler.should_sample(event) is True
    
    def test_random_sampling(self):
        """Test random sampling for normal requests."""
        config = LoggingConfig()
        config.wide_events.sampling_rate = 1.0  # 100% for testing
        sampler = SamplingStrategy(config.wide_events)
        
        event = WideEvent(
            timestamp="2025-01-15T10:23:45Z",
            operation_id="op_123",
            trace_id="trace_123",
            service="test",
            duration_ms=100,
            outcome="success",
        )
        
        # With 100% sampling rate, should always sample
        assert sampler.should_sample(event) is True
    
    def test_sampling_rate_zero(self):
        """Test that sampling rate of 0 never samples normal requests."""
        config = LoggingConfig()
        config.wide_events.sampling_rate = 0.0
        config.wide_events.always_sample_errors = False
        config.wide_events.always_sample_slow = False
        sampler = SamplingStrategy(config.wide_events)
        
        event = WideEvent(
            timestamp="2025-01-15T10:23:45Z",
            operation_id="op_123",
            trace_id="trace_123",
            service="test",
            duration_ms=100,
            outcome="success",
        )
        
        # Should not sample normal requests with 0% rate
        assert sampler.should_sample(event) is False


class TestLoggingManager:
    """Test logging manager."""
    
    def test_initialize(self):
        """Test logging manager initialization."""
        config = LoggingConfig()
        config.console.enabled = True
        config.file.enabled = False  # Disable file for testing
        
        manager = LoggingManager(config)
        assert manager.config == config
        assert manager.get_logger("test") is not None
    
    def test_get_logger(self):
        """Test logger retrieval."""
        config = LoggingConfig()
        config.file.enabled = False
        manager = LoggingManager(config)
        
        logger = manager.get_logger("test_module")
        assert logger.name == "test_module"
    
    def test_create_wide_event(self):
        """Test creating wide event through manager."""
        config = LoggingConfig()
        config.file.enabled = False
        manager = LoggingManager(config)
        
        event_builder = manager.create_wide_event("test_service")
        assert event_builder._service == "test_service"
    
    def test_shutdown(self):
        """Test manager shutdown."""
        config = LoggingConfig()
        config.file.enabled = False
        manager = LoggingManager(config)
        
        # Should not raise
        manager.shutdown()


class TestAsyncFileHandler:
    """Test AsyncFileHandler."""
    
    def test_async_handler_creation(self):
        """Test creating async file handler."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"
            handler = AsyncFileHandler(str(log_file), queue_size=10)
            
            # Write a log record
            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="test.py",
                lineno=1,
                msg="Test message",
                args=(),
                exc_info=None,
            )
            handler.emit(record)
            
            # Give worker thread time to process
            time.sleep(0.1)
            handler.close()
            
            # Check file was created and contains log
            assert log_file.exists()
            content = log_file.read_text()
            assert "Test message" in content
    
    def test_async_handler_queue_full(self):
        """Test handler behavior when queue is full."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"
            handler = AsyncFileHandler(str(log_file), queue_size=2)
            
            # Fill queue beyond capacity
            for i in range(5):
                record = logging.LogRecord(
                    name="test",
                    level=logging.INFO,
                    pathname="test.py",
                    lineno=1,
                    msg=f"Message {i}",
                    args=(),
                    exc_info=None,
                )
                handler.emit(record)
            
            time.sleep(0.2)
            handler.close()
            
            # Some messages should be logged (queue handled some)
            assert log_file.exists()


class TestExceptionHandler:
    """Test exception handling."""
    
    def test_log_operation_success(self):
        """Test log_operation context manager on success."""
        with log_operation("test_service", test_param="value") as event:
            result = "success"
            event.output(result=result)
        
        # Event should be created and logged (event is WideEventBuilder)
        assert event is not None
        assert hasattr(event, "_service")
    
    def test_log_operation_error(self):
        """Test log_operation context manager on error."""
        with pytest.raises(ValueError):
            with log_operation("test_service", test_param="value") as event:
                raise ValueError("Test error")
        
        # Error should be logged (event was created before exception)
        # We can't easily verify logging happened, but exception should propagate
    
    def test_log_operation_sanitization(self):
        """Test that log_operation sanitizes input."""
        with log_operation("test_service", password="secret123") as event:
            pass
        
        # Input should be sanitized
        assert event._input["password"] == "***"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
