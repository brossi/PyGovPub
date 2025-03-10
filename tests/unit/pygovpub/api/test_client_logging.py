"""
Test the API client logging and status tracking.

These tests verify that API client logging correctly captures and tracks API 
requests, responses, rate limits, and other metrics for operational monitoring.
"""

import json
import time
from datetime import datetime, timedelta, timezone
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest
import structlog
from httpx import Response

from pygovpub.auth.models import ApiSource
from pygovpub.logging import configure_logging
from pygovpub.logging.client import (
    ApiEventType,
    ApiLogger,
    get_api_logger,
    get_all_api_metrics,
)


@pytest.fixture
def api_logger():
    """Create a test API logger."""
    return ApiLogger(api_source=ApiSource.CONGRESS)


@pytest.fixture
def logger_with_capture():
    """Create a logger with StringIO capture."""
    # Setup a string buffer to capture log output
    log_output = StringIO()
    
    # Create a custom handler to capture logs
    import logging
    handler = logging.StreamHandler(log_output)
    
    # Configure logging to output JSON for easier parsing
    configure_logging(log_level="DEBUG", json_format=True, handlers=[handler])
    
    # Create API logger
    logger = ApiLogger(api_source=ApiSource.CONGRESS, include_payloads=True, include_headers=True)
    
    return logger, log_output


def test_api_logger_init():
    """Test API logger initialization."""
    logger = ApiLogger(api_source=ApiSource.CONGRESS)
    assert logger.api_source == "congress"
    assert logger._total_requests == 0
    assert logger._failed_requests == 0
    assert logger._rate_limited_requests == 0
    assert logger._cached_requests == 0
    
    # Test with string source
    logger = ApiLogger(api_source="test_api")
    assert logger.api_source == "test_api"


def test_log_request_start(logger_with_capture):
    """Test logging the start of a request."""
    logger, log_output = logger_with_capture
    
    # Log a request
    request_id = logger.log_request_start(
        endpoint="/v3/bill",
        method="GET",
        params={"limit": 10},
        headers={"X-Api-Key": "test_key"},
    )
    
    # Parse the log
    output = log_output.getvalue()
    log_entry = json.loads(output)
    
    # Check basic fields
    assert log_entry["event"] == ApiEventType.REQUEST_STARTED
    assert log_entry["category"] == "api"
    assert log_entry["api_source"] == "congress"
    assert log_entry["endpoint"] == "/v3/bill"
    assert log_entry["method"] == "GET"
    assert log_entry["request_id"] == request_id
    
    # Check sensitive data handling
    assert log_entry["params"] == {"limit": 10}
    assert log_entry["headers"]["X-Api-Key"] == "[REDACTED]"
    
    # Check metrics
    assert logger._total_requests == 1
    assert logger._active_requests == 1


def test_log_request_complete(logger_with_capture):
    """Test logging the completion of a request."""
    logger, log_output = logger_with_capture
    
    # Start a request
    request_id = logger.log_request_start(
        endpoint="/v3/bill",
        method="GET",
    )
    
    # Clear the buffer
    log_output.seek(0)
    log_output.truncate(0)
    
    # Log completion
    logger.log_request_complete(
        request_id=request_id,
        status_code=200,
        duration_ms=150,
        response_data={"results": [{"id": 1}]},
        response_headers={
            "X-RateLimit-Remaining": "4990",
            "X-RateLimit-Limit": "5000",
            "X-RateLimit-Reset": "1609459200",
        },
    )
    
    # Parse the log
    output = log_output.getvalue()
    log_entry = json.loads(output)
    
    # Check basic fields
    assert log_entry["event"] == ApiEventType.REQUEST_COMPLETED
    assert log_entry["request_id"] == request_id
    assert log_entry["status_code"] == 200
    assert log_entry["duration_ms"] == 150
    
    # Check response data
    assert log_entry["response"] == {"results": [{"id": 1}]}
    
    # Check rate limit data
    assert log_entry["rate_limit_remaining"] == 4990
    assert log_entry["rate_limit_total"] == 5000
    assert "rate_limit_reset" in log_entry
    
    # Check metrics
    assert logger._total_requests == 1
    assert logger._active_requests == 0
    assert logger._total_duration_ms == 150
    assert logger._rate_limit_remaining == 4990
    assert logger._rate_limit_total == 5000
    assert logger._rate_limit_reset is not None


def test_log_request_error(logger_with_capture):
    """Test logging a request error."""
    logger, log_output = logger_with_capture
    
    # Start a request
    request_id = logger.log_request_start(
        endpoint="/v3/bill",
        method="GET",
    )
    
    # Clear the buffer
    log_output.seek(0)
    log_output.truncate(0)
    
    # Log an error
    error = ValueError("Test error")
    logger.log_request_error(
        request_id=request_id,
        error=error,
        duration_ms=50,
    )
    
    # Parse the log
    output = log_output.getvalue()
    log_entry = json.loads(output)
    
    # Check basic fields
    assert log_entry["event"] == ApiEventType.REQUEST_FAILED
    assert log_entry["request_id"] == request_id
    assert log_entry["error_type"] == "ValueError"
    assert log_entry["error_message"] == "Test error"
    assert log_entry["duration_ms"] == 50
    
    # Check metrics
    assert logger._total_requests == 1
    assert logger._active_requests == 0
    assert logger._failed_requests == 1
    assert logger._total_duration_ms == 50


