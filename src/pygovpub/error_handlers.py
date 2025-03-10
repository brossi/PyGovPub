"""
API-specific error handlers for PyGovPub SDK.

This module contains specialized handlers for various API error patterns,
normalizing them into consistent PyGovPub exception types.
"""

import json
import re
from typing import Any, Dict, Optional, Tuple, Union, Type

import aiohttp
import requests

from pygovpub.exceptions import (
    ApiError,
    ApiErrorSource,
    AuthenticationError,
    CongressApiError,
    DataParsingError,
    DataValidationError,
    ErrorCode,
    ErrorContext,
    GovInfoApiError,
    InvalidApiKeyError,
    InvalidRequestError,
    MissingApiKeyError,
    NetworkError,
    PyGovPubException,
    RateLimitExceededError,
    ResourceNotFoundError,
    ResourceUnavailableError,
    TimeoutError,
    ConnectionError
)


def extract_error_details(response_data: Any) -> Dict[str, Any]:
    """
    Extract error details from API response data.
    
    Args:
        response_data: Response data from API
        
    Returns:
        Dictionary with extracted error details
    """
    details = {}
    
    # Handle dictionary responses
    if isinstance(response_data, dict):
        # Extract common error fields
        for key in ["error", "message", "description", "code", "details", "retry_after"]:
            if key in response_data:
                details[key] = response_data[key]
                
        # Specifically check for hyphenated version of retry-after and normalize
        if "retry-after" in response_data:
            details["retry_after"] = response_data["retry-after"]
        
        # Extract nested error data
        if "error" in response_data and isinstance(response_data["error"], dict):
            for key, value in response_data["error"].items():
                details[f"error_{key}"] = value
                
    # Handle string responses (try to parse as JSON)
    elif isinstance(response_data, str):
        try:
            json_data = json.loads(response_data)
            if isinstance(json_data, dict):
                return extract_error_details(json_data)
        except json.JSONDecodeError:
            # Not JSON, just use as error message
            details["raw_message"] = response_data
            
    return details


def normalize_error_message(error_details: Dict[str, Any]) -> str:
    """
    Create normalized error message from error details.
    
    Args:
        error_details: Extracted error details
        
    Returns:
        Normalized error message string
    """
    # Try to find most specific message
    for key in ["message", "error_message", "description", "error_description", "error"]:
        if key in error_details and error_details[key]:
            if isinstance(error_details[key], str):
                return error_details[key]
    
    # Fall back to raw message or default
    if "raw_message" in error_details:
        return error_details["raw_message"]
    
    return "Unknown API error occurred"


def handle_congress_api_error(
    status_code: int,
    response_data: Any,
    endpoint: Optional[str] = None
) -> CongressApiError:
    """
    Handle Congress.gov API error.
    
    Args:
        status_code: HTTP status code
        response_data: Response data from API
        endpoint: API endpoint that failed
        
    Returns:
        Appropriate PyGovPub exception
    """
    # Extract error details
    error_details = extract_error_details(response_data)
    
    # Get normalized message
    message = normalize_error_message(error_details)
    
    # Set up error context
    context = ErrorContext(
        source=ApiErrorSource.CONGRESS,
        request_details={"endpoint": endpoint} if endpoint else {},
        response_details={"status_code": status_code}
    )
    
    # Authentication errors
    if status_code == 401:
        if "invalid" in message.lower() or "invalid" in str(error_details).lower():
            return InvalidApiKeyError(
                f"Invalid API key for Congress.gov: {message}",
                api_source=ApiErrorSource.CONGRESS,
                context=context
            )
        elif "missing" in message.lower() or "missing" in str(error_details).lower():
            return MissingApiKeyError(
                f"Missing API key for Congress.gov: {message}",
                api_source=ApiErrorSource.CONGRESS,
                context=context
            )
        else:
            return AuthenticationError(
                f"Authentication failed for Congress.gov: {message}",
                context=context
            )
            
    # Rate limit errors
    if status_code == 429:
        retry_after = None
        # Try to extract retry_after from various fields
        if "retry_after" in error_details:
            try:
                retry_after = int(error_details["retry_after"])
            except (ValueError, TypeError):
                pass
        # Also check for x-ratelimit-reset header value
        elif "x-ratelimit-reset" in error_details:
            try:
                retry_after = int(error_details["x-ratelimit-reset"])
            except (ValueError, TypeError):
                pass
            
        return RateLimitExceededError(
            f"Rate limit exceeded for Congress.gov: {message}",
            retry_after=retry_after,
            api_source=ApiErrorSource.CONGRESS,
            context=context
        )
        
    # Resource not found
    if status_code == 404:
        return ResourceNotFoundError(
            f"Resource not found on Congress.gov: {message}",
            context=context
        )
        
    # Invalid request
    if status_code == 400:
        return InvalidRequestError(
            f"Invalid request to Congress.gov: {message}",
            context=context
        )
        
    # Service unavailable
    if status_code in (502, 503, 504):
        return ResourceUnavailableError(
            f"Congress.gov service unavailable: {message}",
            context=context
        )
        
    # Generic API error for other cases
    return CongressApiError(
        f"Congress.gov API error: {message}",
        status_code=status_code,
        original_error=error_details,
        endpoint=endpoint
    )


