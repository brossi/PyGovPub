"""
Test suite for database connection and transaction management.

This module tests the database connection pool, session management, 
and transaction handling functionality.
"""

import asyncio
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import sqlalchemy
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlmodel import SQLModel, Session, create_engine, select, Field
from contextlib import asynccontextmanager
import uuid
import os
from datetime import datetime
from typing import Optional, AsyncGenerator

from pygovpub.core.database import (
    get_connection_url,
    init_db,
    get_engine,
    get_session,
    with_transaction,
    AsyncDatabaseSession,
    get_async_session,
    with_async_transaction,
    create_tables,
    drop_tables,
    get_migration_version,
    run_migrations,
    MigrationManager
)
from pygovpub.models.base import BaseTable, BaseEntity


# Define a test model outside of the test class to avoid warning
class TestModel(BaseTable, table=True):
    """Test model for database operations."""
    
    __tablename__ = "test_models"
    __table_args__ = {"extend_existing": True}
    
    test_id: str = Field(primary_key=True)
    name: str
    description: Optional[str] = None


@pytest.fixture
def test_db_url(temp_db_path):
    """Provide a temporary SQLite URL for testing.
    
    This uses the temp_db_path fixture to ensure the database file
    is properly cleaned up after the test.
    """
    return temp_db_path


@pytest.fixture
def test_async_db_url(temp_db_path):
    """Provide a temporary SQLite URL for testing async operations.
    
    This modifies the temp_db_path fixture to use the aiosqlite dialect.
    """
    # Convert sqlite:/// to sqlite+aiosqlite:///
    return temp_db_path.replace("sqlite:", "sqlite+aiosqlite:")


@pytest.fixture
def env_setup(monkeypatch, temp_db_path):
    """Setup environment variables for database connection.
    
    This uses the temp_db_path fixture to ensure the database file
    is properly cleaned up after the test.
    """
    db_file = temp_db_path.replace("sqlite:///", "")
    
    monkeypatch.setenv("DB_TYPE", "sqlite")
    monkeypatch.setenv("DB_HOST", db_file)  # Use file path instead of :memory:
    monkeypatch.setenv("DB_PORT", "")
    monkeypatch.setenv("DB_NAME", "test_db")
    monkeypatch.setenv("DB_USER", "test_user")
    monkeypatch.setenv("DB_PASSWORD", "test_password")


def test_get_connection_url(env_setup):
    """Test that connection URL is correctly constructed from environment variables."""
    url = get_connection_url()
    assert "sqlite:///" in url  # Should start with sqlite:///
    
    # Test with a different database type
    with patch.dict(os.environ, {"DB_TYPE": "postgresql"}):
        url = get_connection_url()
        assert "postgresql://" in url
        assert "test_user:test_password@" in url
        assert "test_db" in url


def test_init_db(test_db_url):
    """Test database initialization."""
    engine = init_db(test_db_url)
    assert engine is not None
    
    # Check that engine can be used
    SQLModel.metadata.create_all(engine)
    
    # Test with echo=True
    engine = init_db(test_db_url, echo=True)
    assert engine is not None


def test_get_engine():
    """Test getting the global engine singleton."""
    # First call should create the engine
    engine1 = get_engine()
    assert engine1 is not None
    
    # Second call should return the same engine
    engine2 = get_engine()
    assert engine2 is engine1
    
    # Test with custom URL
    with patch('pygovpub.core.database.DATABASE_URL', 'sqlite:///:memory:'):
        engine3 = get_engine(force_new=True)
        assert engine3 is not engine1


def test_get_session(test_db_url):
    """Test the session factory."""
    # Initialize with a test engine
    engine = create_engine(test_db_url)
    
    with patch('pygovpub.core.database.get_engine', return_value=engine):
        # Get a session
        session = get_session()
        assert isinstance(session, Session)
        
        # The session should be bound to our engine
        assert session.get_bind() == engine
        
        # Test that the session can be used
        SQLModel.metadata.create_all(engine)
        model = TestModel(test_id=str(uuid.uuid4()), name="Test")
        session.add(model)
        session.commit()
        
        # Query the model
        results = session.exec(select(TestModel)).all()
        assert len(results) == 1
        assert results[0].name == "Test"


