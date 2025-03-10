"""
Tests for the rate limit cache.
"""

import time
import pytest
from typing import Dict, Any
from unittest.mock import Mock, patch, MagicMock

from pygovpub.auth.models import ApiSource
from pygovpub.api.cache.rate_limit_cache import RateLimitCache, RateLimitInfo


def test_rate_limit_info_initialization():
    """Test RateLimitInfo initialization and defaults."""
    # Test with minimal parameters
    info = RateLimitInfo(
        limit=100,
        remaining=50,
        reset_time=time.time() + 3600
    )
    
    # Verify values
    assert info.limit == 100
    assert info.remaining == 50
    assert info.reset_time > time.time()
    assert isinstance(info.requests, list)
    assert len(info.requests) == 0


def test_rate_limit_cache_initialization():
    """Test RateLimitCache initialization."""
    # Create cache with default storage
    cache = RateLimitCache()
    
    # Check that limits are initialized for each source
    for source in ApiSource:
        allowed, reset_time = cache.check_limit(source)
        assert allowed is True
        assert reset_time is not None
        assert reset_time > time.time()
        
        # Check usage stats
        stats = cache.get_usage_stats(source)
        assert "limit" in stats
        assert "remaining" in stats
        assert "reset_in" in stats
        assert "request_count" in stats
        assert stats["request_count"] == 0


def test_track_request():
    """Test tracking a request."""
    cache = RateLimitCache()
    source = ApiSource.CONGRESS
    
    # Get initial remaining count
    stats = cache.get_usage_stats(source)
    initial_remaining = stats["remaining"]
    
    # Track a request
    success = cache.track_request(source)
    assert success is True
    
    # Verify remaining count decremented
    stats = cache.get_usage_stats(source)
    assert stats["remaining"] == initial_remaining - 1
    assert stats["request_count"] == 1
    assert stats["request_rate"] == 1


def test_update_from_headers_congress():
    """Test updating from Congress.gov headers."""
    cache = RateLimitCache()
    source = ApiSource.CONGRESS
    
    # Mock headers
    headers = {
        "x-ratelimit-remaining": "4000",
        "x-ratelimit-reset": str(int(time.time()) + 1800)
    }
    
    # Update from headers
    success = cache.update_from_headers(source, headers)
    assert success is True
    
    # Verify updates
    stats = cache.get_usage_stats(source)
    assert stats["remaining"] == 4000
    assert 0 < stats["reset_in"] <= 1800
    assert stats["request_count"] == 1


def test_update_from_headers_govinfo():
    """Test updating from GovInfo.gov headers."""
    cache = RateLimitCache()
    source = ApiSource.GOVINFO
    
    # Mock headers
    headers = {
        "x-rate-limit-remaining": "800",
        "x-rate-limit-reset": "1800"  # seconds until reset
    }
    
    # Update from headers
    success = cache.update_from_headers(source, headers)
    assert success is True
    
    # Verify updates
    stats = cache.get_usage_stats(source)
    assert stats["remaining"] == 800
    assert 0 < stats["reset_in"] <= 1800
    assert stats["request_count"] == 1


def test_check_limit():
    """Test checking rate limits."""
    cache = RateLimitCache()
    source = ApiSource.CONGRESS
    
    # Initial check should allow requests
    allowed, reset_time = cache.check_limit(source)
    assert allowed is True
    assert reset_time > time.time()
    
    # Track many requests to exhaust limit
    for _ in range(5000):
        cache.track_request(source)
    
    # Check limit again, should be exhausted
    allowed, reset_time = cache.check_limit(source)
    assert allowed is False
    assert reset_time > time.time()


def test_limit_reset():
    """Test rate limit reset."""
    cache = RateLimitCache()
    source = ApiSource.CONGRESS
    
    # Mock a storage item with expired reset time
    key = cache._get_source_key(source)
    info = RateLimitInfo(
        limit=5000,
        remaining=0,  # Exhausted
        reset_time=time.time() - 60,  # Already expired
        requests=[]
    )
    cache._storage.set(key, info)
    
    # Check limit, should be reset
    allowed, reset_time = cache.check_limit(source)
    assert allowed is True
    assert reset_time > time.time()
    
    # Verify remaining count reset
    stats = cache.get_usage_stats(source)
    assert stats["remaining"] == 5000


def test_request_rate_calculation():
    """Test request rate calculation."""
    cache = RateLimitCache()
    source = ApiSource.CONGRESS
    
    # Track requests with timestamps
    now = time.time()
    
    # Create mock info with some requests in the past hour
    # but only a few in the last minute
    key = cache._get_source_key(source)
    info = RateLimitInfo(
        limit=5000,
        remaining=4980,
        reset_time=now + 3600,
        requests=[
            # 10 requests in last minute
            now - 1, now - 5, now - 10, now - 15, now - 20,
            now - 25, now - 30, now - 35, now - 40, now - 50,
            # 10 requests older than a minute
            now - 70, now - 80, now - 90, now - 100, now - 200,
            now - 300, now - 400, now - 500, now - 600, now - 700
        ]
    )
    cache._storage.set(key, info)
    
    # Get usage stats
    stats = cache.get_usage_stats(source)
    
    # Verify counts
    assert stats["request_count"] == 20  # Total requests
    assert stats["request_rate"] == 10   # Requests in last minute


def test_header_parsing_error_handling():
    """Test error handling in header parsing."""
    cache = RateLimitCache()
    source = ApiSource.CONGRESS
    
    # Invalid headers
    headers = {
        "x-ratelimit-remaining": "not-a-number",
        "x-ratelimit-reset": "also-not-a-number"
    }
    
    # Should not raise exception
    success = cache.update_from_headers(source, headers)
    assert success is True
    
    # Values should fall back to defaults
    allowed, reset_time = cache.check_limit(source)
    assert allowed is True
    assert reset_time > time.time()


def test_empty_headers():
    """Test handling empty headers."""
    cache = RateLimitCache()
    
    # Empty headers should return False
    success = cache.update_from_headers(ApiSource.CONGRESS, {})
    assert success is False
    
    # None headers should return False
    success = cache.update_from_headers(ApiSource.CONGRESS, None)
    assert success is False