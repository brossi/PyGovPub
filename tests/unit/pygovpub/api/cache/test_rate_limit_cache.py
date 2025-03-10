"""
Tests for the rate limit cache.
"""

import time
import pytest
from typing import Dict, Any
from unittest.mock import Mock, patch, MagicMock

from pygovpub.auth.models import ApiSource
from pygovpub.api.cache.rate_limit_cache import RateLimitCache, RateLimitInfo
from pygovpub.api.cache.storage import CacheStorage, CacheItem, MemoryStorage


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


def test_storage_get_failure_in_update_from_headers():
    """Test handling storage get failure in update_from_headers."""
    # Create a mock storage that returns None for get
    mock_storage = Mock(spec=CacheStorage)
    mock_storage.get.return_value = None
    mock_storage.set = Mock()  # Still need set to work
    
    cache = RateLimitCache(storage=mock_storage)
    source = ApiSource.CONGRESS
    
    # Test with valid headers
    headers = {
        "x-ratelimit-remaining": "4000",
        "x-ratelimit-reset": str(int(time.time()) + 1800)
    }
    
    # Mock _initialize_limits to do nothing
    with patch.object(cache, '_initialize_limits') as mock_init:
        # Call update_from_headers
        success = cache.update_from_headers(source, headers)
        
        # Verify initialization was attempted
        assert mock_init.called
        
        # This should fail gracefully
        assert success is False


def test_reset_time_update():
    """Test updating reset time in update_from_headers."""
    cache = RateLimitCache()
    source = ApiSource.CONGRESS
    
    # First, update without reset time
    headers1 = {
        "x-ratelimit-remaining": "4000"
        # No reset time
    }
    
    success = cache.update_from_headers(source, headers1)
    assert success is True
    
    # Then update with reset time
    headers2 = {
        "x-ratelimit-reset": str(int(time.time()) + 1800)
    }
    
    success = cache.update_from_headers(source, headers2)
    assert success is True
    
    # Verify reset time was updated
    stats = cache.get_usage_stats(source)
    assert 0 < stats["reset_in"] <= 1800


def test_storage_get_failure_in_track_request():
    """Test handling storage get failure in track_request."""
    # Create a mock storage that returns None for get
    mock_storage = Mock(spec=CacheStorage)
    mock_storage.get.return_value = None
    mock_storage.set = Mock()  # Still need set to work
    
    cache = RateLimitCache(storage=mock_storage)
    source = ApiSource.CONGRESS
    
    # Mock _initialize_limits to do nothing
    with patch.object(cache, '_initialize_limits') as mock_init:
        # Call track_request
        success = cache.track_request(source)
        
        # Verify initialization was attempted
        assert mock_init.called
        
        # This should fail gracefully
        assert success is False


def test_reset_handling_in_track_request():
    """Test reset time handling in track_request."""
    cache = RateLimitCache()
    source = ApiSource.CONGRESS
    
    # Create an info object with expired reset time
    key = cache._get_source_key(source)
    now = time.time()
    info = RateLimitInfo(
        limit=5000,
        remaining=500,
        reset_time=now - 10,  # Already expired
        requests=[]
    )
    cache._storage.set(key, info)
    
    # Track a request
    success = cache.track_request(source)
    assert success is True
    
    # Get updated info
    item = cache._storage.get(key)
    assert item is not None
    updated_info = item.value
    
    # Verify reset happened
    assert updated_info.remaining == 4999  # Reset to limit (5000) then decremented
    assert updated_info.reset_time > now  # New reset time in the future


def test_storage_get_failure_in_check_limit():
    """Test handling storage get failure in check_limit."""
    # Create a mock storage that returns None for get
    mock_storage = Mock(spec=CacheStorage)
    mock_storage.get.return_value = None
    mock_storage.set = Mock()  # Still need set to work
    
    cache = RateLimitCache(storage=mock_storage)
    source = ApiSource.CONGRESS
    
    # Mock _initialize_limits to do nothing the first time, then return a valid item
    mock_storage.get.side_effect = [
        None,  # First call returns None
        None   # Second call also returns None
    ]
    
    # Call check_limit
    allowed, reset_time = cache.check_limit(source)
    
    # Should default to allowed with no reset time
    assert allowed is True
    assert reset_time is None


