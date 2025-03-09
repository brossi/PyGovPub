"""
Logging module for PyGovPub SDK.

This module provides structured logging, context propagation, and integration
with Python's standard logging system. It's designed to enable distributed tracing
and comprehensive monitoring for all SDK operations.
"""

import enum
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

import structlog
from structlog.contextvars import bind_contextvars, clear_contextvars, merge_contextvars
from structlog.stdlib import BoundLogger

# Initialize the logger with basic configuration
# Will be properly configured when configure_logging is called
logger = structlog.get_logger()


class LogLevel(enum.IntEnum):
    """Numeric log levels matching Python's standard logging."""
    
    DEBUG = logging.DEBUG        # 10
    INFO = logging.INFO          # 20
    WARNING = logging.WARNING    # 30
    ERROR = logging.ERROR        # 40
    CRITICAL = logging.CRITICAL  # 50


class LogCategory(str, enum.Enum):
    """Log categories for system-wide use."""
    
    API_INTERACTION = "api"       # API request/response tracking
    SYNC = "sync"                # Data synchronization operations
    AUTH = "auth"                # Authentication events
    DOCUMENT = "document"        # Document processing
    PERFORMANCE = "perf"         # Performance metrics
    SECURITY = "security"        # Security events
    SYSTEM = "system"            # General system operations


def configure_logging(
    log_level: Union[str, int] = "INFO",
    console_output: bool = True,
    json_format: bool = False,
    log_file: Optional[str] = None,
    handlers: Optional[List[logging.Handler]] = None,
) -> None:
    """
    Configure structured logging for PyGovPub.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL or numeric values)
        console_output: Whether to output logs to console
        json_format: Whether to format logs as JSON
        log_file: Path to log file (if None, file logging is disabled)
        handlers: Optional list of handlers to use instead of default handlers
    """
    # Convert string log level to numeric if needed
    if isinstance(log_level, str):
        numeric_level = getattr(logging, log_level.upper(), None)
        if not isinstance(numeric_level, int):
            raise ValueError(f"Invalid log level: {log_level}")
        log_level = numeric_level

    # Define processors
    processors = [
        # Add contextual information
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        # Add special handling for stdlib logging
        structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
    ]

    # Configure structlog
    structlog.configure(
        processors=processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Create handlers if not provided
    if handlers is None:
        handlers = []
        
        # Console handler
        if console_output:
            console_handler = logging.StreamHandler(sys.stdout)
            handlers.append(console_handler)
        
        # File handler
        if log_file:
            import os
            
            # Create directory if it doesn't exist
            log_dir = os.path.dirname(log_file)
            if log_dir:
                os.makedirs(log_dir, exist_ok=True)
            
            file_handler = logging.FileHandler(log_file)
            handlers.append(file_handler)

    # Create formatter based on format type
    if json_format:
        formatter = structlog.stdlib.ProcessorFormatter(
            # Format as JSON with all information
            processor=structlog.processors.JSONRenderer(),
        )
    else:
        # Use colorful console output in development
        formatter = structlog.stdlib.ProcessorFormatter(
            # Format with colors and better readable output
            processor=structlog.dev.ConsoleRenderer(colors=True),
        )

    # Apply formatter to all handlers
    for handler in handlers:
        handler.setFormatter(formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Add new handlers
    for handler in handlers:
        root_logger.addHandler(handler)
    
    # Set package logger level
    logging.getLogger("pygovpub").setLevel(log_level)


def get_logger(name: str) -> BoundLogger:
    """
    Get a logger instance with the given name.
    
    Args:
        name: Name of the logger
        
    Returns:
        A structured logger bound to the given name
    """
    return structlog.get_logger(name)


def bind_context(**kwargs) -> None:
    """
    Bind key-value pairs to the current context.
    
    The bound values will be included in all subsequent log entries
    until they are cleared or overwritten.
    
    Args:
        **kwargs: Key-value pairs to bind to the context
    """
    bind_contextvars(**kwargs)


def clear_context() -> None:
    """Clear all bound context variables."""
    clear_contextvars()