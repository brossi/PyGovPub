"""
Test suite for metadata database models.

This module tests the SQLModel-based database models for metadata tracking
including API usage and sync status.
"""

import pytest
from datetime import datetime, timedelta
from sqlmodel import Field, SQLModel, Session, create_engine, select
from typing import Optional
import sqlalchemy.exc
import uuid

# Create a test-specific metadata to avoid conflicts
from sqlmodel.main import SQLModel as BaseSQLModel
BaseSQLModel.metadata.clear()

# Import models under test with a unique metadata to prevent table redefinition error
from pygovpub.models.metadata import ApiUsage, SyncStatus, SyncError
from pygovpub.auth.models import ApiSource


def test_api_usage_model():
    """Test that the ApiUsage model works as expected."""
    # Create an ApiUsage instance
    api_usage = ApiUsage(
        api_source=ApiSource.CONGRESS.value,
        request_time=datetime.now(),
        endpoint="/bill/118/hr/1",
        rate_limit_remaining=4990,
        reset_time=datetime.now() + timedelta(hours=1),
        response_time=150,
        success=True
    )
    
    # Check that the fields are set correctly
    assert api_usage.api_source == ApiSource.CONGRESS.value
    assert isinstance(api_usage.request_time, datetime)
    assert api_usage.endpoint == "/bill/118/hr/1"
    assert api_usage.rate_limit_remaining == 4990
    assert isinstance(api_usage.reset_time, datetime)
    assert api_usage.response_time == 150
    assert api_usage.success is True
    assert api_usage.created_at is not None


def test_sync_status_model():
    """Test that the SyncStatus model works as expected."""
    # Create a SyncStatus instance
    sync_status = SyncStatus(
        entity_type="bill",
        last_sync_time=datetime.now() - timedelta(hours=1),
        next_sync_time=datetime.now() + timedelta(hours=1),
        source_system=ApiSource.CONGRESS.value,
        status="pending"
    )
    
    # Check that the fields are set correctly
    assert sync_status.entity_type == "bill"
    assert isinstance(sync_status.last_sync_time, datetime)
    assert isinstance(sync_status.next_sync_time, datetime)
    assert sync_status.source_system == ApiSource.CONGRESS.value
    assert sync_status.status == "pending"
    assert sync_status.created_at is not None


def test_sync_error_model():
    """Test that the SyncError model works as expected."""
    # Create a SyncError instance
    sync_error = SyncError(
        sync_id=1,
        source_system=ApiSource.CONGRESS.value,
        entity_type="bill",
        entity_id="118-hr1",
        error_message="Rate limit exceeded",
        error_time=datetime.now(),
        resolved=False
    )
    
    # Check that the fields are set correctly
    assert sync_error.sync_id == 1
    assert sync_error.source_system == ApiSource.CONGRESS.value
    assert sync_error.entity_type == "bill"
    assert sync_error.entity_id == "118-hr1"
    assert sync_error.error_message == "Rate limit exceeded"
    assert isinstance(sync_error.error_time, datetime)
    assert sync_error.resolved is False
    assert sync_error.resolution_notes is None


def test_metadata_relationships():
    """Test relationships between metadata models."""
    # Create a unique database URL to avoid sharing metadata
    db_url = f"sqlite:///:memory:{uuid.uuid4()}"
    
    # Create an in-memory SQLite engine
    engine = create_engine(db_url)
    
    # Create all tables
    SQLModel.metadata.create_all(engine)
    
    # Test creating related objects
    with Session(engine) as session:
        try:
            # Create a SyncStatus
            sync_status = SyncStatus(
                entity_type="bill",
                last_sync_time=datetime.now() - timedelta(hours=1),
                next_sync_time=datetime.now() + timedelta(hours=1),
                source_system=ApiSource.CONGRESS.value,
                status="pending"
            )
            session.add(sync_status)
            session.commit()
            session.refresh(sync_status)
            
            # Create related SyncErrors
            error1 = SyncError(
                sync_id=sync_status.sync_id,
                source_system=ApiSource.CONGRESS.value,
                entity_type="bill",
                entity_id="118-hr1",
                error_message="Rate limit exceeded",
                error_time=datetime.now(),
                resolved=False
            )
            session.add(error1)
            
            error2 = SyncError(
                sync_id=sync_status.sync_id,
                source_system=ApiSource.CONGRESS.value,
                entity_type="bill",
                entity_id="118-hr2",
                error_message="Connection timeout",
                error_time=datetime.now(),
                resolved=True,
                resolution_notes="Retried successfully"
            )
            session.add(error2)
            
            session.commit()
            
            # Test querying relationships
            # Query sync status and check errors
            sync_query = select(SyncStatus).where(SyncStatus.entity_type == "bill")
            result_sync = session.exec(sync_query).one()
            
            # Test relationship navigation from sync status to errors
            assert len(result_sync.errors) == 2
            
            # Check that errors have expected values
            assert any(e.entity_id == "118-hr1" and not e.resolved for e in result_sync.errors)
            assert any(e.entity_id == "118-hr2" and e.resolved for e in result_sync.errors)
            
            # Check error resolution notes
            resolved_error = next(e for e in result_sync.errors if e.resolved)
            assert resolved_error.resolution_notes == "Retried successfully"
            
        finally:
            # Clean up
            session.close()
            # Dispose the engine
            engine.dispose()