def handle_govinfo_api_error(
    status_code: int,
    response_data: Any,
    endpoint: Optional[str] = None
) -> GovInfoApiError:
    """
    Handle GovInfo.gov API error.
    
    Args:
        status_code: HTTP status code
        response_data: Response data from API
        endpoint: API endpoint that failed
        
    Returns:
        Appropriate PyGovPub exception
    """
    # Extract error details
    error_details = extract_error_details(response_data)
    
    # Get normalized message
    message = normalize_error_message(error_details)
    
    # Set up error context
    context = ErrorContext(
        source=ApiErrorSource.GOVINFO,
        request_details={"endpoint": endpoint} if endpoint else {},
        response_details={"status_code": status_code}
    )
    
    # Authentication errors (GovInfo uses different patterns than Congress)
    if status_code == 401 or status_code == 403:
        if "key" in message.lower() and ("invalid" in message.lower() or "incorrect" in message.lower()):
            return InvalidApiKeyError(
                f"Invalid API key for GovInfo.gov: {message}",
                api_source=ApiErrorSource.GOVINFO,
                status_code=status_code,
                context=context
            )
        elif "key" in message.lower() and "missing" in message.lower():
            return MissingApiKeyError(
                f"Missing API key for GovInfo.gov: {message}",
                api_source=ApiErrorSource.GOVINFO,
                status_code=status_code,
                context=context
            )
        elif "permission" in message.lower() or "access" in message.lower():
            return AuthenticationError(
                f"Insufficient permissions for GovInfo.gov: {message}",
                error_code=ErrorCode.AUTH_INSUFFICIENT_PERMISSIONS,
                status_code=status_code,
                context=context
            )
        else:
            return AuthenticationError(
                f"Authentication failed for GovInfo.gov: {message}",
                status_code=status_code,
                context=context
            )
            
    # Rate limit errors
    if status_code == 429:
        retry_after = None
        # GovInfo might provide retry-after in seconds
        if "retry-after" in error_details:
            try:
                retry_after = int(error_details["retry-after"])
            except (ValueError, TypeError):
                pass
        # Also check for lowercase version
        elif "retry_after" in error_details:
            try:
                retry_after = int(error_details["retry_after"])
            except (ValueError, TypeError):
                pass
        
        return RateLimitExceededError(
            f"Rate limit exceeded for GovInfo.gov: {message}",
            retry_after=retry_after,
            api_source=ApiErrorSource.GOVINFO,
            context=context
        )
        
    # Resource not found
    if status_code == 404:
        # GovInfo not found can be a missing package or collection
        resource_type = None
        resource_id = None
        
        # Try to extract resource info from endpoint
        if endpoint:
            # Check for package pattern
            package_match = re.search(r"/packages/([^/]+)", endpoint)
            if package_match:
                resource_type = "package"
                resource_id = package_match.group(1)
            
            # Check for collection pattern
            collection_match = re.search(r"/collections/([^/]+)", endpoint)
            if collection_match:
                resource_type = "collection"
                resource_id = collection_match.group(1)
        
        return ResourceNotFoundError(
            f"Resource not found on GovInfo.gov: {message}",
            resource_type=resource_type,
            resource_id=resource_id,
            context=context
        )
        
    # Invalid request
    if status_code == 400:
        # Extract validation errors if present
        validation_errors = None
        if "validation" in str(error_details).lower() or "invalid" in str(error_details).lower():
            validation_errors = error_details
        
        return InvalidRequestError(
            f"Invalid request to GovInfo.gov: {message}",
            validation_errors=validation_errors,
            context=context
        )
        
    # Service unavailable
    if status_code in (502, 503, 504):
        return ResourceUnavailableError(
            f"GovInfo.gov service unavailable: {message}",
            context=context
        )
        
    # Generic API error for other cases
    return GovInfoApiError(
        f"GovInfo.gov API error: {message}",
        status_code=status_code,
        original_error=error_details,
        endpoint=endpoint
    )


