"""
Custom exceptions for PyGovPub SDK.

This module defines the exception hierarchy for the SDK, enabling consistent
error handling and appropriate status code mapping for API responses.
"""

from datetime import datetime
from enum import Enum, IntEnum
from typing import Any, Dict, List, Optional, Union
from zoneinfo import ZoneInfo


class ErrorCode(IntEnum):
    """Error codes for PyGovPub SDK."""
    # General errors (1-99)
    UNKNOWN = 1
    CONFIGURATION = 10
    VALIDATION = 20
    SERIALIZATION = 30
    
    # Authentication errors (100-199)
    AUTH_GENERAL = 100
    AUTH_MISSING_KEY = 101
    AUTH_INVALID_KEY = 102
    AUTH_EXPIRED = 103
    AUTH_INSUFFICIENT_PERMISSIONS = 104
    
    # Rate limit errors (200-299)
    RATE_LIMIT_GENERAL = 200
    RATE_LIMIT_EXCEEDED = 201
    RATE_LIMIT_THROTTLED = 202
    
    # Network errors (300-399)
    NETWORK_GENERAL = 300
    NETWORK_TIMEOUT = 301
    NETWORK_CONNECTION_ERROR = 302
    NETWORK_DNS_ERROR = 303
    
    # Resource errors (400-499)
    RESOURCE_GENERAL = 400
    RESOURCE_NOT_FOUND = 401
    RESOURCE_UNAVAILABLE = 402
    RESOURCE_CONFLICT = 403
    
    # API errors (500-599)
    API_GENERAL = 500
    API_SERVER_ERROR = 501
    API_INVALID_RESPONSE = 502
    API_VERSION_INCOMPATIBLE = 503
    
    # Data errors (600-699)
    DATA_GENERAL = 600
    DATA_PARSING = 601
    DATA_MISSING_FIELDS = 602
    DATA_VALIDATION_FAILED = 603
    
    # Mock server errors (700-799)
    MOCK_GENERAL = 700
    MOCK_CONFIGURATION = 701
    MOCK_RECORDER = 702
    
    # Client errors (800-899)
    CLIENT_GENERAL = 800
    CLIENT_INVALID_PARAMETERS = 801
    CLIENT_INVALID_STATE = 802
    
    # System errors (900-999)
    SYSTEM_GENERAL = 900
    SYSTEM_RESOURCE_EXHAUSTED = 901
    SYSTEM_LIBRARY_ERROR = 902


class ErrorSeverity(str, Enum):
    """Error severity levels."""
    DEBUG = "debug"         # Informational, for development
    INFO = "info"           # Normal operations but noteworthy
    WARNING = "warning"     # Potential issues, operation can continue
    ERROR = "error"         # Operation failed but system stable
    CRITICAL = "critical"   # System stability affected


class ApiErrorSource(str, Enum):
    """Sources of API errors."""
    INTERNAL = "internal"   # Internal SDK error
    CONGRESS = "congress"   # Error from Congress.gov API
    GOVINFO = "govinfo"     # Error from GovInfo.gov API
    NETWORK = "network"     # Network-related error
    CLIENT = "client"       # Client-side error (e.g., invalid parameters)


