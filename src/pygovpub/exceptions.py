"""
Custom exceptions for PyGovPub SDK.

This module defines the exception hierarchy for the SDK, enabling consistent
error handling and appropriate status code mapping for API responses.
"""

from typing import Any, Dict, Optional


class PyGovPubException(Exception):
    """Base exception for all PyGovPub errors."""
    
    status_code: int = 500
    
    def __init__(
        self, 
        message: str, 
        status_code: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """Initialize the exception.
        
        Args:
            message: Error message
            status_code: HTTP status code (optional)
            details: Additional error details (optional)
        """
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class ConfigurationError(PyGovPubException):
    """Error in SDK configuration."""
    
    status_code = 500


class AuthenticationError(PyGovPubException):
    """Authentication failure."""
    
    status_code = 401


class RateLimitExceeded(PyGovPubException):
    """API rate limit exceeded."""
    
    status_code = 429
    
    def __init__(
        self, 
        message: str, 
        retry_after: int, 
        details: Optional[Dict[str, Any]] = None
    ):
        """Initialize the rate limit exception.
        
        Args:
            message: Error message
            retry_after: Seconds until rate limit resets
            details: Additional error details (optional)
        """
        self.retry_after = retry_after
        super().__init__(message, details=details)


class ResourceNotFound(PyGovPubException):
    """Requested resource not found."""
    
    status_code = 404


class InvalidRequest(PyGovPubException):
    """Invalid request parameters or format."""
    
    status_code = 400


class ApiError(PyGovPubException):
    """Error from external API."""
    
    def __init__(
        self, 
        message: str, 
        status_code: int,
        api_name: str,
        details: Optional[Dict[str, Any]] = None
    ):
        """Initialize API error.
        
        Args:
            message: Error message
            status_code: HTTP status code
            api_name: Name of the API that generated the error
            details: Additional error details (optional)
        """
        self.api_name = api_name
        details = details or {}
        details["api_name"] = api_name
        super().__init__(message, status_code, details)


class MockServerError(PyGovPubException):
    """Error in mock server operation."""
    
    status_code = 500