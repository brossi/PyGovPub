"""
Database models for authentication and API usage tracking.

This module defines SQLModel classes for:
- ApiConfiguration: API connection and auth settings
- ApiUsage: Rate limit tracking and API request logging
- AuthRequest: Authentication request data for API calls
- RateLimitUsage: Sharded rate limit tracking
"""

from datetime import datetime
from zoneinfo import ZoneInfo
from enum import Enum
from typing import Optional, Dict, Any, List

from sqlmodel import Field, SQLModel, Index, Column, String
from pydantic import BaseModel


class ApiSource(str, Enum):
    """Source API providers."""
    
    CONGRESS = "congress"
    GOVINFO = "govinfo"
    INTERNAL = "internal"
    NETWORK = "network"
    CLIENT = "client"


class AuthType(str, Enum):
    """Authentication types."""
    
    HEADER = "header"
    PARAMETER = "parameter"


class ApiConfiguration(SQLModel, table=True):
    """API configuration and authentication settings."""
    
    __tablename__ = "api_configurations"
    __table_args__ = {"extend_existing": True}
    
    id: Optional[int] = Field(default=None, primary_key=True)
    source: ApiSource = Field(index=True)
    base_url: str
    auth_type: AuthType
    auth_key_name: str = Field(default="X-API-Key")  # header name or param name
    key_reference: str  # reference to securely stored key, not the key itself
    rate_limit: int
    rate_limit_period: int = 3600  # in seconds (default 1 hour)
    active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(ZoneInfo("UTC")))
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(ZoneInfo("UTC")),
        sa_column_kwargs={"onupdate": lambda: datetime.now(ZoneInfo("UTC"))}
    )


class ApiUsage(SQLModel, table=True):
    """API usage and rate limit tracking."""
    
    __tablename__ = "api_usage"
    __table_args__ = {"extend_existing": True}
    
    id: Optional[int] = Field(default=None, primary_key=True)
    source: ApiSource = Field(index=True)
    endpoint: str
    request_time: datetime = Field(default_factory=lambda: datetime.now(ZoneInfo("UTC")))
    status_code: Optional[int] = None
    response_time_ms: Optional[int] = None
    rate_limit_remaining: Optional[int] = None
    rate_limit_reset: Optional[datetime] = None
    success: bool = True
    error_message: Optional[str] = None


class RateLimitUsage(SQLModel, table=True):
    """Sharded rate limit tracking for high-volume API usage.
    
    This model is designed to be sharded by month and source for performance optimization:
    - Partition by source (congress, govinfo)
    - Partition by month (YYYY_MM)
    
    Example table names created automatically:
    - rate_limit_usage_congress_2025_03
    - rate_limit_usage_govinfo_2025_03
    """
    
    __tablename__ = "rate_limit_usage"
    __table_args__ = {
        "extend_existing": True,
        # Create index on timestamp for fast range queries within a shard
        "postgresql_partition_by": "LIST (source)",
    }
    
    id: Optional[int] = Field(default=None, primary_key=True)
    source: ApiSource = Field(sa_column=Column(String, primary_key=True))
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(ZoneInfo("UTC")),
        sa_column_kwargs={"primary_key": True}
    )
    endpoint: str
    limit: int
    remaining: int
    reset_time: datetime
    request_count: int = 1
    
    # Create index on timestamp
    __table_args__ = (
        Index("ix_rate_limit_usage_timestamp", "timestamp"),
    )
    
    @classmethod
    def get_table_name(cls, source: ApiSource, date: datetime) -> str:
        """Get the sharded table name for a specific source and date."""
        year_month = f"{date.year}_{date.month:02d}"
        return f"rate_limit_usage_{source.value}_{year_month}"
    
    @classmethod
    def create_monthly_partition(cls, engine, source: ApiSource, year: int, month: int) -> None:
        """Create a new monthly partition for the given source."""
        table_name = cls.get_table_name(source, datetime(year, month, 1))
        from_value = f"'{source.value}'"
        
        # Create partition table if it doesn't exist
        with engine.begin() as conn:
            conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {table_name} PARTITION OF rate_limit_usage
            FOR VALUES IN ({from_value})
            """)


class AuthRequest(BaseModel):
    """Authentication request data for API calls."""
    
    api_key: Optional[str] = None
    headers: Dict[str, str] = {}
    params: Dict[str, Any] = {}
    source: ApiSource