class ErrorContext:
    """Contextual information about an error."""
    
    def __init__(
        self,
        request_id: Optional[str] = None,
        timestamp: Optional[datetime] = None,
        source: Optional[ApiErrorSource] = ApiErrorSource.INTERNAL,
        request_details: Optional[Dict[str, Any]] = None,
        response_details: Optional[Dict[str, Any]] = None,
        additional_info: Optional[Dict[str, Any]] = None
    ):
        """Initialize error context.
        
        Args:
            request_id: Unique identifier for the request
            timestamp: When the error occurred
            source: Source of the error
            request_details: Details about the request that caused the error
            response_details: Details from the response (if any)
            additional_info: Any additional context
        """
        self.request_id = request_id
        self.timestamp = timestamp or datetime.now(ZoneInfo("UTC"))
        self.source = source
        self.request_details = request_details or {}
        self.response_details = response_details or {}
        self.additional_info = additional_info or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary."""
        return {
            "request_id": self.request_id,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "request_details": self.request_details,
            "response_details": self.response_details,
            "additional_info": self.additional_info
        }


class PyGovPubException(Exception):
    """Base exception for all PyGovPub errors."""
    
    status_code: int = 500
    error_code: ErrorCode = ErrorCode.UNKNOWN
    severity: ErrorSeverity = ErrorSeverity.ERROR
    
    def __init__(
        self, 
        message: str, 
        status_code: Optional[int] = None,
        error_code: Optional[ErrorCode] = None,
        severity: Optional[ErrorSeverity] = None,
        context: Optional[ErrorContext] = None,
        details: Optional[Dict[str, Any]] = None,
        suggestion: Optional[str] = None,
        recovery_options: Optional[List[str]] = None,
    ):
        """Initialize the exception.
        
        Args:
            message: Error message
            status_code: HTTP status code (optional)
            error_code: PyGovPub error code (optional)
            severity: Error severity level (optional)
            context: Error context information (optional)
            details: Additional error details (optional)
            suggestion: Suggested action to resolve the error (optional)
            recovery_options: List of possible recovery options (optional)
        """
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        if error_code is not None:
            self.error_code = error_code
        if severity is not None:
            self.severity = severity
        self.context = context or ErrorContext()
        self.details = details or {}
        self.suggestion = suggestion
        self.recovery_options = recovery_options or []
        
        # Ensure we preserve the original exception message
        super().__init__(message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary representation.
        
        Returns:
            Dictionary with error details
        """
        result = {
            "message": self.message,
            "status_code": self.status_code,
            "error_code": int(self.error_code),
            "error_type": self.error_code.name,
            "severity": self.severity,
            "context": self.context.to_dict(),
            "details": self.details,
        }
        
        if self.suggestion:
            result["suggestion"] = self.suggestion
            
        if self.recovery_options:
            result["recovery_options"] = self.recovery_options
            
        return result


# Configuration Errors

class ConfigurationError(PyGovPubException):
    """Error in SDK configuration."""
    
    status_code = 500
    error_code = ErrorCode.CONFIGURATION
    severity = ErrorSeverity.ERROR


# Authentication Errors

class AuthenticationError(PyGovPubException):
    """Base class for authentication failures."""
    
    status_code = 401
    error_code = ErrorCode.AUTH_GENERAL
    severity = ErrorSeverity.ERROR


class MissingApiKeyError(AuthenticationError):
    """API key is missing."""
    
    error_code = ErrorCode.AUTH_MISSING_KEY
    
    def __init__(
        self, 
        message: str, 
        api_source: Optional[ApiErrorSource] = None,
        **kwargs
    ):
        """Initialize missing API key error.
        
        Args:
            message: Error message
            api_source: Which API is missing a key
            **kwargs: Additional arguments passed to parent
        """
        suggestion = "Configure API key using environment variables or add_key() method"
        
        # Remove context if already in kwargs to avoid duplicate
        kwargs_copy = kwargs.copy()
        context = kwargs_copy.pop('context', None) or ErrorContext(
            source=api_source or ApiErrorSource.INTERNAL
        )
        
        super().__init__(
            message, 
            suggestion=suggestion,
            context=context,
            **kwargs_copy
        )


class InvalidApiKeyError(AuthenticationError):
    """API key is invalid or rejected."""
    
    error_code = ErrorCode.AUTH_INVALID_KEY
    
    def __init__(
        self, 
        message: str, 
        api_source: Optional[ApiErrorSource] = None,
        **kwargs
    ):
        """Initialize invalid API key error.
        
        Args:
            message: Error message
            api_source: Which API rejected the key
            **kwargs: Additional arguments passed to parent
        """
        suggestion = "Verify API key is correct and has the necessary permissions"
        
        # Remove context if already in kwargs to avoid duplicate
        kwargs_copy = kwargs.copy()
        context = kwargs_copy.pop('context', None) or ErrorContext(
            source=api_source or ApiErrorSource.INTERNAL
        )
        
        super().__init__(
            message, 
            suggestion=suggestion,
            context=context,
            **kwargs_copy
        )