def test_with_transaction(test_db_url):
    """Test the transaction context manager."""
    # Initialize with a test engine
    engine = create_engine(test_db_url)
    SQLModel.metadata.create_all(engine)
    
    with patch('pygovpub.core.database.get_engine', return_value=engine):
        # Test successful transaction
        with with_transaction() as session:
            model = TestModel(test_id=str(uuid.uuid4()), name="Test")
            session.add(model)
        
        # Verify the model was saved
        with Session(engine) as session:
            results = session.exec(select(TestModel)).all()
            assert len(results) == 1
            assert results[0].name == "Test"
        
        # Test transaction rollback on exception
        try:
            with with_transaction() as session:
                model = TestModel(test_id=str(uuid.uuid4()), name="Should Rollback")
                session.add(model)
                raise ValueError("Test exception")
        except ValueError:
            pass
        
        # Verify no new model was saved
        with Session(engine) as session:
            results = session.exec(select(TestModel)).all()
            assert len(results) == 1  # Still just the first one


@pytest.mark.asyncio
async def test_async_session(test_async_db_url):
    """Test async database session."""
    engine = create_async_engine(test_async_db_url)
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    
    with patch('pygovpub.core.database.get_async_engine', return_value=engine):
        async with get_async_session() as session:
            assert isinstance(session, AsyncSession)
            
            # Test that the session can be used
            model = TestModel(test_id=str(uuid.uuid4()), name="Async Test")
            session.add(model)
            await session.commit()
            
            # Query the model
            result = await session.execute(select(TestModel))
            models = result.scalars().all()
            assert len(models) == 1
            assert models[0].name == "Async Test"


@pytest.mark.asyncio
async def test_with_async_transaction(test_async_db_url):
    """Test the async transaction context manager."""
    engine = create_async_engine(test_async_db_url)
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    
    with patch('pygovpub.core.database.get_async_engine', return_value=engine):
        # Test successful transaction
        async with with_async_transaction() as session:
            model = TestModel(test_id=str(uuid.uuid4()), name="Async Transaction")
            session.add(model)
        
        # Verify the model was saved
        async with AsyncSession(engine) as session:
            result = await session.execute(select(TestModel))
            models = result.scalars().all()
            assert len(models) == 1
            assert models[0].name == "Async Transaction"
        
        # Test transaction rollback on exception
        try:
            async with with_async_transaction() as session:
                model = TestModel(test_id=str(uuid.uuid4()), name="Should Rollback")
                session.add(model)
                raise ValueError("Test exception")
        except ValueError:
            pass
        
        # Verify no new model was saved
        async with AsyncSession(engine) as session:
            result = await session.execute(select(TestModel))
            models = result.scalars().all()
            assert len(models) == 1  # Still just the first one


def test_create_tables(test_db_url):
    """Test that tables can be created in the database."""
    engine = create_engine(test_db_url)
    
    # Use patch to mock SQLModel.metadata.create_all to create our test table
    with patch('sqlmodel.SQLModel.metadata.create_all') as mock_create_all:
        with patch('pygovpub.core.database.get_engine', return_value=engine):
            create_tables()
            # Verify that metadata.create_all was called
            mock_create_all.assert_called_once_with(engine)
            
    # Now actually create the table to test manually
    TestModel.__table__.create(engine)
    
    # Verify tables exist
    inspector = sqlalchemy.inspect(engine)
    tables = inspector.get_table_names()
    
    # Check for tables from our models
    assert "test_models" in tables


