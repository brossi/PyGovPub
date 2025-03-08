"""
Tests to complete coverage of the rate_limiter module.
These tests focus on edge cases and exceptional paths.
"""

import pytest
import json
from unittest import mock
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests
from prometheus_client import Counter

from pygovpub.auth.rate_limiter import (
    RateLimiter, ThrottleStrategy, ApiRateLimit, RateLimitData
)
from pygovpub.auth.models import ApiSource
from pygovpub.exceptions import RateLimitExceededError


def test_rate_limiter_with_persistence():
    """Test rate limiter with persistence store."""
    # This tests lines 94-118
    
    # Create a mock persistence store
    class MockPersistenceStore:
        def __init__(self):
            self.data = {}
        
        def save(self, key, value):
            self.data[key] = value
            return True
        
        def load(self, key):
            return self.data.get(key)
        
        def delete(self, key):
            if key in self.data:
                del self.data[key]
                return True
            return False
    
    # Create rate limiter with persistence
    mock_store = MockPersistenceStore()
    limiter = RateLimiter(persistence_store=mock_store)
    
    # Track a request
    limiter.track_request(
        api_source=ApiSource.CONGRESS,
        key="test_key",
        endpoint="/test",
        remaining=5,
        reset_at=datetime.now(ZoneInfo("UTC")) + timedelta(seconds=60)
    )
    
    # Verify data was persisted
    assert "congress:test_key:/test" in mock_store.data
    
    # Load from persistence
    data = limiter.get_rate_limit(ApiSource.CONGRESS, "test_key", "/test")
    assert data is not None
    assert data.remaining == 5
    
    # Delete from persistence
    result = limiter._delete_rate_limit_data("congress:test_key:/test")
    assert result is True
    
    # Verify it's gone
    data = limiter.get_rate_limit(ApiSource.CONGRESS, "test_key", "/test")
    assert data is None


def test_metrics_integration():
    """Test metrics integration in rate limiter."""
    # This tests lines 133-149
    
    # Create a limiter with metrics enabled
    limiter = RateLimiter(collect_metrics=True)
    
    # Replace the counter with a mock
    mock_counter = mock.MagicMock(spec=Counter)
    limiter.request_count = mock_counter
    limiter.throttled_count = mock_counter
    
    # Track a request
    limiter.track_request(
        api_source=ApiSource.CONGRESS,
        key="test_key",
        endpoint="/test",
        remaining=5,
        reset_at=datetime.now(ZoneInfo("UTC")) + timedelta(seconds=60)
    )
    
    # Verify metrics were updated
    mock_counter.labels.assert_called_with(api="congress", endpoint="/test")
    mock_counter.labels().inc.assert_called()
    
    # Test throttling metrics
    limiter.track_request(
        api_source=ApiSource.CONGRESS,
        key="throttled_key",
        endpoint="/test",
        remaining=0,
        reset_at=datetime.now(ZoneInfo("UTC")) + timedelta(seconds=60)
    )
    
    # Check throttled counter was called
    assert mock_counter.labels().inc.call_count >= 2


def test_parse_headers_unknown_source():
    """Test header parsing with unknown API source."""
    # This tests line 183
    limiter = RateLimiter()
    
    # Try to parse headers for an unsupported source
    headers = {"X-Rate-Limit-Remaining": "5"}
    result = limiter.parse_headers_for_rate_limits("UNKNOWN_SOURCE", headers)
    
    # Should return None for unknown sources
    assert result is None


def test_wait_for_capacity_timeout():
    """Test wait_for_capacity with timeout."""
    # This tests lines 205-207
    limiter = RateLimiter()
    
    # Set up a rate limit that exceeds the timeout
    reset_time = datetime.now(ZoneInfo("UTC")) + timedelta(seconds=30)
    limiter.track_request(
        api_source=ApiSource.CONGRESS,
        key="test_key",
        endpoint="/test",
        remaining=0,
        reset_at=reset_time
    )
    
    # Try to wait with a short timeout
    with pytest.raises(RateLimitExceededError):
        limiter.wait_for_capacity(
            api_source=ApiSource.CONGRESS,
            key="test_key",
            endpoint="/test",
            timeout_seconds=1
        )


def test_pre_request_with_custom_strategy():
    """Test pre_request with custom strategy."""
    # This tests line 216
    limiter = RateLimiter()
    
    # Create a custom strategy that always raises
    def custom_strategy(limiter, source, key, endpoint):
        raise RateLimitExceededError("Custom strategy rejected request")
    
    # Try to use the custom strategy
    with pytest.raises(RateLimitExceededError, match="Custom strategy rejected request"):
        limiter.pre_request(
            api_source=ApiSource.CONGRESS,
            key="test_key",
            endpoint="/test",
            strategy=custom_strategy
        )


def test_rate_limit_data_expired():
    """Test RateLimitData expiration check."""
    # This tests line 249
    # Create a RateLimitData that's already expired
    past_time = datetime.now(ZoneInfo("UTC")) - timedelta(seconds=60)
    data = RateLimitData(
        source=ApiSource.CONGRESS,
        endpoint="/test",
        remaining=0,
        reset_at=past_time,
        last_updated=past_time
    )
    
    # Check that it's expired
    assert data.is_expired()
    
    # Create one that's not expired
    future_time = datetime.now(ZoneInfo("UTC")) + timedelta(seconds=60)
    data = RateLimitData(
        source=ApiSource.CONGRESS,
        endpoint="/test",
        remaining=0,
        reset_at=future_time,
        last_updated=past_time
    )
    
    # Check that it's not expired
    assert not data.is_expired()