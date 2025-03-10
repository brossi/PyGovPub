"""
Tests for API-specific error handlers.

This module tests the error handlers that process and normalize
errors from different API sources.
"""

import json
import pytest

from pygovpub.error_handlers import (
    extract_error_details,
    normalize_error_message,
    handle_congress_api_error,
    handle_govinfo_api_error,
    handle_request_exception,
    parse_http_response
)
from pygovpub.exceptions import (
    ApiErrorSource,
    AuthenticationError,
    CongressApiError,
    ConnectionError,
    ErrorCode,
    GovInfoApiError,
    InvalidApiKeyError,
    InvalidRequestError,
    MissingApiKeyError,
    NetworkError,
    PyGovPubException,
    RateLimitExceededError,
    ResourceNotFoundError,
    ResourceUnavailableError,
    TimeoutError
)


class MockResponse:
    """Mock HTTP response for testing."""
    
    def __init__(self, status_code, content, headers=None):
        self.status_code = status_code
        self._content = content
        self.headers = headers or {}
        
    def json(self):
        """Return content as JSON."""
        if isinstance(self._content, str):
            return json.loads(self._content)
        return self._content
        
    @property
    def text(self):
        """Return content as text."""
        if isinstance(self._content, dict):
            return json.dumps(self._content)
        return self._content
        
    # Allow direct access to json data
    @property
    def data(self):
        """Return content data."""
        return self._content


class MockAioHttpResponse:
    """Mock aiohttp response for testing."""
    
    def __init__(self, status, content, headers=None):
        self.status = status
        self._content = content
        self.headers = headers or {}


def test_extract_error_details_dict():
    """Test extracting error details from dictionary."""
    # Simple error object
    data = {"error": "Something went wrong", "code": 123}
    details = extract_error_details(data)
    assert details["error"] == "Something went wrong"
    assert details["code"] == 123
    
    # Nested error object
    data = {"error": {"message": "Validation failed", "details": {"field": "invalid"}}}
    details = extract_error_details(data)
    assert details["error_message"] == "Validation failed"
    assert details["error_details"] == {"field": "invalid"}
    
    # Standard fields
    data = {"message": "Error message", "description": "Error description"}
    details = extract_error_details(data)
    assert details["message"] == "Error message"
    assert details["description"] == "Error description"


def test_extract_error_details_string():
    """Test extracting error details from string."""
    # JSON string
    data = """{"error": "Not found", "code": 404}"""
    details = extract_error_details(data)
    assert details["error"] == "Not found"
    assert details["code"] == 404
    
    # Non-JSON string
    data = "Something went wrong"
    details = extract_error_details(data)
    assert details["raw_message"] == "Something went wrong"


def test_normalize_error_message():
    """Test normalizing error messages from details."""
    # Direct message field
    details = {"message": "Error in request"}
    assert normalize_error_message(details) == "Error in request"
    
    # Nested error message
    details = {"error_message": "Validation error"}
    assert normalize_error_message(details) == "Validation error"
    
    # Description field
    details = {"description": "Rate limit exceeded"}
    assert normalize_error_message(details) == "Rate limit exceeded"
    
    # Simple error string
    details = {"error": "Not found"}
    assert normalize_error_message(details) == "Not found"
    
    # Raw message fallback
    details = {"raw_message": "Raw error text"}
    assert normalize_error_message(details) == "Raw error text"
    
    # Default message
    details = {"other": "stuff"}
    assert normalize_error_message(details) == "Unknown API error occurred"


def test_handle_congress_api_error_auth():
    """Test handling Congress API authentication errors."""
    # Invalid key error
    response_data = {"error": "Invalid API key provided"}
    error = handle_congress_api_error(401, response_data, "/bills")
    
    assert isinstance(error, InvalidApiKeyError)
    assert error.status_code == 401
    assert "Invalid API key" in error.message
    assert error.context.source == ApiErrorSource.CONGRESS
    assert error.context.request_details["endpoint"] == "/bills"
    
    # Missing key error
    response_data = {"error": "Missing API key"}
    error = handle_congress_api_error(401, response_data)
    
    assert isinstance(error, MissingApiKeyError)
    assert error.status_code == 401
    assert "Missing API key" in error.message
    
    # Other auth error
    response_data = {"error": "Authentication failed"}
    error = handle_congress_api_error(401, response_data)
    
    assert isinstance(error, AuthenticationError)
    assert error.status_code == 401
    assert "Authentication failed" in error.message


