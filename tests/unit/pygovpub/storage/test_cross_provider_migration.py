"""
Tests for cross-provider data migration capabilities.

This module tests the ability to migrate data between different storage
providers, particularly between SQL databases and LanceDB for vector operations.
"""

import json
import uuid
import pytest
from unittest.mock import patch, MagicMock, call

import pyarrow as pa
import pandas as pd
import numpy as np

from pygovpub.storage.interface import StorageInterface
from pygovpub.storage.providers.lancedb_provider import LanceDBProvider


class TestCrossProviderMigration:
    """Test suite for cross-provider data migration capabilities."""
    
    @patch("pygovpub.storage.interface.create_engine")
    @patch("pygovpub.storage.providers.lancedb_provider.lancedb")
    def test_migrate_from_sql_to_lancedb(self, mock_lancedb, mock_create_engine):
        """Test migrating data from SQL database to LanceDB."""
        # Mock SQL database
        mock_engine = MagicMock()
        mock_connection = MagicMock()
        mock_result = MagicMock()
        mock_engine.connect.return_value.__enter__.return_value = mock_connection
        mock_connection.execute.return_value = mock_result
        mock_create_engine.return_value = mock_engine
        
        # Mock result data
        mock_data = [
            {"id": "doc1", "content": "Test document 1", "metadata": json.dumps({"source": "test"})},
            {"id": "doc2", "content": "Test document 2", "metadata": json.dumps({"source": "test"})}
        ]
        mock_result.__iter__.return_value = mock_data
        
        # Mock LanceDB
        mock_db = MagicMock()
        mock_table = MagicMock()
        mock_db.table_names.return_value = []
        mock_db.create_table.return_value = mock_table
        mock_lancedb.connect.return_value = mock_db
        
        # Create storage interface with SQL backend
        sql_interface = StorageInterface("sqlite:///test.db")
        
        # Create LanceDB provider
        lancedb_provider = LanceDBProvider(uri="/path/to/lancedb")
        
        # Mock model class
        class TestModel:
            __tablename__ = "documents"
        
        # Perform migration
        with patch.object(sql_interface, "_get_sql_connection") as mock_get_connection:
            mock_get_connection.return_value = mock_connection
            
            # Call migration method on interface
            migrated = sql_interface.migrate_to_provider(
                "documents", 
                lancedb_provider, 
                TestModel,
                embedding_field="embedding"
            )
            
            # Verify SQL query executed
            mock_connection.execute.assert_called_once()
            assert "SELECT" in str(mock_connection.execute.call_args[0][0])
            assert "documents" in str(mock_connection.execute.call_args[0][0])
            
            # Verify data added to LanceDB
            assert mock_table.add.called
            assert migrated == 2  # Two records migrated
    
    @patch("pygovpub.storage.interface.create_engine")
    @patch("pygovpub.storage.providers.lancedb_provider.lancedb")
    def test_migrate_with_embedding_generation(self, mock_lancedb, mock_create_engine):
        """Test migration with automatic embedding generation."""
        # Mock SQL database
        mock_engine = MagicMock()
        mock_connection = MagicMock()
        mock_result = MagicMock()
        mock_engine.connect.return_value.__enter__.return_value = mock_connection
        mock_connection.execute.return_value = mock_result
        mock_create_engine.return_value = mock_engine
        
        # Mock result data without embeddings
        mock_data = [
            {"id": "doc1", "content": "Test document 1", "metadata": json.dumps({"source": "test"})},
            {"id": "doc2", "content": "Test document 2", "metadata": json.dumps({"source": "test"})}
        ]
        mock_result.__iter__.return_value = mock_data
        
        # Mock LanceDB
        mock_db = MagicMock()
        mock_table = MagicMock()
        mock_db.table_names.return_value = []
        mock_db.create_table.return_value = mock_table
        mock_lancedb.connect.return_value = mock_db
        
        # Create storage interface with SQL backend
        sql_interface = StorageInterface("sqlite:///test.db")
        
        # Create LanceDB provider
        lancedb_provider = LanceDBProvider(uri="/path/to/lancedb")
        
        # Mock embedding generation function
        def mock_generate_embedding(text):
            # Return random vector of dimension 384
            return np.random.rand(384).tolist()
        
        # Mock model class
        class TestModel:
            __tablename__ = "documents"
        
        # Perform migration with embedding generation
        with patch.object(sql_interface, "_get_sql_connection") as mock_get_connection:
            mock_get_connection.return_value = mock_connection
            
            # Call migration method on interface with embedding generator
            migrated = sql_interface.migrate_to_provider(
                "documents", 
                lancedb_provider, 
                TestModel,
                embedding_field="embedding",
                embedding_generator=mock_generate_embedding,
                content_field="content"
            )
            
            # Verify data added to LanceDB with embeddings
            add_calls = mock_table.add.call_args_list
            assert len(add_calls) == 1  # Batch add
            
            # Get the records that were added
            added_records = add_calls[0][0][0]
            
            # Verify embeddings were generated
            for record in added_records:
                assert "embedding" in record
                assert len(record["embedding"]) == 384
            
            assert migrated == 2  # Two records migrated
    
    @patch("pygovpub.storage.providers.lancedb_provider.lancedb")
    def test_migrate_between_lancedb_instances(self, mock_lancedb):
        """Test migrating data between two LanceDB instances."""
        # Mock source LanceDB
        mock_source_db = MagicMock()
        mock_source_table = MagicMock()
        mock_source_search = MagicMock()
        mock_source_limit = MagicMock()
        
        # Mock pandas result
        mock_df = pd.DataFrame({
            "id": ["doc1", "doc2"],
            "embedding": [np.random.rand(3).tolist(), np.random.rand(3).tolist()],
            "content": ["Test document 1", "Test document 2"],
            "metadata": ['{"source":"test"}', '{"source":"test"}']
        })
        
        # Set up chain for source
        mock_source_table.search.return_value = mock_source_search
        mock_source_search.limit.return_value = mock_source_limit
        mock_source_limit.to_pandas.return_value = mock_df
        mock_source_db.table_names.return_value = ["documents"]
        mock_source_db.open_table.return_value = mock_source_table
        
        # Mock target LanceDB
        mock_target_db = MagicMock()
        mock_target_table = MagicMock()
        mock_target_db.table_names.return_value = []
        mock_target_db.create_table.return_value = mock_target_table
        
        # Set up connection sequence
        mock_lancedb.connect.side_effect = [mock_source_db, mock_target_db]
        
        # Create LanceDB providers
        source_provider = LanceDBProvider(uri="/path/to/source")
        target_provider = LanceDBProvider(uri="/path/to/target")
        
        # Mock model class
        class TestModel:
            __tablename__ = "documents"
        
        # Perform migration between LanceDB instances
        migrated = source_provider.migrate_to_provider(
            "documents",
            target_provider,
            TestModel
        )
        
        # Verify source queried
        mock_source_table.search.assert_called_once()
        mock_source_search.limit.assert_called_once()
        
        # Verify data added to target
        mock_target_table.add.assert_called_once()
        
        # Should have migrated 2 documents
        assert migrated == 2
    
    @patch("pygovpub.storage.interface.create_engine")
    @patch("pygovpub.storage.providers.lancedb_provider.lancedb")
    def test_migrate_with_schema_version(self, mock_lancedb, mock_create_engine):
        """Test migration with schema version application."""
        # Mock SQL database
        mock_engine = MagicMock()
        mock_connection = MagicMock()
        mock_result = MagicMock()
        mock_engine.connect.return_value.__enter__.return_value = mock_connection
        mock_connection.execute.return_value = mock_result
        mock_create_engine.return_value = mock_engine
        
        # Mock result data
        mock_data = [
            {"id": "doc1", "content": "Test document 1", "metadata": json.dumps({"source": "test"})},
            {"id": "doc2", "content": "Test document 2", "metadata": json.dumps({"source": "test"})}
        ]
        mock_result.__iter__.return_value = mock_data
        
        # Mock LanceDB
        mock_db = MagicMock()
        mock_table = MagicMock()
        mock_db.table_names.return_value = []
        mock_db.create_table.return_value = mock_table
        mock_lancedb.connect.return_value = mock_db
        
        # Mock schema registry
        mock_registry = MagicMock()
        mock_registry.get_schema_version.return_value = {
            "version": "1.0.0",
            "fields": [
                {"name": "id", "type": "string"},
                {"name": "embedding", "type": "vector", "dimension": 384},
                {"name": "content", "type": "string"},
                {"name": "metadata", "type": "json"},
            ]
        }
        
        # Create storage interface with SQL backend
        sql_interface = StorageInterface("sqlite:///test.db")
        
        # Create LanceDB provider with schema registry
        lancedb_provider = LanceDBProvider(
            uri="/path/to/lancedb",
            schema_registry=mock_registry
        )
        
        # Mock model class
        class TestModel:
            __tablename__ = "documents"
        
        # Perform migration with schema version
        with patch.object(sql_interface, "_get_sql_connection") as mock_get_connection:
            mock_get_connection.return_value = mock_connection
            
            # Call migration method with schema version
            migrated = sql_interface.migrate_to_provider(
                "documents", 
                lancedb_provider, 
                TestModel,
                schema_version="1.0.0"
            )
            
            # Verify schema version was retrieved
            mock_registry.get_schema_version.assert_called_once_with("1.0.0")
            
            # Verify table created with schema
            assert mock_db.create_table.called
            
            assert migrated == 2  # Two records migrated