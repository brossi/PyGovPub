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
        
        # Create registry with properly mocked inspector
        with patch('sqlalchemy.inspect') as mock_inspect:
            inspector = MagicMock()
            inspector.get_table_names.return_value = []  # Table doesn't exist yet
            mock_inspect.return_value = inspector
            
            registry = SchemaRegistry(mock_storage)
        
            # Verify table creation
            mock_conn.execute.assert_called_once()
            # Check that the text contains the CREATE TABLE statement
            sql_text = mock_conn.execute.call_args[0][0].text
            assert "CREATE TABLE IF NOT EXISTS schema_versions" in sql_text
    
    def test_ensure_version_table_sqlite(self):
        """Test creation of schema_versions table in SQLite."""
        # Mock storage interface
        mock_storage = MagicMock()
        mock_storage.db_type = "sqlite"
        mock_conn = MagicMock()
        mock_storage.engine.connect.return_value.__enter__.return_value = mock_conn
        
        # Create registry with properly mocked inspector
        with patch('sqlalchemy.inspect') as mock_inspect:
            inspector = MagicMock()
            inspector.get_table_names.return_value = []  # Table doesn't exist yet
            mock_inspect.return_value = inspector
            
            registry = SchemaRegistry(mock_storage)
        
            # Verify table creation
            mock_conn.execute.assert_called_once()
            # Check that the text contains the CREATE TABLE statement
            sql_text = mock_conn.execute.call_args[0][0].text
            assert "CREATE TABLE IF NOT EXISTS schema_versions" in sql_text
    
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
        
    def test_is_compatible_with_api_version(self):
        """Test checking compatibility with specific API version."""
        # Mock storage interface
        mock_storage = MagicMock()
        mock_storage.db_type = "postgresql"
        mock_conn = MagicMock()
        
        # Mock result for API version required schema
        mock_result = MagicMock()
        mock_result.scalar.return_value = 3  # API version requires schema version 3
        mock_conn.execute.return_value = mock_result
        mock_storage.engine.connect.return_value.__enter__.return_value = mock_conn
        
        # Create registry
        registry = SchemaRegistry(mock_storage)
        
        # Mock current version to be 5 (> required 3)
        registry.get_current_version = MagicMock(return_value=5)
        
        # Check API compatibility
        result = registry.is_compatible_with_api_version("1.0.0")
        
        # Should be compatible (current 5 > required 3)
        assert result is True
        mock_conn.execute.assert_called_once()
        assert "api_version = :api_version" in str(mock_conn.execute.call_args[0][0])
        
        # Test incompatible case
        mock_result.scalar.return_value = 7  # API version requires schema version 7
        registry.get_current_version.return_value = 5  # Current version 5 < required 7
        
        # Reset mock to avoid counting previous call
        mock_conn.execute.reset_mock()
        
        # Check API compatibility
        result = registry.is_compatible_with_api_version("2.0.0")
        
        # Should be incompatible (current 5 < required 7)
        assert result is False
        
    def test_is_compatible_with_api_version_cloud_provider(self):
        """Test API version compatibility for cloud providers."""
        # Mock storage interface for cloud provider
        mock_storage = MagicMock()
        mock_storage.db_type = "pinecone"
        
        # Create registry
        registry = SchemaRegistry(mock_storage)
        
        # Check API compatibility
        result = registry.is_compatible_with_api_version("1.0.0")
        
        # Cloud providers are always compatible
        assert result is True
        
    def test_get_required_features(self):
        """Test getting required features for an API version."""
        # Mock storage interface
        mock_storage = MagicMock()
        mock_storage.db_type = "postgresql"
        mock_conn = MagicMock()
        
        # Mock result with components from two schema versions
        mock_result = MagicMock()
        mock_result.__iter__.return_value = [
            (json.dumps(["feature:vector_search", "table:documents"]),),
            (json.dumps(["feature:full_text_search", "table:search_index"]),)
        ]
        mock_conn.execute.return_value = mock_result
        mock_storage.engine.connect.return_value.__enter__.return_value = mock_conn
        
        # Create registry
        registry = SchemaRegistry(mock_storage)
        
        # Get required features
        features = registry.get_required_features("1.0.0")
        
        # Verify extracted features
        assert isinstance(features, set)
        assert len(features) == 2
        assert "vector_search" in features
        assert "full_text_search" in features
        
    def test_get_required_features_cloud_provider(self):
        """Test getting required features for cloud providers."""
        # Mock storage interface for cloud provider
        mock_storage = MagicMock()
        mock_storage.db_type = "pinecone"
        
        # Create registry
        registry = SchemaRegistry(mock_storage)
        
        # Get required features
        features = registry.get_required_features("1.0.0")
        
        # Cloud providers don't use features registry
        assert isinstance(features, set)
        assert len(features) == 0
        
    def test_verify_migrations(self):
        """Test verification of migration sequence."""
        # Mock storage interface
        mock_storage = MagicMock()
        mock_storage.db_type = "postgresql"
        mock_conn = MagicMock()
        
        # Mock result with sequential migrations
        mock_result1 = MagicMock()
        mock_result1.__iter__.return_value = [
            (1, "2023-01-01", "First migration", "abc123"),
            (2, "2023-01-02", "Second migration", "def456"),
            (3, "2023-01-03", "Third migration", "ghi789")
        ]
        
        mock_conn.execute.return_value = mock_result1
        mock_storage.engine.connect.return_value.__enter__.return_value = mock_conn
        
        # Create registry
        registry = SchemaRegistry(mock_storage)
        
        # Reset mock to avoid counting initialization calls
        mock_conn.execute.reset_mock()
        mock_conn.execute.return_value = mock_result1
        
        # Verify migrations
        valid, problems = registry.verify_migrations()
        
        # Should be valid (no gaps)
        assert valid is True
        assert len(problems) == 0
        mock_conn.execute.assert_called_once()
        
        # Now test with non-sequential migrations
        mock_result2 = MagicMock()
        mock_result2.__iter__.return_value = [
            (1, "2023-01-01", "First migration", "abc123"),
            (2, "2023-01-02", "Second migration", "def456"),
            (4, "2023-01-04", "Fourth migration", "jkl012")  # Gap at 3
        ]
        
        mock_conn.execute.reset_mock()
        mock_conn.execute.return_value = mock_result2
        
        # Verify migrations
        valid, problems = registry.verify_migrations()
        
        # Should be invalid (gap at version 3)
        assert valid is False
        assert len(problems) == 1
        assert problems[0]["version"] == 4
        assert "expected 3" in problems[0]["issue"]
        mock_conn.execute.assert_called_once()
        
    def test_verify_migrations_cloud_provider(self):
        """Test migration verification for cloud providers."""
        # Mock storage interface for cloud provider
        mock_storage = MagicMock()
        mock_storage.db_type = "pinecone"
        
        # Create registry
        registry = SchemaRegistry(mock_storage)
        
        # Verify migrations
        valid, problems = registry.verify_migrations()
        
        # Cloud providers always return valid
        assert valid is True
        assert len(problems) == 0