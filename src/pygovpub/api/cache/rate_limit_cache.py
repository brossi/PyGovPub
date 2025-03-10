"""
Rate limit tracking using the cache system.

This module provides cache-based rate limit tracking that works
alongside the auth-based rate limiter to provide redundant tracking
and enforcement of API rate limits.
"""

import time
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Tuple, Any
from dataclasses import dataclass

from pygovpub.auth.models import ApiSource
from pygovpub.api.cache.storage import CacheStorage, CacheItem, MemoryStorage


@dataclass
class RateLimitInfo:
    """Rate limit information for an API source."""
    
    limit: int
    """Total request limit."""
    
    remaining: int
    """Remaining requests before limit is reached."""
    
    reset_time: float
    """Timestamp when the rate limit will reset."""
    
    requests: List[float] = None
    """Timestamps of recent requests (for rate calculation)."""
    
    def __post_init__(self):
        """Initialize requests list if not provided."""
        if self.requests is None:
            self.requests = []


class RateLimitCache:
    """
    Cache-based rate limit tracker.
    
    Uses a cache backend to store and track rate limit information
    for each API source, providing redundancy with the auth-based limiter.
    """
    
    # Default rate limits
    DEFAULT_LIMITS = {
        ApiSource.CONGRESS: 5000,
        ApiSource.GOVINFO: 1000
    }
    
    # Default reset period (1 hour)
    DEFAULT_RESET_PERIOD = 3600
    
    def __init__(self, storage: Optional[CacheStorage] = None):
        """Initialize the rate limit cache.
        
        Args:
            storage: Cache storage backend to use (defaults to MemoryStorage)
        """
        # Set up storage
        self._storage = storage or MemoryStorage[RateLimitInfo]()
        
        # Initialize rate limits for each API source
        self._initialize_limits()
    
    def _initialize_limits(self):
        """Initialize rate limit information for all API sources."""
        now = time.time()
        reset_time = now + self.DEFAULT_RESET_PERIOD
        
        for source in ApiSource:
            limit = self.DEFAULT_LIMITS.get(source, 1000)
            info = RateLimitInfo(
                limit=limit,
                remaining=limit,
                reset_time=reset_time,
                requests=[]
            )
            
            key = self._get_source_key(source)
            self._storage.set(key, info)
    
    def _get_source_key(self, source: ApiSource) -> str:
        """Get cache key for a source's rate limit info."""
        return f"rate_limit:{source.value}"
    
    def update_from_headers(self, source: ApiSource, headers: Dict[str, str]) -> bool:
        """Update rate limit information from response headers.
        
        Args:
            source: API source
            headers: Response headers with rate limit information
            
        Returns:
            Success status
        """
        if not headers:
            return False
        
        # Get current info
        key = self._get_source_key(source)
        item = self._storage.get(key)
        if not item:
            self._initialize_limits()
            item = self._storage.get(key)
            if not item:
                return False
        
        info = item.value
        
        # Parse rate limit information from headers
        remaining = self._parse_remaining(headers, source)
        reset_time = self._parse_reset_time(headers, source)
        
        # Update information if available
        if remaining is not None:
            info.remaining = remaining
            
        if reset_time is not None:
            info.reset_time = reset_time
        
        # Add request timestamp
        now = time.time()
        info.requests.append(now)
        
        # Clean old request timestamps (keep last hour)
        hour_ago = now - 3600
        info.requests = [t for t in info.requests if t > hour_ago]
        
        # Save updated info
        self._storage.set(key, info)
        return True
    
    def track_request(self, source: ApiSource) -> bool:
        """Track a new request and update remaining count.
        
        Args:
            source: API source
            
        Returns:
            Success status
        """
        key = self._get_source_key(source)
        item = self._storage.get(key)
        
        if not item:
            self._initialize_limits()
            item = self._storage.get(key)
            if not item:
                return False
        
        info = item.value
        
        # Check if reset time has passed
        now = time.time()
        if now > info.reset_time:
            # Reset limits
            info.remaining = info.limit
            info.reset_time = now + self.DEFAULT_RESET_PERIOD
        
        # Decrement remaining count
        info.remaining = max(0, info.remaining - 1)
        
        # Track request
        info.requests.append(now)
        
        # Clean old request timestamps
        hour_ago = now - 3600
        info.requests = [t for t in info.requests if t > hour_ago]
        
        # Save updated info
        self._storage.set(key, info)
        return True
    
    def check_limit(self, source: ApiSource) -> Tuple[bool, Optional[float]]:
        """Check if rate limit allows another request.
        
        Args:
            source: API source
            
        Returns:
            Tuple of (allowed, reset_time)
        """
        key = self._get_source_key(source)
        item = self._storage.get(key)
        
        if not item:
            self._initialize_limits()
            item = self._storage.get(key)
            if not item:
                # If still no info, assume allowed
                return True, None
        
        info = item.value
        
        # Check if reset time has passed
        now = time.time()
        if now > info.reset_time:
            # Reset limits
            info.remaining = info.limit
            info.reset_time = now + self.DEFAULT_RESET_PERIOD
            self._storage.set(key, info)
            return True, info.reset_time
        
        # Check if requests remaining
        return info.remaining > 0, info.reset_time
    
    def get_usage_stats(self, source: ApiSource) -> Dict[str, Any]:
        """Get usage statistics for an API source.
        
        Args:
            source: API source
            
        Returns:
            Dictionary with usage statistics
        """
        key = self._get_source_key(source)
        item = self._storage.get(key)
        
        if not item:
            self._initialize_limits()
            item = self._storage.get(key)
            if not item:
                return {
                    "limit": self.DEFAULT_LIMITS.get(source, 1000),
                    "remaining": self.DEFAULT_LIMITS.get(source, 1000),
                    "reset_in": self.DEFAULT_RESET_PERIOD,
                    "request_count": 0,
                    "request_rate": 0
                }
        
        info = item.value
        
        # Calculate time until reset
        now = time.time()
        reset_in = max(0, info.reset_time - now)
        
        # Calculate recent request rate (requests per minute)
        minute_ago = now - 60
        recent_requests = [t for t in info.requests if t > minute_ago]
        request_rate = len(recent_requests)
        
        # Check if reset time has passed
        if now > info.reset_time:
            # Reset would happen if checked
            return {
                "limit": info.limit,
                "remaining": info.limit,
                "reset_in": self.DEFAULT_RESET_PERIOD,
                "request_count": len(info.requests),
                "request_rate": request_rate
            }
        
        return {
            "limit": info.limit,
            "remaining": info.remaining,
            "reset_in": reset_in,
            "request_count": len(info.requests),
            "request_rate": request_rate
        }
    
    def _parse_remaining(self, headers: Dict[str, str], source: ApiSource) -> Optional[int]:
        """Parse remaining requests from headers."""
        if not headers:
            return None
            
        if source == ApiSource.CONGRESS:
            remaining = headers.get("x-ratelimit-remaining")
            if remaining:
                try:
                    return int(remaining)
                except (ValueError, TypeError):
                    pass
        elif source == ApiSource.GOVINFO:
            remaining = headers.get("x-rate-limit-remaining")
            if remaining:
                try:
                    return int(remaining)
                except (ValueError, TypeError):
                    pass
        return None
    
    def _parse_reset_time(self, headers: Dict[str, str], source: ApiSource) -> Optional[float]:
        """Parse rate limit reset time from headers."""
        if not headers:
            return None
            
        now = time.time()
        
        if source == ApiSource.CONGRESS:
            reset_seconds = headers.get("x-ratelimit-reset")
            if reset_seconds:
                try:
                    return float(reset_seconds)
                except (ValueError, TypeError):
                    return now + self.DEFAULT_RESET_PERIOD
        elif source == ApiSource.GOVINFO:
            # GovInfo uses seconds until reset
            reset_in = headers.get("x-rate-limit-reset")
            if reset_in:
                try:
                    return now + float(reset_in)
                except (ValueError, TypeError):
                    return now + self.DEFAULT_RESET_PERIOD
        return None