def test_log_rate_limit(logger_with_capture):
    """Test logging a rate limit event."""
    logger, log_output = logger_with_capture
    
    # Start a request
    request_id = logger.log_request_start(
        endpoint="/v3/bill",
        method="GET",
    )
    
    # Clear the buffer
    log_output.seek(0)
    log_output.truncate(0)
    
    # Log a rate limit
    reset_time = datetime.now(timezone.utc) + timedelta(minutes=5)
    logger.log_rate_limit(
        request_id=request_id,
        endpoint="/v3/bill",
        reset_time=reset_time,
        retry_after=300,
    )
    
    # Parse the log
    output = log_output.getvalue()
    log_entry = json.loads(output)
    
    # Check basic fields
    assert log_entry["event"] == ApiEventType.RATE_LIMITED
    assert log_entry["request_id"] == request_id
    assert log_entry["endpoint"] == "/v3/bill"
    assert log_entry["reset_time"] == reset_time.isoformat()
    assert log_entry["retry_after"] == 300
    
    # Check metrics
    assert logger._rate_limited_requests == 1
    assert logger._rate_limit_reset == reset_time


def test_log_cache_event(logger_with_capture):
    """Test logging cache events."""
    logger, log_output = logger_with_capture
    
    # Start a request
    request_id = logger.log_request_start(
        endpoint="/v3/bill",
        method="GET",
    )
    
    # Clear the buffer
    log_output.seek(0)
    log_output.truncate(0)
    
    # Log a cache hit
    logger.log_cache_event(
        request_id=request_id,
        is_hit=True,
        key="bill:123",
        endpoint="/v3/bill/123",
    )
    
    # Parse the log
    output = log_output.getvalue()
    log_entry = json.loads(output)
    
    # Check basic fields
    assert log_entry["event"] == ApiEventType.CACHE_HIT
    assert log_entry["request_id"] == request_id
    assert log_entry["cache_key"] == "bill:123"
    assert log_entry["endpoint"] == "/v3/bill/123"
    
    # Check metrics
    assert logger._cached_requests == 1


def test_get_metrics(api_logger):
    """Test getting API metrics."""
    # Record some activity
    api_logger._total_requests = 100
    api_logger._failed_requests = 5
    api_logger._rate_limited_requests = 2
    api_logger._cached_requests = 30
    api_logger._total_duration_ms = 15000
    api_logger._rate_limit_remaining = 4900
    api_logger._rate_limit_total = 5000
    api_logger._rate_limit_reset = datetime.now(timezone.utc) + timedelta(minutes=30)
    
    # Get metrics
    metrics = api_logger.get_metrics()
    
    # Check metrics values
    assert metrics["total_requests"] == 100
    assert metrics["failed_requests"] == 5
    assert metrics["rate_limited_requests"] == 2
    assert metrics["cached_requests"] == 30
    assert metrics["avg_duration_ms"] == 150  # 15000/100
    assert metrics["rate_limit_remaining"] == 4900
    assert metrics["rate_limit_total"] == 5000
    assert "rate_limit_reset" in metrics
    assert "seconds_until_reset" in metrics


def test_sanitize_payload(api_logger):
    """Test sanitization of sensitive data in payloads."""
    # Test sanitizing a dictionary with sensitive keys
    payload = {
        "api_key": "secret_key",
        "token": "bearer_token",
        "auth": "basic_auth",
        "password": "123456",
        "safe_data": "public_info",
    }
    
    sanitized = api_logger._sanitize_payload(payload)
    
    # Check that sensitive keys are redacted
    assert sanitized["api_key"] == "[REDACTED]"
    assert sanitized["token"] == "[REDACTED]"
    assert sanitized["auth"] == "[REDACTED]"
    assert sanitized["password"] == "[REDACTED]"
    
    # Check that safe keys are preserved
    assert sanitized["safe_data"] == "public_info"
    
    # Test with non-dict data
    assert api_logger._sanitize_payload("test_string") == "test_string"
    assert api_logger._sanitize_payload(123) == 123


def test_sanitize_headers(api_logger):
    """Test sanitization of sensitive headers."""
    headers = {
        "Authorization": "Bearer token123",
        "X-Api-Key": "api_key_123",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    
    sanitized = api_logger._sanitize_headers(headers)
    
    # Check that sensitive headers are redacted
    assert sanitized["Authorization"] == "[REDACTED]"
    assert sanitized["X-Api-Key"] == "[REDACTED]"
    
    # Check that safe headers are preserved
    assert sanitized["Content-Type"] == "application/json"
    assert sanitized["Accept"] == "application/json"
    
    # Test case-insensitive matching
    headers = {"authorization": "Bearer token123"}
    sanitized = api_logger._sanitize_headers(headers)
    assert sanitized["authorization"] == "[REDACTED]"


def test_get_api_logger():
    """Test getting an API logger."""
    # Get a logger
    logger1 = get_api_logger(ApiSource.CONGRESS)
    
    # Check that it's the right type
    assert isinstance(logger1, ApiLogger)
    assert logger1.api_source == "congress"
    
    # Get the same logger again
    logger2 = get_api_logger(ApiSource.CONGRESS)
    
    # Should be the same instance
    assert logger1 is logger2
    
    # Get a different logger
    logger3 = get_api_logger(ApiSource.GOVINFO)
    
    # Should be a different instance
    assert logger1 is not logger3
    assert logger3.api_source == "govinfo"


def test_get_all_api_metrics():
    """Test getting metrics for all API loggers."""
    # Get loggers for different APIs
    congress_logger = get_api_logger(ApiSource.CONGRESS)
    govinfo_logger = get_api_logger(ApiSource.GOVINFO)
    
    # Record some activity
    congress_logger._total_requests = 50
    govinfo_logger._total_requests = 30
    
    # Get all metrics
    metrics = get_all_api_metrics()
    
    # Check metrics for each API
    assert "congress" in metrics
    assert "govinfo" in metrics
    assert metrics["congress"]["total_requests"] == 50
    assert metrics["govinfo"]["total_requests"] == 30