def test_storage_get_failure_in_get_usage_stats():
    """Test handling storage get failure in get_usage_stats."""
    # Create a mock storage that returns None for get
    mock_storage = Mock(spec=CacheStorage)
    mock_storage.get.return_value = None
    mock_storage.set = Mock()  # Still need set to work
    
    cache = RateLimitCache(storage=mock_storage)
    source = ApiSource.CONGRESS
    
    # Mock _initialize_limits to do nothing the first time, then return a valid item
    mock_storage.get.side_effect = [
        None,  # First call returns None
        None   # Second call also returns None
    ]
    
    # Call get_usage_stats
    stats = cache.get_usage_stats(source)
    
    # Should return default stats
    assert stats["limit"] == cache.DEFAULT_LIMITS.get(source)
    assert stats["remaining"] == cache.DEFAULT_LIMITS.get(source)
    assert stats["reset_in"] == cache.DEFAULT_RESET_PERIOD
    assert stats["request_count"] == 0
    assert stats["request_rate"] == 0


def test_get_usage_stats_with_reset():
    """Test get_usage_stats when reset time has passed."""
    cache = RateLimitCache()
    source = ApiSource.CONGRESS
    
    # Create an info object with expired reset time
    key = cache._get_source_key(source)
    now = time.time()
    info = RateLimitInfo(
        limit=5000,
        remaining=500,
        reset_time=now - 10,  # Already expired
        requests=[now - 30, now - 20]  # Requests are within the last minute
    )
    cache._storage.set(key, info)
    
    # Get usage stats
    stats = cache.get_usage_stats(source)
    
    # Verify reset would happen
    assert stats["limit"] == 5000
    assert stats["remaining"] == 5000  # Would be reset to full limit
    assert stats["reset_in"] == cache.DEFAULT_RESET_PERIOD
    assert stats["request_count"] == 2
    
    # The request rate is still calculated even if the limit is reset
    # These requests are within the last minute timeframe
    assert stats["request_rate"] == 2


def test_parse_remaining_edge_cases():
    """Test edge cases in _parse_remaining."""
    cache = RateLimitCache()
    
    # Test with Congress.gov headers
    # 1. Missing header
    headers1 = {"other-header": "value"}
    assert cache._parse_remaining(headers1, ApiSource.CONGRESS) is None
    
    # 2. Invalid value
    headers2 = {"x-ratelimit-remaining": "not-a-number"}
    assert cache._parse_remaining(headers2, ApiSource.CONGRESS) is None
    
    # 3. Valid value
    headers3 = {"x-ratelimit-remaining": "4500"}
    assert cache._parse_remaining(headers3, ApiSource.CONGRESS) == 4500
    
    # Test with GovInfo.gov headers
    # 1. Missing header
    headers4 = {"other-header": "value"}
    assert cache._parse_remaining(headers4, ApiSource.GOVINFO) is None
    
    # 2. Invalid value
    headers5 = {"x-rate-limit-remaining": "not-a-number"}
    assert cache._parse_remaining(headers5, ApiSource.GOVINFO) is None
    
    # 3. Valid value
    headers6 = {"x-rate-limit-remaining": "850"}
    assert cache._parse_remaining(headers6, ApiSource.GOVINFO) == 850


