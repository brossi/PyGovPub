"""
Rate limiting module for PyGovPub SDK.

This module handles API rate limit tracking and request throttling to
ensure compliance with API provider limits.

Features:
- High-performance rate limit tracking with database sharding
- In-memory fallback when database is unavailable
- Configurable throttling strategies
- Support for multiple API sources with different rate limits
"""

import asyncio
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from enum import Enum
from typing import Dict, Optional, Tuple, List
import logging

from sqlmodel import Session, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text

from pygovpub.auth.models import ApiSource, ApiUsage, RateLimitUsage

logger = logging.getLogger(__name__)


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
                limit = self._memory_limits[source]["limit"]
                
                if rate_limit_headers:
                    remaining = self._parse_remaining(rate_limit_headers, source)
                    reset_time = self._parse_reset_time(rate_limit_headers, source)
                
                # Standard API usage tracking (traditional table)
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
                        # Add to standard ApiUsage table
                        session.add(usage)
                        
                        # Also add to sharded RateLimitUsage if we have rate limit info
                        if remaining is not None and reset_time is not None:
                            # Get current timestamp for partitioning
                            now = datetime.now(ZoneInfo("UTC"))
                            
                            # Create partition for current month if needed
                            self._ensure_partition_exists(session, source, now)
                            
                            # Use table name based on date and source for proper sharding
                            table_name = RateLimitUsage.get_table_name(source, now)
                            
                            # Check if we already have an entry for this timestamp and endpoint
                            stmt = text(f"""
                            SELECT id FROM {table_name}
                            WHERE timestamp = :timestamp
                            AND endpoint = :endpoint
                            LIMIT 1
                            """)
                            
                            result = session.execute(
                                stmt,
                                {"timestamp": now, "endpoint": endpoint}
                            ).first()
                            
                            if result:
                                # Update existing entry
                                update_stmt = text(f"""
                                UPDATE {table_name}
                                SET remaining = :remaining,
                                    reset_time = :reset_time,
                                    request_count = request_count + 1
                                WHERE id = :id
                                """)
                                
                                session.execute(
                                    update_stmt,
                                    {
                                        "id": result[0],
                                        "remaining": remaining,
                                        "reset_time": reset_time
                                    }
                                )
                            else:
                                # Insert new entry using the appropriate partition
                                insert_stmt = text(f"""
                                INSERT INTO {table_name}
                                (source, timestamp, endpoint, limit, remaining, reset_time, request_count)
                                VALUES
                                (:source, :timestamp, :endpoint, :limit, :remaining, :reset_time, 1)
                                """)
                                
                                session.execute(
                                    insert_stmt,
                                    {
                                        "source": source.value,
                                        "timestamp": now,
                                        "endpoint": endpoint,
                                        "limit": limit,
                                        "remaining": remaining,
                                        "reset_time": reset_time
                                    }
                                )
                        
                        # Commit all changes
                        session.commit()
                        
                except SQLAlchemyError as e:
                    logger.warning(f"Database error tracking rate limit: {str(e)}")
                    # If database operation fails, continue with in-memory tracking
                    pass
                except Exception as e:
                    logger.error(f"Unexpected error tracking rate limit: {str(e)}")
                    pass
    
    def _ensure_partition_exists(self, session: Session, source: ApiSource, date: datetime) -> None:
        """
        Ensure that the appropriate partition exists for the given source and date.
        Creates it if it doesn't exist.
        
        Args:
            session: Database session
            source: API source
            date: Date for partitioning
        """
        try:
            # Get table name for this source and date
            table_name = RateLimitUsage.get_table_name(source, date)
            
            # Check if partition exists
            check_stmt = text(f"""
            SELECT 1 FROM pg_tables
            WHERE tablename = :table_name
            """)
            
            result = session.execute(check_stmt, {"table_name": table_name.lower()}).first()
            
            if not result:
                # Create partition
                create_stmt = text(f"""
                CREATE TABLE IF NOT EXISTS {table_name} PARTITION OF rate_limit_usage
                FOR VALUES IN ('{source.value}')
                """)
                
                session.execute(create_stmt)
                logger.info(f"Created new rate limit partition: {table_name}")
        except Exception as e:
            logger.warning(f"Error ensuring partition exists: {str(e)}")
            # Continue even if partition creation fails - it will fall back to in-memory

    async def check_rate_limit(self, source: ApiSource) -> Tuple[bool, Optional[datetime]]:
        """
        Check if rate limit allows another request.
        
        Args:
            source: API source to check
            
        Returns:
            Tuple: (allowed, reset_time)
        """
        async with self._locks[source]:
            # Try to get from sharded database table first
            if self._session_factory:
                try:
                    with self._session_factory() as session:
                        # Get current timestamp for partitioning
                        now = datetime.now(ZoneInfo("UTC"))
                        
                        # Use table name based on date and source for proper sharding
                        table_name = RateLimitUsage.get_table_name(source, now)
                        
                        # Check if the table exists (it might not exist yet for a new month)
                        check_stmt = text(f"""
                        SELECT 1 FROM pg_tables
                        WHERE tablename = :table_name
                        """)
                        
                        table_exists = session.execute(check_stmt, {"table_name": table_name.lower()}).first() is not None
                        
                        if table_exists:
                            # Query the most recent record from the sharded table
                            rate_limit_stmt = text(f"""
                            SELECT remaining, reset_time
                            FROM {table_name}
                            WHERE source = :source
                            ORDER BY timestamp DESC
                            LIMIT 1
                            """)
                            
                            result = session.execute(rate_limit_stmt, {"source": source.value}).first()
                            
                            # If we found a record and it has a valid reset time
                            if result and result[1] > now:
                                # Use the sharded table data
                                return result[0] > 0, result[1]
                        
                        # If sharded table doesn't exist or no valid results,
                        # fall back to traditional ApiUsage table
                        stmt = (
                            select(ApiUsage)
                            .where(ApiUsage.source == source)
                            .order_by(ApiUsage.request_time.desc())
                            .limit(1)
                        )
                        result = session.exec(stmt).first()
                        
                        if result and result.rate_limit_remaining is not None:
                            # Use ApiUsage table data if available and current
                            if result.rate_limit_reset and result.rate_limit_reset > now:
                                return result.rate_limit_remaining > 0, result.rate_limit_reset
                except SQLAlchemyError as e:
                    logger.warning(f"Database error checking rate limit: {str(e)}")
                    # Fall back to memory tracking on database error
                    pass
                except Exception as e:
                    logger.error(f"Unexpected error checking rate limit: {str(e)}")
                    pass
            
            # Fall back to in-memory tracking
            source_limits = self._memory_limits[source]
            
            # Check if reset time has passed
            now = datetime.now(ZoneInfo("UTC"))
            if source_limits["reset_time"] <= now:
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
    
    async def purge_old_rate_limit_data(self, months_to_keep: int = 3) -> None:
        """
        Purges old rate limit data by dropping old partitions.
        
        Args:
            months_to_keep: Number of recent months to keep (default: 3)
        """
        if not self._session_factory:
            return
            
        try:
            with self._session_factory() as session:
                # Get current date for reference
                now = datetime.now(ZoneInfo("UTC"))
                
                # Find all rate_limit_usage partitioned tables
                find_tables_stmt = text("""
                SELECT tablename FROM pg_tables
                WHERE tablename LIKE 'rate_limit_usage_%_%'
                """)
                
                tables = [row[0] for row in session.execute(find_tables_stmt)]
                
                # Identify tables older than our retention period
                tables_to_drop = []
                for table in tables:
                    # Extract source and date parts from table name
                    # Format: rate_limit_usage_SOURCE_YYYY_MM
                    parts = table.split('_')
                    if len(parts) >= 5:
                        try:
                            # Extract year and month
                            year = int(parts[-2])
                            month = int(parts[-1])
                            
                            # Calculate age in months
                            table_date = datetime(year, month, 1)
                            age_months = (now.year - table_date.year) * 12 + (now.month - table_date.month)
                            
                            if age_months > months_to_keep:
                                tables_to_drop.append(table)
                        except (ValueError, IndexError):
                            # Skip tables with invalid naming format
                            logger.warning(f"Skipping table with invalid format: {table}")
                
                # Drop old tables
                for table in tables_to_drop:
                    try:
                        drop_stmt = text(f"DROP TABLE {table}")
                        session.execute(drop_stmt)
                        logger.info(f"Dropped old rate limit partition: {table}")
                    except Exception as e:
                        logger.error(f"Failed to drop old partition {table}: {str(e)}")
                
                # Commit changes
                session.commit()
                
                logger.info(f"Purged {len(tables_to_drop)} old rate limit partitions")
        except Exception as e:
            logger.error(f"Error purging old rate limit data: {str(e)}")
        
    def _parse_remaining(self, headers: Dict[str, str], source: ApiSource) -> Optional[int]:
        """Parse remaining requests from headers."""
        if source == ApiSource.CONGRESS:
            return int(headers.get("x-ratelimit-remaining", "0"))
        elif source == ApiSource.GOVINFO:
            return int(headers.get("x-rate-limit-remaining", "0"))
        return None
        
    def _parse_reset_time(self, headers: Dict[str, str], source: ApiSource) -> Optional[datetime]:
        """Parse rate limit reset time from headers."""
        try:
            if source == ApiSource.CONGRESS:
                reset_seconds = headers.get("x-ratelimit-reset")
                if reset_seconds:
                    return datetime.fromtimestamp(int(reset_seconds), ZoneInfo("UTC"))
            elif source == ApiSource.GOVINFO:
                # GovInfo uses seconds until reset
                reset_in = headers.get("x-rate-limit-reset")
                if reset_in:
                    return datetime.now(ZoneInfo("UTC")) + timedelta(seconds=int(reset_in))
        except (ValueError, TypeError, OverflowError):
            # Handle invalid values
            logger.warning(f"Invalid rate limit reset value in headers for source {source}")
        return None