"""
Tests for the schema registry module.

This module tests the schema versioning system that tracks 
database schema versions across different database backends.
"""

import json
import pytest
from unittest.mock import patch, MagicMock, call

from pygovpub.storage.schema_registry import SchemaRegistry
from sqlalchemy.exc import SQLAlchemyError


class TestSchemaRegistry:
    """Test suite for the SchemaRegistry class."""
    
    def test_ensure_version_table_postgresql(self):
        """Test creation of schema_versions table in PostgreSQL."""
        # Mock storage interface
        mock_storage = MagicMock()
        mock_storage.db_type = "postgresql"
        mock_conn = MagicMock()
        mock_storage.engine.connect.return_value.__enter__.return_value = mock_conn
        
        # Create registry
        registry = SchemaRegistry(mock_storage)
        
        # Verify table creation
        mock_conn.execute.assert_called_once()
        assert "CREATE TABLE IF NOT EXISTS schema_versions" in str(mock_conn.execute.call_args)
    
    def test_ensure_version_table_sqlite(self):
        """Test creation of schema_versions table in SQLite."""
        # Mock storage interface
        mock_storage = MagicMock()
        mock_storage.db_type = "sqlite"
        mock_conn = MagicMock()
        mock_storage.engine.connect.return_value.__enter__.return_value = mock_conn
        
        # Create registry
        registry = SchemaRegistry(mock_storage)
        
        # Verify table creation
        mock_conn.execute.assert_called_once()
        assert "CREATE TABLE IF NOT EXISTS schema_versions" in str(mock_conn.execute.call_args)
    
    def test_ensure_version_table_cloud_provider(self):
        """Test that cloud providers skip schema_versions table creation."""
        # Mock storage interface for Pinecone
        mock_storage = MagicMock()
        mock_storage.db_type = "pinecone"
        mock_conn = MagicMock()
        mock_storage.engine.connect.return_value.__enter__.return_value = mock_conn
        
        # Create registry
        registry = SchemaRegistry(mock_storage)
        
        # Verify no table creation attempted
        mock_conn.execute.assert_not_called()
    
    def test_get_current_version(self):
        """Test retrieval of current schema version."""
        # Mock storage interface
        mock_storage = MagicMock()
        mock_storage.db_type = "postgresql"
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = 5  # Current version is 5
        mock_conn.execute.return_value = mock_result
        mock_storage.engine.connect.return_value.__enter__.return_value = mock_conn
        
        # Mock inspector
        mock_inspector = MagicMock()
        mock_inspector.get_table_names.return_value = ["schema_versions"]
        mock_storage.engine.connect.return_value.__enter__.return_value = mock_conn
        
        with patch('sqlalchemy.inspect', return_value=mock_inspector):
            # Create registry
            registry = SchemaRegistry(mock_storage)
            
            # Get current version
            version = registry.get_current_version()
            
            # Verify version
            assert version == 5
            assert mock_conn.execute.call_count == 2  # Once for table creation, once for version query
    
    def test_get_current_version_no_table(self):
        """Test version retrieval when schema_versions table doesn't exist."""
        # Mock storage interface
        mock_storage = MagicMock()
        mock_storage.db_type = "postgresql"
        mock_conn = MagicMock()
        mock_storage.engine.connect.return_value.__enter__.return_value = mock_conn
        
        # Mock inspector to indicate table doesn't exist
        mock_inspector = MagicMock()
        mock_inspector.get_table_names.return_value = []  # No schema_versions table
        
        with patch('sqlalchemy.inspect', return_value=mock_inspector):
            # Create registry
            registry = SchemaRegistry(mock_storage)
            
            # Reset mock to avoid counting the call during initialization
            mock_conn.execute.reset_mock()
            
            # Get current version
            version = registry.get_current_version()
            
            # Verify version is None
            assert version is None
            # No execute call since table doesn't exist
            mock_conn.execute.assert_not_called()
    
    def test_register_version(self):
        """Test registration of a new schema version."""
        # Mock storage interface
        mock_storage = MagicMock()
        mock_storage.db_type = "postgresql"
        mock_conn = MagicMock()
        mock_storage.engine.connect.return_value.__enter__.return_value = mock_conn
        
        # Create registry
        registry = SchemaRegistry(mock_storage)
        
        # Reset mock to avoid counting the call during initialization
        mock_conn.execute.reset_mock()
        
        # Register a new version
        components = ["table1", "table2"]
        result = registry.register_version(3, "Added table1 and table2", components)
        
        # Verify registration
        assert result is True
        mock_conn.execute.assert_called_once()
        
        # Check that parameters were correctly passed
        call_args = mock_conn.execute.call_args[0][1]
        assert call_args["version"] == 3
        assert call_args["description"] == "Added table1 and table2"
        assert json.loads(call_args["components"]) == components
        assert call_args["db_type"] == "postgresql"
    
    def test_register_version_cloud_provider(self):
        """Test version registration for cloud providers (should be no-op)."""
        # Mock storage interface for Pinecone
        mock_storage = MagicMock()
        mock_storage.db_type = "pinecone"
        mock_conn = MagicMock()
        mock_storage.engine.connect.return_value.__enter__.return_value = mock_conn
        
        # Create registry
        registry = SchemaRegistry(mock_storage)
        
        # Reset mock to avoid counting the call during initialization
        mock_conn.execute.reset_mock()
        
        # Register a new version
        result = registry.register_version(3, "Test version", ["component1"])
        
        # Verify registration was no-op
        assert result is False
        mock_conn.execute.assert_not_called()
    
    def test_register_version_error(self):
        """Test error handling during version registration."""
        # Mock storage interface
        mock_storage = MagicMock()
        mock_storage.db_type = "postgresql"
        mock_conn = MagicMock()
        # Simulate error during execution
        mock_conn.execute.side_effect = SQLAlchemyError("Test error")
        mock_storage.engine.connect.return_value.__enter__.return_value = mock_conn
        
        # Create registry with error during initialization
        with patch('sqlalchemy.inspect'):
            registry = SchemaRegistry(mock_storage)
        
        # Reset mock to avoid counting the call during initialization
        mock_conn.execute.reset_mock()
        mock_conn.execute.side_effect = SQLAlchemyError("Test error")
        
        # Register a new version
        result = registry.register_version(3, "Test version", ["component1"])
        
        # Verify registration failed
        assert result is False
        mock_conn.execute.assert_called_once()
    
    def test_supports_feature(self):
        """Test feature compatibility checking based on schema version."""
        # Mock storage interface
        mock_storage = MagicMock()
        mock_storage.db_type = "postgresql"
        
        # Create registry
        registry = SchemaRegistry(mock_storage)
        
        # Mock get_current_version
        registry.get_current_version = MagicMock(return_value=5)
        
        # Check feature compatibility
        assert registry.supports_feature("vector_search") is True
        assert registry.supports_feature("advanced_partitioning") is False
        
        # Change version
        registry.get_current_version.return_value = 10
        assert registry.supports_feature("advanced_partitioning") is True
        
        # Check unknown feature
        assert registry.supports_feature("unknown_feature") is False
        
        # Check with no version
        registry.get_current_version.return_value = None
        assert registry.supports_feature("vector_search") is False
    
    def test_get_version_history(self):
        """Test retrieval of version history."""
        # Mock storage interface
        mock_storage = MagicMock()
        mock_storage.db_type = "postgresql"
        mock_conn = MagicMock()
        
        # Mock result with version history
        mock_result = MagicMock()
        version_history = [
            (1, "2023-01-01 12:00:00", "Initial schema", json.dumps(["table1"])),
            (2, "2023-01-02 12:00:00", "Added table2", json.dumps(["table2"])),
            (3, "2023-01-03 12:00:00", "Added indexes", json.dumps(["index1", "index2"]))
        ]
        mock_result.__iter__.return_value = iter(version_history)
        mock_conn.execute.return_value = mock_result
        mock_storage.engine.connect.return_value.__enter__.return_value = mock_conn
        
        # Create registry
        registry = SchemaRegistry(mock_storage)
        
        # Reset mock to avoid counting the call during initialization
        mock_conn.execute.reset_mock()
        
        # Get version history
        history = registry.get_version_history()
        
        # Verify history
        assert len(history) == 3
        assert history[0]["version"] == 1
        assert history[0]["description"] == "Initial schema"
        assert history[0]["components"] == ["table1"]
        assert history[2]["version"] == 3
        assert history[2]["components"] == ["index1", "index2"]
        mock_conn.execute.assert_called_once()
    
    def test_get_version_history_cloud_provider(self):
        """Test version history for cloud providers (should return empty list)."""
        # Mock storage interface for Pinecone
        mock_storage = MagicMock()
        mock_storage.db_type = "pinecone"
        mock_conn = MagicMock()
        mock_storage.engine.connect.return_value.__enter__.return_value = mock_conn
        
        # Create registry
        registry = SchemaRegistry(mock_storage)
        
        # Reset mock to avoid counting the call during initialization
        mock_conn.execute.reset_mock()
        
        # Get version history
        history = registry.get_version_history()
        
        # Verify empty history
        assert history == []
        mock_conn.execute.assert_not_called()
    
    def test_get_version_history_error(self):
        """Test error handling during version history retrieval."""
        # Mock storage interface
        mock_storage = MagicMock()
        mock_storage.db_type = "postgresql"
        mock_conn = MagicMock()
        # Simulate error during execution
        mock_conn.execute.side_effect = SQLAlchemyError("Test error")
        mock_storage.engine.connect.return_value.__enter__.return_value = mock_conn
        
        # Create registry with error during initialization
        with patch('sqlalchemy.inspect'):
            registry = SchemaRegistry(mock_storage)
        
        # Reset mock to avoid counting the call during initialization
        mock_conn.execute.reset_mock()
        mock_conn.execute.side_effect = SQLAlchemyError("Test error")
        
        # Get version history
        history = registry.get_version_history()
        
        # Verify empty history due to error
        assert history == []
        mock_conn.execute.assert_called_once()
    
    def test_get_feature_compatibility(self):
        """Test retrieval of all feature compatibility status."""
        # Mock storage interface
        mock_storage = MagicMock()
        mock_storage.db_type = "postgresql"
        
        # Create registry
        registry = SchemaRegistry(mock_storage)
        
        # Mock supports_feature
        registry.supports_feature = lambda feature: feature in ["vector_search", "full_text_search"]
        
        # Get feature compatibility
        compatibility = registry.get_feature_compatibility()
        
        # Verify compatibility
        assert compatibility["vector_search"] is True
        assert compatibility["full_text_search"] is True
        assert compatibility["advanced_partitioning"] is False
        assert compatibility["document_versioning"] is False
        assert compatibility["database_events"] is False
    
    def test_get_feature_compatibility_cloud_provider(self):
        """Test feature compatibility for cloud providers."""
        # Mock storage interface for Pinecone
        mock_storage = MagicMock()
        mock_storage.db_type = "pinecone"
        mock_storage.features = {
            "cloud_storage": True,
            "vector_operations": True
        }
        
        # Create registry
        registry = SchemaRegistry(mock_storage)
        
        # Get feature compatibility
        compatibility = registry.get_feature_compatibility()
        
        # Verify compatibility based on storage features
        assert compatibility["vector_search"] is True  # Should be True for Pinecone
        assert compatibility["database_events"] is False  # Not in features