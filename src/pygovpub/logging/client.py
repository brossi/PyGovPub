"""
HTTP client with integrated logging and debugging features.

This module provides a wrapped HTTP client that automatically logs and times 
requests, handles error reporting, and provides detailed debugging information.
"""

import json
import time
from typing import Any, Dict, Optional, Union

import httpx

from pygovpub.exceptions import NetworkError, TimeoutError
from pygovpub.logging import LogCategory, get_logger
from pygovpub.logging.debug import debug_mode
from pygovpub.logging.performance import timer


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
    ):
        """
        Initialize the logging client.
        
        Args:
            base_url: Base URL for all requests
            timeout: Default request timeout in seconds
            headers: Default headers for all requests
            verify: Whether to verify SSL certificates
            logger_name: Name for the logger
        """
        self.base_url = base_url
        self.timeout = timeout
        self.headers = headers or {}
        self.verify = verify
        self.logger = get_logger(logger_name)
        
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
        except httpx.TimeoutException as e:
            # Handle timeout errors
            elapsed = time.perf_counter() - start_time
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
            
            # Convert to our exception type
            raise TimeoutError(
                f"Request timed out: {method} {url}",
                timeout_seconds=timeout_seconds,
            ) from e
            
        except httpx.NetworkError as e:
            # Handle network errors
            self.logger.error(
                "http_network_error",
                category=LogCategory.API_INTERACTION,
                method=method,
                url=url,
                error=str(e),
            )
            
            # Convert to our exception type
            raise NetworkError(
                f"Network error: {method} {url} - {str(e)}",
            ) from e
        
        # Calculate elapsed time
        elapsed = time.perf_counter() - start_time
        
        # Log response details
        self.logger.debug(
            "http_response",
            category=LogCategory.API_INTERACTION,
            method=method,
            url=url,
            status_code=response.status_code,
            elapsed_ms=elapsed * 1000,
        )
        
        # Capture response for debugging
        debug_mode.capture_response(
            status_code=response.status_code,
            headers=dict(response.headers),
            content=response.content,
            elapsed=elapsed,
        )
        
        return response
    
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