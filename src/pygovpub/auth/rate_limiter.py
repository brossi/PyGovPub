"""
Rate limiting module for PyGovPub SDK.

This module handles API rate limit tracking and request throttling to
ensure compliance with API provider limits.
"""

import asyncio
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from enum import Enum
from typing import Dict, Optional, Tuple

from sqlmodel import Session, select

from pygovpub.auth.models import ApiSource, ApiUsage


class ThrottleStrategy(str, Enum):
    """Rate limit throttling strategies."""
    
    WAIT = "wait"       # Wait until rate limit resets
    EXCEPTION = "error" # Raise exception when limit reached
    QUEUE = "queue"     # Queue requests until capacity available


class RateLimiter:
    """
    Rate limiter for API requests.
    
    Tracks and enforces rate limits across multiple sources,
    providing strategies for handling limit exhaustion.
    """
    
    def __init__(self, session_factory=None, strategy: ThrottleStrategy = ThrottleStrategy.WAIT):
        """Initialize rate limiter.
        
        Args:
            session_factory: Function to get database session
            strategy: Throttling strategy to use when limits are reached
        """
        self._session_factory = session_factory
        self.strategy = strategy
        
        # In-memory tracking for when DB is unavailable
        self._memory_limits: Dict[ApiSource, Dict] = {
            ApiSource.CONGRESS: {
                "limit": 5000,
                "remaining": 5000,
                "reset_time": datetime.now(ZoneInfo("UTC")) + timedelta(hours=1),
                "requests": []
            },
            ApiSource.GOVINFO: {
                "limit": 1000,
                "remaining": 1000, 
                "reset_time": datetime.now(ZoneInfo("UTC")) + timedelta(hours=1),
                "requests": []
            }
        }
        
        # Locks for concurrent access protection
        self._locks: Dict[ApiSource, asyncio.Lock] = {
            ApiSource.CONGRESS: asyncio.Lock(),
            ApiSource.GOVINFO: asyncio.Lock(),
        }

    async def track_request(self, 
                           source: ApiSource, 
                           endpoint: str, 
                           status_code: Optional[int] = None,
                           rate_limit_headers: Optional[Dict[str, str]] = None,
                           response_time_ms: Optional[int] = None,
                           success: bool = True,
                           error_message: Optional[str] = None) -> None:
        """
        Track an API request and update rate limit information.
        
        Args:
            source: API source (congress or govinfo)
            endpoint: API endpoint accessed
            status_code: HTTP status code
            rate_limit_headers: Headers with rate limit info
            response_time_ms: Response time in milliseconds
            success: Whether request was successful
            error_message: Error message if request failed
        """
        async with self._locks[source]:
            # Update in-memory tracking
            self._update_memory_limits(source, rate_limit_headers)
            
            # Record in database if session factory available
            if self._session_factory:
                remaining = None
                reset_time = None
                
                if rate_limit_headers:
                    remaining = self._parse_remaining(rate_limit_headers, source)
                    reset_time = self._parse_reset_time(rate_limit_headers, source)
                
                usage = ApiUsage(
                    source=source,
                    endpoint=endpoint,
                    status_code=status_code,
                    response_time_ms=response_time_ms,
                    rate_limit_remaining=remaining,
                    rate_limit_reset=reset_time,
                    success=success,
                    error_message=error_message
                )
                
                try:
                    with self._session_factory() as session:
                        session.add(usage)
                        session.commit()
                except Exception:
                    # If database operation fails, continue with in-memory tracking
                    pass

    async def check_rate_limit(self, source: ApiSource) -> Tuple[bool, Optional[datetime]]:
        """
        Check if rate limit allows another request.
        
        Args:
            source: API source to check
            
        Returns:
            Tuple: (allowed, reset_time)
        """
        async with self._locks[source]:
            # Try to get from database first
            if self._session_factory:
                try:
                    with self._session_factory() as session:
                        stmt = (
                            select(ApiUsage)
                            .where(ApiUsage.source == source)
                            .order_by(ApiUsage.request_time.desc())
                            .limit(1)
                        )
                        result = session.exec(stmt).first()
                        
                        if result and result.rate_limit_remaining is not None:
                            # Use DB data if available and current
                            if result.rate_limit_reset and result.rate_limit_reset > datetime.now(ZoneInfo("UTC")):
                                return result.rate_limit_remaining > 0, result.rate_limit_reset
                except Exception:
                    # Fall back to memory tracking on database error
                    pass
            
            # Fall back to in-memory tracking
            source_limits = self._memory_limits[source]
            
            # Check if reset time has passed
            if source_limits["reset_time"] <= datetime.now(ZoneInfo("UTC")):
                # Reset counters if reset time has passed
                self._reset_memory_limits(source)
                return True, source_limits["reset_time"]
            
            # Check remaining capacity
            return source_limits["remaining"] > 0, source_limits["reset_time"]

    async def wait_for_capacity(self, source: ApiSource) -> None:
        """
        Wait until rate limit capacity is available.
        
        Args:
            source: API source to wait for
        """
        while True:
            allowed, reset_time = await self.check_rate_limit(source)
            
            if allowed:
                return
            
            # Calculate wait time with 1 second buffer
            now = datetime.now(ZoneInfo("UTC"))
            if reset_time and reset_time > now:
                wait_seconds = (reset_time - now).total_seconds() + 1
                await asyncio.sleep(wait_seconds)
            else:
                # Default wait if reset time is invalid
                await asyncio.sleep(5)

    async def pre_request(self, source: ApiSource) -> None:
        """
        Handle pre-request rate limit check with configured strategy.
        
        Args:
            source: API source for the request
        
        Raises:
            Exception: If rate limit exceeded and strategy is EXCEPTION
        """
        allowed, reset_time = await self.check_rate_limit(source)
        
        if not allowed:
            if self.strategy == ThrottleStrategy.WAIT:
                await self.wait_for_capacity(source)
            elif self.strategy == ThrottleStrategy.EXCEPTION:
                wait_time = "unknown"
                if reset_time:
                    wait_time = str(reset_time - datetime.now(ZoneInfo("UTC")))
                raise Exception(f"Rate limit exceeded for {source}. Reset in {wait_time}")
            elif self.strategy == ThrottleStrategy.QUEUE:
                # This would ideally use a more robust queue mechanism
                await self.wait_for_capacity(source)
        
        # Pre-emptively decrement limit in memory
        async with self._locks[source]:
            self._memory_limits[source]["remaining"] = max(0, self._memory_limits[source]["remaining"] - 1)

    def _update_memory_limits(self, source: ApiSource, headers: Optional[Dict[str, str]]) -> None:
        """Update memory limits from response headers."""
        if not headers:
            return
            
        # Update remaining
        remaining = self._parse_remaining(headers, source)
        if remaining is not None:
            self._memory_limits[source]["remaining"] = remaining
            
        # Update reset time
        reset_time = self._parse_reset_time(headers, source)
        if reset_time:
            self._memory_limits[source]["reset_time"] = reset_time
            
        # Track request time
        now = datetime.now(ZoneInfo("UTC"))
        self._memory_limits[source]["requests"].append(now)
        
        # Clean old requests (keep last hour)
        hour_ago = now - timedelta(hours=1)
        self._memory_limits[source]["requests"] = [
            t for t in self._memory_limits[source]["requests"] if t > hour_ago
        ]

    def _reset_memory_limits(self, source: ApiSource) -> None:
        """Reset memory limits after reset time passed."""
        self._memory_limits[source]["remaining"] = self._memory_limits[source]["limit"]
        self._memory_limits[source]["reset_time"] = datetime.now(ZoneInfo("UTC")) + timedelta(hours=1)
        
    def _parse_remaining(self, headers: Dict[str, str], source: ApiSource) -> Optional[int]:
        """Parse remaining requests from headers."""
        if source == ApiSource.CONGRESS:
            return int(headers.get("x-ratelimit-remaining", "0"))
        elif source == ApiSource.GOVINFO:
            return int(headers.get("x-rate-limit-remaining", "0"))
        return None
        
    def _parse_reset_time(self, headers: Dict[str, str], source: ApiSource) -> Optional[datetime]:
        """Parse rate limit reset time from headers."""
        if source == ApiSource.CONGRESS:
            reset_seconds = headers.get("x-ratelimit-reset")
            if reset_seconds:
                return datetime.fromtimestamp(int(reset_seconds), ZoneInfo("UTC"))
        elif source == ApiSource.GOVINFO:
            # GovInfo uses seconds until reset
            reset_in = headers.get("x-rate-limit-reset")
            if reset_in:
                return datetime.now(ZoneInfo("UTC")) + timedelta(seconds=int(reset_in))
        return None