# Rate Limit Errors

class RateLimitExceededError(PyGovPubException):
    """API rate limit exceeded."""
    
    status_code = 429
    error_code = ErrorCode.RATE_LIMIT_EXCEEDED
    severity = ErrorSeverity.WARNING
    
    def __init__(
        self, 
        message: str, 
        retry_after: Optional[int] = None, 
        api_source: Optional[ApiErrorSource] = None,
        **kwargs
    ):
        """Initialize the rate limit exception.
        
        Args:
            message: Error message
            retry_after: Seconds until rate limit resets
            api_source: Which API enforced the rate limit
            **kwargs: Additional arguments passed to parent
        """
        self.retry_after = retry_after
        suggestion = None
        recovery_options = []
        
        if retry_after:
            suggestion = f"Retry after {retry_after} seconds when rate limit resets"
            recovery_options = [
                f"Wait for {retry_after} seconds",
                "Reduce request frequency",
                "Request rate limit increase from API provider"
            ]
        else:
            suggestion = "Reduce request frequency to avoid rate limits"
            recovery_options = [
                "Implement caching to reduce API calls",
                "Request rate limit increase from API provider",
                "Spread requests over longer time periods"
            ]
            
        # Remove context if already in kwargs to avoid duplicate
        kwargs_copy = kwargs.copy()
        context = kwargs_copy.pop('context', None) or ErrorContext(
            source=api_source or ApiErrorSource.INTERNAL,
            additional_info={"retry_after": retry_after} if retry_after else {}
        )
        
        super().__init__(
            message, 
            suggestion=suggestion,
            recovery_options=recovery_options,
            context=context,
            **kwargs_copy
        )


# Resource Errors

class ResourceNotFoundError(PyGovPubException):
    """Requested resource not found."""
    
    status_code = 404
    error_code = ErrorCode.RESOURCE_NOT_FOUND
    severity = ErrorSeverity.WARNING
    
    def __init__(
        self, 
        message: str, 
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        **kwargs
    ):
        """Initialize resource not found error.
        
        Args:
            message: Error message
            resource_type: Type of resource not found
            resource_id: ID of resource not found
            **kwargs: Additional arguments passed to parent
        """
        # Make a copy of kwargs to avoid modifying the original
        kwargs_copy = kwargs.copy()
        
        # Handle details
        details = kwargs_copy.pop('details', {}) or {}
        if resource_type:
            details["resource_type"] = resource_type
        if resource_id:
            details["resource_id"] = resource_id
        
        # Generate suggestion if not provided
        if 'suggestion' not in kwargs_copy:
            suggestion = "Verify the resource identifier and existence"
            if resource_type and resource_id:
                suggestion = f"Verify that {resource_type} with ID '{resource_id}' exists"
            kwargs_copy['suggestion'] = suggestion
            
        super().__init__(
            message, 
            details=details,
            **kwargs_copy
        )


class ResourceUnavailableError(PyGovPubException):
    """Resource exists but is temporarily unavailable."""
    
    status_code = 503
    error_code = ErrorCode.RESOURCE_UNAVAILABLE
    severity = ErrorSeverity.WARNING
    
    def __init__(
        self, 
        message: str, 
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        retry_after: Optional[int] = None,
        **kwargs
    ):
        """Initialize resource unavailable error.
        
        Args:
            message: Error message
            resource_type: Type of unavailable resource
            resource_id: ID of unavailable resource
            retry_after: Seconds after which to retry
            **kwargs: Additional arguments passed to parent
        """
        # Make a copy of kwargs to avoid modifying the original
        kwargs_copy = kwargs.copy()
        
        # Handle details
        details = kwargs_copy.pop('details', {}) or {}
        if resource_type:
            details["resource_type"] = resource_type
        if resource_id:
            details["resource_id"] = resource_id
        if retry_after:
            details["retry_after"] = retry_after
        
        # Generate suggestion if not provided
        if 'suggestion' not in kwargs_copy:
            if retry_after:
                kwargs_copy['suggestion'] = f"Retry after {retry_after} seconds"
            else:
                kwargs_copy['suggestion'] = "Try again later"
        
        # Generate recovery options if not provided
        if 'recovery_options' not in kwargs_copy:
            if retry_after:
                kwargs_copy['recovery_options'] = [f"Wait for {retry_after} seconds and retry"]
            else:
                kwargs_copy['recovery_options'] = ["Try again later"]
            
        super().__init__(
            message, 
            details=details,
            **kwargs_copy
        )