def test_parse_reset_time_edge_cases():
    """Test edge cases in _parse_reset_time."""
    cache = RateLimitCache()
    now = time.time()
    
    # Test with Congress.gov headers
    # 1. Missing header
    headers1 = {"other-header": "value"}
    assert cache._parse_reset_time(headers1, ApiSource.CONGRESS) is None
    
    # 2. Invalid value
    headers2 = {"x-ratelimit-reset": "not-a-number"}
    reset_time = cache._parse_reset_time(headers2, ApiSource.CONGRESS)
    assert reset_time is not None
    assert reset_time > now  # Should default to now + DEFAULT_RESET_PERIOD
    
    # 3. Valid value
    future_time = now + 1800
    headers3 = {"x-ratelimit-reset": str(future_time)}
    assert cache._parse_reset_time(headers3, ApiSource.CONGRESS) == future_time
    
    # Test with GovInfo.gov headers
    # 1. Missing header
    headers4 = {"other-header": "value"}
    assert cache._parse_reset_time(headers4, ApiSource.GOVINFO) is None
    
    # 2. Invalid value
    headers5 = {"x-rate-limit-reset": "not-a-number"}
    reset_time = cache._parse_reset_time(headers5, ApiSource.GOVINFO)
    assert reset_time is not None
    assert reset_time > now  # Should default to now + DEFAULT_RESET_PERIOD
    
    # 3. Valid value - GovInfo uses seconds until reset
    headers6 = {"x-rate-limit-reset": "1800"}
    reset_time = cache._parse_reset_time(headers6, ApiSource.GOVINFO)
    assert reset_time is not None
    assert now + 1800 - 1 <= reset_time <= now + 1800 + 1  # Allow small float precision differences
    
    # 4. Test with unknown API source
    headers7 = {"x-rate-limit-reset": "1800"}
    assert cache._parse_reset_time(headers7, "UNKNOWN_SOURCE") is None


def test_edge_case_parser_with_missing_header():
    """Test parsing behavior with completely missing headers."""
    cache = RateLimitCache()
    
    # Test with empty headers dict
    headers = {}
    
    # For Congress source
    remaining = cache._parse_remaining(headers, ApiSource.CONGRESS)
    assert remaining is None
    
    reset_time = cache._parse_reset_time(headers, ApiSource.CONGRESS)
    assert reset_time is None
    
    # For GovInfo source
    remaining = cache._parse_remaining(headers, ApiSource.GOVINFO)
    assert remaining is None
    
    reset_time = cache._parse_reset_time(headers, ApiSource.GOVINFO)
    assert reset_time is None
    
    # Test with None headers
    remaining = cache._parse_remaining(None, ApiSource.CONGRESS)
    assert remaining is None
    
    reset_time = cache._parse_reset_time(None, ApiSource.CONGRESS)
    assert reset_time is None


def test_unknown_header_format():
    """Test with completely different header formats."""
    cache = RateLimitCache()
    
    # Headers with completely different keys that don't match either format
    headers = {
        "x-custom-limit-remaining": "500",
        "x-custom-limit-reset": "1200"
    }
    
    # For both sources
    for source in [ApiSource.CONGRESS, ApiSource.GOVINFO]:
        remaining = cache._parse_remaining(headers, source)
        assert remaining is None
        
        reset_time = cache._parse_reset_time(headers, source)
        assert reset_time is None


def test_consecutive_storage_failures():
    """Test handling consecutive storage failures."""
    # Create a mock storage with more complex failure patterns
    mock_storage = Mock(spec=CacheStorage)
    
    # For update_from_headers: First get fails, initialize, second get also fails
    mock_storage.get.side_effect = [None, None, None, None]
    mock_storage.set = Mock()
    
    cache = RateLimitCache(storage=mock_storage)
    source = ApiSource.CONGRESS
    
    # Update from headers should fail gracefully after initialize fails
    headers = {"x-ratelimit-remaining": "4000"}
    success = cache.update_from_headers(source, headers)
    assert success is False
    
    # Reset mock to test track_request with same pattern
    mock_storage.reset_mock()
    mock_storage.get.side_effect = [None, None]
    
    # Track request should fail gracefully
    success = cache.track_request(source)
    assert success is False