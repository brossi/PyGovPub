"""
Additional test coverage for the database module.

This module focuses on edge cases and special scenarios to improve test coverage
for the database module.
"""

import pytest
import os
import uuid
import sqlite3
import sqlalchemy
from unittest.mock import patch, MagicMock, call, AsyncMock
from datetime import datetime, timezone
from sqlmodel import SQLModel, Field, Session, select
from typing import Optional, List, Dict

from pygovpub.core.database import (
    get_connection_url,
    init_db,
    get_engine,
    get_async_engine,
    get_session,
    with_transaction,
    create_tables,
    drop_tables,
    get_migration_version,
    run_migrations,
    MigrationManager,
    AsyncDatabaseSession
)
from pygovpub.models.base import BaseTable


# Define a test model for our tests
class ExtendedTestModel(BaseTable, table=True):
    """Test model for extended database tests."""
    
    __tablename__ = "extended_test_models"
    __table_args__ = {"extend_existing": True}
    
    test_id: str = Field(primary_key=True)
    name: str
    # Using str instead of Dict since SQLModel can't directly map Dict
    data: Optional[str] = None


def test_connection_url_with_custom_db_types():
    """Test connection URL generation with different database types."""
    # Test MySQL
    with patch.dict(os.environ, {
        "DB_TYPE": "mysql",
        "DB_HOST": "localhost",
        "DB_PORT": "3306",
        "DB_NAME": "testdb",
        "DB_USER": "root",
        "DB_PASSWORD": "password"
    }):
        url = get_connection_url()
        assert url == "mysql://root:password@localhost:3306/testdb"
    
    # Test PostgreSQL
    with patch.dict(os.environ, {
        "DB_TYPE": "postgresql",
        "DB_HOST": "localhost",
        "DB_PORT": "5432",
        "DB_NAME": "testdb",
        "DB_USER": "postgres",
        "DB_PASSWORD": "password"
    }):
        url = get_connection_url()
        assert url == "postgresql://postgres:password@localhost:5432/testdb"
    
    # Test SQLite with file path
    with patch.dict(os.environ, {
        "DB_TYPE": "sqlite",
        "DB_HOST": "/path/to/db.sqlite"
    }):
        url = get_connection_url()
        assert url == "sqlite:////path/to/db.sqlite"
    
    # Test with minimal configuration
    with patch.dict(os.environ, {
        "DB_TYPE": "postgresql",
        "DB_HOST": "localhost",
        "DB_NAME": "testdb"
    }):
        url = get_connection_url()
        assert url == "postgresql://localhost/testdb"


def test_init_db_echo_mode():
    """Test database initialization with echo mode."""
    # Create a unique URL to avoid conflicts
    db_url = f"sqlite:///:memory:{uuid.uuid4()}"
    
    # Test with echo=True
    with patch('pygovpub.core.database.create_engine') as mock_create_engine:
        # Set up the mock
        mock_engine = MagicMock()
        mock_create_engine.return_value = mock_engine
        
        # Call with echo=True
        engine = init_db(db_url, echo=True)
        
        # Verify create_engine was called with echo=True
        mock_create_engine.assert_called_once()
        call_args = mock_create_engine.call_args
        assert call_args[0][0] == db_url
        assert call_args[1]['echo'] is True
    
    # Test with echo=False
    with patch('pygovpub.core.database.create_engine') as mock_create_engine:
        # Set up the mock
        mock_engine = MagicMock()
        mock_create_engine.return_value = mock_engine
        
        # Call with echo=False
        engine = init_db(db_url, echo=False)
        
        # Verify create_engine was called with echo=False
        mock_create_engine.assert_called_once()
        call_args = mock_create_engine.call_args
        assert call_args[0][0] == db_url
        assert call_args[1]['echo'] is False


def test_get_engine_force_new():
    """Test getting a new engine instance with force_new=True."""
    # Create a unique URL to avoid conflicts with other tests
    unique_url = f"sqlite:///:memory:{uuid.uuid4()}"
    
    # Patch the DATABASE_URL to use our unique URL
    with patch('pygovpub.core.database.DATABASE_URL', unique_url):
        # Get the initial engine
        engine1 = get_engine()
        
        # Get the engine again with force_new=True
        engine2 = get_engine(force_new=True)
        
        # They should be different instances
        assert engine1 is not engine2
        assert id(engine1) != id(engine2)


