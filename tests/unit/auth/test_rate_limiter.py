"""
Tests for rate limiting functionality.

This module tests the RateLimiter class that handles
API rate limit tracking and enforcement.
"""

import asyncio
import pytest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from unittest.mock import MagicMock, patch

# Direct imports using conftest.py path configuration
from pygovpub.auth.models import ApiSource
from pygovpub.auth.rate_limiter import RateLimiter, ThrottleStrategy


@pytest.fixture
def rate_limiter():
    """Create a RateLimiter instance for testing."""
    return RateLimiter()


@pytest.mark.asyncio
async def test_track_request_in_memory(rate_limiter):
    """Test tracking requests in memory."""
    source = ApiSource.CONGRESS
    
    # Initial state
    initial_remaining = rate_limiter._memory_limits[source]["remaining"]
    
    # Track a request with rate limit headers (using timezone-aware datetime)
    future_time = datetime.now(ZoneInfo("UTC")) + timedelta(minutes=30)
    headers = {
        "x-ratelimit-remaining": "4980",
        "x-ratelimit-reset": str(int(future_time.timestamp()))
    }
    
    await rate_limiter.track_request(
        source=source,
        endpoint="/bills",
        status_code=200,
        rate_limit_headers=headers,
        response_time_ms=100,
        success=True
    )
    
    # Verify updated state
    assert rate_limiter._memory_limits[source]["remaining"] == 4980
    assert len(rate_limiter._memory_limits[source]["requests"]) == 1


@pytest.mark.asyncio
async def test_check_rate_limit_allowed(rate_limiter):
    """Test checking rate limit when requests are allowed."""
    source = ApiSource.CONGRESS
    
    # Set up state with available capacity using timezone-aware datetimes
    rate_limiter._memory_limits[source]["remaining"] = 10
    rate_limiter._memory_limits[source]["reset_time"] = datetime.now(ZoneInfo("UTC")) + timedelta(minutes=5)
    
    # Check limit
    allowed, reset_time = await rate_limiter.check_rate_limit(source)
    
    # Verify result
    assert allowed is True
    assert reset_time > datetime.now(ZoneInfo("UTC"))


@pytest.mark.asyncio
async def test_check_rate_limit_exceeded(rate_limiter):
    """Test checking rate limit when limit is exceeded."""
    source = ApiSource.CONGRESS
    
    # Set up state with no capacity (using timezone-aware datetime)
    rate_limiter._memory_limits[source]["remaining"] = 0
    reset_time = datetime.now(ZoneInfo("UTC")) + timedelta(minutes=5)
    rate_limiter._memory_limits[source]["reset_time"] = reset_time
    
    # Check limit
    allowed, returned_reset_time = await rate_limiter.check_rate_limit(source)
    
    # Verify result
    assert allowed is False
    assert returned_reset_time == reset_time


@pytest.mark.asyncio
async def test_check_rate_limit_reset(rate_limiter):
    """Test rate limit reset after reset time passes."""
    source = ApiSource.CONGRESS
    
    # Set up state with expired reset time (using timezone-aware datetime)
    rate_limiter._memory_limits[source]["remaining"] = 0
    rate_limiter._memory_limits[source]["reset_time"] = datetime.now(ZoneInfo("UTC")) - timedelta(minutes=5)
    
    # Check limit
    allowed, reset_time = await rate_limiter.check_rate_limit(source)
    
    # Verify result - should reset and allow request
    assert allowed is True
    assert reset_time > datetime.now(ZoneInfo("UTC"))
    assert rate_limiter._memory_limits[source]["remaining"] == rate_limiter._memory_limits[source]["limit"]


@pytest.mark.asyncio
async def test_pre_request_allowed(rate_limiter):
    """Test pre-request check when allowed."""
    source = ApiSource.CONGRESS
    
    # Set up state with available capacity (using timezone-aware datetime)
    rate_limiter._memory_limits[source]["remaining"] = 10
    rate_limiter._memory_limits[source]["reset_time"] = datetime.now(ZoneInfo("UTC")) + timedelta(minutes=5)
    
    # Pre-request check
    await rate_limiter.pre_request(source)
    
    # Verify remaining count decremented
    assert rate_limiter._memory_limits[source]["remaining"] == 9


