"""
Tests for exception hierarchy and error classification.

This module tests the PyGovPub exception system, including error codes,
severity levels, and context handling.
"""

import pytest
from datetime import datetime, timezone

from pygovpub.exceptions import (
    ApiError,
    ApiErrorSource,
    AuthenticationError,
    CongressApiError,
    ConfigurationError,
    ConnectionError,
    DataParsingError,
    DataValidationError,
    ErrorCode,
    ErrorContext,
    ErrorSeverity,
    GovInfoApiError,
    InvalidApiKeyError,
    InvalidRequestError,
    MissingApiKeyError,
    MockServerError,
    NetworkError,
    PyGovPubException,
    RateLimitExceededError,
    ResourceNotFoundError,
    ResourceUnavailableError,
    TimeoutError
)


def test_base_exception_defaults():
    """Test PyGovPubException default values."""
    exc = PyGovPubException("Test error")
    
    assert exc.message == "Test error"
    assert exc.status_code == 500
    assert exc.error_code == ErrorCode.UNKNOWN
    assert exc.severity == ErrorSeverity.ERROR
    assert isinstance(exc.context, ErrorContext)
    assert isinstance(exc.details, dict)
    assert len(exc.details) == 0
    assert exc.suggestion is None
    assert isinstance(exc.recovery_options, list)
    assert len(exc.recovery_options) == 0


def test_base_exception_custom_values():
    """Test PyGovPubException with custom values."""
    context = ErrorContext(request_id="test-123")
    exc = PyGovPubException(
        message="Custom error",
        status_code=418,
        error_code=ErrorCode.CONFIGURATION,
        severity=ErrorSeverity.WARNING,
        context=context,
        details={"test": "value"},
        suggestion="Try this fix",
        recovery_options=["Option 1", "Option 2"]
    )
    
    assert exc.message == "Custom error"
    assert exc.status_code == 418
    assert exc.error_code == ErrorCode.CONFIGURATION
    assert exc.severity == ErrorSeverity.WARNING
    assert exc.context is context
    assert exc.details == {"test": "value"}
    assert exc.suggestion == "Try this fix"
    assert exc.recovery_options == ["Option 1", "Option 2"]


def test_error_context():
    """Test ErrorContext initialization and conversion to dict."""
    timestamp = datetime.now(timezone.utc)
    context = ErrorContext(
        request_id="req-123",
        timestamp=timestamp,
        source=ApiErrorSource.CONGRESS,
        request_details={"endpoint": "/bills"},
        response_details={"status": 404},
        additional_info={"attempt": 2}
    )
    
    assert context.request_id == "req-123"
    assert context.timestamp == timestamp
    assert context.source == ApiErrorSource.CONGRESS
    assert context.request_details == {"endpoint": "/bills"}
    assert context.response_details == {"status": 404}
    assert context.additional_info == {"attempt": 2}
    
    # Test conversion to dict
    context_dict = context.to_dict()
    assert context_dict["request_id"] == "req-123"
    assert context_dict["timestamp"] == timestamp.isoformat()
    assert context_dict["source"] == ApiErrorSource.CONGRESS
    assert context_dict["request_details"] == {"endpoint": "/bills"}
    assert context_dict["response_details"] == {"status": 404}
    assert context_dict["additional_info"] == {"attempt": 2}


def test_exception_to_dict():
    """Test PyGovPubException to_dict method."""
    context = ErrorContext(request_id="test-123")
    exc = PyGovPubException(
        message="Test error",
        error_code=ErrorCode.DATA_PARSING,
        suggestion="Check the data format",
        context=context
    )
    
    result = exc.to_dict()
    
    assert result["message"] == "Test error"
    assert result["status_code"] == 500
    assert result["error_code"] == int(ErrorCode.DATA_PARSING)
    assert result["error_type"] == "DATA_PARSING"
    assert result["severity"] == ErrorSeverity.ERROR
    assert "context" in result
    assert result["context"]["request_id"] == "test-123"
    assert "suggestion" in result
    assert result["suggestion"] == "Check the data format"