# Request Errors

class InvalidRequestError(PyGovPubException):
    """Invalid request parameters or format."""
    
    status_code = 400
    error_code = ErrorCode.CLIENT_INVALID_PARAMETERS
    severity = ErrorSeverity.WARNING
    
    def __init__(
        self, 
        message: str, 
        validation_errors: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        """Initialize invalid request error.
        
        Args:
            message: Error message
            validation_errors: Details about validation failures
            **kwargs: Additional arguments passed to parent
        """
        # Make a copy of kwargs to avoid modifying the original
        kwargs_copy = kwargs.copy()
        
        # Handle details
        details = kwargs_copy.pop('details', {}) or {}
        if validation_errors:
            details["validation_errors"] = validation_errors
        
        # Generate suggestion if not provided
        if 'suggestion' not in kwargs_copy:
            kwargs_copy['suggestion'] = "Check request parameters and format"
            
        super().__init__(
            message, 
            details=details,
            **kwargs_copy
        )


# API Errors

class ApiError(PyGovPubException):
    """Error from external API."""
    
    error_code = ErrorCode.API_GENERAL
    
    def __init__(
        self, 
        message: str, 
        status_code: int,
        api_name: str,
        original_error: Optional[Dict[str, Any]] = None,
        endpoint: Optional[str] = None,
        **kwargs
    ):
        """Initialize API error.
        
        Args:
            message: Error message
            status_code: HTTP status code
            api_name: Name of the API that generated the error
            original_error: Original error from API (optional)
            endpoint: API endpoint that failed (optional)
            **kwargs: Additional arguments passed to parent
        """
        self.api_name = api_name
        details = kwargs.get('details', {}) or {}
        details["api_name"] = api_name
        
        if original_error:
            details["original_error"] = original_error
        if endpoint:
            details["endpoint"] = endpoint
            
        api_source = None
        if api_name.lower() == "congress":
            api_source = ApiErrorSource.CONGRESS
        elif api_name.lower() == "govinfo":
            api_source = ApiErrorSource.GOVINFO
            
        context = kwargs.get('context') or ErrorContext(source=api_source)
        if endpoint:
            context.request_details["endpoint"] = endpoint
        if original_error:
            context.response_details["original_error"] = original_error
            
        # Set specific error codes based on status
        specific_error_code = ErrorCode.API_GENERAL
        if status_code >= 500:
            specific_error_code = ErrorCode.API_SERVER_ERROR
        
        super().__init__(
            message, 
            status_code=status_code,
            error_code=specific_error_code,
            context=context,
            details=details,
            **kwargs
        )


class CongressApiError(ApiError):
    """Error specific to Congress.gov API."""
    
    def __init__(
        self, 
        message: str, 
        status_code: int,
        **kwargs
    ):
        """Initialize Congress API error.
        
        Args:
            message: Error message
            status_code: HTTP status code
            **kwargs: Additional arguments passed to parent
        """
        super().__init__(
            message, 
            status_code=status_code,
            api_name="congress",
            **kwargs
        )


class GovInfoApiError(ApiError):
    """Error specific to GovInfo.gov API."""
    
    def __init__(
        self, 
        message: str, 
        status_code: int,
        **kwargs
    ):
        """Initialize GovInfo API error.
        
        Args:
            message: Error message
            status_code: HTTP status code
            **kwargs: Additional arguments passed to parent
        """
        super().__init__(
            message, 
            status_code=status_code,
            api_name="govinfo",
            **kwargs
        )


# Network Errors

class NetworkError(PyGovPubException):
    """Base class for network-related errors."""
    
    status_code = 503
    error_code = ErrorCode.NETWORK_GENERAL
    severity = ErrorSeverity.ERROR
    
    def __init__(
        self, 
        message: str, 
        **kwargs
    ):
        """Initialize network error.
        
        Args:
            message: Error message
            **kwargs: Additional arguments passed to parent
        """
        # Remove context if already in kwargs to avoid duplicate
        kwargs_copy = kwargs.copy()
        context = kwargs_copy.pop('context', None) or ErrorContext(source=ApiErrorSource.NETWORK)
        
        recovery_options = [
            "Check network connectivity",
            "Verify API endpoint is correct",
            "Try again later"
        ]
        
        super().__init__(
            message, 
            context=context,
            recovery_options=recovery_options,
            **kwargs_copy
        )


class TimeoutError(NetworkError):
    """Request timed out."""
    
    error_code = ErrorCode.NETWORK_TIMEOUT
    
    def __init__(
        self, 
        message: str, 
        timeout_seconds: Optional[int] = None,
        **kwargs
    ):
        """Initialize timeout error.
        
        Args:
            message: Error message
            timeout_seconds: Seconds before timeout occurred
            **kwargs: Additional arguments passed to parent
        """
        details = kwargs.get('details', {})
        if timeout_seconds:
            details["timeout_seconds"] = timeout_seconds
            
        suggestion = "Increase timeout or check API responsiveness"
        
        super().__init__(
            message, 
            suggestion=suggestion,
            details=details,
            **kwargs
        )


class ConnectionError(NetworkError):
    """Failed to establish connection."""
    
    error_code = ErrorCode.NETWORK_CONNECTION_ERROR


# Data Errors

class DataError(PyGovPubException):
    """Base class for data-related errors."""
    
    status_code = 400
    error_code = ErrorCode.DATA_GENERAL
    severity = ErrorSeverity.WARNING


class DataParsingError(DataError):
    """Failed to parse data from API."""
    
    error_code = ErrorCode.DATA_PARSING
    
    def __init__(
        self, 
        message: str, 
        data_format: Optional[str] = None,
        parsing_error: Optional[Exception] = None,
        **kwargs
    ):
        """Initialize data parsing error.
        
        Args:
            message: Error message
            data_format: Format of data that failed to parse
            parsing_error: Original parsing exception
            **kwargs: Additional arguments passed to parent
        """
        # Make a copy of kwargs to avoid modifying the original
        kwargs_copy = kwargs.copy()
        
        # Handle details
        details = kwargs_copy.pop('details', {}) or {}
        if data_format:
            details["data_format"] = data_format
        if parsing_error:
            details["parsing_error"] = str(parsing_error)
        
        # Generate suggestion if not provided
        if 'suggestion' not in kwargs_copy:
            kwargs_copy['suggestion'] = "Check data format and structure"
            
        super().__init__(
            message, 
            details=details,
            **kwargs_copy
        )


class DataValidationError(DataError):
    """Data failed validation."""
    
    error_code = ErrorCode.DATA_VALIDATION_FAILED
    
    def __init__(
        self, 
        message: str, 
        validation_errors: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        """Initialize data validation error.
        
        Args:
            message: Error message
            validation_errors: Details about validation failures
            **kwargs: Additional arguments passed to parent
        """
        # Make a copy of kwargs to avoid modifying the original
        kwargs_copy = kwargs.copy()
        
        # Handle details
        details = kwargs_copy.pop('details', {}) or {}
        if validation_errors:
            details["validation_errors"] = validation_errors
        
        # Generate suggestion if not provided
        if 'suggestion' not in kwargs_copy:
            kwargs_copy['suggestion'] = "Check data structure against schema"
            
        super().__init__(
            message, 
            details=details,
            **kwargs_copy
        )


# Mock Server Errors

class MockServerError(PyGovPubException):
    """Error in mock server operation."""
    
    status_code = 500
    error_code = ErrorCode.MOCK_GENERAL
    severity = ErrorSeverity.ERROR