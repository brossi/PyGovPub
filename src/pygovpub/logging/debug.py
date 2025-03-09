"""
Debug features for PyGovPub SDK.

This module provides debug tools and utilities for capturing 
detailed information about SDK operations for troubleshooting.
"""

import functools
import inspect
import json
import os
import pprint
import sys
import traceback
from contextlib import contextmanager
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, TextIO, Union

from pygovpub.logging import LogLevel, get_logger


class DebugLevel(Enum):
    """Debug levels for controlling verbosity."""
    
    NONE = 0      # No debug output
    BASIC = 1     # Basic information
    DETAILED = 2  # Detailed information
    TRACE = 3     # Full trace with all details
    DEV = 4       # Developer debug mode


class DebugMode:
    """Controls debug mode settings throughout the SDK."""
    
    def __init__(self, level: Union[DebugLevel, int] = DebugLevel.NONE):
        """
        Initialize the debug mode controller.
        
        Args:
            level: Initial debug level
        """
        self.level = level if isinstance(level, DebugLevel) else DebugLevel(level)
        self._enabled_categories: Set[str] = set()
        self._output: TextIO = sys.stdout
        self._file_output: Optional[TextIO] = None
        self.logger = get_logger("pygovpub.debug")
    
    def set_level(self, level: Union[DebugLevel, int]) -> None:
        """
        Set the debug level.
        
        Args:
            level: Debug level to set
        """
        self.level = level if isinstance(level, DebugLevel) else DebugLevel(level)
        self.logger.info(
            "debug_level_changed",
            level=self.level.name,
        )
    
    def enable_category(self, category: str) -> None:
        """
        Enable debugging for a specific category.
        
        Args:
            category: Category to enable
        """
        self._enabled_categories.add(category)
        self.logger.info(
            "debug_category_enabled",
            category=category,
        )
    
    def disable_category(self, category: str) -> None:
        """
        Disable debugging for a specific category.
        
        Args:
            category: Category to disable
        """
        if category in self._enabled_categories:
            self._enabled_categories.remove(category)
            self.logger.info(
                "debug_category_disabled",
                category=category,
            )
    
    def is_category_enabled(self, category: str) -> bool:
        """
        Check if a category is enabled for debugging.
        
        Args:
            category: Category to check
            
        Returns:
            True if the category is enabled
        """
        return category in self._enabled_categories
    
    def set_output(self, output: Union[TextIO, str]) -> None:
        """
        Set the output destination for debug information.
        
        Args:
            output: Output stream or file path
        """
        if isinstance(output, str):
            # Close previous file if any
            if self._file_output:
                self._file_output.close()
            
            # Create directory if needed
            directory = os.path.dirname(output)
            if directory and not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)
            
            # Open file for writing
            self._file_output = open(output, "a")
            self._output = self._file_output
        else:
            # Use provided stream
            self._output = output
        
        self.logger.info(
            "debug_output_changed",
            output=str(output),
        )
    
    def is_enabled(self, required_level: Union[DebugLevel, int] = DebugLevel.BASIC) -> bool:
        """
        Check if debug mode is enabled at the specified level.
        
        Args:
            required_level: Minimum level required
            
        Returns:
            True if debug is enabled at the required level
        """
        required = required_level if isinstance(required_level, DebugLevel) else DebugLevel(required_level)
        return self.level.value >= required.value
    
    def log(
        self,
        message: str,
        category: Optional[str] = None,
        level: Union[DebugLevel, int] = DebugLevel.BASIC,
        data: Optional[Any] = None,
    ) -> None:
        """
        Log a debug message if the current level permits.
        
        Args:
            message: Debug message
            category: Debug category
            level: Required debug level
            data: Additional data to include
        """
        # Check if this message should be logged
        required = level if isinstance(level, DebugLevel) else DebugLevel(level)
        
        if self.level.value < required.value:
            return
        
        if category and not self.is_category_enabled(category):
            return
        
        # Format timestamp
        timestamp = datetime.now(timezone.utc).isoformat()
        
        # Format message
        output_parts = [f"[{timestamp}] [DEBUG] [{self.level.name}]"]
        
        if category:
            output_parts.append(f"[{category}]")
        
        output_parts.append(message)
        
        # Add data if provided
        data_str = ""
        if data is not None:
            try:
                if isinstance(data, (dict, list, tuple)):
                    data_str = "\n" + pprint.pformat(data)
                else:
                    data_str = "\n" + str(data)
            except Exception as e:
                data_str = f"\n[Error formatting data: {e}]"
        
        # Write to output
        self._output.write(" ".join(output_parts) + data_str + "\n")
        self._output.flush()
    
    def capture_request(
        self,
        method: str,
        url: str,
        headers: Dict[str, str],
        data: Optional[Any] = None,
        params: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        Capture details of an outgoing HTTP request.
        
        Args:
            method: HTTP method
            url: Request URL
            headers: HTTP headers
            data: Request body
            params: URL parameters
        """
        if not self.is_enabled(DebugLevel.DETAILED):
            return
        
        # Create a safe copy of headers without sensitive data
        safe_headers = {}
        sensitive_headers = {'authorization', 'x-api-key', 'cookie'}
        
        for key, value in headers.items():
            if key.lower() in sensitive_headers:
                safe_headers[key] = "[REDACTED]"
            else:
                safe_headers[key] = value
        
        # Capture request details
        request_info = {
            "method": method,
            "url": url,
            "headers": safe_headers,
            "params": params,
        }
        
        # Include data if debug level is high enough
        if self.is_enabled(DebugLevel.TRACE) and data:
            try:
                # Try to represent data as string
                if isinstance(data, (dict, list)):
                    request_info["data"] = data
                elif isinstance(data, bytes):
                    # Try to decode as JSON
                    try:
                        request_info["data"] = json.loads(data.decode("utf-8"))
                    except:
                        # Fall back to string representation
                        request_info["data"] = data.decode("utf-8", errors="replace")
                else:
                    request_info["data"] = str(data)
            except Exception as e:
                request_info["data"] = f"[Error capturing data: {e}]"
        
        self.log(
            "Outgoing HTTP Request",
            category="http",
            level=DebugLevel.DETAILED,
            data=request_info,
        )
    
    def capture_response(
        self,
        status_code: int,
        headers: Dict[str, str],
        content: Optional[Any] = None,
        elapsed: Optional[float] = None,
    ) -> None:
        """
        Capture details of an HTTP response.
        
        Args:
            status_code: HTTP status code
            headers: Response headers
            content: Response content
            elapsed: Response time in seconds
        """
        if not self.is_enabled(DebugLevel.DETAILED):
            return
        
        # Capture response details
        response_info = {
            "status_code": status_code,
            "headers": dict(headers),
        }
        
        if elapsed is not None:
            response_info["elapsed_ms"] = elapsed * 1000
        
        # Include content if debug level is high enough
        if self.is_enabled(DebugLevel.TRACE) and content:
            try:
                # Try to represent content as JSON or string
                if isinstance(content, (dict, list)):
                    response_info["content"] = content
                elif isinstance(content, bytes):
                    # Try to decode as JSON
                    try:
                        response_info["content"] = json.loads(content.decode("utf-8"))
                    except:
                        # Fall back to string representation if < 10KB
                        if len(content) < 10240:
                            response_info["content"] = content.decode("utf-8", errors="replace")
                        else:
                            response_info["content"] = f"[{len(content)} bytes]"
                else:
                    # String representation for other types
                    response_info["content"] = str(content)
            except Exception as e:
                response_info["content"] = f"[Error capturing content: {e}]"
        
        self.log(
            f"HTTP Response: {status_code}",
            category="http",
            level=DebugLevel.DETAILED,
            data=response_info,
        )
    
    def capture_exception(
        self,
        exception: Exception,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Capture details of an exception.
        
        Args:
            exception: The exception to capture
            context: Additional context information
        """
        if not self.is_enabled(DebugLevel.BASIC):
            return
        
        # Get traceback
        tb = traceback.format_exception(
            type(exception),
            exception,
            exception.__traceback__
        )
        
        # Capture exception details
        exception_info = {
            "type": type(exception).__name__,
            "message": str(exception),
            "traceback": "".join(tb),
        }
        
        if context:
            exception_info["context"] = context
        
        self.log(
            f"Exception: {type(exception).__name__}",
            category="error",
            level=DebugLevel.BASIC,
            data=exception_info,
        )
    
    def capture_call(
        self,
        func: Callable,
        args: tuple,
        kwargs: Dict[str, Any],
        result: Optional[Any] = None,
        exception: Optional[Exception] = None,
        duration_ms: Optional[float] = None,
    ) -> None:
        """
        Capture details of a function call.
        
        Args:
            func: Function that was called
            args: Positional arguments
            kwargs: Keyword arguments
            result: Function result (if successful)
            exception: Exception (if failed)
            duration_ms: Call duration in milliseconds
        """
        if not self.is_enabled(DebugLevel.TRACE):
            return
        
        # Get function information
        module = func.__module__
        qualname = func.__qualname__
        
        # Try to get source code location
        try:
            source_file = inspect.getsourcefile(func)
            source_line = inspect.getsourcelines(func)[1]
            location = f"{source_file}:{source_line}"
        except (TypeError, OSError):
            location = "unknown"
        
        # Capture call details
        call_info = {
            "function": f"{module}.{qualname}",
            "location": location,
        }
        
        # Add timing if available
        if duration_ms is not None:
            call_info["duration_ms"] = duration_ms
        
        # Add arguments if trace level
        if self.is_enabled(DebugLevel.TRACE):
            # Convert arguments to safe representations
            safe_args = []
            for arg in args:
                if hasattr(arg, '__dict__'):
                    safe_args.append(f"{type(arg).__name__}")
                else:
                    safe_args.append(arg)
            
            safe_kwargs = {}
            for key, value in kwargs.items():
                if hasattr(value, '__dict__'):
                    safe_kwargs[key] = f"{type(value).__name__}"
                else:
                    safe_kwargs[key] = value
            
            call_info["args"] = safe_args
            call_info["kwargs"] = safe_kwargs
        
        # Add result or exception
        if exception:
            call_info["status"] = "error"
            call_info["error"] = {
                "type": type(exception).__name__,
                "message": str(exception),
            }
        else:
            call_info["status"] = "success"
            
            # Only include result in DEV level
            if result is not None and self.is_enabled(DebugLevel.DEV):
                try:
                    if isinstance(result, (dict, list, tuple)):
                        call_info["result"] = result
                    elif hasattr(result, '__dict__'):
                        call_info["result"] = f"{type(result).__name__}"
                    else:
                        call_info["result"] = str(result)
                except Exception as e:
                    call_info["result"] = f"[Error capturing result: {e}]"
        
        self.log(
            f"Function Call: {qualname}",
            category="function",
            level=DebugLevel.TRACE,
            data=call_info,
        )


# Global debug mode controller
debug_mode = DebugMode()


@contextmanager
def debug_context(level: Union[DebugLevel, int] = DebugLevel.DETAILED):
    """
    Context manager for temporarily setting a debug level.
    
    Args:
        level: Debug level to use within the context
        
    Yields:
        None
    """
    # Save current level
    previous_level = debug_mode.level
    
    try:
        # Set new level
        debug_mode.set_level(level)
        yield
    finally:
        # Restore previous level
        debug_mode.set_level(previous_level)


def debug_function(
    level: Union[DebugLevel, int] = DebugLevel.DETAILED,
    log_args: bool = True,
    log_result: bool = True,
) -> Callable:
    """
    Decorator for debugging function calls.
    
    Args:
        level: Debug level required to log this function
        log_args: Whether to log function arguments
        log_result: Whether to log function result
        
    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Skip if debug level is not high enough
            required = level if isinstance(level, DebugLevel) else DebugLevel(level)
            if debug_mode.level.value < required.value:
                return func(*args, **kwargs)
            
            # Record start time
            import time
            start_time = time.perf_counter()
            
            # Prepare call information
            result = None
            exception = None
            duration_ms = None
            
            try:
                # Call the function
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                exception = e
                raise
            finally:
                # Calculate duration
                duration_ms = (time.perf_counter() - start_time) * 1000
                
                # Capture call details
                debug_mode.capture_call(
                    func=func,
                    args=args if log_args else (),
                    kwargs=kwargs if log_args else {},
                    result=result if log_result else None,
                    exception=exception,
                    duration_ms=duration_ms,
                )
        
        return wrapper
    
    return decorator