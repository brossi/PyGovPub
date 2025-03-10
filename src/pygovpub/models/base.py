"""
Base models for SQLModel integration.

This module provides base classes for database models using SQLModel,
including timestamp fields for auditing.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


class BaseTable(SQLModel):
    """Base table model with timestamp fields.
    
    Provides created_at and updated_at timestamp fields for all tables
    that inherit from it. These fields are automatically managed.
    
    Note: Tables inheriting from this must define their own primary key.
    """
    
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        index=True
    )
    """When the record was created."""
    
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), 
        index=True
    )
    """When the record was last updated."""


class BaseEntity(SQLModel, table=True):
    """Base entity model with ID field.
    
    Provides an auto-incrementing ID field for tables that need a
    sequential primary key instead of a natural key, along with
    timestamp fields for auditing.
    """
    
    id: Optional[int] = Field(default=None, primary_key=True)
    """Auto-incremented primary key."""
    
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        index=True
    )
    """When the record was created."""
    
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        index=True
    )
    """When the record was last updated."""