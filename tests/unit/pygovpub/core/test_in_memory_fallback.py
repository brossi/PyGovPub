"""
Tests for in-memory cache fallback functionality.

These tests verify that the system falls back to in-memory cache when
database operations fail or are unavailable.
"""

import pytest
from unittest.mock import patch, MagicMock, Mock
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Field, Session, SQLModel

from pygovpub.auth.models import ApiSource
from pygovpub.auth.rate_limiter import RateLimiter, ThrottleStrategy

# Use UTC timezone for all datetime objects to match the implementation
UTC = ZoneInfo("UTC")


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
        mock.execute = MagicMock()
        
        # Configure the exec result to return None (no results)
        mock.exec.return_value.first.return_value = None
        
        # Configure the execute result to return None (no results)
        mock_result = MagicMock()
        mock_result.first.return_value = None
        mock_result.scalar.return_value = None
        mock.execute.return_value = mock_result
        
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
        # Configure mock session to raise an exception during query (both exec and execute)
        mock_session.exec.side_effect = SQLAlchemyError("Database query failed")
        mock_session.execute.side_effect = SQLAlchemyError("Database query failed")
        
        # Set known values in memory tracking for verification
        now = datetime.now(UTC)
        reset_time = now + timedelta(minutes=30)
        rate_limiter._memory_limits[ApiSource.CONGRESS]["remaining"] = 25
        rate_limiter._memory_limits[ApiSource.CONGRESS]["reset_time"] = reset_time
        
        # Check rate limit - should fall back to in-memory after DB failure
        allowed, returned_reset = await rate_limiter.check_rate_limit(ApiSource.CONGRESS)
        
        # Verify DB was attempted - with either exec or execute
        assert mock_session.exec.called or mock_session.execute.called, "Neither exec nor execute was called on the session"
        
        # Verify we got the in-memory values
        assert allowed is True
        assert returned_reset == reset_time
        
    async def test_in_memory_reset_when_expired(self, rate_limiter):
        """Test that in-memory limits reset when the reset time has passed."""
        # Set up expired rate limit in memory
        one_hour_ago = datetime.now(UTC) - timedelta(hours=1)
        rate_limiter._memory_limits[ApiSource.CONGRESS]["remaining"] = 0
        rate_limiter._memory_limits[ApiSource.CONGRESS]["reset_time"] = one_hour_ago
        
        # Check rate limit - should reset since time has passed
        allowed, _ = await rate_limiter.check_rate_limit(ApiSource.CONGRESS)
        
        # Verify reset behavior
        assert allowed is True
        assert rate_limiter._memory_limits[ApiSource.CONGRESS]["remaining"] == 5000  # Default limit
        
    @patch("pygovpub.auth.rate_limiter.asyncio.sleep")
    async def test_wait_for_capacity_using_memory(self, mock_sleep, rate_limiter):
        """Test wait_for_capacity using in-memory tracking."""
        # Set up exhausted rate limit that will reset shortly
        reset_time = datetime.now(UTC) + timedelta(seconds=1)
        rate_limiter._memory_limits[ApiSource.CONGRESS]["remaining"] = 0
        rate_limiter._memory_limits[ApiSource.CONGRESS]["reset_time"] = reset_time
        
        # Track if reset was called
        reset_was_called = [False]
        original_reset = rate_limiter._reset_memory_limits
        
        # Use a dummy async sleep that doesn't actually sleep
        async def fake_sleep(seconds):
            # Record that sleep was called with the expected time
            fake_sleep.called_with = seconds
            
            # After fake sleep, simulate time passing by resetting limits
            if not reset_was_called[0]:
                original_reset(ApiSource.CONGRESS)
                reset_was_called[0] = True
            
        fake_sleep.called_with = None
        mock_sleep.side_effect = fake_sleep
        
        # Wait for capacity - should wait until reset time then return
        await rate_limiter.wait_for_capacity(ApiSource.CONGRESS)
        
        # Verify the sleep was called with approximately the right wait time
        assert fake_sleep.called_with is not None, "Sleep was never called"
        assert fake_sleep.called_with > 0, "Sleep time was not positive"
        assert fake_sleep.called_with <= 2, "Sleep time was too long"
        
        # Verify reset happened and remaining was increased
        assert rate_limiter._memory_limits[ApiSource.CONGRESS]["remaining"] > 0
    
    @patch("pygovpub.auth.rate_limiter.RateLimiter.check_rate_limit")
    @patch("pygovpub.auth.rate_limiter.RateLimiter.wait_for_capacity")
    async def test_in_memory_throttling(self, mock_wait_for_capacity, mock_check_rate_limit, rate_limiter):
        """Test throttling based on in-memory tracking."""
        # Set strategy to WAIT so that it will actually wait for capacity
        rate_limiter.strategy = ThrottleStrategy.WAIT
        
        # Configure mock to simulate rate limit exceeded
        reset_time = datetime.now(UTC) + timedelta(seconds=1)
        mock_check_rate_limit.return_value = (False, reset_time)
        
        # Set up wait_for_capacity mock to do nothing
        mock_wait_for_capacity.return_value = None
        
        # Pre-request should call wait_for_capacity when limit exceeded
        await rate_limiter.pre_request(ApiSource.CONGRESS)
        
        # Verify check_rate_limit was called
        mock_check_rate_limit.assert_called_once_with(ApiSource.CONGRESS)
        
        # Verify wait_for_capacity was called
        mock_wait_for_capacity.assert_called_once_with(ApiSource.CONGRESS)


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])