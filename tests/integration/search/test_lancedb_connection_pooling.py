"""
Integration tests for LanceDB connection pooling.

These tests verify that the LanceDB connection pooling implementation works
correctly in a real-world environment with concurrent operations.
"""

import os
import pytest
import time
import threading
import concurrent.futures
from typing import List, Dict, Any

from pygovpub.storage.providers.lancedb_provider import (
    LanceDBProvider,
    LanceDBConnectionPool,
    get_connection_pool
)


@pytest.fixture
def temp_db_path(tmp_path):
    """Create a temporary path for LanceDB database."""
    db_path = os.path.join(tmp_path, "lancedb_test")
    os.makedirs(db_path, exist_ok=True)
    return db_path


def test_provider_connection_pooling(temp_db_path):
    """
    Test that the LanceDB provider correctly uses connection pooling.
    """
    # Create a provider with connection pooling
    provider = LanceDBProvider(
        uri=temp_db_path,
        use_connection_pool=True,
        pool_id="test_pool",
        pool_max_size=5,
        pool_min_size=2,
        vector_dim=4  # Small dimension for testing
    )
    
    # Get the pool for verification
    pool = provider.connection_pool
    assert pool is not None
    
    # Check pool configuration
    stats = pool.get_stats()
    assert stats["pool_id"] == "test_pool"
    assert stats["max_size"] == 5
    assert stats["min_size"] == 2
    
    # The test should account for both available and in-use connections
    # One connection is used by the provider itself
    assert stats["available_connections"] + stats["in_use_connections"] >= 2  # Should have at least min_size connections total
    
    # Create some test data
    from datetime import datetime
    
    class TestModel:
        __tablename__ = "test_table"
    
    # Create a few records using the provider
    for i in range(10):
        provider.create(TestModel, {
            "id": f"test-{i}",
            "title": f"Test Title {i}",
            "content": f"Test content for document {i}",
            "embedding": [0.1, 0.2, 0.3, 0.4],  # 4-dimensional vector
            "metadata": {"test": True, "index": i},
            "created_at": datetime.now().isoformat()
        })
    
    # Run concurrent searches
    results_list = []
    
    def perform_search(i):
        # Perform a vector search
        results = provider.vector_search(
            TestModel,
            query_vector=[0.1, 0.2, 0.3, 0.4],
            limit=5
        )
        return results
    
    # Run concurrent searches
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(perform_search, i) for i in range(20)]
        results_list = [future.result() for future in futures]
    
    # Verify results
    assert len(results_list) == 20  # Should have 20 result sets
    for results in results_list:
        assert len(results) > 0  # Each result set should have results
    
    # Check pool statistics after all operations
    stats = pool.get_stats()
    assert stats["available_connections"] <= 5  # Should not exceed max_size
    assert stats["in_use_connections"] <= 1  # All non-permanent connections should be released
                                            # The provider keeps one connection in use
    
    # Clean up
    pool.close_all()


