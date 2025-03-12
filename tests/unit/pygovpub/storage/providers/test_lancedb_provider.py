"""
Tests for the LanceDB provider module.

This module tests the LanceDB integration for vector search and storage.
"""

import json
import tempfile
import uuid
from pathlib import Path
from unittest.mock import patch, MagicMock, call

import pytest
import pyarrow as pa
import numpy as np

from pygovpub.storage.providers.lancedb_provider import LanceDBProvider


class TestLanceDBProvider:
    """Test suite for the LanceDBProvider class."""
    
    def test_init_with_uri(self):
        """Test initialization with a URI."""
        with patch('lancedb.connect') as mock_connect:
            mock_db = MagicMock()
            mock_connect.return_value = mock_db
            
            # Create provider with URI
            provider = LanceDBProvider(uri="/path/to/db")
            
            # Verify connection
            mock_connect.assert_called_once_with("/path/to/db")
            assert provider.db == mock_db
            assert provider.vector_dim == 384  # Default
    
    def test_init_without_uri(self):
        """Test initialization without a URI (should use default path)."""
        with patch('lancedb.connect') as mock_connect:
            with patch('os.makedirs') as mock_makedirs:
                mock_db = MagicMock()
                mock_connect.return_value = mock_db
                
                # Create provider without URI
                provider = LanceDBProvider()
                
                # Verify directory creation
                mock_makedirs.assert_called_once()
                # Verify connection to a path in the default directory
                assert mock_connect.call_count == 1
                assert "pygovpub" in str(mock_connect.call_args)
                assert provider.db == mock_db
    
    def test_init_with_custom_vector_dim(self):
        """Test initialization with custom vector dimension."""
        with patch('lancedb.connect') as mock_connect:
            mock_db = MagicMock()
            mock_connect.return_value = mock_db
            
            # Create provider with custom vector dimension
            provider = LanceDBProvider(uri="/path/to/db", vector_dim=768)
            
            # Verify dimension was set
            assert provider.vector_dim == 768
    
    def test_model_to_dict_pydantic(self):
        """Test conversion of Pydantic model to dict."""
        with patch('lancedb.connect') as mock_connect:
            mock_connect.return_value = MagicMock()
            provider = LanceDBProvider(uri="/path/to/db")
            
            # Create a mock Pydantic model with model_dump method
            mock_model = MagicMock()
            mock_model.model_dump.return_value = {"field": "value"}
            
            # Convert to dict
            result = provider._model_to_dict(mock_model)
            
            # Verify result
            assert result == {"field": "value"}
            mock_model.model_dump.assert_called_once()
    
    def test_model_to_dict_sqlalchemy(self):
        """Test conversion of SQLAlchemy model to dict."""
        with patch('lancedb.connect') as mock_connect:
            mock_connect.return_value = MagicMock()
            provider = LanceDBProvider(uri="/path/to/db")
            
            # Create a mock SQLAlchemy model with __dict__
            mock_model = MagicMock()
            mock_model.__dict__ = {"_sa_instance_state": "ignored", "field": "value"}
            
            # Prevent model_dump from being called
            del mock_model.model_dump
            
            # Convert to dict
            result = provider._model_to_dict(mock_model)
            
            # Verify result (should ignore SQLAlchemy internal attributes)
            assert result == {"field": "value"}
            assert "_sa_instance_state" not in result
    
    def test_model_to_dict_dict(self):
        """Test conversion of dict to dict (no-op)."""
        with patch('lancedb.connect') as mock_connect:
            mock_connect.return_value = MagicMock()
            provider = LanceDBProvider(uri="/path/to/db")
            
            # Convert dict to dict
            data = {"field": "value"}
            result = provider._model_to_dict(data)
            
            # Verify result is the same dict
            assert result == data
            assert result is data  # Should be the same object
    
    def test_get_or_create_table_existing(self):
        """Test getting an existing table."""
        with patch('lancedb.connect') as mock_connect:
            mock_db = MagicMock()
            mock_db.table_names.return_value = ["existing_table"]
            mock_table = MagicMock()
            mock_db.open_table.return_value = mock_table
            mock_connect.return_value = mock_db
            
            # Create provider
            provider = LanceDBProvider(uri="/path/to/db")
            
            # Get existing table
            result = provider._get_or_create_table("existing_table")
            
            # Verify table opened
            mock_db.open_table.assert_called_once_with("existing_table")
            mock_db.create_table.assert_not_called()
            assert result == mock_table
    
    def test_get_or_create_table_new(self):
        """Test creating a new table."""
        with patch('lancedb.connect') as mock_connect:
            mock_db = MagicMock()
            mock_db.table_names.return_value = []  # No existing tables
            mock_table = MagicMock()
            mock_db.create_table.return_value = mock_table
            mock_connect.return_value = mock_db
            
            # Create provider
            provider = LanceDBProvider(uri="/path/to/db")
            
            # Create new table
            result = provider._get_or_create_table("new_table")
            
            # Verify table created
            mock_db.open_table.assert_not_called()
            mock_db.create_table.assert_called_once()
            assert result == mock_table
            
            # Verify empty data was created
            create_args = mock_db.create_table.call_args[0]
            assert create_args[0] == "new_table"  # Table name
            assert isinstance(create_args[1], pa.Table)  # PyArrow table
    
    def test_get_or_create_table_with_vector_index(self):
        """Test creating a table with vector index."""
        with patch('lancedb.connect') as mock_connect:
            mock_db = MagicMock()
            mock_db.table_names.return_value = []  # No existing tables
            mock_table = MagicMock()
            mock_db.create_table.return_value = mock_table
            mock_connect.return_value = mock_db
            
            # Create provider with vector index enabled
            provider = LanceDBProvider(uri="/path/to/db", create_vector_index=True)
            
            # Create new table
            result = provider._get_or_create_table("new_table")
            
            # Verify table created with index
            mock_db.create_table.assert_called_once()
            mock_table.create_index.assert_called_once()
            assert "embedding" in str(mock_table.create_index.call_args)
    
    def test_check_table_has_vector_index(self):
        """Test checking if a table has a vector index."""
        with patch('lancedb.connect') as mock_connect:
            mock_db = MagicMock()
            mock_connect.return_value = mock_db
            
            # Create provider
            provider = LanceDBProvider(uri="/path/to/db")
            
            # Mock table with index
            mock_table = MagicMock()
            mock_table.describe_indices.return_value = [
                {"column_names": ["embedding"], "index_type": "IVF_PQ"}
            ]
            
            # Check for index
            has_index = provider._check_table_has_vector_index(mock_table)
            
            # Verify check
            assert has_index is True
            mock_table.describe_indices.assert_called_once()
    
    def test_check_table_without_vector_index(self):
        """Test checking a table without a vector index."""
        with patch('lancedb.connect') as mock_connect:
            mock_db = MagicMock()
            mock_connect.return_value = mock_db
            
            # Create provider
            provider = LanceDBProvider(uri="/path/to/db")
            
            # Mock table without index
            mock_table = MagicMock()
            mock_table.describe_indices.return_value = []
            
            # Check for index
            has_index = provider._check_table_has_vector_index(mock_table)
            
            # Verify check
            assert has_index is False
            mock_table.describe_indices.assert_called_once()
    
    def test_convert_model_to_arrow(self):
        """Test conversion of model data to Arrow format."""
        with patch('lancedb.connect') as mock_connect:
            mock_db = MagicMock()
            mock_connect.return_value = mock_db
            
            # Create provider
            provider = LanceDBProvider(uri="/path/to/db", vector_dim=3)
            
            # Test data
            model_class = MagicMock()
            data = {
                "id": "test-id",
                "embedding": [0.1, 0.2, 0.3],
                "metadata": {"key": "value"},
                "content": "Test content",
                "other_field": 42
            }
            
            # Convert to Arrow
            result = provider._convert_model_to_arrow(model_class, data)
            
            # Verify conversion
            assert result["id"] == "test-id"
            assert result["embedding"] == [0.1, 0.2, 0.3]
            assert isinstance(result["metadata"], str)
            assert json.loads(result["metadata"]) == {"key": "value"}
            assert result["content"] == "Test content"
            assert result["other_field"] == 42
            # Should have created_at and updated_at timestamps
            assert "created_at" in result
            assert "updated_at" in result
    
    def test_convert_model_to_arrow_with_numpy_embedding(self):
        """Test conversion with NumPy embedding array."""
        with patch('lancedb.connect') as mock_connect:
            mock_db = MagicMock()
            mock_connect.return_value = mock_db
            
            # Create provider
            provider = LanceDBProvider(uri="/path/to/db", vector_dim=3)
            
            # Test data with NumPy array
            model_class = MagicMock()
            data = {
                "id": "test-id",
                "embedding": np.array([0.1, 0.2, 0.3]),
                "content": "Test content"
            }
            
            # Convert to Arrow
            result = provider._convert_model_to_arrow(model_class, data)
            
            # Verify conversion
            assert result["embedding"] == [0.1, 0.2, 0.3]  # Should be converted to list
    
    def test_convert_model_to_arrow_with_string_embedding(self):
        """Test conversion with string JSON embedding."""
        with patch('lancedb.connect') as mock_connect:
            mock_db = MagicMock()
            mock_connect.return_value = mock_db
            
            # Create provider
            provider = LanceDBProvider(uri="/path/to/db", vector_dim=3)
            
            # Test data with string JSON
            model_class = MagicMock()
            data = {
                "id": "test-id",
                "embedding": "[0.1, 0.2, 0.3]",
                "content": "Test content"
            }
            
            # Convert to Arrow
            result = provider._convert_model_to_arrow(model_class, data)
            
            # Verify conversion
            assert result["embedding"] == [0.1, 0.2, 0.3]  # Should be parsed
    
    def test_convert_model_to_arrow_with_wrong_dimension(self):
        """Test conversion with wrong embedding dimension."""
        with patch('lancedb.connect') as mock_connect:
            mock_db = MagicMock()
            mock_connect.return_value = mock_db
            
            # Create provider with dimension 5
            provider = LanceDBProvider(uri="/path/to/db", vector_dim=5)
            
            # Test data with dimension 3
            model_class = MagicMock()
            data = {
                "id": "test-id",
                "embedding": [0.1, 0.2, 0.3],
                "content": "Test content"
            }
            
            # Convert to Arrow
            result = provider._convert_model_to_arrow(model_class, data)
            
            # Verify conversion (should pad with zeros)
            assert len(result["embedding"]) == 5
            assert result["embedding"][:3] == [0.1, 0.2, 0.3]
            assert result["embedding"][3:] == [0.0, 0.0]
    
    def test_convert_model_to_arrow_with_no_embedding(self):
        """Test conversion with no embedding field."""
        with patch('lancedb.connect') as mock_connect:
            mock_db = MagicMock()
            mock_connect.return_value = mock_db
            
            # Create provider
            provider = LanceDBProvider(uri="/path/to/db", vector_dim=3)
            
            # Test data without embedding
            model_class = MagicMock()
            data = {
                "id": "test-id",
                "content": "Test content"
            }
            
            # Convert to Arrow
            result = provider._convert_model_to_arrow(model_class, data)
            
            # Verify conversion (should create zero embedding)
            assert result["embedding"] == [0.0, 0.0, 0.0]
    
    def test_create(self):
        """Test creating a record."""
        with patch('lancedb.connect') as mock_connect:
            mock_db = MagicMock()
            mock_table = MagicMock()
            mock_db.table_names.return_value = ["test_table"]
            mock_db.open_table.return_value = mock_table
            mock_connect.return_value = mock_db
            
            # Create provider
            provider = LanceDBProvider(uri="/path/to/db")
            
            # Mock model class
            model_class = MagicMock()
            model_class.__tablename__ = "test_table"
            
            # Test data
            data = {
                "id": "test-id",
                "content": "Test content"
            }
            
            # Create record
            result = provider.create(model_class, data)
            
            # Verify record created
            assert result == "test-id"
            mock_table.add.assert_called_once()
    
    def test_create_with_auto_id(self):
        """Test creating a record with auto-generated ID."""
        with patch('lancedb.connect') as mock_connect:
            with patch('uuid.uuid4') as mock_uuid:
                mock_db = MagicMock()
                mock_table = MagicMock()
                mock_db.table_names.return_value = ["test_table"]
                mock_db.open_table.return_value = mock_table
                mock_connect.return_value = mock_db
                mock_uuid.return_value = uuid.UUID('00000000-0000-0000-0000-000000000001')
                
                # Create provider
                provider = LanceDBProvider(uri="/path/to/db")
                
                # Mock model class
                model_class = MagicMock()
                model_class.__tablename__ = "test_table"
                
                # Test data without ID
                data = {
                    "content": "Test content"
                }
                
                # Create record
                result = provider.create(model_class, data)
                
                # Verify record created with generated ID
                assert result == "00000000-0000-0000-0000-000000000001"
                mock_table.add.assert_called_once()
                
                # Verify UUID was used in the added data
                add_args = mock_table.add.call_args[0][0][0]
                assert add_args["id"] == "00000000-0000-0000-0000-000000000001"
    
    def test_get(self):
        """Test retrieving a record by ID."""
        with patch('lancedb.connect') as mock_connect:
            mock_db = MagicMock()
            mock_table = MagicMock()
            mock_search = MagicMock()
            mock_where = MagicMock()
            mock_limit = MagicMock()
            
            # Set up response
            mock_pandas_result = MagicMock()
            mock_pandas_result.iloc[0].to_dict.return_value = {
                "id": "test-id",
                "metadata": '{"key": "value"}',
                "content": "Test content"
            }
            mock_pandas_result.__len__.return_value = 1
            
            # Set up chain of calls
            mock_table.search.return_value = mock_search
            mock_search.where.return_value = mock_where
            mock_where.limit.return_value = mock_limit
            mock_limit.to_pandas.return_value = mock_pandas_result
            
            # Set up LanceDB
            mock_db.table_names.return_value = ["test_table"]
            mock_db.open_table.return_value = mock_table
            mock_connect.return_value = mock_db
            
            # Create provider
            provider = LanceDBProvider(uri="/path/to/db")
            
            # Mock model class
            model_class = MagicMock()
            model_class.__tablename__ = "test_table"
            
            # Get record
            result = provider.get(model_class, "test-id")
            
            # Verify search performed correctly
            mock_table.search.assert_called_once()
            mock_search.where.assert_called_once()
            assert "id = 'test-id'" in str(mock_search.where.call_args)
            mock_where.limit.assert_called_once_with(1)
            mock_limit.to_pandas.assert_called_once()
            
            # Verify result parsed
            assert result["id"] == "test-id"
            assert result["content"] == "Test content"
            assert result["metadata"] == {"key": "value"}  # Should be parsed from JSON
    
    def test_get_not_found(self):
        """Test retrieving a non-existent record."""
        with patch('lancedb.connect') as mock_connect:
            mock_db = MagicMock()
            mock_table = MagicMock()
            mock_search = MagicMock()
            mock_where = MagicMock()
            mock_limit = MagicMock()
            
            # Set up empty response
            mock_pandas_result = MagicMock()
            mock_pandas_result.__len__.return_value = 0
            
            # Set up chain of calls
            mock_table.search.return_value = mock_search
            mock_search.where.return_value = mock_where
            mock_where.limit.return_value = mock_limit
            mock_limit.to_pandas.return_value = mock_pandas_result
            
            # Set up LanceDB
            mock_db.table_names.return_value = ["test_table"]
            mock_db.open_table.return_value = mock_table
            mock_connect.return_value = mock_db
            
            # Create provider
            provider = LanceDBProvider(uri="/path/to/db")
            
            # Mock model class
            model_class = MagicMock()
            model_class.__tablename__ = "test_table"
            
            # Get non-existent record
            result = provider.get(model_class, "non-existent-id")
            
            # Verify search performed correctly
            mock_search.where.assert_called_once()
            
            # Verify result is None
            assert result is None
    
    def test_vector_search(self):
        """Test vector similarity search."""
        with patch('lancedb.connect') as mock_connect:
            mock_db = MagicMock()
            mock_table = MagicMock()
            mock_search = MagicMock()
            mock_where = MagicMock()
            mock_limit = MagicMock()
            
            # Set up responses
            mock_pandas_result = MagicMock()
            # Create two records for result
            record1 = {
                "id": "test-id-1",
                "metadata": '{"key": "value1"}',
                "content": "Test content 1"
            }
            record2 = {
                "id": "test-id-2",
                "metadata": '{"key": "value2"}',
                "content": "Test content 2"
            }
            mock_pandas_result.iterrows.return_value = [
                (0, MagicMock(to_dict=lambda: record1)),
                (1, MagicMock(to_dict=lambda: record2))
            ]
            
            # Set up chain of calls
            mock_table.search.return_value = mock_search
            mock_search.where.return_value = mock_where
            mock_where.limit.return_value = mock_limit
            mock_limit.to_pandas.return_value = mock_pandas_result
            
            # Set up LanceDB
            mock_db.table_names.return_value = ["test_table"]
            mock_db.open_table.return_value = mock_table
            mock_connect.return_value = mock_db
            
            # Create provider
            provider = LanceDBProvider(uri="/path/to/db")
            
            # Mock model class
            model_class = MagicMock()
            model_class.__tablename__ = "test_table"
            
            # Perform vector search
            query_vector = [0.1, 0.2, 0.3]
            filter_criteria = {"category": "test"}
            results = provider.vector_search(model_class, query_vector, limit=10, filter_criteria=filter_criteria)
            
            # Verify search performed correctly
            mock_table.search.assert_called_once_with(query_vector, vector_column_name="embedding")
            mock_search.where.assert_called_once()
            assert "category = 'test'" in str(mock_search.where.call_args)
            mock_where.limit.assert_called_once_with(10)
            mock_limit.to_pandas.assert_called_once()
            
            # Verify results parsed
            assert len(results) == 2
            assert results[0]["id"] == "test-id-1"
            assert results[0]["content"] == "Test content 1"
            assert results[0]["metadata"] == {"key": "value1"}  # Should be parsed from JSON
            assert results[1]["id"] == "test-id-2"
    
    def test_hybrid_search(self):
        """Test hybrid (vector + text) search."""
        with patch('lancedb.connect') as mock_connect:
            mock_db = MagicMock()
            mock_table = MagicMock()
            mock_search = MagicMock()
            mock_where = MagicMock()
            mock_limit = MagicMock()
            
            # Set up responses
            mock_pandas_result = MagicMock()
            # Create a record for result
            record = {
                "id": "test-id",
                "metadata": '{"key": "value"}',
                "content": "Test content hybrid search"
            }
            mock_pandas_result.iterrows.return_value = [
                (0, MagicMock(to_dict=lambda: record))
            ]
            
            # Set up chain of calls
            mock_table.search.return_value = mock_search
            mock_search.where.return_value = mock_where
            mock_where.limit.return_value = mock_limit
            mock_limit.to_pandas.return_value = mock_pandas_result
            
            # Set up LanceDB
            mock_db.table_names.return_value = ["test_table"]
            mock_db.open_table.return_value = mock_table
            mock_connect.return_value = mock_db
            
            # Create provider
            provider = LanceDBProvider(uri="/path/to/db")
            
            # Mock model class
            model_class = MagicMock()
            model_class.__tablename__ = "test_table"
            
            # Perform hybrid search
            query_text = "hybrid search"
            query_vector = [0.1, 0.2, 0.3]
            results = provider.hybrid_search(model_class, query_text, query_vector)
            
            # Verify search performed correctly
            mock_table.search.assert_called_once_with(query_vector, query_text=query_text)
            mock_search.where.assert_not_called()  # No filter criteria
            mock_search.limit.assert_called_once_with(10)  # Default limit
            
            # Verify results parsed
            assert len(results) == 1
            assert results[0]["id"] == "test-id"
            assert results[0]["content"] == "Test content hybrid search"
            assert results[0]["metadata"] == {"key": "value"}  # Should be parsed from JSON
    
    def test_hybrid_search_text_only(self):
        """Test hybrid search with only text query."""
        with patch('lancedb.connect') as mock_connect:
            mock_db = MagicMock()
            mock_table = MagicMock()
            mock_search = MagicMock()
            mock_limit = MagicMock()
            
            # Set up responses
            mock_pandas_result = MagicMock()
            # Create a record for result
            record = {
                "id": "test-id",
                "content": "Test content text search"
            }
            mock_pandas_result.iterrows.return_value = [
                (0, MagicMock(to_dict=lambda: record))
            ]
            
            # Set up chain of calls
            mock_table.search.return_value = mock_search
            mock_search.limit.return_value = mock_limit
            mock_limit.to_pandas.return_value = mock_pandas_result
            
            # Set up LanceDB
            mock_db.table_names.return_value = ["test_table"]
            mock_db.open_table.return_value = mock_table
            mock_connect.return_value = mock_db
            
            # Create provider
            provider = LanceDBProvider(uri="/path/to/db")
            
            # Mock model class
            model_class = MagicMock()
            model_class.__tablename__ = "test_table"
            
            # Perform text-only search
            query_text = "text search"
            results = provider.hybrid_search(model_class, query_text, query_vector=None)
            
            # Verify search performed correctly
            mock_table.search.assert_called_once_with(query_text=query_text)
            
            # Verify results parsed
            assert len(results) == 1
            assert results[0]["id"] == "test-id"
            assert results[0]["content"] == "Test content text search"