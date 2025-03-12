"""
Tests for concurrent access to the schema registry.

This module tests that the schema registry properly handles
concurrent access from multiple threads or processes.

NOTE: These tests need further implementation work to properly mock
the SchemaRegistry's internal operations. Currently the tests need
to be updated to match how the registry actually performs database operations.
"""

import asyncio
import pytest
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Any
from unittest.mock import patch, MagicMock

from pygovpub.storage.schema_registry import SchemaRegistry


class TestConcurrentSchemaRegistry:
    """Test concurrent access to the schema registry."""

    @pytest.fixture
    def mock_storage_interface(self):
        """Create a mock storage interface."""
        interface = MagicMock()
        # Mock connection
        conn = MagicMock()
        interface.conn = conn
        
        # Mock transaction context manager
        transaction = MagicMock()
        conn.begin.return_value = transaction
        
        # Mock execute results for get_current_version
        execute_result = MagicMock()
        execute_result.fetchone.return_value = {
            "version": "1.0.0",
            "description": "Initial version",
            "applied_at": "2025-03-12T10:00:00",
            "api_version": "1.0.0"
        }
        conn.execute.return_value = execute_result
        
        return interface

    @pytest.fixture
    def registry(self, mock_storage_interface):
        """Create a schema registry with a mock storage interface."""
        with patch('pygovpub.storage.schema_registry.inspect'):
            registry = SchemaRegistry(mock_storage_interface)
            # Mock _ensure_version_table to avoid actual table creation
            registry._ensure_version_table = MagicMock(return_value=True)
            return registry

    def test_concurrent_version_registration(self, registry):
        """Test that concurrent version registration is handled correctly with locks."""
        # List to store successful registrations
        successful_registrations = []
        registration_errors = []
        
        # Function to register a version in a thread
        def register_version(version, description):
            try:
                success = registry.register_version(
                    version=version,
                    description=description,
                    api_version="1.0.0"
                )
                if success:
                    successful_registrations.append(version)
                else:
                    registration_errors.append(f"Registration failed for {version}")
            except Exception as e:
                registration_errors.append(f"Error registering {version}: {str(e)}")
        
        # Start multiple threads to register versions concurrently
        threads = []
        for i in range(1, 6):
            version = f"1.0.{i}"
            description = f"Version {version}"
            thread = threading.Thread(
                target=register_version,
                args=(version, description)
            )
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify that each version was attempted
        assert len(successful_registrations) + len(registration_errors) == 5
        
        # Check mock connection was used correctly
        # Each registration should call execute at least once
        assert registry.storage.conn.execute.call_count >= 5

    def test_concurrent_get_version_history(self, registry):
        """Test that concurrent reads of version history work correctly."""
        # Mock response for get_version_history
        history_result = MagicMock()
        history_result.fetchall.return_value = [
            {"version": "1.0.0", "description": "Initial version", 
             "applied_at": "2025-03-12T10:00:00", "api_version": "1.0.0"},
            {"version": "1.0.1", "description": "Schema update", 
             "applied_at": "2025-03-12T11:00:00", "api_version": "1.0.0"}
        ]
        registry.storage.conn.execute.return_value = history_result
        
        # Function to get version history in a thread
        results = []
        errors = []
        
        def get_history():
            try:
                history = registry.get_version_history()
                results.append(len(history))
            except Exception as e:
                errors.append(str(e))
        
        # Start multiple threads to get history concurrently
        with ThreadPoolExecutor(max_workers=10) as executor:
            # Submit 10 concurrent tasks
            futures = [executor.submit(get_history) for _ in range(10)]
            
            # Wait for all to complete
            for future in futures:
                future.result()
        
        # Verify all calls succeeded
        assert len(results) == 10
        assert len(errors) == 0
        # All should return 2 versions
        assert all(count == 2 for count in results)
        
    def test_concurrent_apply_migration(self, registry):
        """Test that concurrent migrations are properly synchronized."""
        # Track migration attempts and results
        migration_results = []
        
        # Function to apply a migration in a thread
        def apply_migration(version, description, sql):
            try:
                success = registry.apply_migration(
                    version=version,
                    description=description,
                    up_sql=sql,
                    down_sql=f"-- Down migration for {version}",
                    register=True
                )
                migration_results.append((version, success))
            except Exception as e:
                migration_results.append((version, str(e)))
        
        # Start multiple threads to apply migrations concurrently
        threads = []
        for i in range(1, 4):
            version = f"1.0.{i}"
            description = f"Migration {version}"
            sql = f"CREATE TABLE test_{i} (id INTEGER PRIMARY KEY);"
            thread = threading.Thread(
                target=apply_migration,
                args=(version, description, sql)
            )
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify that migrations were attempted
        assert len(migration_results) == 3
        
        # Check that correct calls were made
        assert registry.storage.conn.begin.call_count == 3  # One transaction per migration
        assert registry.storage.conn.execute.call_count >= 3  # At least one execute per migration

    @pytest.mark.asyncio
    async def test_async_concurrent_schema_operations(self, registry):
        """Test async concurrent operations on the schema registry."""
        
        # Create async functions for schema operations
        async def async_register_version(version, description):
            return registry.register_version(
                version=version,
                description=description,
                api_version="1.0.0"
            )
        
        async def async_get_current_version():
            return registry.get_current_version()
        
        async def async_get_version_history():
            return registry.get_version_history()
        
        # Run multiple operations concurrently
        tasks = []
        for i in range(1, 4):
            # Mix registration and query operations
            version = f"1.1.{i}"
            description = f"Async version {version}"
            
            # Create tasks for different operations
            tasks.append(asyncio.create_task(async_register_version(version, description)))
            tasks.append(asyncio.create_task(async_get_current_version()))
            tasks.append(asyncio.create_task(async_get_version_history()))
        
        # Wait for all tasks to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Verify no exceptions occurred
        exceptions = [r for r in results if isinstance(r, Exception)]
        assert len(exceptions) == 0, f"Exceptions occurred: {exceptions}"
        
        # Verify at least some operations succeeded
        assert any(results), "No operation succeeded"
        
        # Check that appropriate DB calls were made
        assert registry.storage.conn.execute.call_count > 0


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])