def handle_request_exception(
    exception: Exception,
    api_source: Optional[ApiErrorSource] = None,
    endpoint: Optional[str] = None
) -> PyGovPubException:
    """
    Handle request-related exceptions.
    
    Args:
        exception: The caught exception
        api_source: API source being accessed when error occurred
        endpoint: API endpoint being accessed
        
    Returns:
        Appropriate PyGovPub exception
    """
    # Set up error context
    context = ErrorContext(
        source=api_source or ApiErrorSource.NETWORK,
        request_details={"endpoint": endpoint} if endpoint else {}
    )
    
    # Handle timeout exceptions
    if (
        isinstance(exception, (requests.Timeout, aiohttp.ClientTimeout, aiohttp.ServerTimeoutError)) or
        "timeout" in str(exception).lower() or
        "timed out" in str(exception).lower()
    ):
        return TimeoutError(
            f"Request timed out: {str(exception)}",
            context=context
        )
        
    # Handle connection errors
    if (
        isinstance(exception, (requests.ConnectionError, aiohttp.ClientConnectionError)) or
        "connection" in str(exception).lower()
    ):
        return ConnectionError(
            f"Connection error: {str(exception)}",
            context=context
        )
        
    # Handle DNS errors
    if "dns" in str(exception).lower() or "name resolution" in str(exception).lower():
        return NetworkError(
            f"DNS resolution error: {str(exception)}",
            error_code=ErrorCode.NETWORK_DNS_ERROR,
            context=context
        )
        
    # Handle SSL errors
    if "ssl" in str(exception).lower() or "certificate" in str(exception).lower():
        return NetworkError(
            f"SSL/TLS error: {str(exception)}",
            error_code=ErrorCode.NETWORK_GENERAL,
            context=context
        )
        
    # Generic network error for other cases
    return NetworkError(
        f"Network error: {str(exception)}",
        context=context
    )


def parse_http_response(
    response: Union[requests.Response, aiohttp.ClientResponse, Dict[str, Any], Any],
    api_source: ApiErrorSource,
    endpoint: Optional[str] = None
) -> Optional[PyGovPubException]:
    """
    Parse HTTP response and return appropriate exception if it's an error.
    
    Args:
        response: HTTP response object or dict with status and data
        api_source: API source that generated the response
        endpoint: API endpoint that was accessed
        
    Returns:
        PyGovPub exception if it's an error response, None otherwise
    """
    status_code = None
    data = None
    
    # Handle requests.Response
    if isinstance(response, requests.Response):
        status_code = response.status_code
        try:
            data = response.json()
        except (ValueError, json.JSONDecodeError):
            data = response.text
    
    # Handle aiohttp.ClientResponse (must be already read)
    elif isinstance(response, aiohttp.ClientResponse):
        status_code = response.status
        # Data should be provided separately for aiohttp
        data = None
    
    # Handle dict representation
    elif isinstance(response, dict) and "status_code" in response:
        status_code = response["status_code"]
        data = response.get("data")
        
    # Handle MockResponse or other response-like objects
    elif hasattr(response, 'status_code') and hasattr(response, '_content'):
        status_code = response.status_code
        data = response._content
        
    # If not an error response, return None
    if not status_code or status_code < 400:
        return None
        
    # Choose appropriate error handler based on API source
    if api_source == ApiErrorSource.CONGRESS:
        return handle_congress_api_error(status_code, data, endpoint)
    elif api_source == ApiErrorSource.GOVINFO:
        return handle_govinfo_api_error(status_code, data, endpoint)
    else:
        # Generic API error for unknown sources
        error_details = extract_error_details(data)
        message = normalize_error_message(error_details)
        
        return ApiError(
            f"API error: {message}",
            status_code=status_code,
            api_name=str(api_source),
            original_error=error_details,
            endpoint=endpoint
        )