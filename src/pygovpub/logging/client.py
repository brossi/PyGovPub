"""
HTTP client with integrated logging and debugging features.

This module provides a wrapped HTTP client that automatically logs and times 
requests, handles error reporting, and provides detailed debugging information.
It also includes specialized API logging for tracking rate limits and API status.
"""

import json
import time
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Union, cast

import httpx
import structlog
from structlog.stdlib import BoundLogger

from pygovpub.auth.models import ApiSource
from pygovpub.exceptions import NetworkError, TimeoutError
from pygovpub.logging import LogCategory, bind_context, get_logger
from pygovpub.logging.debug import debug_mode
from pygovpub.logging.performance import timer


class ApiEventType(str, Enum):
    """API event types for logging purposes."""
    
    REQUEST_STARTED = "request_started"
    REQUEST_COMPLETED = "request_completed"
    REQUEST_FAILED = "request_failed"
    RATE_LIMITED = "rate_limited"
    AUTHENTICATION_FAILED = "authentication_failed"
    CACHE_HIT = "cache_hit"
    CACHE_MISS = "cache_miss"
    RETRY_ATTEMPT = "retry_attempt"
    CIRCUIT_BROKEN = "circuit_broken"


class ApiLogger:
    """
    Specialized logger for API interactions.
    
    This logger records API requests, responses, and related events
    with rich context and performance metrics.
    """
    
    def __init__(
        self,
        api_source: Union[str, ApiSource],
        logger_name: Optional[str] = None,
        include_payloads: bool = False,
        include_headers: bool = False,
    ):
        """Initialize API logger.
        
        Args:
            api_source: API source name or enum
            logger_name: Logger name (defaults to pygovpub.api.{api_source})
            include_payloads: Whether to include request/response payloads
            include_headers: Whether to include request/response headers
        """
        # Convert api_source to string if it's an enum
        if isinstance(api_source, ApiSource):
            self.api_source = api_source.value
        else:
            self.api_source = api_source
        
        # Set logger name
        if not logger_name:
            logger_name = f"pygovpub.api.{self.api_source}"
        
        # Get structured logger
        self.logger = cast(BoundLogger, get_logger(logger_name))
        
        # Set configuration
        self.include_payloads = include_payloads
        self.include_headers = include_headers
        
        # Initialize request counters
        self._total_requests = 0
        self._failed_requests = 0
        self._rate_limited_requests = 0
        self._cached_requests = 0
        
        # Initialize timing metrics
        self._total_duration_ms = 0
        self._last_request_time = None
        self._active_requests = 0
        
        # Rate limit tracking
        self._rate_limit_reset = None
        self._rate_limit_remaining = None
        self._rate_limit_total = None
    
    def log_request_start(
        self,
        endpoint: str,
        method: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Any] = None,
        headers: Optional[Dict[str, str]] = None,
        request_id: Optional[str] = None,
    ) -> Optional[str]:
        """
        Log the start of an API request.
        
        Args:
            endpoint: API endpoint path
            method: HTTP method
            params: Query parameters
            data: Request body data
            headers: Request headers
            request_id: Optional request ID (generated if not provided)
            
        Returns:
            Request ID string for correlating logs
        """
        # Generate and bind request context
        from uuid import uuid4
        
        if not request_id:
            request_id = str(uuid4())
        
        # Prepare log data
        log_data = {
            "event": ApiEventType.REQUEST_STARTED,
            "category": LogCategory.API_INTERACTION,
            "api_source": self.api_source,
            "endpoint": endpoint,
            "method": method,
            "request_id": request_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        # Add optional data
        if params and self.include_payloads:
            log_data["params"] = self._sanitize_payload(params)
        
        if data and self.include_payloads:
            log_data["data"] = self._sanitize_payload(data)
        
        if headers and self.include_headers:
            log_data["headers"] = self._sanitize_headers(headers)
        
        # Update metrics
        self._total_requests += 1
        self._active_requests += 1
        self._last_request_time = time.time()
        
        # Log the request
        self.logger.info(**log_data)
        
        return request_id
    
    def log_request_complete(
        self,
        request_id: str,
        status_code: int,
        duration_ms: int,
        response_data: Optional[Any] = None,
        response_headers: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        Log the completion of an API request.
        
        Args:
            request_id: Request ID from log_request_start
            status_code: HTTP status code
            duration_ms: Request duration in milliseconds
            response_data: Response body data
            response_headers: Response headers
        """
        # Prepare log data
        log_data = {
            "event": ApiEventType.REQUEST_COMPLETED,
            "category": LogCategory.API_INTERACTION,
            "request_id": request_id,
            "status_code": status_code,
            "duration_ms": duration_ms,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        # Add optional data
        if response_data and self.include_payloads:
            log_data["response"] = self._sanitize_payload(response_data)
        
        if response_headers and self.include_headers:
            log_data["response_headers"] = self._sanitize_headers(response_headers)
            
            # Extract rate limit information if available
            if "X-RateLimit-Remaining" in response_headers:
                try:
                    self._rate_limit_remaining = int(response_headers["X-RateLimit-Remaining"])
                    log_data["rate_limit_remaining"] = self._rate_limit_remaining
                except (ValueError, TypeError):
                    pass
                
            if "X-RateLimit-Limit" in response_headers:
                try:
                    self._rate_limit_total = int(response_headers["X-RateLimit-Limit"])
                    log_data["rate_limit_total"] = self._rate_limit_total
                except (ValueError, TypeError):
                    pass
                
            if "X-RateLimit-Reset" in response_headers:
                try:
                    reset_time = int(response_headers["X-RateLimit-Reset"])
                    self._rate_limit_reset = datetime.fromtimestamp(reset_time, timezone.utc)
                    log_data["rate_limit_reset"] = self._rate_limit_reset.isoformat()
                except (ValueError, TypeError):
                    pass
        
        # Update metrics
        self._active_requests -= 1
        self._total_duration_ms += duration_ms
        
        # Determine log level based on status code
        if 200 <= status_code < 300:
            # Successful response
            self.logger.info(**log_data)
        elif 300 <= status_code < 400:
            # Redirection
            self.logger.info(**log_data)
        elif status_code == 429:
            # Rate limited
            self._rate_limited_requests += 1
            self.logger.warning(**log_data)
        elif 400 <= status_code < 500:
            # Client error
            self._failed_requests += 1
            self.logger.warning(**log_data)
        else:
            # Server error or unknown
            self._failed_requests += 1
            self.logger.error(**log_data)
    
    def log_request_error(
        self,
        request_id: str,
        error: Exception,
        duration_ms: Optional[int] = None,
    ) -> None:
        """
        Log an API request error.
        
        Args:
            request_id: Request ID from log_request_start
            error: Exception that occurred
            duration_ms: Request duration in milliseconds (optional)
        """
        # Prepare log data
        log_data = {
            "event": ApiEventType.REQUEST_FAILED,
            "category": LogCategory.API_INTERACTION,
            "request_id": request_id,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        # Add duration if available
        if duration_ms is not None:
            log_data["duration_ms"] = duration_ms
            self._total_duration_ms += duration_ms
        
        # Update metrics
        self._active_requests -= 1
        self._failed_requests += 1
        
        # Log the error
        self.logger.error(**log_data, exc_info=error)
    
    def log_cache_event(
        self,
        request_id: str,
        is_hit: bool,
        key: str,
        endpoint: str,
    ) -> None:
        """
        Log a cache hit or miss event.
        
        Args:
            request_id: Request ID for correlation
            is_hit: Whether the cache was hit
            key: Cache key
            endpoint: API endpoint
        """
        event_type = ApiEventType.CACHE_HIT if is_hit else ApiEventType.CACHE_MISS
        
        # Prepare log data
        log_data = {
            "event": event_type,
            "category": LogCategory.API_INTERACTION,
            "request_id": request_id,
            "cache_key": key,
            "endpoint": endpoint,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        # Update metrics
        if is_hit:
            self._cached_requests += 1
        
        # Log the event
        self.logger.debug(**log_data)
    
    def log_rate_limit(
        self,
        request_id: str,
        endpoint: str,
        reset_time: Optional[datetime] = None,
        retry_after: Optional[int] = None,
    ) -> None:
        """
        Log a rate limit event.
        
        Args:
            request_id: Request ID for correlation
            endpoint: API endpoint that was rate limited
            reset_time: When the rate limit resets
            retry_after: Seconds to wait before retrying
        """
        # Prepare log data
        log_data = {
            "event": ApiEventType.RATE_LIMITED,
            "category": LogCategory.API_INTERACTION,
            "request_id": request_id,
            "endpoint": endpoint,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        # Add reset time if available
        if reset_time:
            log_data["reset_time"] = reset_time.isoformat()
            self._rate_limit_reset = reset_time
        
        # Add retry_after if available
        if retry_after:
            log_data["retry_after"] = retry_after
        
        # Update metrics
        self._rate_limited_requests += 1
        
        # Log the event
        self.logger.warning(**log_data)
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get API client metrics.
        
        Returns:
            Dictionary of metrics
        """
        metrics = {
            "total_requests": self._total_requests,
            "failed_requests": self._failed_requests,
            "rate_limited_requests": self._rate_limited_requests,
            "cached_requests": self._cached_requests,
            "active_requests": self._active_requests,
        }
        
        # Calculate average duration if we have requests
        if self._total_requests > 0:
            metrics["avg_duration_ms"] = round(self._total_duration_ms / self._total_requests, 2)
        
        # Add rate limit info if available
        if self._rate_limit_remaining is not None:
            metrics["rate_limit_remaining"] = self._rate_limit_remaining
        
        if self._rate_limit_total is not None:
            metrics["rate_limit_total"] = self._rate_limit_total
        
        if self._rate_limit_reset:
            metrics["rate_limit_reset"] = self._rate_limit_reset.isoformat()
            
            # Add time until reset
            now = datetime.now(timezone.utc)
            if now < self._rate_limit_reset:
                delta = self._rate_limit_reset - now
                metrics["seconds_until_reset"] = delta.total_seconds()
        
        return metrics
    
    def _sanitize_payload(self, payload: Any) -> Any:
        """
        Sanitize payload data for logging.
        
        This method removes sensitive information and truncates large payloads.
        
        Args:
            payload: Payload data
            
        Returns:
            Sanitized payload
        """
        # Convert to string for simple sanitization
        if isinstance(payload, (dict, list)):
            try:
                # Make a copy to avoid modifying the original
                payload_copy = json.loads(json.dumps(payload))
                
                # Sanitize sensitive fields
                if isinstance(payload_copy, dict):
                    for key in list(payload_copy.keys()):
                        # Remove API keys or tokens
                        if any(sensitive in key.lower() for sensitive in ("api_key", "token", "secret", "password", "auth")):
                            payload_copy[key] = "[REDACTED]"
                
                return payload_copy
            except (TypeError, json.JSONDecodeError):
                # Fall back to string representation if JSON serialization fails
                return str(payload)
        
        return payload
    
    def _sanitize_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        """
        Sanitize HTTP headers for logging.
        
        This method removes sensitive information from headers.
        
        Args:
            headers: HTTP headers
            
        Returns:
            Sanitized headers
        """
        # Make a copy to avoid modifying the original
        sanitized = headers.copy()
        
        # Redact sensitive headers
        sensitive_headers = [
            "Authorization", "X-Api-Key", "Api-Key", "Token",
            "Cookie", "Set-Cookie"
        ]
        
        for header in sensitive_headers:
            if header in sanitized:
                sanitized[header] = "[REDACTED]"
            
            # Case-insensitive check
            for key in list(sanitized.keys()):
                if key.lower() == header.lower() and key != header:
                    sanitized[key] = "[REDACTED]"
        
        return sanitized


# Global dictionary of API loggers, keyed by api_source
_api_loggers: Dict[str, ApiLogger] = {}


def get_api_logger(
    api_source: Union[str, ApiSource],
    include_payloads: bool = False,
    include_headers: bool = False,
) -> ApiLogger:
    """
    Get an API logger for the specified API source.
    
    This function returns a cached logger if one exists,
    or creates a new one if needed.
    
    Args:
        api_source: API source name or enum
        include_payloads: Whether to include request/response payloads
        include_headers: Whether to include request/response headers
        
    Returns:
        API logger instance
    """
    # Convert api_source to string if it's an enum
    if isinstance(api_source, ApiSource):
        api_source_str = api_source.value
    else:
        api_source_str = api_source
    
    # Create logger if it doesn't exist
    if api_source_str not in _api_loggers:
        _api_loggers[api_source_str] = ApiLogger(
            api_source=api_source_str,
            include_payloads=include_payloads,
            include_headers=include_headers,
        )
    
    return _api_loggers[api_source_str]


def get_all_api_metrics() -> Dict[str, Dict[str, Any]]:
    """
    Get metrics for all API clients.
    
    Returns:
        Dictionary of API metrics, keyed by API source
    """
    return {source: logger.get_metrics() for source, logger in _api_loggers.items()}


class LoggingClient:
    """
    HTTP client with built-in logging, tracing, and error handling.
    
    This class wraps httpx.Client to add comprehensive logging,
    performance tracking, and debugging functionality.
    """
    
    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: Union[float, httpx.Timeout] = 30.0,
        headers: Optional[Dict[str, str]] = None,
        verify: bool = True,
        logger_name: str = "pygovpub.http.client",
        api_source: Optional[Union[str, ApiSource]] = None,
    ):
        """
        Initialize the logging client.
        
        Args:
            base_url: Base URL for all requests
            timeout: Default request timeout in seconds
            headers: Default headers for all requests
            verify: Whether to verify SSL certificates
            logger_name: Name for the logger
            api_source: API source for specialized logging (optional)
        """
        self.base_url = base_url
        self.timeout = timeout
        self.headers = headers or {}
        self.verify = verify
        self.logger = get_logger(logger_name)
        
        # Set up API logging if api_source is provided
        self.api_source = api_source
        self.api_logger = None
        
        if api_source:
            self.api_logger = get_api_logger(api_source)
        
        # Create httpx client
        self.client = httpx.Client(
            base_url=base_url,
            timeout=timeout,
            headers=headers,
            verify=verify,
        )
    
    def request(
        self,
        method: str,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        data: Optional[Any] = None,
        timeout: Optional[Union[float, httpx.Timeout]] = None,
    ) -> httpx.Response:
        """
        Send an HTTP request with logging and error handling.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            url: Request URL
            params: URL parameters
            headers: HTTP headers
            json_data: JSON data (will be serialized)
            data: Request body
            timeout: Request timeout (overrides client default)
            
        Returns:
            HTTP response
            
        Raises:
            NetworkError: For connection errors
            TimeoutError: For request timeouts
            TransportError: For other transport errors
        """
        # Merge headers
        merged_headers = {**self.headers}
        if headers:
            merged_headers.update(headers)
        
        # Log the request
        self.logger.debug(
            "http_request",
            category=LogCategory.API_INTERACTION,
            method=method,
            url=url,
            params=params,
        )
        
        # Log API request if api_logger is available
        api_request_id = None
        if self.api_logger:
            api_request_id = self.api_logger.log_request_start(
                endpoint=url,
                method=method,
                params=params,
                data=json_data or data,
                headers=merged_headers,
            )
        
        # Capture request details for debugging
        debug_mode.capture_request(
            method=method,
            url=str(url),
            headers=merged_headers,
            data=json_data or data,
            params=params,
        )
        
        start_time = time.perf_counter()
        
        try:
            # Time the request
            with timer(f"http_{method.lower()}", extra_context={"url": url}):
                response = self.client.request(
                    method=method,
                    url=url,
                    params=params,
                    headers=merged_headers,
                    json=json_data,
                    data=data,
                    timeout=timeout or self.timeout,
                )
                
            # Calculate elapsed time
            elapsed = time.perf_counter() - start_time
            elapsed_ms = int(elapsed * 1000)
            
            # Log response details
            self.logger.debug(
                "http_response",
                category=LogCategory.API_INTERACTION,
                method=method,
                url=url,
                status_code=response.status_code,
                elapsed_ms=elapsed_ms,
            )
            
            # Log API response if api_logger is available
            if self.api_logger and api_request_id:
                # Try to parse response data
                response_data = None
                if response.headers.get("content-type", "").startswith("application/json"):
                    try:
                        response_data = response.json()
                    except Exception:
                        pass
                
                self.api_logger.log_request_complete(
                    request_id=api_request_id,
                    status_code=response.status_code,
                    duration_ms=elapsed_ms,
                    response_data=response_data,
                    response_headers=dict(response.headers),
                )
                
                # Special handling for rate limits (status code 429)
                if response.status_code == 429:
                    # Try to extract retry-after header
                    retry_after = None
                    if "retry-after" in response.headers:
                        try:
                            retry_after = int(response.headers["retry-after"])
                        except (ValueError, TypeError):
                            pass
                    
                    # Calculate reset time
                    reset_time = None
                    if retry_after:
                        reset_time = datetime.now(timezone.utc) + timedelta(seconds=retry_after)
                    
                    self.api_logger.log_rate_limit(
                        request_id=api_request_id,
                        endpoint=url,
                        reset_time=reset_time,
                        retry_after=retry_after,
                    )
            
            # Capture response for debugging
            debug_mode.capture_response(
                status_code=response.status_code,
                headers=dict(response.headers),
                content=response.content,
                elapsed=elapsed,
            )
            
            return response
            
        except httpx.TimeoutException as e:
            # Handle timeout errors
            elapsed = time.perf_counter() - start_time
            elapsed_ms = int(elapsed * 1000)
            
            timeout_seconds = timeout or (
                self.timeout if isinstance(self.timeout, (int, float)) 
                else self.timeout.connect
            )
            
            self.logger.error(
                "http_timeout",
                category=LogCategory.API_INTERACTION,
                method=method,
                url=url,
                timeout_seconds=timeout_seconds,
                elapsed_seconds=elapsed,
                error=str(e),
            )
            
            # Log API error if api_logger is available
            if self.api_logger and api_request_id:
                self.api_logger.log_request_error(
                    request_id=api_request_id,
                    error=e,
                    duration_ms=elapsed_ms,
                )
            
            # Convert to our exception type
            raise TimeoutError(
                f"Request timed out: {method} {url}",
                timeout_seconds=timeout_seconds,
            ) from e
            
        except httpx.NetworkError as e:
            # Handle network errors
            elapsed = time.perf_counter() - start_time
            elapsed_ms = int(elapsed * 1000)
            
            self.logger.error(
                "http_network_error",
                category=LogCategory.API_INTERACTION,
                method=method,
                url=url,
                error=str(e),
            )
            
            # Log API error if api_logger is available
            if self.api_logger and api_request_id:
                self.api_logger.log_request_error(
                    request_id=api_request_id,
                    error=e,
                    duration_ms=elapsed_ms,
                )
            
            # Convert to our exception type
            raise NetworkError(
                f"Network error: {method} {url} - {str(e)}",
            ) from e
    
    def get(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, Any]] = None,
        timeout: Optional[Union[float, httpx.Timeout]] = None,
    ) -> httpx.Response:
        """
        Send a GET request.
        
        Args:
            url: Request URL
            params: URL parameters
            headers: HTTP headers
            timeout: Request timeout
            
        Returns:
            HTTP response
        """
        return self.request(
            method="GET",
            url=url,
            params=params,
            headers=headers,
            timeout=timeout,
        )
    
    def post(
        self,
        url: str,
        json_data: Optional[Dict[str, Any]] = None,
        data: Optional[Any] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, Any]] = None,
        timeout: Optional[Union[float, httpx.Timeout]] = None,
    ) -> httpx.Response:
        """
        Send a POST request.
        
        Args:
            url: Request URL
            json_data: JSON data
            data: Form data
            params: URL parameters
            headers: HTTP headers
            timeout: Request timeout
            
        Returns:
            HTTP response
        """
        return self.request(
            method="POST",
            url=url,
            json_data=json_data,
            data=data,
            params=params,
            headers=headers,
            timeout=timeout,
        )
    
    def put(
        self,
        url: str,
        json_data: Optional[Dict[str, Any]] = None,
        data: Optional[Any] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, Any]] = None,
        timeout: Optional[Union[float, httpx.Timeout]] = None,
    ) -> httpx.Response:
        """
        Send a PUT request.
        
        Args:
            url: Request URL
            json_data: JSON data
            data: Form data
            params: URL parameters
            headers: HTTP headers
            timeout: Request timeout
            
        Returns:
            HTTP response
        """
        return self.request(
            method="PUT",
            url=url,
            json_data=json_data,
            data=data,
            params=params,
            headers=headers,
            timeout=timeout,
        )
    
    def delete(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, Any]] = None,
        timeout: Optional[Union[float, httpx.Timeout]] = None,
    ) -> httpx.Response:
        """
        Send a DELETE request.
        
        Args:
            url: Request URL
            params: URL parameters
            headers: HTTP headers
            timeout: Request timeout
            
        Returns:
            HTTP response
        """
        return self.request(
            method="DELETE",
            url=url,
            params=params,
            headers=headers,
            timeout=timeout,
        )
    
    def close(self) -> None:
        """Close the underlying HTTP client."""
        self.client.close()
    
    def __enter__(self) -> "LoggingClient":
        """Enter context manager."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context manager and close client."""
        self.close()