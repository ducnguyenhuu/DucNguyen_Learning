"""
Logging Utilities - Structured Logging with File Rotation

This module provides centralized logging configuration for the application.
Features:
- Structured logging with timestamps, levels, and context
- File output with automatic rotation (10MB per file, keep 5 backups)
- Console output with color coding (development)
- Integration with application settings
- Easy logger retrieval by module name

Usage:
    from src.shelf_monitor.utils.logging import setup_logging, get_logger
    
    # Setup once at application startup
    setup_logging()
    
    # Get logger in any module
    logger = get_logger(__name__)
    logger.info("Application started", extra={"user_id": 123})
    logger.error("Error occurred", exc_info=True)

Related:
- Settings: src/shelf_monitor/config/settings.py
- Main app: src/shelf_monitor/api/main.py
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

from src.shelf_monitor.config.settings import settings


# ============================================================================
# Custom Formatter
# ============================================================================


class StructuredFormatter(logging.Formatter):
    """
    Custom formatter that provides structured, readable log output.
    
    Format: [TIMESTAMP] [LEVEL] [MODULE] MESSAGE {context}
    Example: [2025-12-26 10:30:45] [INFO] [api.main] Server started {"port": 8000}
    """
    
    # Color codes for console output (ANSI escape sequences)
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
        'RESET': '\033[0m'        # Reset
    }
    
    def __init__(self, use_colors: bool = False):
        """
        Initialize formatter.
        
        Args:
            use_colors: Whether to use ANSI colors (for console output)
        """
        super().__init__()
        self.use_colors = use_colors
    
    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record with timestamp, level, module, and message.
        
        Args:
            record: Log record to format
            
        Returns:
            Formatted log string
        """
        # Format timestamp
        timestamp = self.formatTime(record, datefmt='%Y-%m-%d %H:%M:%S')
        
        # Get level name with optional color
        level = record.levelname
        if self.use_colors and level in self.COLORS:
            level = f"{self.COLORS[level]}{level}{self.COLORS['RESET']}"
        
        # Get module name (shorten if too long)
        module = record.name
        if len(module) > 30:
            module = '...' + module[-27:]
        
        # Format base message
        message = record.getMessage()
        
        # Add exception info if present
        if record.exc_info:
            exc_text = self.formatException(record.exc_info)
            message = f"{message}\n{exc_text}"
        
        # Add extra context if present (from extra={} in log calls)
        extra_fields = {}
        for key, value in record.__dict__.items():
            # Skip standard logging attributes
            if key not in [
                'name', 'msg', 'args', 'created', 'filename', 'funcName',
                'levelname', 'levelno', 'lineno', 'module', 'msecs',
                'message', 'pathname', 'process', 'processName', 'relativeCreated',
                'thread', 'threadName', 'exc_info', 'exc_text', 'stack_info'
            ]:
                extra_fields[key] = value
        
        # Build final log line
        log_line = f"[{timestamp}] [{level}] [{module}] {message}"
        
        # Add extra fields if present
        if extra_fields:
            context = ", ".join(f"{k}={v}" for k, v in extra_fields.items())
            log_line += f" | {context}"
        
        return log_line


# ============================================================================
# Logging Setup
# ============================================================================


