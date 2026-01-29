"""LoggingManager - Core orchestrator for the logging system."""

import atexit
import logging
import sys
from typing import Optional

from .config import LoggingConfig
from .formatters import ColoredFormatter, StandardFormatter, StructuredFormatter
from .handlers import (
    AsyncFileHandler,
    ColoredConsoleHandler,
    RotatingFileHandlerWithRetention,
)
from .sampling import SamplingStrategy, set_sampler
from .utils import get_log_level, ensure_log_directory
from .wide_event import create_wide_event


class LoggingManager:
    """Central orchestrator for the logging system.
    
    Initializes all handlers based on configuration, configures Python's
    logging system, and provides factory methods for loggers and wide events.
    """
    
    def __init__(self, config: LoggingConfig):
        """Initialize logging manager.
        
        Args:
            config: Logging configuration
        """
        self.config = config
        self.sampler: Optional[SamplingStrategy] = None
        self._handlers = []
        
        # Setup handlers
        self._setup_handlers()
        
        # Setup root logger
        self._setup_root_logger()
        
        # Setup sampling
        self._setup_sampling()
        
        # Register shutdown handler
        atexit.register(self.shutdown)
    
    def _setup_handlers(self) -> None:
        """Setup all log handlers based on configuration."""
        # Console handler
        if self.config.console.enabled:
            console_handler = self._create_console_handler()
            if console_handler:
                self._handlers.append(console_handler)
        
        # Main file handler
        if self.config.file.enabled:
            file_handler = self._create_file_handler()
            if file_handler:
                self._handlers.append(file_handler)
        
        # Error file handler
        if self.config.error_file and self.config.error_file.enabled:
            error_handler = self._create_error_handler()
            if error_handler:
                self._handlers.append(error_handler)
    
    def _create_console_handler(self) -> Optional[logging.Handler]:
        """Create console handler.
        
        Returns:
            Console handler or None
        """
        handler = ColoredConsoleHandler(sys.stdout)
        handler.setLevel(get_log_level(self.config.console.level))
        
        # Choose formatter based on config
        if self.config.console.format == "json":
            formatter = StructuredFormatter()
        elif self.config.console.format == "colored":
            formatter = ColoredFormatter()
        else:
            formatter = StandardFormatter()
        
        handler.setFormatter(formatter)
        return handler
    
    def _create_file_handler(self) -> Optional[logging.Handler]:
        """Create main file handler.
        
        Returns:
            File handler or None
        """
        try:
            # Use async handler for non-blocking I/O
            handler = AsyncFileHandler(
                filename=self.config.file.path,
                encoding="utf-8",
                queue_size=self.config.file.queue_size,
            )
            handler.setLevel(get_log_level(self.config.file.level))
            
            # Use structured formatter for file logs
            formatter = StructuredFormatter()
            handler.setFormatter(formatter)
            
            return handler
        except Exception:
            # Fallback to rotating handler if async fails
            try:
                handler = RotatingFileHandlerWithRetention(
                    filename=self.config.file.path,
                    maxBytes=self.config.file.max_bytes,
                    backupCount=self.config.file.backup_count,
                    encoding="utf-8",
                    retention_days=self.config.file.retention_days,
                )
                handler.setLevel(get_log_level(self.config.file.level))
                formatter = StructuredFormatter()
                handler.setFormatter(formatter)
                return handler
            except Exception:
                import sys
                sys.stderr.write(f"Failed to create file handler: {sys.exc_info()}\n")
                return None
    
    def _create_error_handler(self) -> Optional[logging.Handler]:
        """Create error file handler.
        
        Returns:
            Error file handler or None
        """
        if not self.config.error_file:
            return None
        
        try:
            # Use async handler
            handler = AsyncFileHandler(
                filename=self.config.error_file.path,
                encoding="utf-8",
                queue_size=self.config.error_file.queue_size,
            )
            handler.setLevel(get_log_level("ERROR"))  # Errors only
            
            formatter = StructuredFormatter()
            handler.setFormatter(formatter)
            
            return handler
        except Exception:
            # Fallback to rotating handler
            try:
                handler = RotatingFileHandlerWithRetention(
                    filename=self.config.error_file.path,
                    maxBytes=self.config.error_file.max_bytes,
                    backupCount=self.config.error_file.backup_count,
                    encoding="utf-8",
                    retention_days=self.config.error_file.retention_days,
                )
                handler.setLevel(get_log_level("ERROR"))
                formatter = StructuredFormatter()
                handler.setFormatter(formatter)
                return handler
            except Exception:
                return None
    
    def _setup_root_logger(self) -> None:
        """Setup root logger with handlers."""
        root_logger = logging.getLogger()
        root_logger.setLevel(get_log_level(self.config.global_level))
        
        # Clear existing handlers
        root_logger.handlers.clear()
        
        # Add our handlers
        for handler in self._handlers:
            root_logger.addHandler(handler)
        
        # Prevent propagation to avoid duplicate logs
        root_logger.propagate = False
    
    def _setup_sampling(self) -> None:
        """Setup sampling strategy."""
        if self.config.wide_events.enabled:
            self.sampler = SamplingStrategy(self.config.wide_events)
            set_sampler(self.sampler)
    
    def get_logger(self, name: str) -> logging.Logger:
        """Get a logger instance.
        
        Args:
            name: Logger name (typically __name__)
            
        Returns:
            Logger instance
        """
        return logging.getLogger(name)
    
    def create_wide_event(
        self,
        service: str,
        trace_id: Optional[str] = None,
    ):
        """Create a wide event builder.
        
        Args:
            service: Service name
            trace_id: Optional trace ID
            
        Returns:
            WideEventBuilder instance
        """
        return create_wide_event(
            service,
            trace_id=trace_id,
            sampler=self.sampler,
        )
    
    def shutdown(self) -> None:
        """Shutdown logging manager and flush all handlers."""
        # Flush all handlers
        for handler in self._handlers:
            try:
                handler.flush()
                handler.close()
            except Exception:
                pass
        
        # Clear handlers
        self._handlers.clear()


# Global manager instance
_manager: Optional[LoggingManager] = None


def initialize(config: Optional[LoggingConfig] = None, config_path: Optional[str] = None) -> LoggingManager:
    """Initialize the global logging manager.
    
    Args:
        config: Optional LoggingConfig instance
        config_path: Optional path to YAML config file
        
    Returns:
        LoggingManager instance
    """
    global _manager
    
    if config is None:
        from .config import load_config
        config = load_config(config_path)
    
    _manager = LoggingManager(config)
    return _manager


def get_manager() -> Optional[LoggingManager]:
    """Get the global logging manager.
    
    Returns:
        LoggingManager instance or None if not initialized
    """
    return _manager


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance (convenience function).
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Logger instance
    """
    if _manager:
        return _manager.get_logger(name)
    else:
        # Fallback to standard logging
        return logging.getLogger(name)
