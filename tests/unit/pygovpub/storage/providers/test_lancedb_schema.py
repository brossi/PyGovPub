"""
Tests for the LanceDB schema compatibility layer.

This module tests the schema compatibility layer for LanceDB that ensures
the provider works correctly with the schema registry.
"""

import pytest
import pyarrow as pa
from unittest.mock import patch, MagicMock

from pygovpub.storage.providers.lancedb_provider import LanceDBProvider
from pygovpub.storage.providers.lancedb_schema import LanceDBSchemaAdapter
from pygovpub.storage.schema_registry import SchemaRegistry


class TestLanceDBSchemaAdapter:
    """Test suite for the LanceDBSchemaAdapter class."""
    
    def test_init(self):
        """Test initialization of the schema adapter."""
        provider = MagicMock(spec=LanceDBProvider)
        registry = MagicMock(spec=SchemaRegistry)
        
        adapter = LanceDBSchemaAdapter(provider, registry)
        
        assert adapter.provider == provider
        assert adapter.registry == registry
    
    def test_get_table_schema(self):
        """Test retrieving table schema from LanceDB."""
        provider = MagicMock(spec=LanceDBProvider)
        registry = MagicMock(spec=SchemaRegistry)
        
        # Mock table and schema
        mock_table = MagicMock()
        mock_schema = pa.schema([
            ("id", pa.string()),
            ("embedding", pa.list_(pa.float32(), 384)),
            ("content", pa.string()),
            ("metadata", pa.string()),
        ])
        mock_table.schema = mock_schema
        
        # Set up provider mock
        provider._get_or_create_table.return_value = mock_table
        
        # Create adapter
        adapter = LanceDBSchemaAdapter(provider, registry)
        
        # Get schema
        schema = adapter.get_table_schema("test_table")
        
        # Verify
        provider._get_or_create_table.assert_called_once_with("test_table")
        assert schema == mock_schema
    
    def test_apply_schema_version(self):
        """Test applying a schema version to a LanceDB table."""
        provider = MagicMock(spec=LanceDBProvider)
        registry = MagicMock(spec=SchemaRegistry)
        
        # Mock table
        mock_table = MagicMock()
        
        # Set up provider mock
        provider._get_or_create_table.return_value = mock_table
        
        # Mock registry schema version
        mock_schema_version = {
            "version": "1.0.0",
            "fields": [
                {"name": "id", "type": "string"},
                {"name": "embedding", "type": "vector", "dimension": 384},
                {"name": "content", "type": "string"},
                {"name": "metadata", "type": "json"},
                {"name": "new_field", "type": "string"},
            ]
        }
        registry.get_schema_version.return_value = mock_schema_version
        
        # Create adapter
        adapter = LanceDBSchemaAdapter(provider, registry)
        
        # Apply schema version
        result = adapter.apply_schema_version("test_table", "1.0.0")
        
        # Verify
        registry.get_schema_version.assert_called_once_with("1.0.0")
        provider._get_or_create_table.assert_called_once()
        assert result is True
    
    def test_convert_schema_version_to_arrow(self):
        """Test converting schema version to PyArrow schema."""
        provider = MagicMock(spec=LanceDBProvider)
        registry = MagicMock(spec=SchemaRegistry)
        
        # Create adapter
        adapter = LanceDBSchemaAdapter(provider, registry)
        
        # Test schema version
        schema_version = {
            "version": "1.0.0",
            "fields": [
                {"name": "id", "type": "string"},
                {"name": "embedding", "type": "vector", "dimension": 384},
                {"name": "content", "type": "string"},
                {"name": "metadata", "type": "json"},
                {"name": "integer_field", "type": "integer"},
                {"name": "float_field", "type": "float"},
                {"name": "boolean_field", "type": "boolean"},
                {"name": "timestamp_field", "type": "timestamp"},
            ]
        }
        
        # Convert to Arrow schema
        arrow_schema = adapter._convert_schema_version_to_arrow(schema_version)
        
        # Verify
        assert isinstance(arrow_schema, pa.Schema)
        assert len(arrow_schema) == 8
        assert arrow_schema.field("id").type == pa.string()
        assert arrow_schema.field("embedding").type == pa.list_(pa.float32(), 384)
        assert arrow_schema.field("content").type == pa.string()
        assert arrow_schema.field("metadata").type == pa.string()  # JSON is stored as string
        assert arrow_schema.field("integer_field").type == pa.int64()
        assert arrow_schema.field("float_field").type == pa.float64()
        assert arrow_schema.field("boolean_field").type == pa.bool_()
        assert arrow_schema.field("timestamp_field").type == pa.timestamp("us")
    
    def test_check_schema_compatibility(self):
        """Test checking compatibility between schemas."""
        provider = MagicMock(spec=LanceDBProvider)
        registry = MagicMock(spec=SchemaRegistry)
        
        # Create adapter
        adapter = LanceDBSchemaAdapter(provider, registry)
        
        # Mock current schema
        current_schema = pa.schema([
            ("id", pa.string()),
            ("embedding", pa.list_(pa.float32(), 384)),
            ("content", pa.string()),
            ("metadata", pa.string()),
        ])
        
        # Test target schema (compatible - adds a field)
        target_schema = pa.schema([
            ("id", pa.string()),
            ("embedding", pa.list_(pa.float32(), 384)),
            ("content", pa.string()),
            ("metadata", pa.string()),
            ("new_field", pa.string()),
        ])
        
        # Check compatibility
        is_compatible, _ = adapter._check_schema_compatibility(current_schema, target_schema)
        
        # Verify
        assert is_compatible is True
        
        # Test incompatible schema (changes field type)
        incompatible_schema = pa.schema([
            ("id", pa.string()),
            ("embedding", pa.list_(pa.float32(), 384)),
            ("content", pa.int64()),  # Changed from string to int
            ("metadata", pa.string()),
        ])
        
        # Check compatibility
        is_compatible, changes = adapter._check_schema_compatibility(current_schema, incompatible_schema)
        
        # Verify
        assert is_compatible is False
        assert "content" in changes
    
    @patch("pygovpub.storage.providers.lancedb_schema.pa")
    def test_create_schema_migration(self, mock_pa):
        """Test creating a schema migration plan."""
        provider = MagicMock(spec=LanceDBProvider)
        registry = MagicMock(spec=SchemaRegistry)
        
        # Create adapter
        adapter = LanceDBSchemaAdapter(provider, registry)
        
        # Mock current and target schemas
        current_schema = MagicMock()
        current_schema.names = ["id", "embedding", "content", "metadata"]
        
        target_schema = MagicMock()
        target_schema.names = ["id", "embedding", "content", "metadata", "new_field"]
        
        # Get field mock
        field_mock = MagicMock()
        target_schema.field.return_value = field_mock
        
        # Create migration plan
        migration_plan = adapter._create_schema_migration(current_schema, target_schema)
        
        # Verify
        assert "add_fields" in migration_plan
        assert len(migration_plan["add_fields"]) == 1
        assert migration_plan["add_fields"][0] == field_mock
        
        # Test removing fields (unsupported in LanceDB)
        current_schema.names = ["id", "embedding", "content", "metadata", "old_field"]
        target_schema.names = ["id", "embedding", "content", "metadata"]
        
        # Mock get field on current schema
        current_schema.field.return_value = MagicMock()
        
        # Create migration plan for removing fields
        migration_plan = adapter._create_schema_migration(current_schema, target_schema)
        
        # Verify - should note unsupported operation
        assert "unsupported_operations" in migration_plan
        assert "remove_fields" in migration_plan["unsupported_operations"]