def setup_logging(
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    enable_console: bool = True,
    enable_file: bool = True
) -> None:
    """
    Configure application logging with file rotation and console output.
    
    This should be called once at application startup, typically in main.py.
    Creates logs directory if it doesn't exist and sets up rotating file handler.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
                   If None, uses settings.log_level
        log_file: Path to log file. If None, uses settings.log_file
        enable_console: Whether to enable console output (default: True)
        enable_file: Whether to enable file output (default: True)
    
    Example:
        >>> setup_logging()  # Uses defaults from settings
        >>> setup_logging(log_level="DEBUG", log_file="logs/debug.log")
    
    Notes:
        - File rotation: 10MB per file, keeps 5 backup files
        - Console output: Colored for development
        - File output: Plain text for production parsing
    """
    # Use settings if not provided
    log_level = log_level or settings.log_level
    log_file = log_file or settings.log_file
    
    # Convert log level string to logging constant
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    
    # Remove existing handlers (avoid duplicate logs)
    root_logger.handlers.clear()
    
    # ========================================================================
    # Console Handler (colored, for development)
    # ========================================================================
    
    if enable_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(numeric_level)
        
        # Use colors for console output
        console_formatter = StructuredFormatter(use_colors=True)
        console_handler.setFormatter(console_formatter)
        
        root_logger.addHandler(console_handler)
    
    # ========================================================================
    # File Handler (rotating, for production)
    # ========================================================================
    
    if enable_file:
        # Create logs directory if it doesn't exist
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Rotating file handler: 10MB per file, keep 5 backups
        file_handler = RotatingFileHandler(
            filename=log_file,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(numeric_level)
        
        # No colors for file output (plain text)
        file_formatter = StructuredFormatter(use_colors=False)
        file_handler.setFormatter(file_formatter)
        
        root_logger.addHandler(file_handler)
    
    # ========================================================================
    # Suppress noisy third-party loggers
    # ========================================================================
    
    # Reduce uvicorn verbosity (only show warnings+)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    
    # Reduce SQLAlchemy verbosity
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    
    # Log successful setup
    root_logger.info(
        f"Logging configured: level={log_level}, file={log_file}, "
        f"console={enable_console}, file_rotation={enable_file}"
    )


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a module.
    
    Use __name__ as the logger name to automatically include module path.
    This allows filtering logs by module and seeing where logs come from.
    
    Args:
        name: Logger name (typically __name__)
    
    Returns:
        Logger instance configured with application settings
    
    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("Processing started")
        >>> logger.error("Failed to process", exc_info=True)
        >>> logger.debug("Debug details", extra={"count": 42})
    
    Notes:
        - Logger inherits configuration from setup_logging()
        - Must call setup_logging() first (typically in main.py)
        - extra={} dict adds context to log output
    """
    return logging.getLogger(name)


# ============================================================================
# Context Managers for Logging
# ============================================================================


class LogExecutionTime:
    """
    Context manager to log execution time of a code block.
    
    Useful for performance monitoring and debugging slow operations.
    
    Example:
        >>> logger = get_logger(__name__)
        >>> with LogExecutionTime(logger, "Database query"):
        ...     results = db.query(Product).all()
        [2025-12-26 10:30:45] [INFO] [module] Database query completed in 0.125s
    """
    
    def __init__(self, logger: logging.Logger, operation: str, level: int = logging.INFO):
        """
        Initialize execution timer.
        
        Args:
            logger: Logger instance to use
            operation: Description of operation being timed
            level: Log level (default: INFO)
        """
        self.logger = logger
        self.operation = operation
        self.level = level
        self.start_time = None
    
    def __enter__(self):
        """Start timing."""
        import time
        self.start_time = time.time()
        self.logger.log(self.level, f"{self.operation} started")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Log completion time."""
        import time
        elapsed = time.time() - self.start_time
        
        if exc_type is None:
            self.logger.log(
                self.level,
                f"{self.operation} completed in {elapsed:.3f}s"
            )
        else:
            self.logger.error(
                f"{self.operation} failed after {elapsed:.3f}s",
                exc_info=(exc_type, exc_val, exc_tb)
            )
        
        # Don't suppress exceptions
        return False


# ============================================================================
# Convenience Functions
# ============================================================================


def log_request_response(logger: logging.Logger, request_id: str, method: str, path: str, status: int, duration: float):
    """
    Log HTTP request/response in structured format.
    
    Useful for API logging and debugging.
    
    Args:
        logger: Logger instance
        request_id: Unique request identifier
        method: HTTP method (GET, POST, etc.)
        path: Request path
        status: HTTP status code
        duration: Request duration in seconds
    
    Example:
        >>> logger = get_logger(__name__)
        >>> log_request_response(logger, "abc123", "POST", "/api/v1/detect-gaps", 200, 0.523)
    """
    logger.info(
        f"{method} {path} {status}",
        extra={
            "request_id": request_id,
            "method": method,
            "path": path,
            "status": status,
            "duration_ms": round(duration * 1000, 2)
        }
    )
