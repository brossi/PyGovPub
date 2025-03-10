"""
SQLModel-based metadata database models.

This module defines models for tracking API usage, sync status, and errors.
"""

from datetime import datetime
from typing import List, Optional

from sqlmodel import Field, Relationship, SQLModel

from pygovpub.models.base import BaseTable, BaseEntity


class ApiUsage(BaseTable, table=True):
    """API usage tracking."""
    
    __tablename__ = "api_usage"
    __table_args__ = {"extend_existing": True}
    
    usage_id: Optional[int] = Field(default=None, primary_key=True)
    """Unique identifier for the usage record."""
    
    api_source: str = Field(max_length=10)
    # Valid values: 'govinfo', 'congress', 'internal'
    """Source API that was accessed."""
    
    request_time: datetime
    """When the request was made."""
    
    endpoint: str
    """API endpoint that was accessed."""
    
    rate_limit_remaining: Optional[int] = None
    """Remaining rate limit after this request."""
    
    reset_time: Optional[datetime] = None
    """When the rate limit resets."""
    
    response_time: Optional[int] = None
    """Time taken to process the request in milliseconds."""
    
    success: bool
    """Whether the request was successful."""
    
    error_message: Optional[str] = None
    """Error message if the request failed."""


class SyncStatus(BaseTable, table=True):
    """Synchronization status tracking."""
    
    __tablename__ = "sync_status"
    __table_args__ = {"extend_existing": True}
    
    sync_id: Optional[int] = Field(default=None, primary_key=True)
    """Unique identifier for the sync status record."""
    
    entity_type: str = Field(max_length=50)
    """Type of entity being synchronized (bill, member, etc.)."""
    
    last_sync_time: Optional[datetime] = None
    """When the entity was last synchronized."""
    
    next_sync_time: Optional[datetime] = None
    """When the entity is scheduled to be synchronized next."""
    
    source_system: str = Field(max_length=10)
    # Valid values: 'govinfo', 'congress'
    """Source system for the synchronization."""
    
    status: str = Field(max_length=20, default="pending")
    # Valid values: 'pending', 'in_progress', 'completed', 'failed', 'skipped'
    """Current status of the synchronization."""
    
    # Relationships
    errors: List["SyncError"] = Relationship(back_populates="sync_status")
    """Errors encountered during synchronization."""


class SyncError(BaseTable, table=True):
    """Synchronization error tracking."""
    
    __tablename__ = "sync_errors"
    __table_args__ = {"extend_existing": True}
    
    error_id: Optional[int] = Field(default=None, primary_key=True)
    """Unique identifier for the error record."""
    
    sync_id: int = Field(foreign_key="sync_status.sync_id")
    """Sync status record this error is associated with."""
    
    source_system: str = Field(max_length=10)
    # Valid values: 'govinfo', 'congress'
    """Source system where the error occurred."""
    
    entity_type: str
    """Type of entity being synchronized when the error occurred."""
    
    entity_id: str
    """ID of the entity being synchronized when the error occurred."""
    
    error_message: str
    """Error message describing what went wrong."""
    
    error_time: datetime = Field(default_factory=datetime.now)
    """When the error occurred."""
    
    resolved: bool = Field(default=False)
    """Whether the error has been resolved."""
    
    resolution_notes: Optional[str] = None
    """Notes about how the error was resolved, if applicable."""
    
    # Relationships
    sync_status: SyncStatus = Relationship(back_populates="errors")
    """Sync status record this error is associated with."""


class SchemaVersion(BaseTable, table=True):
    """Schema version tracking."""
    
    __tablename__ = "schema_versions"
    __table_args__ = {"extend_existing": True}
    
    version_id: Optional[int] = Field(default=None, primary_key=True)
    """Unique identifier for the version record."""
    
    api_source: str = Field(max_length=10)
    # Valid values: 'govinfo', 'congress', 'internal'
    """Source API for this schema version."""
    
    endpoint: str
    """API endpoint for this schema version."""
    
    schema_hash: str
    """Hash of the schema."""
    
    schema_json: str
    """JSON representation of the schema."""
    
    version_string: Optional[str] = None
    """API version string, if available."""
    
    detected_at: datetime = Field(default_factory=datetime.now)
    """When this schema version was first detected."""
    
    is_current: bool = Field(default=True)
    """Whether this is the current schema version for the endpoint."""