def test_handle_congress_api_error_rate_limit():
    """Test handling Congress API rate limit errors."""
    # With retry_after
    response_data = {"error": "Rate limit exceeded", "retry_after": "30"}
    error = handle_congress_api_error(429, response_data)
    
    assert isinstance(error, RateLimitExceededError)
    assert error.status_code == 429
    assert "Rate limit exceeded" in error.message
    assert error.retry_after == 30
    
    # Without retry_after
    response_data = {"error": "Too many requests"}
    error = handle_congress_api_error(429, response_data)
    
    assert isinstance(error, RateLimitExceededError)
    assert "Too many requests" in error.message
    assert error.retry_after is None


def test_handle_congress_api_error_resource():
    """Test handling Congress API resource errors."""
    # Not found
    response_data = {"error": "Resource not found"}
    error = handle_congress_api_error(404, response_data, "/bills/hr123")
    
    assert isinstance(error, ResourceNotFoundError)
    assert error.status_code == 404
    assert "Resource not found" in error.message
    
    # Invalid request
    response_data = {"error": "Invalid parameter"}
    error = handle_congress_api_error(400, response_data)
    
    assert isinstance(error, InvalidRequestError)
    assert error.status_code == 400
    assert "Invalid parameter" in error.message
    
    # Service unavailable
    response_data = {"error": "Service temporarily unavailable"}
    error = handle_congress_api_error(503, response_data)
    
    assert isinstance(error, ResourceUnavailableError)
    assert error.status_code == 503
    assert "service unavailable" in error.message.lower()


def test_handle_congress_api_error_other():
    """Test handling other Congress API errors."""
    # Server error
    response_data = {"error": "Internal server error"}
    error = handle_congress_api_error(500, response_data, "/members")
    
    assert isinstance(error, CongressApiError)
    assert error.status_code == 500
    assert "Internal server error" in error.message
    assert error.api_name == "congress"
    assert error.details["endpoint"] == "/members"
    assert error.details["original_error"]["error"] == "Internal server error"


def test_handle_govinfo_api_error_auth():
    """Test handling GovInfo API authentication errors."""
    # Invalid key
    response_data = {"error": "The API key provided is invalid"}
    error = handle_govinfo_api_error(403, response_data)
    
    assert isinstance(error, InvalidApiKeyError)
    assert error.status_code == 403
    assert "Invalid API key" in error.message
    assert error.context.source == ApiErrorSource.GOVINFO
    
    # Missing key
    response_data = {"message": "Missing key parameter"}
    error = handle_govinfo_api_error(401, response_data)
    
    assert isinstance(error, MissingApiKeyError)
    assert error.status_code == 401
    assert "Missing API key" in error.message
    
    # Permission error
    response_data = {"error": "Insufficient permissions for resource"}
    error = handle_govinfo_api_error(403, response_data)
    
    assert isinstance(error, AuthenticationError)
    assert error.status_code == 403
    assert "Insufficient permissions" in error.message
    assert error.error_code == ErrorCode.AUTH_INSUFFICIENT_PERMISSIONS


def test_handle_govinfo_api_error_rate_limit():
    """Test handling GovInfo API rate limit errors."""
    # With retry-after
    response_data = {"error": "Rate limit exceeded", "retry-after": "60"}
    error = handle_govinfo_api_error(429, response_data)
    
    assert isinstance(error, RateLimitExceededError)
    assert error.status_code == 429
    assert "Rate limit exceeded" in error.message
    assert error.retry_after == 60
    
    # With retry_after (underscore version)
    response_data = {"message": "Too many requests", "retry_after": 30}
    error = handle_govinfo_api_error(429, response_data)
    
    assert isinstance(error, RateLimitExceededError)
    assert "Too many requests" in error.message
    assert error.retry_after == 30


def test_handle_govinfo_api_error_resource():
    """Test handling GovInfo API resource errors."""
    # Not found with extractable resource info
    response_data = {"error": "Package not found"}
    error = handle_govinfo_api_error(404, response_data, "/packages/BILLS-117hr1")
    
    assert isinstance(error, ResourceNotFoundError)
    assert error.status_code == 404
    assert "Resource not found" in error.message
    assert error.details.get("resource_type") == "package"
    assert error.details.get("resource_id") == "BILLS-117hr1"
    
    # Not found for collection
    response_data = {"error": "Collection not found"}
    error = handle_govinfo_api_error(404, response_data, "/collections/BILLS")
    
    assert isinstance(error, ResourceNotFoundError)
    assert error.details.get("resource_type") == "collection"
    assert error.details.get("resource_id") == "BILLS"
    
    # Invalid request with validation errors
    response_data = {"error": "Invalid parameters", "validation": {"dateFrom": "Invalid format"}}
    error = handle_govinfo_api_error(400, response_data)
    
    assert isinstance(error, InvalidRequestError)
    assert error.status_code == 400
    assert "Invalid request" in error.message
    assert error.details.get("validation_errors") is not None
    
    # Service unavailable
    response_data = {"message": "Service temporarily down for maintenance"}
    error = handle_govinfo_api_error(503, response_data)
    
    assert isinstance(error, ResourceUnavailableError)
    assert error.status_code == 503
    assert "service unavailable" in error.message.lower()


