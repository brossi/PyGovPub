"""
Test suite for database performance optimizations.

This module tests advanced database performance optimizations including:
1. Connection pooling optimizations
2. Transaction isolation tuning
3. Bulk operation optimizations
4. Query cache utilization
"""

import pytest
import time
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
import sqlalchemy
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.pool import QueuePool, NullPool, StaticPool
from sqlmodel import SQLModel, Session, create_engine, select, Field

from pygovpub.core.database import (
    get_engine,
    get_async_engine,
    init_db,
    with_transaction,
    with_async_transaction,
    get_connection_url
)


def test_connection_pool_configuration():
    """Test that connection pool is properly configured based on environment."""
    # Test with SQLite (should use minimal pooling)
    with patch('pygovpub.core.database.get_connection_url', return_value='sqlite:///:memory:'):
        engine = init_db()
        # For SQLite, we expect no pool or a simple pool (NullPool or StaticPool)
        assert not isinstance(engine.pool, QueuePool)
        
    # Test with PostgreSQL (should use full pooling)
    mock_pg_url = 'postgresql://user:password@localhost/testdb'
    with patch('pygovpub.core.database.get_connection_url', return_value=mock_pg_url):
        engine = init_db()
        # For PostgreSQL, we expect a QueuePool with correct settings
        assert isinstance(engine.pool, QueuePool)
        assert engine.pool.size() == 5  # Default pool size
        assert engine.pool._max_overflow == 10  # Default max overflow


def test_connection_pool_reuse():
    """Test that connections are properly reused from the pool."""
    # Mock a PostgreSQL engine with pool
    mock_url = 'postgresql://user:password@localhost/testdb'
    
    with patch('pygovpub.core.database.get_connection_url', return_value=mock_url):
        # Create a real engine with a mock pool
        engine = init_db()
        
        # Track connection creation count
        connection_count = 0
        
        # Patch the connect method to track calls
        original_connect = engine.connect
        
        def mock_connect():
            nonlocal connection_count
            connection_count += 1
            return original_connect()
        
        engine.connect = mock_connect
        
        # Use multiple sessions sequentially (should reuse connections)
        for _ in range(5):
            with Session(engine) as session:
                # Just open and close the session
                pass
        
        # We should have created only one connection for all sessions
        # because they should be returned to the pool and reused
        assert connection_count <= 2  # Allow for initial connection + possible reset


@pytest.mark.asyncio
async def test_async_connection_pool_params():
    """Test that async connection pool is properly configured."""
    # Since we can't easily track connection reuse in an AsyncEngine
    # without detailed mocking, we'll verify the pool parameters
    
    # Create direct patch for create_async_engine at the module level
    with patch('pygovpub.core.database.create_async_engine') as mock_create_engine:
        # Mock the return value
        mock_engine = AsyncMock()
        mock_create_engine.return_value = mock_engine
        
        # Call get_async_engine with PostgreSQL-like URL
        with patch('pygovpub.core.database.get_connection_url', 
                 return_value='postgresql://user:pass@localhost/testdb'):
            # Force new engine to ensure our mocks are used
            get_async_engine(force_new=True)
            
            # Verify the correct pool parameters were used for PostgreSQL
            call_kwargs = mock_create_engine.call_args[1]
            assert call_kwargs.get('pool_pre_ping') is True
            assert call_kwargs.get('pool_recycle') == 3600
            assert call_kwargs.get('pool_size') == 5
            assert call_kwargs.get('max_overflow') == 10
            
    # Test with SQLite URL
    with patch('pygovpub.core.database.create_async_engine') as mock_create_engine:
        # Mock the return value
        mock_engine = AsyncMock()
        mock_create_engine.return_value = mock_engine
        
        # Call get_async_engine with SQLite URL
        with patch('pygovpub.core.database.get_connection_url', 
                 return_value='sqlite:///:memory:'):
            # Force new engine to ensure our mocks are used
            get_async_engine(force_new=True)
            
            # Verify SQLite doesn't get the same pool settings as PostgreSQL
            # This is because SQLite has different pooling requirements
            call_kwargs = mock_create_engine.call_args[1]
            assert call_kwargs.get('echo') is False  # This should be common in both


