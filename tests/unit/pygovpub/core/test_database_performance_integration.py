"""
Integration tests for database performance optimizations.

These tests verify that the database performance optimization features
work correctly with real database operations.
"""

import pytest
import time
from unittest.mock import patch, MagicMock
import sqlalchemy
from sqlalchemy import text, Column, Integer, String, create_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker

from pygovpub.core.database import (
    bulk_insert,
    bulk_update,
    optimize_connection_pool,
    get_recommended_isolation_level,
    get_database_performance_stats
)
from pygovpub.core.db_performance import (
    ConnectionPoolManager,
    TransactionManager,
    BulkOperationOptimizer,
    QueryCache,
    DatabasePerformanceManager
)

# Create a simple test model
Base = declarative_base()

# Renamed from TestItem to PerformanceTestItem to avoid pytest collection warning
class PerformanceTestItem(Base):
    """Test model for database performance tests."""
    __tablename__ = "performance_test_items"
    
    id = Column(Integer, primary_key=True)
    name = Column(String)
    value = Column(String)


def test_query_cache():
    """Test that QueryCache works correctly."""
    # Create a query cache
    cache = QueryCache(ttl_seconds=60)
    
    # Test caching
    query_key = "SELECT * FROM test_table WHERE id = 1"
    result = ["test_result"]
    
    # Cache miss initially
    assert cache.get(query_key) is None
    assert cache.stats["misses"] == 1
    
    # Set cache
    cache.set(query_key, result)
    
    # Cache hit
    assert cache.get(query_key) == result
    assert cache.stats["hits"] == 1
    
    # Test invalidation
    cache.invalidate(query_key)
    assert cache.get(query_key) is None
    assert cache.stats["misses"] == 2
    assert cache.stats["invalidations"] == 1
    
    # Test stats
    stats = cache.get_stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 2
    assert stats["invalidations"] == 1
    assert stats["cache_size"] == 0


def test_transaction_manager():
    """Test that TransactionManager works correctly."""
    # Create a mock engine
    mock_engine = MagicMock()
    
    # Create transaction manager
    manager = TransactionManager(mock_engine)
    
    # Test get_recommended_isolation_level
    isolation_level = manager.get_recommended_isolation_level("read")
    assert isolation_level == "READ COMMITTED"
    
    isolation_level = manager.get_recommended_isolation_level("report")
    assert isolation_level == "READ UNCOMMITTED"
    
    isolation_level = manager.get_recommended_isolation_level("write")
    assert isolation_level == "REPEATABLE READ"
    
    isolation_level = manager.get_recommended_isolation_level("financial")
    assert isolation_level == "SERIALIZABLE"


def test_bulk_operation_optimizer():
    """Test that BulkOperationOptimizer works correctly."""
    # Create a real SQLite in-memory database
    engine = create_engine("sqlite:///:memory:")
    
    # Create test table for PerformanceTestItem
    Base.metadata.create_all(engine)
    
    # Create optimizer
    optimizer = BulkOperationOptimizer(engine)
    
    # Test bulk insert
    test_data = [
        {"id": i, "name": f"Item {i}", "value": f"Value {i}"}
        for i in range(10)
    ]
    
    rows_inserted = optimizer.bulk_insert("performance_test_items", test_data)
    assert rows_inserted == 10
    
    # Check data was inserted
    with sessionmaker(engine)() as session:
        result = session.execute(text("SELECT COUNT(*) FROM performance_test_items")).scalar()
        assert result == 10
    
    # Test bulk update
    update_data = [
        {"id": i, "name": f"Updated Item {i}", "value": f"Updated Value {i}"}
        for i in range(5)
    ]
    
    rows_updated = optimizer.bulk_update("performance_test_items", update_data, "id")
    assert rows_updated == 5
    
    # Check data was updated
    with sessionmaker(engine)() as session:
        result = session.execute(
            text("SELECT COUNT(*) FROM performance_test_items WHERE name LIKE 'Updated%'")
        ).scalar()
        assert result == 5
    
    # Test stats
    stats = optimizer.get_stats()
    assert stats["insert"]["rows"] == 10
    assert stats["update"]["rows"] == 5


def test_database_performance_manager():
    """Test that DatabasePerformanceManager works correctly."""
    # Create a real SQLite in-memory database
    engine = create_engine("sqlite:///:memory:")
    
    # Create test table for PerformanceTestItem
    Base.metadata.create_all(engine)
    
    # Create performance manager
    manager = DatabasePerformanceManager(engine)
    
    # Test bulk insert
    test_data = [
        {"id": i, "name": f"Item {i}", "value": f"Value {i}"}
        for i in range(10)
    ]
    
    rows_inserted = manager.bulk_insert("performance_test_items", test_data)
    assert rows_inserted == 10
    
    # Test getting stats
    stats = manager.get_performance_stats()
    assert "bulk_operations" in stats
    assert "query_cache" in stats
    
    # Test recommendations
    recommendations = manager.get_optimization_recommendations()
    assert isinstance(recommendations, list)