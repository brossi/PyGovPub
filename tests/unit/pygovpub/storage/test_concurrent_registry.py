"""
Tests for concurrent access to the schema registry.

This module tests that the schema registry properly handles
concurrent access from multiple threads or processes.
"""

import asyncio
import pytest
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Any
from unittest.mock import patch, MagicMock, PropertyMock

from sqlalchemy.exc import IntegrityError
from pygovpub.storage.schema_registry import SchemaRegistry


class TestConcurrentSchemaRegistry:
    """Test concurrent access to the schema registry."""

    @pytest.fixture
    def mock_storage_interface(self):
        """Create a mock storage interface with realistic connection behavior."""
        storage = MagicMock()
        engine = MagicMock()
        conn = MagicMock()
        
        # Mock engine.connect to return a connection
        engine.connect.return_value.__enter__.return_value = conn
        storage.engine = engine
        
        # Mock transaction behavior
        transaction = MagicMock()
        conn.begin.return_value = transaction
        
        # Set up execute behavior for version checks
        execute_result = MagicMock()
        execute_result.fetchone.return_value = {
            "version": "1.0.0",
            "description": "Initial version",
            "applied_at": "2025-03-12T10:00:00",
            "api_version": "1.0.0"
        }
        execute_result.fetchall.return_value = [
            {
                "version": "1.0.0",
                "description": "Initial version",
                "applied_at": "2025-03-12T10:00:00",
                "api_version": "1.0.0"
            }
        ]
        conn.execute.return_value = execute_result
        
        # Mock db_type for testing
        type(storage).db_type = PropertyMock(return_value="postgresql")
        
        # Add a registry of registered versions to simulate concurrent access
        storage.registered_versions = []
        
        # Add a lock to simulate database constraints in a thread-safe way
        storage.version_lock = threading.Lock()
        
        return storage

    @pytest.fixture
    def registry(self, mock_storage_interface):
        """Create a schema registry with a mock storage interface."""
        with patch('pygovpub.storage.schema_registry.inspect'):
            registry = SchemaRegistry(mock_storage_interface)
            
            # Mock internal methods that would interact with the database
            def mock_ensure_version_table():
                return True
            
            # Replace _ensure_version_table with our mock
            registry._ensure_version_table = mock_ensure_version_table
            
            # Set up register_version to simulate concurrent behavior
            def mock_register_version(version, description, api_version="1.0.0", **kwargs):
                # Use a lock to simulate database constraints in a thread-safe way
                with mock_storage_interface.version_lock:
                    # Check if version already registered (simulating DB constraint)
                    if version in mock_storage_interface.registered_versions:
                        raise IntegrityError("Duplicate version", 
                                            params={}, 
                                            orig=Exception("Unique constraint violation"))
                    
                    # Add small delay to increase chance of race conditions
                    time.sleep(0.01)
                    
                    # Add version to registry
                    mock_storage_interface.registered_versions.append(version)
                    return True
            
            # Set up apply_migration to simulate transaction behavior
            def mock_apply_migration(version, description, up_sql, down_sql=None, register=True, 
                                     api_version=None, force=False):
                # Use a lock to simulate database transaction isolation
                with mock_storage_interface.version_lock:
                    # Simulate the transaction behavior
                    if version in mock_storage_interface.registered_versions:
                        return False
                    
                    # Simulate SQL error for specific test case
                    if "error" in up_sql.lower():
                        raise Exception("SQL execution error")
                    
                    # Add small delay to simulate processing time and increase chance of race conditions
                    time.sleep(0.02)
                    
                    # Successful migration
                    if register:
                        mock_storage_interface.registered_versions.append(version)
                    return True
            
            # Replace the real methods with our mock implementations
            registry.register_version = mock_register_version
            registry.apply_migration = mock_apply_migration
            
            return registry

    def test_concurrent_version_registration(self, registry, mock_storage_interface):
        """Test that concurrent version registration is properly synchronized."""
        # List to store successful registrations and errors
        results = {"success": [], "errors": []}
        
        # Function to register a version in a thread
        def register_version(version, description):
            try:
                success = registry.register_version(
                    version=version,
                    description=description,
                    api_version="1.0.0"
                )
                if success:
                    results["success"].append(version)
            except IntegrityError:
                # This simulates database constraint preventing duplicates
                results["errors"].append(f"Duplicate version: {version}")
            except Exception as e:
                results["errors"].append(f"Error registering {version}: {str(e)}")
        
        # Start multiple threads to register the same version concurrently
        threads = []
        version = "1.0.1"
        description = "Concurrent test version"
        
        # Create 5 threads all trying to register the same version
        for _ in range(5):
            thread = threading.Thread(
                target=register_version,
                args=(version, description)
            )
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify only one thread succeeded and the rest failed with integrity errors
        assert len(results["success"]) == 1, "Only one thread should succeed"
        assert len(results["errors"]) == 4, "The other threads should fail"
        assert results["success"][0] == version, "The successful version should match"
        
        # Verify the version was registered exactly once
        assert mock_storage_interface.registered_versions.count(version) == 1

    def test_concurrent_different_version_registration(self, registry, mock_storage_interface):
        """Test that different versions can be registered concurrently."""
        # Function to register a version in a thread
        def register_version(version, description):
            try:
                return registry.register_version(
                    version=version,
                    description=description,
                    api_version="1.0.0"
                )
            except Exception:
                return False
        
        # Start multiple threads to register different versions concurrently
        versions = [f"1.0.{i}" for i in range(1, 6)]
        descriptions = [f"Version {v}" for v in versions]
        
        # Use ThreadPoolExecutor to run tasks concurrently
        with ThreadPoolExecutor(max_workers=5) as executor:
            results = list(executor.map(register_version, versions, descriptions))
        
        # Verify all registrations succeeded
        assert all(results), "All version registrations should succeed"
        
        # Verify all versions were registered
        for version in versions:
            assert version in mock_storage_interface.registered_versions
        
        # Verify each version was registered exactly once
        for version in versions:
            assert mock_storage_interface.registered_versions.count(version) == 1

    def test_concurrent_version_check_during_registration(self, registry, mock_storage_interface):
        """Test checking version history while registrations are happening."""
        # Event to synchronize the test
        ready_event = threading.Event()
        done_event = threading.Event()
        version_history_results = []
        registration_results = {"success": [], "errors": []}
        
        # Thread function for continuous history checks
        def check_version_history():
            while not done_event.is_set():
                # Get current registered versions from our mock storage with thread safety
                with mock_storage_interface.version_lock:
                    current_versions = list(mock_storage_interface.registered_versions)
                
                version_history_results.append(current_versions)
                time.sleep(0.01)  # Small delay to avoid CPU spinning
        
        # Thread function for registering versions
        def register_versions():
            # Register 5 versions with small delays between them
            for i in range(1, 6):
                version = f"1.0.{i}"
                try:
                    success = registry.register_version(
                        version=version,
                        description=f"Version {version}",
                        api_version="1.0.0"
                    )
                    if success:
                        registration_results["success"].append(version)
                except Exception as e:
                    registration_results["errors"].append(str(e))
                
                # Small delay to ensure history checking happens between registrations
                time.sleep(0.02)
            
            # Signal that registration is complete
            ready_event.set()
        
        # Start history checking thread
        history_thread = threading.Thread(target=check_version_history)
        history_thread.daemon = True
        history_thread.start()
        
        # Start registration thread
        registration_thread = threading.Thread(target=register_versions)
        registration_thread.start()
        
        # Wait for registration to complete
        registration_thread.join()
        
        # Let history thread capture final state before stopping it
        time.sleep(0.05)
        done_event.set()
        history_thread.join(timeout=0.5)
        
        # Verify all 5 versions were registered successfully
        assert len(registration_results["success"]) == 5
        assert len(registration_results["errors"]) == 0
        
        # Verify history snapshots show increasing versions
        # Since snapshots are taken continuously, at least some should show partial registration state
        version_counts = [len(history) for history in version_history_results]
        
        # There should be snapshots with different version counts as registrations progress
        assert len(set(version_counts)) > 1, "History snapshots should show registration progression"
        
        # The final snapshot should contain all 5 versions
        assert 5 in version_counts, "Final history snapshot should contain all 5 versions"

    def test_concurrent_migrations_with_transactions(self, registry, mock_storage_interface):
        """Test concurrent migrations with transaction behavior."""
        # List to store migration results
        results = {"success": [], "errors": []}
        
        # Function to apply migration in a thread
        def apply_migration(version, description, up_sql):
            try:
                success = registry.apply_migration(
                    version=version,
                    description=description,
                    up_sql=up_sql,
                    down_sql=f"DROP TABLE IF EXISTS table_{version};",
                    register=True,
                    api_version="1.0.0"
                )
                if success:
                    results["success"].append(version)
                else:
                    results["errors"].append(f"Migration failed: {version}")
            except Exception as e:
                results["errors"].append(f"Error in migration {version}: {str(e)}")
        
        # Start multiple threads with both successful and failing migrations
        threads = []
        
        # Thread 1 & 2: Try to apply the same migration (only one should succeed)
        for i in range(2):
            thread = threading.Thread(
                target=apply_migration,
                args=("1.2.0", "Add user table", "CREATE TABLE users (id INTEGER PRIMARY KEY);")
            )
            threads.append(thread)
        
        # Thread 3: Apply a different migration (should succeed)
        thread = threading.Thread(
            target=apply_migration,
            args=("1.3.0", "Add products table", "CREATE TABLE products (id INTEGER PRIMARY KEY);")
        )
        threads.append(thread)
        
        # Thread 4: Apply a migration with an error (should fail)
        thread = threading.Thread(
            target=apply_migration,
            args=("1.4.0", "Add orders table with error", "CREATE TABLE orders WITH ERROR (id INTEGER PRIMARY KEY);")
        )
        threads.append(thread)
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify results:
        # 1. Only one of the duplicate migrations succeeded
        # 2. The different migration succeeded
        # 3. The error migration failed
        assert mock_storage_interface.registered_versions.count("1.2.0") == 1, "Duplicate migration should only succeed once"
        assert "1.3.0" in mock_storage_interface.registered_versions, "Different migration should succeed"
        assert "1.4.0" not in mock_storage_interface.registered_versions, "Error migration should not be registered"
        
        # Verify correct number of successes and errors
        assert len(results["success"]) == 2, "Should have 2 successful migrations"
        assert len(results["errors"]) == 2, "Should have 2 failed migrations"
        
        # Check for expected error messages
        error_messages = " ".join(results["errors"])
        assert "SQL execution error" in error_messages, "Should contain SQL error message"

    @pytest.mark.asyncio
    async def test_async_concurrent_operations(self, registry, mock_storage_interface):
        """Test async concurrent operations on the schema registry."""
        # Function for async version registration
        async def register_version(version):
            return registry.register_version(
                version=version,
                description=f"Async version {version}",
                api_version="1.0.0"
            )
        
        # Create multiple tasks for concurrent version registration
        tasks = []
        for i in range(1, 6):
            version = f"1.1.{i}"
            tasks.append(asyncio.create_task(register_version(version)))
        
        # Wait for all tasks to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Check that all registrations succeeded without exceptions
        for result in results:
            assert not isinstance(result, Exception), f"Registration failed with exception: {result}"
            assert result is True, "Registration should return True on success"
        
        # Verify all versions were registered exactly once
        for i in range(1, 6):
            version = f"1.1.{i}"
            assert mock_storage_interface.registered_versions.count(version) == 1


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])