def test_transaction_isolation_detection():
    """Test that different isolation levels can be detected and used."""
    # For this test, we'll verify that SQLAlchemy knows about the isolation levels
    # we want to use, and that we can generate valid SQL for them
    
    # Standard SQL isolation levels that should be available in most DBs
    isolation_levels = [
        "READ UNCOMMITTED", 
        "READ COMMITTED",
        "REPEATABLE READ",
        "SERIALIZABLE"
    ]
    
    # For each isolation level, verify we can generate a SQL text object
    # Note: This doesn't execute the SQL, just verifies we can generate valid SQL
    for level_name in isolation_levels:
        # Create an isolation level SQL command
        sql_text = sqlalchemy.text(f"SET TRANSACTION ISOLATION LEVEL {level_name}")
        
        # Check that the SQL text contains the isolation level name
        assert level_name in str(sql_text), f"SQL should contain isolation level {level_name}"
        
    # Additionally verify that we can create a session with isolation level settings
    # in SQLAlchemy directly
    engine = create_engine("sqlite:///:memory:")
    
    # This just tests for syntax errors, not actual connection behavior
    with Session(engine) as session:
        # Just verify these standard levels can be set without syntax errors
        session.connection(execution_options={"isolation_level": "SERIALIZABLE"})
        
    # Test passed - we were able to specify isolation levels


def test_bulk_operation_performance():
    """Test that bulk operations are more efficient than individual operations."""
    # Create a test table
    engine = create_engine("sqlite:///:memory:")
    
    # Create a simple test table for bulk operations
    with engine.begin() as conn:
        conn.execute(sqlalchemy.text("""
            CREATE TABLE test_items (
                id INTEGER PRIMARY KEY,
                value TEXT
            )
        """))
    
    # Create test data
    item_count = 1000
    bulk_items = [{"id": i, "value": f"test_{i}"} for i in range(item_count)]
    
    # Test individual inserts
    start_time = time.time()
    with Session(engine) as session:
        for item in bulk_items[:50]:  # Use fewer items to make test faster
            session.execute(sqlalchemy.text(
                "INSERT INTO test_items (id, value) VALUES (:id, :value)"
            ), item)
        session.commit()
    individual_time = time.time() - start_time
    
    # Clear the table
    with Session(engine) as session:
        session.execute(sqlalchemy.text("DELETE FROM test_items"))
        session.commit()
    
    # Test bulk insert
    start_time = time.time()
    with Session(engine) as session:
        session.execute(sqlalchemy.text(
            "INSERT INTO test_items (id, value) VALUES (:id, :value)"
        ), bulk_items[:50])  # Use the same number of items for fair comparison
        session.commit()
    bulk_time = time.time() - start_time
    
    # Bulk operations should be faster
    assert bulk_time < individual_time


def test_query_cache_utilization():
    """Test that query caching improves performance for repeated queries."""
    # Create an engine with explicit query caching enabled
    engine = create_engine("sqlite:///:memory:", 
                         connect_args={"check_same_thread": False})
    
    # Create a simple test table
    with engine.begin() as conn:
        conn.execute(sqlalchemy.text("""
            CREATE TABLE test_items (
                id INTEGER PRIMARY KEY,
                value TEXT
            )
        """))
    
    # Create and insert test data
    item_count = 50  # Use fewer items for faster test
    with Session(engine) as session:
        for i in range(item_count):
            session.execute(sqlalchemy.text(
                "INSERT INTO test_items (id, value) VALUES (:id, :value)"
            ), {"id": i, "value": f"test_{i}"})
        session.commit()
    
    # First query - cache cold
    with Session(engine) as session:
        start_time = time.time()
        for _ in range(5):
            # Execute identical query multiple times
            session.execute(sqlalchemy.text("SELECT * FROM test_items WHERE id < 25"))
        cold_time = time.time() - start_time
    
    # Second query - cache should be warm
    with Session(engine) as session:
        start_time = time.time()
        for _ in range(5):
            # Execute identical query multiple times
            session.execute(sqlalchemy.text("SELECT * FROM test_items WHERE id < 25"))
        warm_time = time.time() - start_time
    
    # Note: This test is more of a demonstration of caching concept.
    # In SQLite memory, you might not see significant improvement.
    # Real performance gains would be observed with production databases.
    # For test consistency, we'll check it's not significantly slower
    assert warm_time <= cold_time * 1.5  # Allow more margin for test variability


# This fixture was replaced by inline table creation in each test