@pytest.mark.asyncio
async def test_pre_request_wait_strategy(rate_limiter):
    """Test pre-request wait strategy when limit exceeded."""
    source = ApiSource.CONGRESS
    rate_limiter.strategy = ThrottleStrategy.WAIT
    
    # Set up state with no capacity
    rate_limiter._memory_limits[source]["remaining"] = 0
    
    # Mock wait_for_capacity to avoid actual waiting
    with patch.object(rate_limiter, 'wait_for_capacity') as mock_wait:
        # Configure mock
        mock_wait.return_value = None
        
        # Pre-request check
        await rate_limiter.pre_request(source)
        
        # Verify wait called
        mock_wait.assert_called_once_with(source)


@pytest.mark.asyncio
async def test_pre_request_exception_strategy(rate_limiter):
    """Test pre-request exception strategy when limit exceeded."""
    source = ApiSource.CONGRESS
    rate_limiter.strategy = ThrottleStrategy.EXCEPTION
    
    # Set up state with no capacity (using timezone-aware datetime)
    rate_limiter._memory_limits[source]["remaining"] = 0
    rate_limiter._memory_limits[source]["reset_time"] = datetime.now(ZoneInfo("UTC")) + timedelta(minutes=5)
    
    # Pre-request check should raise exception
    with pytest.raises(Exception) as exc_info:
        await rate_limiter.pre_request(source)
    
    # Verify exception message
    assert "Rate limit exceeded" in str(exc_info.value)


@pytest.mark.asyncio
async def test_wait_for_capacity(rate_limiter):
    """Test waiting for rate limit capacity."""
    source = ApiSource.CONGRESS
    
    # Set up checks to return False once then True
    # Using timezone-aware datetimes
    check_results = [
        (False, datetime.now(ZoneInfo("UTC")) + timedelta(seconds=0.1)),  # First check: not allowed
        (True, datetime.now(ZoneInfo("UTC")) + timedelta(minutes=5))      # Second check: allowed
    ]
    
    # Mock check_rate_limit to return our predetermined results
    with patch.object(rate_limiter, 'check_rate_limit') as mock_check:
        mock_check.side_effect = check_results
        
        # Wait for capacity - should return after second check
        await rate_limiter.wait_for_capacity(source)
        
        # Verify check called twice
        assert mock_check.call_count == 2


@pytest.mark.asyncio
async def test_parse_headers_congress(rate_limiter):
    """Test parsing Congress.gov rate limit headers."""
    source = ApiSource.CONGRESS
    # Use timezone-aware datetime
    future_time = datetime.now(ZoneInfo("UTC")) + timedelta(minutes=30)
    reset_time = int(future_time.timestamp())
    
    headers = {
        "x-ratelimit-remaining": "4980",
        "x-ratelimit-reset": str(reset_time)
    }
    
    # Parse remaining
    remaining = rate_limiter._parse_remaining(headers, source)
    assert remaining == 4980
    
    # Parse reset time
    parsed_reset = rate_limiter._parse_reset_time(headers, source)
    assert parsed_reset
    # Use timezone-aware datetime for comparison
    assert abs((parsed_reset - datetime.fromtimestamp(reset_time, tz=ZoneInfo("UTC"))).total_seconds()) < 1


@pytest.mark.asyncio
async def test_parse_headers_govinfo(rate_limiter):
    """Test parsing GovInfo.gov rate limit headers."""
    source = ApiSource.GOVINFO
    reset_seconds = 1800  # 30 minutes
    
    headers = {
        "x-rate-limit-remaining": "950",
        "x-rate-limit-reset": str(reset_seconds)
    }
    
    # Parse remaining
    remaining = rate_limiter._parse_remaining(headers, source)
    assert remaining == 950
    
    # Parse reset time
    # Use timezone-aware datetime for comparisons
    now = datetime.now(ZoneInfo("UTC"))
    parsed_reset = rate_limiter._parse_reset_time(headers, source)
    assert parsed_reset
    
    # Verify reset time is approximately now + reset_seconds
    time_diff = (parsed_reset - now).total_seconds()
    assert abs(time_diff - reset_seconds) < 1  # Allow 1 second difference for execution time