def test_authentication_errors():
    """Test authentication error hierarchy."""
    # Base authentication error
    auth_error = AuthenticationError("Auth failed")
    assert auth_error.status_code == 401
    assert auth_error.error_code == ErrorCode.AUTH_GENERAL
    
    # Missing API key error
    missing_key = MissingApiKeyError("No API key for Congress.gov", ApiErrorSource.CONGRESS)
    assert missing_key.status_code == 401
    assert missing_key.error_code == ErrorCode.AUTH_MISSING_KEY
    assert missing_key.suggestion is not None
    assert "Configure API key" in missing_key.suggestion
    assert missing_key.context.source == ApiErrorSource.CONGRESS
    
    # Invalid API key error
    invalid_key = InvalidApiKeyError("Invalid API key", ApiErrorSource.GOVINFO)
    assert invalid_key.status_code == 401
    assert invalid_key.error_code == ErrorCode.AUTH_INVALID_KEY
    assert invalid_key.suggestion is not None
    assert "Verify API key" in invalid_key.suggestion
    assert invalid_key.context.source == ApiErrorSource.GOVINFO


def test_rate_limit_error():
    """Test rate limit exceeded error."""
    # Without retry time
    rate_error = RateLimitExceededError("Rate limit exceeded", api_source=ApiErrorSource.CONGRESS)
    assert rate_error.status_code == 429
    assert rate_error.error_code == ErrorCode.RATE_LIMIT_EXCEEDED
    assert rate_error.severity == ErrorSeverity.WARNING
    assert rate_error.retry_after is None
    assert rate_error.suggestion is not None
    assert "Reduce request frequency" in rate_error.suggestion
    assert len(rate_error.recovery_options) > 0
    
    # With retry time
    retry_error = RateLimitExceededError(
        "Rate limit exceeded", 
        retry_after=30, 
        api_source=ApiErrorSource.GOVINFO
    )
    assert retry_error.retry_after == 30
    assert retry_error.suggestion is not None
    assert "Retry after 30 seconds" in retry_error.suggestion
    assert any("Wait for 30 seconds" in opt for opt in retry_error.recovery_options)
    assert retry_error.context.source == ApiErrorSource.GOVINFO


def test_resource_errors():
    """Test resource error types."""
    # Resource not found
    not_found = ResourceNotFoundError(
        "Bill not found", 
        resource_type="bill", 
        resource_id="hr123-117"
    )
    assert not_found.status_code == 404
    assert not_found.error_code == ErrorCode.RESOURCE_NOT_FOUND
    assert not_found.severity == ErrorSeverity.WARNING
    assert not_found.details["resource_type"] == "bill"
    assert not_found.details["resource_id"] == "hr123-117"
    assert not_found.suggestion is not None
    assert "Verify that bill with ID 'hr123-117' exists" in not_found.suggestion
    
    # Resource not found without resource_type and resource_id
    simple_not_found = ResourceNotFoundError("Resource not found")
    assert simple_not_found.status_code == 404
    assert simple_not_found.error_code == ErrorCode.RESOURCE_NOT_FOUND
    assert simple_not_found.suggestion is not None
    assert "Verify the resource identifier and existence" in simple_not_found.suggestion
    
    # Resource unavailable
    unavailable = ResourceUnavailableError(
        "Bill temporarily unavailable",
        resource_type="bill",
        resource_id="hr123-117",
        retry_after=60
    )
    assert unavailable.status_code == 503
    assert unavailable.error_code == ErrorCode.RESOURCE_UNAVAILABLE
    assert unavailable.severity == ErrorSeverity.WARNING
    assert unavailable.details["resource_type"] == "bill"
    assert unavailable.details["resource_id"] == "hr123-117"
    assert unavailable.details["retry_after"] == 60
    assert unavailable.suggestion is not None
    assert "Retry after 60 seconds" in unavailable.suggestion
    assert len(unavailable.recovery_options) > 0


def test_api_errors():
    """Test API error hierarchy."""
    # Base API error
    api_error = ApiError(
        message="API error occurred", 
        status_code=500, 
        api_name="testapi",
        original_error={"code": "server_error"},
        endpoint="/test"
    )
    assert api_error.status_code == 500
    assert api_error.error_code == ErrorCode.API_SERVER_ERROR  # Should be server error based on status
    assert api_error.api_name == "testapi"
    assert api_error.details["api_name"] == "testapi"
    assert api_error.details["original_error"] == {"code": "server_error"}
    assert api_error.details["endpoint"] == "/test"
    
    # Congress API error
    congress_error = CongressApiError(
        message="Congress API error", 
        status_code=400,
        endpoint="/bills"
    )
    assert congress_error.status_code == 400
    assert congress_error.api_name == "congress"
    assert congress_error.details["api_name"] == "congress"
    assert congress_error.details["endpoint"] == "/bills"
    assert congress_error.context.source == ApiErrorSource.CONGRESS
    
    # GovInfo API error
    govinfo_error = GovInfoApiError(
        message="GovInfo API error", 
        status_code=500
    )
    assert govinfo_error.status_code == 500
    assert govinfo_error.api_name == "govinfo"
    assert govinfo_error.details["api_name"] == "govinfo"
    assert govinfo_error.context.source == ApiErrorSource.GOVINFO