def test_router_specific_pooling(temp_db_path):
    """
    Test that router-specific connection pooling works correctly.
    """
    # Create connection pools for different routers
    bills_pool = get_connection_pool(
        uri=temp_db_path,
        pool_id="bills_router",
        max_size=3,
        min_size=1
    )
    
    search_pool = get_connection_pool(
        uri=temp_db_path,
        pool_id="search_router",
        max_size=5,
        min_size=2
    )
    
    # Create providers that use these pools
    bills_provider = LanceDBProvider(
        uri=temp_db_path,
        use_connection_pool=True,
        pool_id="bills_router",
        vector_dim=4
    )
    
    search_provider = LanceDBProvider(
        uri=temp_db_path,
        use_connection_pool=True,
        pool_id="search_router",
        vector_dim=4
    )
    
    # Verify that the providers are using the correct pools
    assert bills_provider.connection_pool is bills_pool
    assert search_provider.connection_pool is search_pool
    
    # Create a model class for testing
    class TestModel:
        __tablename__ = "test_router_pool"
    
    # Run operations concurrently on both providers
    results = {"bills": [], "search": []}
    
    def bills_operation(i):
        bills_provider.create(TestModel, {
            "id": f"bill-{i}",
            "title": f"Bill Title {i}",
            "embedding": [0.1, 0.2, 0.3, 0.4]
        })
        return bills_provider.get(TestModel, f"bill-{i}")
    
    def search_operation(i):
        return search_provider.vector_search(
            TestModel,
            query_vector=[0.1, 0.2, 0.3, 0.4],
            limit=5
        )
    
    # Run concurrent operations
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        # Submit bills operations
        bill_futures = [executor.submit(bills_operation, i) for i in range(10)]
        # Submit search operations
        search_futures = [executor.submit(search_operation, i) for i in range(10)]
        
        # Get results
        for future in concurrent.futures.as_completed(bill_futures):
            results["bills"].append(future.result())
        for future in concurrent.futures.as_completed(search_futures):
            results["search"].append(future.result())
    
    # Verify results
    assert len(results["bills"]) == 10
    assert all(result is not None for result in results["bills"])
    assert len(results["search"]) == 10
    
    # Verify pool statistics
    bills_stats = bills_pool.get_stats()
    search_stats = search_pool.get_stats()
    
    assert bills_stats["max_size"] == 3
    assert search_stats["max_size"] == 5
    
    assert bills_stats["in_use_connections"] <= 1  # All non-permanent connections should be released
                                                  # Each provider keeps one connection in use
    assert search_stats["in_use_connections"] <= 1  # All non-permanent connections should be released
                                                   # Each provider keeps one connection in use
    
    # Clean up
    bills_pool.close_all()
    search_pool.close_all()


def test_connection_pool_health_check(temp_db_path):
    """
    Test that the connection pool correctly handles invalid connections.
    """
    # Create a pool
    pool = LanceDBConnectionPool(
        uri=temp_db_path,
        pool_id="health_test",
        min_size=2,
        max_size=3
    )
    
    # Get initial connections
    conn1, conn_id1 = pool.get_connection()
    conn2, conn_id2 = pool.get_connection()
    
    # Release both connections
    pool.release_connection(conn1, conn_id1)
    pool.release_connection(conn2, conn_id2)
    
    # Make one connection invalid - replace table_names method with one that raises exception
    original_table_names = conn1.table_names
    conn1.table_names = lambda: exec('raise Exception("Connection error")')
    
    # Try to get connections again - the invalid one should be discarded
    new_conn1, new_conn_id1 = pool.get_connection()
    new_conn2, new_conn_id2 = pool.get_connection()
    
    # At least one connection should be new (not the invalid one)
    assert new_conn1 is not conn1 or new_conn2 is not conn1
    
    # Clean up
    pool.close_all()
    
    # Restore original method
    conn1.table_names = original_table_names


def test_connection_pool_idle_cleanup(temp_db_path):
    """
    Test that the connection pool correctly cleans up idle connections.
    """
    # Create a pool with short idle timeout
    pool = LanceDBConnectionPool(
        uri=temp_db_path,
        pool_id="idle_test",
        min_size=1,
        max_size=3,
        idle_timeout=0.1  # 100ms idle timeout for testing
    )
    
    # Get a few connections
    connections = []
    for _ in range(3):
        conn, conn_id = pool.get_connection()
        connections.append((conn, conn_id))
    
    # Release all connections
    for conn, conn_id in connections:
        pool.release_connection(conn, conn_id)
    
    # Wait for idle timeout to expire
    time.sleep(0.2)
    
    # Clean up idle connections
    cleaned_up = pool.cleanup_idle_connections()
    
    # Should have cleaned up all connections exceeding min_size
    assert cleaned_up >= 2  # Should clean up at least 2 connections (max_size - min_size)
    
    # Verify pool state
    stats = pool.get_stats()
    assert stats["available_connections"] == 1  # Should only keep min_size connections
    
    # Clean up
    pool.close_all()