def test_migration_manager_empty_version():
    """Test migration manager with no current version."""
    # Create an in-memory database
    engine = sqlalchemy.create_engine(f"sqlite:///:memory:{uuid.uuid4()}")
    
    # Create a migration manager
    manager = MigrationManager(engine)
    
    # Ensure version table exists
    manager.ensure_version_table()
    
    # Get current version when none exists
    version = manager.get_current_version()
    assert version is None
    
    # Set a version when none exists
    manager.set_version("1.0.0")
    version = manager.get_current_version()
    assert version == "1.0.0"


def test_migration_manager_missing_migrations():
    """Test migration manager with missing migration functions."""
    engine = sqlalchemy.create_engine(f"sqlite:///:memory:{uuid.uuid4()}")
    manager = MigrationManager(engine)
    
    # Test applying a migration that doesn't exist
    with pytest.raises(KeyError):
        manager.apply_migration("non_existent")
    
    # Test rolling back a migration that doesn't exist
    with pytest.raises(KeyError):
        manager.rollback_migration("non_existent")


def test_migration_manager_empty_migrations():
    """Test migration manager with no registered migrations."""
    engine = sqlalchemy.create_engine(f"sqlite:///:memory:{uuid.uuid4()}")
    manager = MigrationManager(engine)
    
    # No migrations registered, so should return empty list
    applied = manager.run_migrations()
    assert applied == []


def test_migration_manager_previous_version_tracking():
    """Test migration manager's tracking of previous versions."""
    engine = sqlalchemy.create_engine(f"sqlite:///:memory:{uuid.uuid4()}")
    manager = MigrationManager(engine)
    
    # Create version table
    manager.ensure_version_table()
    
    # Set multiple versions to test version history
    manager.set_version("1.0.0")
    manager.set_version("1.1.0")
    manager.set_version("2.0.0")
    
    # Get current version
    version = manager.get_current_version()
    assert version == "2.0.0"
    
    # Define a mock rollback
    def mock_rollback(session):
        pass
    
    # Register the rollback
    manager.rollbacks["2.0.0"] = mock_rollback
    
    # Apply the rollback
    manager.rollback_migration("2.0.0")
    
    # Verify we returned to the previous version
    version = manager.get_current_version()
    assert version == "1.1.0"


def test_migration_manager_run_migrations_downgrade():
    """Test running migrations to downgrade schema version."""
    engine = sqlalchemy.create_engine(f"sqlite:///:memory:{uuid.uuid4()}")
    manager = MigrationManager(engine)
    
    # Create version table
    manager.ensure_version_table()
    
    # Set initial version
    manager.set_version("2.0.0")
    
    # Define migrations for different versions
    def mock_up_1_0_0(session):
        session.execute(sqlalchemy.text(
            "CREATE TABLE test_1_0_0 (id INTEGER PRIMARY KEY)"
        ))
    
    def mock_down_1_0_0(session):
        session.execute(sqlalchemy.text("DROP TABLE test_1_0_0"))
    
    def mock_up_2_0_0(session):
        session.execute(sqlalchemy.text(
            "CREATE TABLE test_2_0_0 (id INTEGER PRIMARY KEY)"
        ))
    
    def mock_down_2_0_0(session):
        session.execute(sqlalchemy.text("DROP TABLE test_2_0_0"))
    
    # Register migrations and rollbacks
    manager.migrations["1.0.0"] = mock_up_1_0_0
    manager.rollbacks["1.0.0"] = mock_down_1_0_0
    manager.migrations["2.0.0"] = mock_up_2_0_0
    manager.rollbacks["2.0.0"] = mock_down_2_0_0
    
    # Mock the rollback_migration method to verify it's called
    with patch.object(manager, 'rollback_migration') as mock_rollback:
        # Run migrations to downgrade to 1.0.0
        applied = manager.run_migrations(target_version="1.0.0")
        
        # Verify rollback was called for 2.0.0
        mock_rollback.assert_called_once_with("2.0.0")
        
        # Verify the returned list of applied migrations
        assert applied == ["rollback_2.0.0"]


def test_migration_manager_run_migrations_invalid_target():
    """Test running migrations with an invalid target version."""
    engine = sqlalchemy.create_engine(f"sqlite:///:memory:{uuid.uuid4()}")
    manager = MigrationManager(engine)
    
    # Create version table
    manager.ensure_version_table()
    
    # Define a simple migration
    def mock_up(session):
        pass
    
    # Register the migration
    manager.migrations["1.0.0"] = mock_up
    
    # Try to run migrations with an invalid target
    with pytest.raises(ValueError):
        manager.run_migrations(target_version="non_existent")