def test_handle_govinfo_api_error_other():
    """Test handling other GovInfo API errors."""
    # Server error
    response_data = {"error": "Internal server error"}
    error = handle_govinfo_api_error(500, response_data, "/packages/search")
    
    assert isinstance(error, GovInfoApiError)
    assert error.status_code == 500
    assert "Internal server error" in error.message
    assert error.api_name == "govinfo"
    assert error.details["endpoint"] == "/packages/search"


def test_handle_request_exception():
    """Test handling request exceptions."""
    # Timeout error
    error = handle_request_exception(
        Exception("Read timed out after 30 seconds"),
        ApiErrorSource.CONGRESS,
        "/bills"
    )
    
    assert isinstance(error, TimeoutError)
    assert "timed out" in error.message
    assert error.context.source == ApiErrorSource.CONGRESS
    assert error.context.request_details["endpoint"] == "/bills"
    
    # Connection error
    error = handle_request_exception(
        Exception("Connection refused"),
        ApiErrorSource.GOVINFO
    )
    
    assert isinstance(error, ConnectionError)
    assert "Connection" in error.message
    assert error.context.source == ApiErrorSource.GOVINFO
    
    # DNS error
    error = handle_request_exception(
        Exception("DNS resolution failed"),
        ApiErrorSource.NETWORK
    )
    
    assert isinstance(error, NetworkError)
    assert "DNS" in error.message
    assert error.error_code == ErrorCode.NETWORK_DNS_ERROR
    
    # SSL error
    error = handle_request_exception(
        Exception("SSL certificate verification failed"),
        ApiErrorSource.CONGRESS
    )
    
    assert isinstance(error, NetworkError)
    assert "SSL" in error.message
    
    # Generic error
    error = handle_request_exception(Exception("Something went wrong"))
    
    assert isinstance(error, NetworkError)
    assert "Something went wrong" in error.message
    assert error.context.source == ApiErrorSource.NETWORK


def test_parse_http_response_requests():
    """Test parsing requests.Response objects."""
    # Success response
    response = MockResponse(200, {"data": "success"})
    error = parse_http_response(response, ApiErrorSource.CONGRESS)
    assert error is None
    
    # Congress API error
    response = MockResponse(401, {"error": "Invalid API key"})
    error = parse_http_response(response, ApiErrorSource.CONGRESS, "/bills")
    
    assert isinstance(error, InvalidApiKeyError)
    assert error.status_code == 401
    assert "Invalid API key" in error.message
    
    # GovInfo API error
    response = MockResponse(429, {"error": "Rate limit exceeded", "retry-after": "30"})
    error = parse_http_response(response, ApiErrorSource.GOVINFO, "/packages")
    
    assert isinstance(error, RateLimitExceededError)
    assert error.status_code == 429
    assert error.retry_after == 30


def test_parse_http_response_aiohttp():
    """Test parsing aiohttp.ClientResponse objects."""
    # Success response
    response = MockAioHttpResponse(200, {"data": "success"})
    error = parse_http_response(response, ApiErrorSource.CONGRESS)
    assert error is None
    
    # Error response (note: data must be provided separately for aiohttp)
    response = MockAioHttpResponse(404, None)
    response_dict = {"status_code": 404, "data": {"error": "Resource not found"}}
    error = parse_http_response(response_dict, ApiErrorSource.GOVINFO, "/collections/BILLS")
    
    assert isinstance(error, ResourceNotFoundError)
    assert error.status_code == 404
    assert "Resource not found" in error.message


def test_parse_http_response_dict():
    """Test parsing dictionary response representation."""
    # Success response
    response_dict = {"status_code": 200, "data": {"result": "success"}}
    error = parse_http_response(response_dict, ApiErrorSource.CONGRESS)
    assert error is None
    
    # Error response
    response_dict = {"status_code": 500, "data": {"error": "Server error"}}
    error = parse_http_response(response_dict, ApiErrorSource.INTERNAL)
    
    assert isinstance(error, PyGovPubException)
    assert error.status_code == 500
    assert "Server error" in error.message