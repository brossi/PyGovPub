"""
Error reporting and logging for PyGovPub SDK.

This module provides structured logging, metrics collection,
and error aggregation capabilities for comprehensive error monitoring.
"""

import inspect
import json
import logging
import os
import sys
import traceback
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union, cast

import structlog
from structlog.stdlib import BoundLogger

from pygovpub.exceptions import (
    ApiErrorSource,
    ErrorCode,
    ErrorContext,
    ErrorSeverity,
    PyGovPubException
)


# Configure structlog
def configure_structured_logging(
    log_level: str = "INFO",
    console_output: bool = True,
    json_output: bool = False,
    log_file: Optional[str] = None
) -> None:
    """
    Configure structured logging for PyGovPub.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        console_output: Whether to output logs to console
        json_output: Whether to format console logs as JSON
        log_file: Path to log file (if None, file logging is disabled)
    """
    # Set up processors
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
    ]
    
    # Configure structlog
    structlog.configure(
        processors=processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # Set up formatter
    if json_output:
        formatter = structlog.stdlib.ProcessorFormatter(
            processor=structlog.processors.JSONRenderer(),
        )
    else:
        formatter = structlog.stdlib.ProcessorFormatter(
            processor=structlog.dev.ConsoleRenderer(colors=True),
        )
    
    # Configure stdlib logging
    handlers = []
    
    # Console handler
    if console_output:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        handlers.append(console_handler)
    
    # File handler
    if log_file:
        # Create directory if it doesn't exist
        log_dir = os.path.dirname(log_file)
        if log_dir:  # Only try to create dir if there is one
            os.makedirs(log_dir, exist_ok=True)
        
        # Create and configure file handler
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)
    
    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        handlers=handlers,
        format="%(message)s",
    )
    
    # Set package logger level
    logging.getLogger("pygovpub").setLevel(getattr(logging, log_level.upper()))


