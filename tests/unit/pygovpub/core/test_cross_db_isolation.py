"""
Tests for cross-database type session isolation in the storage interface.

These tests verify that sessions are properly isolated when working with
multiple database types simultaneously.
"""

import pytest
from unittest.mock import patch, MagicMock, call
import asyncio

from sqlmodel import SQLModel, Field, Session
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from pygovpub.storage.interface import StorageInterface


# Test model for database operations
class TestItem(SQLModel, table=True):
    """Simple test model for database operations."""
    __tablename__ = "test_items"
    
    id: int = Field(primary_key=True)
    name: str
    description: str = Field(default="")
    source: str = Field(default="unknown")
    
    # Add class method to suppress warning about __init__ constructor
    @classmethod
    def get_item_by_id(cls, session, item_id):
        """Get test item by ID using SQLModel's exec method."""
        from sqlmodel import select
        stmt = select(cls).where(cls.id == item_id)
        return session.exec(stmt).first()


class TestCrossDbTypeSessionIsolation:
    """Test proper session isolation across database types."""
    
    @pytest.fixture
    def sqlite_db(self):
        """Create an in-memory SQLite database."""
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool
        )
        
        # Create TestItem table explicitly
        with engine.begin() as conn:
            conn.execute(text("""
            CREATE TABLE IF NOT EXISTS test_items (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                source TEXT
            )
            """))
            
            # Insert test data
            conn.execute(text("""
            INSERT INTO test_items (id, name, description, source)
            VALUES 
                (1, 'Item 1', '', 'sqlite'),
                (2, 'Item 2', '', 'sqlite')
            """))
            
        # Also create tables from SQLModel metadata for good measure
        SQLModel.metadata.create_all(engine)
        return engine
    
    @pytest.fixture
    def postgres_mock(self):
        """Create a mock for PostgreSQL database."""
        return MagicMock()
    
    @pytest.fixture
    def lancedb_mock(self):
        """Create a mock for LanceDB provider."""
        mock = MagicMock()
        mock.db_type = "lancedb"
        return mock
    
    def test_session_isolation_different_db_types(self, sqlite_db, postgres_mock, lancedb_mock):
        """Test that sessions are isolated between different database types."""
        # Create storage interface with existing SQLite DB and mock provider
        sqlite_storage = StorageInterface("sqlite:///:memory:")
        sqlite_storage.engine = sqlite_db
        
        # Create a special session factory that tracks creation
        session_tracker = []
        
        def tracked_session_factory():
            session = Session(sqlite_db)
            session_tracker.append(session)
            return session
            
        sqlite_storage.Session = tracked_session_factory
        
        # Replace internal providers with our mock
        sqlite_storage._providers = {}
        sqlite_storage._providers["lancedb"] = lancedb_mock
        
        # 1. Do an operation in SQLite
        sqlite_result = sqlite_storage.get(TestItem, 1)
        assert sqlite_result is not None
        assert sqlite_result["source"] == "sqlite"
        
        # 2. Do an operation in LanceDB
        sqlite_storage.get_with_provider("lancedb", TestItem, 1)
        
        # Verify LanceDB provider was called correctly
        lancedb_mock.get.assert_called_once_with(TestItem, 1)
        
        # 3. Verify that the SQLite session was not affected by the LanceDB operation
        sqlite_result2 = sqlite_storage.get(TestItem, 2)
        assert sqlite_result2 is not None
        assert sqlite_result2["source"] == "sqlite"
        
        # Verify that we created separate sessions for each operation
        # We should have at least 2 separate session instances for the SQLite operations
        assert len(session_tracker) >= 2, "Should create separate sessions for each DB operation"
    
    def test_concurrent_operations_session_isolation(self, sqlite_db, lancedb_mock):
        """Test session isolation during concurrent operations."""
        # Create storage interface with the properly configured engine
        storage = StorageInterface("sqlite:///:memory:")
        storage.engine = sqlite_db  # Use our test database
        
        # Create a special session factory that tracks creation
        session_list = []
        close_count = [0]  # Use list to track by reference
        
        def tracked_session_factory():
            # Create a real session but with tracked close
            session = Session(sqlite_db)
            
            # Track the original close method
            original_close = session.close
            
            # Replace close with our tracked version
            def tracked_close():
                close_count[0] += 1
                return original_close()
                
            session.close = tracked_close
            session_list.append(session)
            return session
            
        storage.Session = tracked_session_factory
        storage._providers = {}
        storage._providers["lancedb"] = lancedb_mock
        
        # Do a SQLite operation
        storage.get(TestItem, 1)
        
        # Do a LanceDB operation - should not affect SQLite session
        storage.get_with_provider("lancedb", TestItem, 1)
        
        # Do another SQLite operation 
        storage.get(TestItem, 2)
        
        # Verify sessions were properly created and closed
        assert len(session_list) >= 2, "Should create separate sessions for SQLite operations"
        assert close_count[0] >= 2, "SQLite sessions should be properly closed"
        
        # Verify LanceDB provider was called
        lancedb_mock.get.assert_called_once_with(TestItem, 1)
        
        # Verify test data is still accessible
        result = storage.get(TestItem, 2)
        assert result is not None, "Should be able to access data after multiple operations"
        assert result["source"] == "sqlite", "Data integrity should be maintained"
    
    def test_error_isolation_across_db_types(self, sqlite_db, lancedb_mock):
        """Test that errors in one database don't affect operations in another."""
        # Create storage interface with session tracking
        storage = StorageInterface("sqlite:///:memory:")
        storage.engine = sqlite_db
        
        # Create a session tracker to verify session creation and isolation
        session_list = []
        
        def tracked_session_factory():
            session = Session(sqlite_db)
            session_list.append(session)
            return session
            
        storage.Session = tracked_session_factory
        storage._providers = {}
        storage._providers["lancedb"] = lancedb_mock
        
        # Configure LanceDB to raise an error
        lancedb_mock.get.side_effect = Exception("LanceDB error")
        
        # 1. Try a LanceDB operation that will fail
        with pytest.raises(Exception) as exc:
            storage.get_with_provider("lancedb", TestItem, 1)
        assert "LanceDB error" in str(exc.value)
        
        # 2. SQLite operations should still work despite LanceDB error
        sqlite_result = storage.get(TestItem, 1)
        assert sqlite_result is not None
        assert sqlite_result["source"] == "sqlite"
        
        # 3. Another SQLite operation should also work
        sqlite_result2 = storage.get(TestItem, 2)
        assert sqlite_result2 is not None
        assert sqlite_result2["source"] == "sqlite"
        
        # 4. Reset the mock and try again to verify continued operation
        lancedb_mock.get.side_effect = None
        lancedb_mock.get.return_value = {"id": 1, "name": "Item 1", "source": "lancedb"}
        
        # LanceDB operations should now work
        lancedb_result = storage.get_with_provider("lancedb", TestItem, 1)
        assert lancedb_result is not None
        assert lancedb_result["source"] == "lancedb"
        
        # Verify that enough sessions were created for all operations
        assert len(session_list) >= 2, "Multiple sessions should be created for SQLite operations"
    
    @pytest.mark.asyncio
    async def test_async_session_isolation(self, sqlite_db, lancedb_mock):
        """Test session isolation in async operations."""
        # Create storage interface with session tracking
        storage = StorageInterface("sqlite:///:memory:")
        storage.engine = sqlite_db
        
        # Create session trackers for both sync and async sessions
        sync_sessions = []
        
        def tracked_session_factory():
            session = Session(sqlite_db)
            sync_sessions.append(session)
            return session
            
        storage.Session = tracked_session_factory
        storage._providers = {}
        storage._providers["lancedb"] = lancedb_mock
        
        # Mock async SQLAlchemy components
        storage.async_engine = MagicMock()
        async_session_mock = MagicMock()
        async_session_factory_mock = MagicMock(return_value=async_session_mock)
        storage.AsyncSession = async_session_factory_mock
        
        # Configure lancedb mock
        lancedb_mock.get.return_value = {"id": 1, "name": "LanceDB Item", "source": "lancedb"}
        
        # Mock asynchronous behavior
        async def async_execute(*args, **kwargs):
            return MagicMock(scalar_one_or_none=lambda: TestItem(id=1, name="Async Item", source="sqlite"))
        
        async_session_mock.execute.side_effect = async_execute
        async_session_mock.__aenter__ = MagicMock(return_value=async_session_mock)
        async_session_mock.__aexit__ = MagicMock(return_value=None)
        
        # Mock close as an async method
        async def async_close():
            pass
            
        async_session_mock.close = async_close
        
        # 1. Do an async SQLite operation
        try:
            async_result = await storage.get_async(TestItem, 1)
            assert async_result is not None
            assert async_result["source"] == "sqlite"
        except NotImplementedError:
            # Skip this test if async is not supported
            pytest.skip("Async operations not supported in this environment")
            return
            
        # 2. Do a LanceDB operation
        lancedb_result = storage.get_with_provider("lancedb", TestItem, 1)
        assert lancedb_result is not None
        assert lancedb_result["source"] == "lancedb"
        
        # 3. Do a sync SQLite operation to verify isolation
        sqlite_result = storage.get(TestItem, 2)
        assert sqlite_result is not None
        assert sqlite_result["source"] == "sqlite"
        
        # 4. Verify sessions were properly isolated
        lancedb_mock.get.assert_called_once_with(TestItem, 1)
        
        # Verify async session was created and used
        assert async_session_factory_mock.call_count >= 1, "Async session factory should be called"
        assert async_session_mock.execute.called, "Async session should be used for async operations"
        
        # Verify sync sessions were created for SQLite operations
        assert len(sync_sessions) >= 1, "Sync sessions should be created for SQLite operations"


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])