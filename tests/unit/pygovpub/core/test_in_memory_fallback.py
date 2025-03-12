"""
Tests for in-memory cache fallback functionality.

These tests verify that the system falls back to in-memory cache when
database operations fail or are unavailable.
"""

import pytest
from unittest.mock import patch, MagicMock, Mock
import time
from datetime import datetime, timedelta

from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Field, Session, SQLModel

from pygovpub.auth.models import ApiSource
from pygovpub.auth.rate_limiter import RateLimiter


class TestInMemoryFallback:
    """Test in-memory fallback functionality."""
    
    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        mock = MagicMock()
        # Configure session methods
        mock.__enter__ = MagicMock(return_value=mock)
        mock.__exit__ = MagicMock(return_value=None)
        mock.commit = MagicMock()
        mock.rollback = MagicMock()
        mock.close = MagicMock()
        mock.add = MagicMock()
        mock.exec = MagicMock()
        
        # Configure the exec result to return None (no results)
        mock.exec.return_value.first.return_value = None
        
        return mock
    
    @pytest.fixture
    def session_factory(self, mock_session):
        """Create a session factory that returns the mock session."""
        return lambda: mock_session
    
    @pytest.fixture
    def rate_limiter(self, session_factory):
        """Create a RateLimiter with the mock session factory."""
        return RateLimiter(session_factory=session_factory)
    
    async def test_in_memory_fallback_when_db_fails(self, rate_limiter, mock_session):
        """Test fallback to in-memory tracking when database fails."""
        # Configure mock session to raise an exception during commit
        mock_session.commit.side_effect = SQLAlchemyError("Database connection failed")
        
        # Create test headers with rate limit info
        headers = {
            "x-ratelimit-remaining": "42",
            "x-ratelimit-reset": str(int(time.time()) + 3600)  # 1 hour from now
        }
        
        # Track a request - should fall back to in-memory after DB failure
        await rate_limiter.track_request(
            source=ApiSource.CONGRESS,
            endpoint="/bills",
            status_code=200,
            rate_limit_headers=headers,
            response_time_ms=150,
            success=True
        )
        
        # Verify commit was called (attempt to use DB)
        mock_session.commit.assert_called_once()
        
        # Check that in-memory tracking was updated despite DB failure
        # Get remaining count from in-memory tracking
        allowed, _ = await rate_limiter.check_rate_limit(ApiSource.CONGRESS)
        assert allowed is True
        
        # Verify the in-memory tracking has the correct remaining value (42)
        assert rate_limiter._memory_limits[ApiSource.CONGRESS]["remaining"] == 42
    
    async def test_check_rate_limit_in_memory_fallback(self, rate_limiter, mock_session):
        """Test fallback to in-memory tracking when checking rate limit."""
        # Configure mock session to raise an exception during query
        mock_session.exec.side_effect = SQLAlchemyError("Database query failed")
        
        # Set known values in memory tracking for verification
        now = datetime.now()
        reset_time = now + timedelta(minutes=30)
        rate_limiter._memory_limits[ApiSource.CONGRESS]["remaining"] = 25
        rate_limiter._memory_limits[ApiSource.CONGRESS]["reset_time"] = reset_time
        
        # Check rate limit - should fall back to in-memory after DB failure
        allowed, returned_reset = await rate_limiter.check_rate_limit(ApiSource.CONGRESS)
        
        # Verify DB was attempted
        mock_session.exec.assert_called_once()
        
        # Verify we got the in-memory values
        assert allowed is True
        assert returned_reset == reset_time
        
    async def test_in_memory_reset_when_expired(self, rate_limiter):
        """Test that in-memory limits reset when the reset time has passed."""
        # Set up expired rate limit in memory
        one_hour_ago = datetime.now() - timedelta(hours=1)
        rate_limiter._memory_limits[ApiSource.CONGRESS]["remaining"] = 0
        rate_limiter._memory_limits[ApiSource.CONGRESS]["reset_time"] = one_hour_ago
        
        # Check rate limit - should reset since time has passed
        allowed, _ = await rate_limiter.check_rate_limit(ApiSource.CONGRESS)
        
        # Verify reset behavior
        assert allowed is True
        assert rate_limiter._memory_limits[ApiSource.CONGRESS]["remaining"] == 5000  # Default limit
        
    async def test_wait_for_capacity_using_memory(self, rate_limiter):
        """Test wait_for_capacity using in-memory tracking."""
        # Set up exhausted rate limit that will reset shortly
        reset_time = datetime.now() + timedelta(seconds=1)
        rate_limiter._memory_limits[ApiSource.CONGRESS]["remaining"] = 0
        rate_limiter._memory_limits[ApiSource.CONGRESS]["reset_time"] = reset_time
        
        # Create a timeout to ensure the test doesn't hang
        start_time = time.time()
        
        # Wait for capacity - should wait until reset time then return
        await rate_limiter.wait_for_capacity(ApiSource.CONGRESS)
        
        # Calculate actual wait time
        wait_time = time.time() - start_time
        
        # Verify we waited approximately the right amount of time
        # Should be at least 1 second but less than 2 seconds
        assert wait_time >= 1.0
        assert wait_time < 3.0  # Allow some wiggle room for async execution
        
        # Verify reset happened
        assert rate_limiter._memory_limits[ApiSource.CONGRESS]["remaining"] > 0
    
    @patch("pygovpub.auth.rate_limiter.RateLimiter.check_rate_limit")
    async def test_in_memory_throttling(self, mock_check_rate_limit, rate_limiter):
        """Test throttling based on in-memory tracking."""
        # Configure mock to simulate rate limit exceeded first, then available
        mock_check_rate_limit.side_effect = [
            (False, datetime.now() + timedelta(seconds=1)),  # First call: no capacity
            (True, datetime.now() + timedelta(hours=1))      # Second call: capacity available
        ]
        
        # Pre-request should wait for capacity when limit exceeded
        start_time = time.time()
        await rate_limiter.pre_request(ApiSource.CONGRESS)
        wait_time = time.time() - start_time
        
        # Verify we waited for capacity
        assert wait_time >= 1.0
        assert mock_check_rate_limit.call_count == 2


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])