def test_network_errors():
    """Test network error hierarchy."""
    # Base network error
    net_error = NetworkError("Network error occurred")
    assert net_error.status_code == 503
    assert net_error.error_code == ErrorCode.NETWORK_GENERAL
    assert net_error.severity == ErrorSeverity.ERROR
    assert net_error.context.source == ApiErrorSource.NETWORK
    assert len(net_error.recovery_options) > 0
    
    # Timeout error
    timeout = TimeoutError("Request timed out", timeout_seconds=30)
    assert timeout.status_code == 503
    assert timeout.error_code == ErrorCode.NETWORK_TIMEOUT
    assert timeout.details["timeout_seconds"] == 30
    assert timeout.suggestion is not None
    assert "Increase timeout" in timeout.suggestion
    
    # Connection error
    conn_error = ConnectionError("Failed to connect to server")
    assert conn_error.status_code == 503
    assert conn_error.error_code == ErrorCode.NETWORK_CONNECTION_ERROR


def test_data_errors():
    """Test data error hierarchy."""
    # Parsing error
    parsing_error = DataParsingError(
        "Failed to parse JSON",
        data_format="JSON",
        parsing_error=ValueError("Invalid JSON")
    )
    assert parsing_error.status_code == 400
    assert parsing_error.error_code == ErrorCode.DATA_PARSING
    assert parsing_error.severity == ErrorSeverity.WARNING
    assert parsing_error.details["data_format"] == "JSON"
    assert "Invalid JSON" in parsing_error.details["parsing_error"]
    assert parsing_error.suggestion is not None
    
    # Validation error
    validation_error = DataValidationError(
        "Data validation failed",
        validation_errors={"field": "Must be a string"}
    )
    assert validation_error.status_code == 400
    assert validation_error.error_code == ErrorCode.DATA_VALIDATION_FAILED
    assert validation_error.details["validation_errors"] == {"field": "Must be a string"}
    assert validation_error.suggestion is not None
    assert "Check data structure" in validation_error.suggestion


def test_configuration_error():
    """Test configuration error."""
    config_error = ConfigurationError("Invalid configuration")
    assert config_error.status_code == 500
    assert config_error.error_code == ErrorCode.CONFIGURATION
    assert config_error.severity == ErrorSeverity.ERROR


def test_invalid_request_error():
    """Test invalid request error."""
    invalid_req = InvalidRequestError(
        "Invalid request parameters",
        validation_errors={"param": "Required field missing"}
    )
    assert invalid_req.status_code == 400
    assert invalid_req.error_code == ErrorCode.CLIENT_INVALID_PARAMETERS
    assert invalid_req.severity == ErrorSeverity.WARNING
    assert invalid_req.details["validation_errors"] == {"param": "Required field missing"}
    assert invalid_req.suggestion is not None
    assert "Check request parameters" in invalid_req.suggestion


def test_mock_server_error():
    """Test mock server error."""
    mock_error = MockServerError("Mock server failure")
    assert mock_error.status_code == 500
    assert mock_error.error_code == ErrorCode.MOCK_GENERAL
    assert mock_error.severity == ErrorSeverity.ERROR


def test_error_context_with_none_values():
    """Test ErrorContext with None values."""
    context = ErrorContext()
    assert context.request_id is None
    assert context.timestamp is not None  # Should default to current time
    assert context.source == ApiErrorSource.INTERNAL
    assert context.request_details == {}
    assert context.response_details == {}
    assert context.additional_info == {}
    
    # Test to_dict with None values
    context_dict = context.to_dict()
    assert context_dict["request_id"] is None
    assert "timestamp" in context_dict
    assert context_dict["source"] == ApiErrorSource.INTERNAL
    assert context_dict["request_details"] == {}
    assert context_dict["response_details"] == {}
    assert context_dict["additional_info"] == {}