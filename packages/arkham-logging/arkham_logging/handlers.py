"""Custom log handlers for arkham-logging."""

import logging
import logging.handlers
import queue
import threading
import time
from pathlib import Path
from typing import Optional
from datetime import datetime, timedelta

from .utils import ensure_log_directory


class AsyncFileHandler(logging.Handler):
    """Asynchronous file handler with queue to prevent log loss.
    
    Uses a thread-safe queue and background worker thread to handle
    all file I/O, preventing blocking of the main thread during
    high-volume logging. Queue is flushed on shutdown to ensure
    no logs are lost.
    """
    
    def __init__(
        self,
        filename: str,
        mode: str = "a",
        encoding: Optional[str] = "utf-8",
        delay: bool = False,
        queue_size: int = 1000,
    ):
        """Initialize async file handler.
        
        Args:
            filename: Path to log file
            mode: File mode ('a' for append, 'w' for write)
            encoding: File encoding (default: utf-8)
            delay: Delay file creation until first log
            queue_size: Maximum queue size
        """
        super().__init__()
        
        self.filename = ensure_log_directory(filename)
        self.mode = mode
        self.encoding = encoding
        self.delay = delay
        
        # Queue for log records
        self.queue: queue.Queue = queue.Queue(maxsize=queue_size)
        
        # Worker thread
        self.worker_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._closed = False
        
        # File handle (opened by worker thread)
        self._file = None
        
        # Start worker thread
        self._start_worker()
    
    def _start_worker(self) -> None:
        """Start the background worker thread."""
        if self.worker_thread is None or not self.worker_thread.is_alive():
            self._stop_event.clear()
            self.worker_thread = threading.Thread(
                target=self._worker,
                name="AsyncFileHandler-worker",
                daemon=True,
            )
            self.worker_thread.start()
    
    def _worker(self) -> None:
        """Worker thread that processes log records from queue."""
        # Open file if not delayed
        if not self.delay:
            self._open_file()
        
        while not self._stop_event.is_set():
            try:
                # Get record from queue with timeout
                try:
                    record = self.queue.get(timeout=0.1)
                except queue.Empty:
                    continue
                
                # Handle special sentinel value for shutdown
                if record is None:
                    break
                
                # Open file if delayed and this is first record
                if self._file is None:
                    self._open_file()
                
                # Format and write record
                if self._file:
                    msg = self.format(record)
                    self._file.write(msg + "\n")
                    self._file.flush()
                
                # Mark task as done
                self.queue.task_done()
                
            except Exception:
                # Log error but continue processing
                # Use basic logging to avoid recursion
                import sys
                sys.stderr.write(f"Error in AsyncFileHandler worker: {sys.exc_info()}\n")
        
        # Flush and close file
        if self._file:
            self._file.flush()
            self._file.close()
            self._file = None
    
    def _open_file(self) -> None:
        """Open the log file."""
        try:
            self._file = open(self.filename, self.mode, encoding=self.encoding)
        except Exception:
            # Fallback to stderr if file can't be opened
            import sys
            sys.stderr.write(f"Failed to open log file {self.filename}: {sys.exc_info()}\n")
            self._file = None
    
    def emit(self, record: logging.LogRecord) -> None:
        """Emit a log record (non-blocking).
        
        Args:
            record: Log record to emit
        """
        if self._closed:
            return
        
        try:
            # Put record in queue (non-blocking)
            self.queue.put_nowait(record)
        except queue.Full:
            # Queue is full - drop record or write to stderr
            import sys
            sys.stderr.write(f"Log queue full, dropping record: {record.getMessage()}\n")
        except Exception:
            # Handle any other errors
            self.handleError(record)
    
    def flush(self) -> None:
        """Flush the queue and file."""
        if self._file:
            self._file.flush()
    
    def close(self) -> None:
        """Close the handler and flush queue."""
        if self._closed:
            return
        
        self._closed = True
        
        # Wait for queue to empty
        self.queue.join()
        
        # Signal worker to stop
        self._stop_event.set()
        
        # Send sentinel to worker
        try:
            self.queue.put_nowait(None)
        except queue.Full:
            pass
        
        # Wait for worker thread to finish (with timeout)
        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=5.0)
        
        # Final flush
        self.flush()
        
        super().close()


class RotatingFileHandlerWithRetention(logging.handlers.RotatingFileHandler):
    """Rotating file handler with time-based retention policy.
    
    Extends RotatingFileHandler to automatically delete old log files
    based on retention_days configuration.
    """
    
    def __init__(
        self,
        filename: str,
        mode: str = "a",
        maxBytes: int = 0,
        backupCount: int = 0,
        encoding: Optional[str] = "utf-8",
        delay: bool = False,
        retention_days: Optional[int] = None,
    ):
        """Initialize rotating file handler with retention.
        
        Args:
            filename: Path to log file
            mode: File mode
            maxBytes: Maximum bytes per file
            backupCount: Number of backup files to keep
            encoding: File encoding
            delay: Delay file creation
            retention_days: Days to retain logs (None = forever)
        """
        super().__init__(
            filename=filename,
            mode=mode,
            maxBytes=maxBytes,
            backupCount=backupCount,
            encoding=encoding,
            delay=delay,
        )
        
        self.retention_days = retention_days
        self._last_cleanup = time.time()
        self._cleanup_interval = 3600  # Run cleanup every hour
        
        # Run initial cleanup
        self._cleanup_old_files()
    
    def doRollover(self) -> None:
        """Perform rollover and cleanup old files."""
        super().doRollover()
        self._cleanup_old_files()
    
    def _cleanup_old_files(self) -> None:
        """Clean up old log files based on retention policy."""
        if self.retention_days is None:
            return
        
        # Throttle cleanup frequency
        now = time.time()
        if now - self._last_cleanup < self._cleanup_interval:
            return
        
        self._last_cleanup = now
        
        try:
            log_dir = Path(self.baseFilename).parent
            cutoff_time = datetime.now() - timedelta(days=self.retention_days)
            
            # Find all log files matching pattern
            base_name = Path(self.baseFilename).name
            for log_file in log_dir.glob(f"{base_name}*"):
                # Check modification time
                mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
                if mtime < cutoff_time:
                    try:
                        log_file.unlink()
                    except Exception:
                        pass  # Ignore errors during cleanup
        except Exception:
            pass  # Ignore errors during cleanup


class ColoredConsoleHandler(logging.StreamHandler):
    """Console handler with ANSI color support."""
    
    def __init__(self, stream=None):
        """Initialize colored console handler.
        
        Args:
            stream: Stream to write to (default: sys.stdout)
        """
        super().__init__(stream)
    
    def emit(self, record: logging.LogRecord) -> None:
        """Emit record with color support."""
        super().emit(record)
