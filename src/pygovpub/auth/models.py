"""
Database models for authentication and API usage tracking.

This module defines SQLModel classes for:
- ApiConfiguration: API connection and auth settings
- ApiUsage: Rate limit tracking and API request logging
"""

from datetime import datetime
from zoneinfo import ZoneInfo
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel


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