class ErrorReporter:
    """
    Error reporter for tracking and reporting SDK errors.
    
    Provides structured logging, context preservation, and error aggregation
    for comprehensive error monitoring.
    """
    
    def __init__(
        self, 
        logger_name: str = "pygovpub.errors",
        debug_mode: bool = False
    ):
        """Initialize error reporter.
        
        Args:
            logger_name: Name for the logger
            debug_mode: Whether to include detailed debug information
        """
        self.logger = cast(BoundLogger, structlog.get_logger(logger_name))
        self.debug_mode = debug_mode
        self._error_counts: Dict[str, int] = {}
    
    def report_exception(
        self,
        exception: Exception,
        additional_context: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
        source: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Report an exception.
        
        Args:
            exception: The exception to report
            additional_context: Additional context to include
            request_id: Unique request identifier
            source: Source of the error
            
        Returns:
            Error report as a dictionary
        """
        # Generate request ID if not provided
        request_id = request_id or str(uuid.uuid4())
        
        # Get call stack
        frame = inspect.currentframe()
        if frame:
            frame = frame.f_back  # Get caller's frame
        
        # Extract caller information
        caller_info = {}
        if frame:
            caller_info = {
                "file": frame.f_code.co_filename,
                "function": frame.f_code.co_name,
                "line": frame.f_lineno
            }
        
        # Process PyGovPubException specially
        if isinstance(exception, PyGovPubException):
            # Track error count
            error_key = f"{exception.error_code.name}:{exception.status_code}"
            self._error_counts[error_key] = self._error_counts.get(error_key, 0) + 1
            
            # Create error report
            error_report = {
                "request_id": request_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error_code": exception.error_code.name,
                "status_code": exception.status_code,
                "message": exception.message,
                "severity": exception.severity,
                "source": source or getattr(exception.context, "source", None) or "unknown",
                "caller": caller_info
            }
            
            # Add context from exception
            if exception.context:
                error_report["context"] = exception.context.to_dict()
            
            # Add details and suggestions
            if exception.details:
                error_report["details"] = exception.details
            if exception.suggestion:
                error_report["suggestion"] = exception.suggestion
            if exception.recovery_options:
                error_report["recovery_options"] = exception.recovery_options
                
            # Include stack trace in debug mode
            if self.debug_mode:
                error_report["stacktrace"] = traceback.format_exc()
                
            # Add additional context if provided
            if additional_context:
                error_report["additional_context"] = additional_context
                
            # Log the error with structlog
            log_method = self._get_log_method(exception.severity)
            log_method(
                event="exception",
                exception_type=type(exception).__name__,
                **error_report
            )
            
            return error_report
        
        # Handle standard exceptions
        else:
            # Track error counts
            error_key = type(exception).__name__
            self._error_counts[error_key] = self._error_counts.get(error_key, 0) + 1
            
            # Create error report
            error_report = {
                "request_id": request_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error_type": type(exception).__name__,
                "message": str(exception),
                "severity": "error",
                "source": source or "unknown",
                "caller": caller_info
            }
            
            # Include stack trace in debug mode
            if self.debug_mode:
                error_report["stacktrace"] = traceback.format_exc()
                
            # Add additional context if provided
            if additional_context:
                error_report["additional_context"] = additional_context
                
            # Log the error with structlog
            self.logger.error(
                "exception",
                exception_type=type(exception).__name__,
                **error_report
            )
            
            return error_report
    
    def report_error(
        self,
        message: str,
        severity: Union[str, ErrorSeverity] = ErrorSeverity.ERROR,
        error_code: Optional[Union[int, ErrorCode]] = None,
        source: Optional[Union[str, ApiErrorSource]] = None,
        details: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Report an error without an exception.
        
        Args:
            message: Error message
            severity: Error severity
            error_code: Error code
            source: Source of the error
            details: Additional error details
            request_id: Unique request identifier
            
        Returns:
            Error report as a dictionary
        """
        # Generate request ID if not provided
        request_id = request_id or str(uuid.uuid4())
        
        # Convert severity and source to strings if needed
        if isinstance(severity, ErrorSeverity):
            severity = severity.value
        if isinstance(source, ApiErrorSource):
            source = source.value
        if isinstance(error_code, ErrorCode):
            error_code = int(error_code)
            
        # Get caller information
        frame = inspect.currentframe()
        if frame:
            frame = frame.f_back  # Get caller's frame
        
        caller_info = {}
        if frame:
            caller_info = {
                "file": frame.f_code.co_filename,
                "function": frame.f_code.co_name,
                "line": frame.f_lineno
            }
            
        # Create error report
        error_report = {
            "request_id": request_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message": message,
            "severity": severity,
            "source": source or "unknown",
            "caller": caller_info
        }
        
        # Add error code if provided
        if error_code is not None:
            error_report["error_code"] = error_code
            
        # Add details if provided
        if details:
            error_report["details"] = details
            
        # Include stack trace in debug mode
        if self.debug_mode:
            error_report["stacktrace"] = traceback.format_tb(sys._getframe().f_back.f_back.f_back)
            
        # Log the error with structlog
        log_method = self._get_log_method(severity)
        log_method(
            event="error",
            **error_report
        )
        
        # Track error count
        error_key = f"{error_code}:{severity}" if error_code else f"generic:{severity}"
        self._error_counts[error_key] = self._error_counts.get(error_key, 0) + 1
        
        return error_report
    
    def _get_log_method(self, severity: Union[str, ErrorSeverity]) -> Any:
        """Get the appropriate logging method based on severity."""
        if isinstance(severity, ErrorSeverity):
            severity = severity.value
            
        if severity == "critical":
            return self.logger.critical
        elif severity == "error":
            return self.logger.error
        elif severity == "warning":
            return self.logger.warning
        elif severity == "info":
            return self.logger.info
        else:
            return self.logger.debug
    
    def get_error_counts(self) -> Dict[str, int]:
        """Get counts of reported errors by type."""
        return self._error_counts.copy()
    
    def reset_error_counts(self) -> None:
        """Reset error counts."""
        self._error_counts = {}
    
    def set_debug_mode(self, enabled: bool) -> None:
        """Set debug mode status."""
        self.debug_mode = enabled


# Initialize default error reporter
default_error_reporter = ErrorReporter()


def report_exception(
    exception: Exception,
    additional_context: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None,
    source: Optional[str] = None
) -> Dict[str, Any]:
    """
    Report an exception using the default error reporter.
    
    Args:
        exception: The exception to report
        additional_context: Additional context to include
        request_id: Unique request identifier
        source: Source of the error
        
    Returns:
        Error report as a dictionary
    """
    return default_error_reporter.report_exception(
        exception,
        additional_context,
        request_id,
        source
    )


def report_error(
    message: str,
    severity: Union[str, ErrorSeverity] = ErrorSeverity.ERROR,
    error_code: Optional[Union[int, ErrorCode]] = None,
    source: Optional[Union[str, ApiErrorSource]] = None,
    details: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Report an error using the default error reporter.
    
    Args:
        message: Error message
        severity: Error severity
        error_code: Error code
        source: Source of the error
        details: Additional error details
        request_id: Unique request identifier
        
    Returns:
        Error report as a dictionary
    """
    return default_error_reporter.report_error(
        message,
        severity,
        error_code,
        source,
        details,
        request_id
    )


def set_debug_mode(enabled: bool) -> None:
    """Set debug mode for the default error reporter."""
    default_error_reporter.set_debug_mode(enabled)


def get_error_counts() -> Dict[str, int]:
    """Get error counts from the default error reporter."""
    return default_error_reporter.get_error_counts()


def reset_error_counts() -> None:
    """Reset error counts in the default error reporter."""
    default_error_reporter.reset_error_counts()