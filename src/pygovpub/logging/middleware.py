"""
FastAPI middleware for request logging and tracing.

This module provides middleware components for FastAPI applications
to enable request logging, distributed tracing, and performance monitoring.
"""

import time
import uuid
from typing import Any, Callable, Dict, Optional, Union

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from pygovpub.logging import LogCategory, LogLevel, bind_context, clear_context, get_logger


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for logging HTTP requests and responses.
    
    This middleware:
    - Generates or propagates trace IDs
    - Measures request duration
    - Logs request and response details
    - Captures exceptions
    - Binds trace context to all loggers during the request
    """
    
    def __init__(
        self,
        app: ASGIApp,
        exclude_paths: Optional[list[str]] = None,
        trace_header: str = "X-Trace-ID",
        exclude_headers: Optional[list[str]] = None,
        log_request_body: bool = False,
        log_response_body: bool = False,
    ):
        """
        Initialize the middleware.
        
        Args:
            app: The ASGI application
            exclude_paths: Paths to exclude from logging (e.g. ["/health"])
            trace_header: Header name for trace ID
            exclude_headers: Headers to exclude from logs (for privacy)
            log_request_body: Whether to log request bodies
            log_response_body: Whether to log response bodies
        """
        super().__init__(app)
        self.exclude_paths = exclude_paths or []
        self.trace_header = trace_header
        self.exclude_headers = exclude_headers or ["authorization", "cookie", "x-api-key"]
        self.log_request_body = log_request_body
        self.log_response_body = log_response_body
        self.logger = get_logger("pygovpub.http")
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process the request, log details, and measure performance.
        
        Args:
            request: The incoming request
            call_next: Function to call the next middleware or route handler
            
        Returns:
            The response from the next middleware or route handler
        """
        # Skip excluded paths
        if any(request.url.path.startswith(path) for path in self.exclude_paths):
            return await call_next(request)
        
        # Get or generate trace ID
        trace_id = request.headers.get(self.trace_header)
        if not trace_id:
            trace_id = str(uuid.uuid4())
        
        # Record start time
        start_time = time.perf_counter()
        
        # Clear any existing context
        clear_context()
        
        # Bind trace ID and request info to the context
        bind_context(
            trace_id=trace_id,
            http_method=request.method,
            path=request.url.path,
            client_host=request.client.host if request.client else None,
            query_params=dict(request.query_params) if request.query_params else None,
        )
        
        # Log the request
        self.logger.info(
            "request_started",
            category=LogCategory.API_INTERACTION,
        )
        
        # Process the request and catch exceptions
        status_code = 500
        exception_details = None
        
        try:
            # Execute the request
            response = await call_next(request)
            status_code = response.status_code
            return response
            
        except Exception as e:
            # Log the exception
            exception_details = {
                "type": type(e).__name__,
                "message": str(e),
            }
            self.logger.error(
                "request_failed",
                category=LogCategory.API_INTERACTION,
                exception=exception_details,
                exc_info=True,
            )
            # Re-raise to allow FastAPI's exception handlers to process it
            raise
            
        finally:
            # Calculate duration
            duration_ms = (time.perf_counter() - start_time) * 1000
            
            # Log request completion
            self.logger.info(
                "request_completed",
                category=LogCategory.API_INTERACTION,
                duration_ms=duration_ms,
                status_code=status_code,
                exception=exception_details,
            )
            
            # Clear context
            clear_context()


def add_logging_middleware(
    app: FastAPI,
    exclude_paths: Optional[list[str]] = None,
    trace_header: str = "X-Trace-ID",
    exclude_headers: Optional[list[str]] = None,
    log_request_body: bool = False,
    log_response_body: bool = False,
) -> None:
    """
    Add logging middleware to a FastAPI application.
    
    Helper function to add the RequestLoggingMiddleware to a FastAPI app.
    
    Args:
        app: FastAPI application
        exclude_paths: Paths to exclude from logging (e.g. ["/health"])
        trace_header: Header name for trace ID
        exclude_headers: Headers to exclude from logs (for privacy)
        log_request_body: Whether to log request bodies
        log_response_body: Whether to log response bodies
    """
    app.add_middleware(
        RequestLoggingMiddleware,
        exclude_paths=exclude_paths,
        trace_header=trace_header,
        exclude_headers=exclude_headers,
        log_request_body=log_request_body,
        log_response_body=log_response_body,
    )