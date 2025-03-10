"""
Tests for authentication models.

This module tests the model classes for API authentication
and usage tracking.
"""

import pytest
from datetime import datetime
from zoneinfo import ZoneInfo
from unittest.mock import MagicMock

# Direct import using conftest.py path settings
from pygovpub.auth.models import ApiSource, AuthType


def test_api_configuration_model():
    """Test ApiConfiguration model fields."""
    # Create a test instance with mock attributes
    source = ApiSource.CONGRESS
    base_url = "https://api.congress.gov/v3"
    auth_type = AuthType.HEADER
    auth_key_name = "X-API-Key"
    key_reference = "env:CONGRESS_GOV_API_KEY"
    rate_limit = 5000
    rate_limit_period = 3600
    active = True
    created_at = datetime.now(ZoneInfo("UTC"))
    updated_at = datetime.now(ZoneInfo("UTC"))
    
    # Verify enums work correctly
    assert source == ApiSource.CONGRESS
    assert auth_type == AuthType.HEADER
    assert source.value == "congress"
    assert auth_type.value == "header"
    
    # Verify the types match what we expect
    assert isinstance(created_at, datetime)
    assert isinstance(updated_at, datetime)
    assert isinstance(rate_limit, int)
    assert isinstance(rate_limit_period, int)
    assert isinstance(active, bool)
    assert isinstance(base_url, str)
    assert isinstance(auth_key_name, str)
    assert isinstance(key_reference, str)


def test_api_usage_model():
    """Test ApiUsage model fields."""
    # Create test values
    source = ApiSource.GOVINFO
    endpoint = "/collections"
    status_code = 200
    response_time_ms = 150
    rate_limit_remaining = 999
    rate_limit_reset = datetime.now(ZoneInfo("UTC"))
    success = True
    error_message = None
    request_time = datetime.now(ZoneInfo("UTC"))
    
    # Verify enums work correctly
    assert source == ApiSource.GOVINFO
    assert source.value == "govinfo"
    
    # Verify the types match what we expect
    assert isinstance(endpoint, str)
    assert isinstance(status_code, int)
    assert isinstance(response_time_ms, int)
    assert isinstance(rate_limit_remaining, int)
    assert isinstance(rate_limit_reset, datetime)
    assert isinstance(success, bool)
    assert error_message is None
    assert isinstance(request_time, datetime)


def test_api_source_enum():
    """Test ApiSource enum values."""
    assert ApiSource.CONGRESS == "congress"
    assert ApiSource.GOVINFO == "govinfo"
    
    # Test conversion from string
    assert ApiSource("congress") == ApiSource.CONGRESS
    assert ApiSource("govinfo") == ApiSource.GOVINFO
    
    # Test invalid value
    with pytest.raises(ValueError):
        ApiSource("invalid")


def test_auth_type_enum():
    """Test AuthType enum values."""
    assert AuthType.HEADER == "header"
    assert AuthType.PARAMETER == "parameter"
    
    # Test conversion from string
    assert AuthType("header") == AuthType.HEADER
    assert AuthType("parameter") == AuthType.PARAMETER
    
    # Test invalid value
    with pytest.raises(ValueError):
        AuthType("invalid")