def test_drop_tables(test_db_url):
    """Test that tables can be dropped from the database."""
    engine = create_engine(test_db_url)
    
    # Create the test table directly
    TestModel.__table__.create(engine)
    
    # Verify tables exist before dropping
    inspector = sqlalchemy.inspect(engine)
    tables_before = inspector.get_table_names()
    assert len(tables_before) > 0
    assert "test_models" in tables_before
    
    with patch('pygovpub.core.database.get_engine', return_value=engine):
        # Use patch to mock SQLModel.metadata.drop_all
        with patch('sqlmodel.SQLModel.metadata.drop_all') as mock_drop_all:
            drop_tables()
            # Verify that metadata.drop_all was called
            mock_drop_all.assert_called_once_with(engine)
    
    # Manually drop the table to test
    TestModel.__table__.drop(engine)
    
    # Verify tables are gone
    inspector = sqlalchemy.inspect(engine)
    tables_after = inspector.get_table_names()
    assert len(tables_after) == 0


def test_get_migration_version(test_db_url):
    """Test retrieving the current migration version."""
    engine = create_engine(test_db_url)
    
    with patch('pygovpub.core.database.get_engine', return_value=engine):
        # Create migration version table
        with patch.object(MigrationManager, 'ensure_version_table'):
            # Test with no version yet
            with patch.object(MigrationManager, 'get_current_version', return_value=None):
                version = get_migration_version()
                assert version is None
            
            # Test with a version
            with patch.object(MigrationManager, 'get_current_version', return_value="1.0.0"):
                version = get_migration_version()
                assert version == "1.0.0"


def test_run_migrations(test_db_url):
    """Test running database migrations."""
    engine = create_engine(test_db_url)
    
    with patch('pygovpub.core.database.get_engine', return_value=engine):
        # Mock the migration manager
        with patch.object(MigrationManager, 'run_migrations') as mock_run:
            # Run migrations
            result = run_migrations()
            
            # Verify the migration manager was called
            mock_run.assert_called_once()
            
            # Test with a target version
            run_migrations(target_version="1.1.0")
            mock_run.assert_called_with(target_version="1.1.0")


def test_migration_manager(test_db_url):
    """Test the migration manager."""
    engine = create_engine(test_db_url)
    
    # Create a migration manager
    manager = MigrationManager(engine)
    
    # Test ensuring version table
    manager.ensure_version_table()
    
    # Verify the version table exists
    inspector = sqlalchemy.inspect(engine)
    tables = inspector.get_table_names()
    assert "schema_versions" in tables
    
    # Test getting current version when none exists
    version = manager.get_current_version()
    assert version is None
    
    # Test setting a version
    manager.set_version("1.0.0")
    
    # Test getting the version after it's set
    version = manager.get_current_version()
    assert version == "1.0.0"
    
    # Test applying a migration
    def mock_migration(session):
        # Create a test table
        session.execute(sqlalchemy.text(
            "CREATE TABLE test_migration (id INTEGER PRIMARY KEY, name TEXT)"
        ))
    
    # Register a mock migration
    with patch.dict(manager.migrations, {"1.1.0": mock_migration}):
        # Apply the migration
        manager.apply_migration("1.1.0")
        
        # Verify the migration was applied
        inspector = sqlalchemy.inspect(engine)
        tables = inspector.get_table_names()
        assert "test_migration" in tables
        
        # Check the version was updated
        version = manager.get_current_version()
        assert version == "1.1.0"
    
    # Test rollback functionality
    def mock_rollback(session):
        # Drop the test table
        session.execute(sqlalchemy.text("DROP TABLE test_migration"))
    
    # Register a mock rollback
    with patch.dict(manager.rollbacks, {"1.1.0": mock_rollback}):
        # Apply the rollback
        manager.rollback_migration("1.1.0")
        
        # Verify the table was dropped
        inspector = sqlalchemy.inspect(engine)
        tables = inspector.get_table_names()
        assert "test_migration" not in tables
        
        # Check the version was downgraded
        version = manager.get_current_version()
        assert version == "1.0.0"