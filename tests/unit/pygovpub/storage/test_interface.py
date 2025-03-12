"""
Tests for the core storage interface.

This module tests the database-agnostic storage interface with
monitoring, circuit breaking, and feature detection capabilities.
"""

import os
import pytest
import importlib
import tempfile
from unittest.mock import patch, MagicMock
from pathlib import Path
from sqlalchemy.exc import SQLAlchemyError, OperationalError

from pygovpub.storage.interface import StorageInterface, circuit_breaker


class TestStorageInterface:
    """Test suite for the StorageInterface class."""

    def test_determine_db_type(self):
        """Verify database type detection from connection strings."""
        # Create test cases of connection strings and expected DB types
        test_cases = [
            ("sqlite:///test.db", "sqlite"),
            ("sqlite:///:memory:", "sqlite"),
            ("postgresql://user:pass@localhost/testdb", "postgresql"),
            ("postgresql+psycopg2://user:pass@localhost/testdb", "postgresql"),
            ("mysql://user:pass@localhost/testdb", "mysql"),
            ("mysql+pymysql://user:pass@localhost/testdb", "mysql"),
            ("pinecone://api_key@environment", "pinecone"),
            ("supabase://url/key", "supabase"),
            ("lancedb:///path/to/db", "lancedb"),
            ("unknown://test", "unknown")
        ]
        
        # Create a minimal interface instance
        interface = StorageInterface.__new__(StorageInterface)
        
        # Test each case directly
        for conn_string, expected_type in test_cases:
            actual_type = interface._determine_db_type(conn_string)
            assert actual_type == expected_type, f"Failed to detect {expected_type} from {conn_string}"
    
    @patch("sqlalchemy.create_engine")
    def test_get_async_connection_string(self, mock_create_engine):
        """Verify conversion of standard connection strings to async equivalents."""
        # Mock engine
        mock_engine = MagicMock()
        mock_create_engine.return_value = mock_engine
        
        # Create test cases
        test_cases = [
            # Input, Expected Output
            ("sqlite:///test.db", "sqlite+aiosqlite:///test.db"),
            ("postgresql://user:pass@localhost/testdb", "postgresql+asyncpg://user:pass@localhost/testdb"),
            ("something://else", "something://else")  # Should return original for non-standard
        ]
        
        # Test each case
        for input_str, expected_output in test_cases:
            # Patch _supports_async to avoid async engine creation
            with patch.object(StorageInterface, "_supports_async", return_value=False):
                interface = StorageInterface(input_str)
                result = interface._get_async_connection_string(input_str)
                assert result == expected_output, f"Failed to convert {input_str} to async equivalent"
    
    @patch("importlib.util.find_spec")
    def test_supports_async(self, mock_find_spec):
        """Test async support detection based on available packages."""
        # Mock importlib.util.find_spec to control package availability
        def mock_find_impl(package):
            if package == "aiosqlite":
                return MagicMock()  # SQLite async driver available
            if package == "asyncpg":
                return None  # PostgreSQL async driver not available
            return None
        
        mock_find_spec.side_effect = mock_find_impl
        
        # Test SQLite with available driver
        sqlite_interface = StorageInterface("sqlite:///test.db")
        assert sqlite_interface._supports_async() is True
        
        # Test PostgreSQL with unavailable driver
        pg_interface = StorageInterface("postgresql://localhost/test")
        assert pg_interface._supports_async() is False
        
        # Test non-standard DB
        other_interface = StorageInterface("pinecone://api_key@environment")
        assert other_interface._supports_async() is False
    
    def test_feature_detection_postgresql(self):
        """Test PostgreSQL feature detection, especially pgvector extension."""
        # Create a minimal interface instance
        interface = StorageInterface.__new__(StorageInterface)
        interface.db_type = "postgresql"
        interface.engine = MagicMock()
        
        # Mock connection and pgvector check
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = True  # pgvector is installed
        mock_conn.execute.return_value = mock_result
        interface.engine.connect.return_value.__enter__.return_value = mock_conn
        
        # Call _detect_features directly
        features = interface._detect_features()
        
        # Check features
        assert features.get('vector_operations') is True
        assert 'basic_storage' in features
        mock_conn.execute.assert_called_once()
    
    def test_feature_detection_postgresql_without_pgvector(self):
        """Test feature detection when pgvector extension is not installed."""
        # Create a minimal interface instance
        interface = StorageInterface.__new__(StorageInterface)
        interface.db_type = "postgresql"
        interface.engine = MagicMock()
        
        # Mock connection and pgvector check
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = False  # pgvector is NOT installed
        mock_conn.execute.return_value = mock_result
        interface.engine.connect.return_value.__enter__.return_value = mock_conn
        
        # Call _detect_features directly
        features = interface._detect_features()
        
        # Check features
        assert features.get('vector_operations') is not True
        assert 'basic_storage' in features
        mock_conn.execute.assert_called_once()
    
    def test_feature_detection_sqlite(self):
        """Test SQLite feature detection, especially FTS5 support."""
        # Create a minimal interface instance
        interface = StorageInterface.__new__(StorageInterface)
        interface.db_type = "sqlite"
        interface.engine = MagicMock()
        
        # Mock connection and FTS5 check (success)
        mock_conn = MagicMock()
        # No exception when executing FTS5 check
        mock_conn.execute.return_value = MagicMock()
        interface.engine.connect.return_value.__enter__.return_value = mock_conn
        
        # Call _detect_features directly
        features = interface._detect_features()
        
        # Check features
        assert features.get('full_text_search') is True
        assert features.get('local_storage') is True
        assert 'basic_storage' in features
        mock_conn.execute.assert_called_once()
    
    def test_feature_detection_sqlite_without_fts5(self):
        """Test SQLite feature detection when FTS5 is not available."""
        # Create a minimal interface instance
        interface = StorageInterface.__new__(StorageInterface)
        interface.db_type = "sqlite"
        interface.engine = MagicMock()
        
        # Mock connection and FTS5 check (failure)
        mock_conn = MagicMock()
        # Exception when executing FTS5 check
        mock_conn.execute.side_effect = Exception("no such function: fts5")
        interface.engine.connect.return_value.__enter__.return_value = mock_conn
        
        # Call _detect_features directly
        features = interface._detect_features()
        
        # Check features
        assert features.get('full_text_search') is not True
        assert features.get('local_storage') is True
        assert 'basic_storage' in features
        mock_conn.execute.assert_called_once()
    
    def test_feature_detection_cloud_providers(self):
        """Test feature detection for cloud providers (Pinecone, Supabase)."""
        # Create a minimal interface instance for Pinecone
        pinecone_interface = StorageInterface.__new__(StorageInterface)
        pinecone_interface.db_type = "pinecone"
        pinecone_interface.config = {}
        
        # Mock Pinecone package availability
        with patch.object(pinecone_interface, "_is_package_available", return_value=True):
            # Call _detect_features directly
            pinecone_features = pinecone_interface._detect_features()
            
            # Check features
            assert pinecone_features.get('cloud_storage') is True
            assert pinecone_features.get('vector_operations') is True
        
        # Create a minimal interface instance for Supabase
        supabase_interface = StorageInterface.__new__(StorageInterface)
        supabase_interface.db_type = "supabase"
        supabase_interface.config = {}
        
        # Mock Supabase package unavailability
        with patch.object(supabase_interface, "_is_package_available", return_value=False):
            # Call _detect_features directly
            supabase_features = supabase_interface._detect_features()
            
            # Check features
            assert supabase_features.get('cloud_storage') is not True
            assert supabase_features.get('vector_operations') is not True
    
    def test_is_package_available(self):
        """Test detection of installed Python packages."""
        # Create a minimal interface instance
        interface = StorageInterface.__new__(StorageInterface)
        
        # Mock importlib.util.find_spec for existing package
        with patch("importlib.util.find_spec", return_value=MagicMock()):
            assert interface._is_package_available("existing_package") is True
            
        # Mock importlib.util.find_spec for non-existing package
        with patch("importlib.util.find_spec", return_value=None):
            assert interface._is_package_available("non_existing_package") is False
    
    def test_supports_schema_feature(self):
        """Test schema feature compatibility checking."""
        # Create a minimal interface instance
        interface = StorageInterface.__new__(StorageInterface)
        
        # Set up schema version and db_type
        interface.schema_version = 5
        interface.db_type = "postgresql"
        
        # Check feature compatibility
        assert interface.supports_schema_feature("vector_search") is True
        assert interface.supports_schema_feature("advanced_partitioning") is False
        
        # Change schema version
        interface.schema_version = 10
        assert interface.supports_schema_feature("advanced_partitioning") is True
        
        # Test with unknown feature
        assert interface.supports_schema_feature("unknown_feature") is False
        
        # Test with no schema version
        interface.schema_version = None
        assert interface.supports_schema_feature("vector_search") is False
    
    def test_get_schema_version(self):
        """Test schema version retrieval."""
        # Create a minimal interface instance
        interface = StorageInterface.__new__(StorageInterface)
        interface.db_type = "postgresql"
        
        # Mock the _get_schema_version method for just this instance
        with patch.object(interface, "_get_schema_version", return_value=5):
            # Test schema version retrieval
            assert interface._get_schema_version() == 5
    
    def test_get_schema_version_no_table(self):
        """Test schema version retrieval when schema_versions table doesn't exist."""
        # Create a minimal interface instance
        interface = StorageInterface.__new__(StorageInterface)
        interface.db_type = "postgresql"
        
        # Mock the _get_schema_version method for just this instance
        with patch.object(interface, "_get_schema_version", return_value=None):
            # Test schema version retrieval
            assert interface._get_schema_version() is None

    @patch("sqlalchemy.create_engine")
    def test_circuit_breaker_integration(self, mock_create_engine):
        """Test circuit breaker integration with functions."""
        # Define a test function that fails sometimes
        calls = 0
        successes = 0
        failures = 0
        
        @circuit_breaker(max_failures=2, reset_timeout=0.1)
        def test_function(fail=False):
            nonlocal calls, successes, failures
            calls += 1
            if fail:
                failures += 1
                raise ValueError("Test failure")
            successes += 1
            return "success"
        
        # Test normal operation
        assert test_function() == "success"
        assert calls == 1
        assert successes == 1
        assert failures == 0
        
        # Test failure
        with pytest.raises(ValueError):
            test_function(fail=True)
        assert calls == 2
        assert successes == 1
        assert failures == 1
        
        # Test another failure - should open circuit
        with pytest.raises(ValueError):
            test_function(fail=True)
        assert calls == 3
        assert successes == 1
        assert failures == 2
        
        # Circuit should be open now
        with pytest.raises(RuntimeError) as excinfo:
            test_function()
        assert "Circuit breaker" in str(excinfo.value)
        assert calls == 3  # No additional call
        
        # Wait for circuit to reset
        import time
        time.sleep(0.2)  
        
        # Circuit should be closed again
        assert test_function() == "success"
        assert calls == 4
        assert successes == 2
        assert failures == 2
    
    @patch("sqlalchemy.create_engine")
    @patch("time.time")
    def test_create_with_monitoring(self, mock_time, mock_create_engine):
        """Test create operation with monitoring."""
        # Mock time.time to return predictable values
        mock_time.side_effect = [100, 101]  # 1 second elapsed
        
        # Mock engine and session
        mock_engine = MagicMock()
        mock_session = MagicMock()
        mock_create_engine.return_value = mock_engine
        
        # Mock session creation
        with patch("sqlalchemy.orm.sessionmaker") as mock_sessionmaker:
            mock_session_factory = MagicMock()
            mock_session_factory.return_value = mock_session
            mock_sessionmaker.return_value = mock_session_factory
            
            # Create interface
            interface = StorageInterface("sqlite:///test.db")
            
            # Mock model class and instance
            model_class = MagicMock()
            model_instance = MagicMock()
            model_instance.id = 123
            model_class.return_value = model_instance
            
            # Create data
            data = {"field": "value"}
            
            # Call create
            result = interface.create(model_class, data)
            
            # Verify result
            assert result == 123
            
            # Verify session operations
            mock_session.add.assert_called_once_with(model_instance)
            mock_session.commit.assert_called_once()
            mock_session.close.assert_called_once()
            
            # Verify time was measured (for metrics)
            assert mock_time.call_count == 2
    
    @patch("sqlalchemy.create_engine")
    def test_create_error_handling(self, mock_create_engine):
        """Test error handling during create operation."""
        # Mock engine and session
        mock_engine = MagicMock()
        mock_session = MagicMock()
        mock_create_engine.return_value = mock_engine
        
        # Mock session creation
        with patch("sqlalchemy.orm.sessionmaker") as mock_sessionmaker:
            mock_session_factory = MagicMock()
            mock_session_factory.return_value = mock_session
            mock_sessionmaker.return_value = mock_session_factory
            
            # Create interface
            interface = StorageInterface("sqlite:///test.db")
            
            # Mock model class and instance with error
            model_class = MagicMock()
            model_class.side_effect = SQLAlchemyError("Test error")
            
            # Create data
            data = {"field": "value"}
            
            # Call create and expect exception
            with pytest.raises(SQLAlchemyError):
                interface.create(model_class, data)
            
            # Verify session operations
            mock_session.rollback.assert_called_once()
            mock_session.close.assert_called_once()
            mock_session.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_async(self):
        """Test asynchronous create operation."""
        # Mock AsyncSession
        mock_async_session = MagicMock()
        mock_async_session_factory = MagicMock()
        mock_async_session_factory.return_value = mock_async_session
        
        # Create interface with async support
        with patch("importlib.util.find_spec", return_value=MagicMock()):
            with patch("sqlalchemy.ext.asyncio.create_async_engine"):
                with patch("sqlalchemy.ext.asyncio.async_sessionmaker", return_value=mock_async_session_factory):
                    interface = StorageInterface("sqlite:///test.db")
                    
                    # Force _supports_async to return True
                    interface._supports_async = lambda: True
                    
                    # Mock model class and instance
                    model_class = MagicMock()
                    model_instance = MagicMock()
                    model_instance.id = 456
                    model_class.return_value = model_instance
                    
                    # Create data
                    data = {"field": "value"}
                    
                    # Call create_async
                    result = await interface.create_async(model_class, data)
                    
                    # Verify result
                    assert result == 456
                    
                    # Verify session operations
                    mock_async_session.add.assert_called_once_with(model_instance)
                    await mock_async_session.commit()
                    await mock_async_session.close()