def test_migration_manager_no_previous_version():
    """Test rollback when there's no previous version."""
    engine = sqlalchemy.create_engine(f"sqlite:///:memory:{uuid.uuid4()}")
    manager = MigrationManager(engine)
    
    # Create version table
    manager.ensure_version_table()
    
    # Set only one version
    manager.set_version("1.0.0")
    
    # Define a mock rollback
    def mock_rollback(session):
        pass
    
    # Register the rollback
    manager.rollbacks["1.0.0"] = mock_rollback
    
    # We'll patch the Session directly to avoid issues with the mock
    # Just verify that after rollback, there's no current version
    manager.rollback_migration("1.0.0")
    version = manager.get_current_version()
    assert version is None


def test_run_migrations_with_target():
    """Test the run_migrations convenience function with a target version."""
    # Create a mock MigrationManager
    mock_manager = MagicMock()
    
    # Patch the MigrationManager class to return our mock
    with patch('pygovpub.core.database.MigrationManager', return_value=mock_manager):
        # Call run_migrations with a target version
        run_migrations(target_version="1.0.0")
        
        # Verify run_migrations was called on the manager with the target version
        mock_manager.run_migrations.assert_called_with(target_version="1.0.0")


def test_get_async_engine():
    """Test getting the async engine singleton."""
    # Reset the global engine
    from pygovpub.core.database import _ASYNC_ENGINE
    import pygovpub.core.database
    pygovpub.core.database._ASYNC_ENGINE = None
    
    # Test basic singleton behavior
    with patch('pygovpub.core.database.create_async_engine') as mock_create:
        mock_engine1 = MagicMock()
        mock_engine2 = MagicMock()
        mock_create.side_effect = [mock_engine1, mock_engine2]
        
        # Get the engine first time - should create
        engine1 = get_async_engine()
        assert engine1 is mock_engine1
        assert mock_create.call_count == 1
        
        # Get the engine again - should reuse singleton
        engine2 = get_async_engine()
        assert engine2 is mock_engine1
        assert mock_create.call_count == 1
        
        # Force a new engine - should create again
        engine3 = get_async_engine(force_new=True)
        assert engine3 is mock_engine2
        assert mock_create.call_count == 2
    
    # Reset for next test
    pygovpub.core.database._ASYNC_ENGINE = None
    
    # Test URL transformation for SQLite
    with patch('pygovpub.core.database.DATABASE_URL', 'sqlite:///:memory:'):
        with patch('pygovpub.core.database.create_async_engine') as mock_create:
            get_async_engine()
            args, kwargs = mock_create.call_args
            assert args[0] == 'sqlite+aiosqlite:///:memory:'
    
    # Reset for next test
    pygovpub.core.database._ASYNC_ENGINE = None
    
    # Test URL for PostgreSQL remains unchanged
    with patch('pygovpub.core.database.DATABASE_URL', 'postgresql://user:pass@localhost/db'):
        with patch('pygovpub.core.database.create_async_engine') as mock_create:
            get_async_engine()
            args, kwargs = mock_create.call_args
            assert args[0] == 'postgresql://user:pass@localhost/db'


@pytest.mark.asyncio
async def test_async_database_session():
    """Test the AsyncDatabaseSession class directly."""
    # Mock the AsyncSession
    mock_session = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()
    mock_session.close = AsyncMock()
    
    # Mock the async_sessionmaker to return our mock session
    mock_sessionmaker = MagicMock()
    mock_sessionmaker.return_value = mock_session
    
    # Create AsyncDatabaseSession with mocked components
    async_db = AsyncDatabaseSession()
    async_db.session_factory = mock_sessionmaker
    
    # Test successful context
    async with async_db as session:
        assert session is mock_session
    
    # Verify commit and close were called
    mock_session.commit.assert_called_once()
    mock_session.close.assert_called_once()
    mock_session.rollback.assert_not_called()
    
    # Reset mocks
    mock_session.commit.reset_mock()
    mock_session.close.reset_mock()
    
    # Test context with exception
    try:
        async with async_db as session:
            assert session is mock_session
            raise ValueError("Test exception")
    except ValueError:
        pass
    
    # Verify rollback and close were called
    mock_session.rollback.assert_called_once()
    mock_session.close.assert_called_once()
    mock_session.commit.assert_not_called()