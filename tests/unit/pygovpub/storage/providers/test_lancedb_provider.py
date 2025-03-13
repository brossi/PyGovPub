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


class TestLanceDBConnectionPool:
    """Test suite for the LanceDBConnectionPool class."""
    
    def test_init(self):
        """Test initialization of connection pool."""
        with patch('lancedb.connect') as mock_connect:
            # Create mock connections
            mock_connections = [MagicMock() for _ in range(3)]
            mock_connect.side_effect = mock_connections
            
            # Create pool with min_size of 3
            from pygovpub.storage.providers.lancedb_provider import LanceDBConnectionPool
            pool = LanceDBConnectionPool(
                uri="/path/to/db", 
                pool_id="test", 
                min_size=3,
                max_size=5
            )
            
            # Verify connections created
            assert mock_connect.call_count == 3
            assert pool._available_connections.qsize() == 3
            assert len(pool._in_use_connections) == 0
            
            # Verify metrics initialized
            with patch('pygovpub.storage.providers.lancedb_provider.LANCEDB_POOL_CONNECTIONS.labels') as mock_metrics:
                mock_gauge = MagicMock()
                mock_metrics.return_value = mock_gauge
                
                # Create a new pool to trigger metrics
                pool = LanceDBConnectionPool(uri="/path/to/db", pool_id="metrics_test", min_size=1)
                
                # Verify metrics called
                mock_metrics.assert_called()
    
    def test_get_connection(self):
        """Test getting a connection from the pool."""
        with patch('lancedb.connect') as mock_connect:
            mock_connection = MagicMock()
            mock_connect.return_value = mock_connection
            
            # Create pool with min_size of 1
            from pygovpub.storage.providers.lancedb_provider import LanceDBConnectionPool
            pool = LanceDBConnectionPool(uri="/path/to/db", pool_id="test", min_size=1)
            
            # Mock connection validation
            mock_connection.table_names.return_value = ["test_table"]
            
            # Get a connection
            connection, conn_id = pool.get_connection()
            
            # Verify connection
            assert connection is mock_connection
            assert conn_id is not None
            assert pool._available_connections.qsize() == 0
            assert len(pool._in_use_connections) == 1
            assert conn_id in pool._in_use_connections
            
            # Verify connection validation
            mock_connection.table_names.assert_called_once()
    
    def test_release_connection(self):
        """Test releasing a connection back to the pool."""
        with patch('lancedb.connect') as mock_connect:
            mock_connection = MagicMock()
            mock_connect.return_value = mock_connection
            
            # Create pool with min_size of 1
            from pygovpub.storage.providers.lancedb_provider import LanceDBConnectionPool
            pool = LanceDBConnectionPool(uri="/path/to/db", pool_id="test", min_size=1)
            
            # Mock connection validation
            mock_connection.table_names.return_value = ["test_table"]
            
            # Get a connection
            connection, conn_id = pool.get_connection()
            
            # Release the connection
            pool.release_connection(connection, conn_id)
            
            # Verify connection is back in the pool
            assert pool._available_connections.qsize() == 1
            assert len(pool._in_use_connections) == 0
    
    def test_invalid_connection_handling(self):
        """Test handling of invalid connections."""
        with patch('lancedb.connect') as mock_connect:
            mock_connection1 = MagicMock()
            mock_connection2 = MagicMock()
            mock_connect.side_effect = [mock_connection1, mock_connection2]
            
            # Create pool with min_size of 1
            from pygovpub.storage.providers.lancedb_provider import LanceDBConnectionPool
            pool = LanceDBConnectionPool(uri="/path/to/db", pool_id="test", min_size=1)
            
            # Make the connection invalid
            mock_connection1.table_names.side_effect = Exception("Connection error")
            
            # Get a connection (should create a new one)
            connection, conn_id = pool.get_connection()
            
            # Verify new connection
            assert connection is mock_connection2
            assert conn_id is not None
            assert mock_connect.call_count == 2
    
    def test_cleanup_idle_connections(self):
        """Test cleaning up idle connections."""
        with patch('lancedb.connect') as mock_connect:
            mock_connection1 = MagicMock()
            mock_connection2 = MagicMock()
            mock_connect.side_effect = [mock_connection1, mock_connection2]
            
            # Create pool with min_size of 1 and idle_timeout of 0.1 seconds
            from pygovpub.storage.providers.lancedb_provider import LanceDBConnectionPool
            with patch('time.time', side_effect=[100.0, 100.1, 200.2]):  # First creation time, then check time
                pool = LanceDBConnectionPool(
                    uri="/path/to/db", 
                    pool_id="test", 
                    min_size=1,
                    idle_timeout=0.1
                )
                
                # Clean up idle connections
                with patch('time.time', return_value=200.2):  # 100.2 seconds later
                    cleaned_up = pool.cleanup_idle_connections()
            
            # Verify connections were cleaned up and recreated
            assert cleaned_up == 1
            assert mock_connect.call_count == 2  # 1 initial + 1 recreated
            assert pool._available_connections.qsize() == 1
    
    def test_get_connection_pool_function(self):
        """Test the get_connection_pool function for singleton pools."""
        with patch('pygovpub.storage.providers.lancedb_provider.LanceDBConnectionPool') as mock_pool_class:
            mock_pool1 = MagicMock()
            mock_pool2 = MagicMock()
            mock_pool_class.side_effect = [mock_pool1, mock_pool2]
            
            # Get pools with the same URI and pool_id
            from pygovpub.storage.providers.lancedb_provider import get_connection_pool
            pool1 = get_connection_pool(uri="/path/to/db", pool_id="test")
            pool2 = get_connection_pool(uri="/path/to/db", pool_id="test")
            
            # Verify only one pool created
            assert mock_pool_class.call_count == 1
            assert pool1 is pool2
            
            # Get pool with a different pool_id
            pool3 = get_connection_pool(uri="/path/to/db", pool_id="other")
            
            # Verify a new pool was created
            assert mock_pool_class.call_count == 2
            assert pool1 is not pool3


class TestLanceDBProviderWithPool:
    """Test suite for LanceDBProvider with connection pooling."""
    
    def test_init_with_pool_enabled(self):
        """Test provider initialization with connection pooling enabled."""
        with patch('pygovpub.storage.providers.lancedb_provider.get_connection_pool') as mock_get_pool:
            mock_pool = MagicMock()
            mock_connection = MagicMock()
            mock_pool.get_connection.return_value = (mock_connection, "test_conn_id")
            mock_get_pool.return_value = mock_pool
            
            # Create provider with connection pooling
            provider = LanceDBProvider(
                uri="/path/to/db", 
                use_connection_pool=True,
                pool_id="test_pool",
                pool_max_size=10,
                pool_min_size=2
            )
            
            # Verify pool created and used
            mock_get_pool.assert_called_once_with(
                uri="/path/to/db",
                pool_id="test_pool",
                max_size=10,
                min_size=2,
                **{}
            )
            assert provider.connection_pool is mock_pool
            assert provider.db is mock_connection
            assert provider.current_connection_id == "test_conn_id"
    
    def test_init_with_pool_disabled(self):
        """Test provider initialization with connection pooling disabled."""
        with patch('lancedb.connect') as mock_connect:
            with patch('pygovpub.storage.providers.lancedb_provider.get_connection_pool') as mock_get_pool:
                mock_connection = MagicMock()
                mock_connect.return_value = mock_connection
                
                # Create provider with connection pooling disabled
                provider = LanceDBProvider(
                    uri="/path/to/db", 
                    use_connection_pool=False
                )
                
                # Verify direct connection used
                mock_get_pool.assert_not_called()
                mock_connect.assert_called_once_with("/path/to/db")
                assert provider.connection_pool is None
                assert provider.db is mock_connection
    
    def test_get_connection_method(self):
        """Test the _get_connection method."""
        # Test with pooling enabled
        with patch('pygovpub.storage.providers.lancedb_provider.get_connection_pool') as mock_get_pool:
            mock_pool = MagicMock()
            mock_connection = MagicMock()
            mock_pool.get_connection.return_value = (mock_connection, "test_conn_id")
            mock_get_pool.return_value = mock_pool
            
            # Create provider with connection pooling
            provider = LanceDBProvider(
                uri="/path/to/db", 
                use_connection_pool=True
            )
            
            # Get connection
            connection, conn_id = provider._get_connection()
            
            # Verify connection from pool
            assert connection is mock_connection
            assert conn_id == "test_conn_id"
            mock_pool.get_connection.assert_called_once()
        
        # Test with pooling disabled
        with patch('lancedb.connect') as mock_connect:
            mock_connection = MagicMock()
            mock_connect.return_value = mock_connection
            
            # Create provider without connection pooling
            provider = LanceDBProvider(
                uri="/path/to/db", 
                use_connection_pool=False
            )
            
            # Get connection
            connection, conn_id = provider._get_connection()
            
            # Verify direct connection
            assert connection is mock_connection
            assert conn_id is None
    
    def test_with_connection_method(self):
        """Test the _with_connection method."""
        with patch('pygovpub.storage.providers.lancedb_provider.get_connection_pool') as mock_get_pool:
            mock_pool = MagicMock()
            mock_connection = MagicMock()
            mock_pool.get_connection.return_value = (mock_connection, "test_conn_id")
            mock_get_pool.return_value = mock_pool
            
            # Create provider with connection pooling
            provider = LanceDBProvider(
                uri="/path/to/db", 
                use_connection_pool=True
            )
            
            # Test function to run with connection
            test_func = MagicMock(return_value="test_result")
            
            # Execute with connection
            result = provider._with_connection(test_func)
            
            # Verify function called with connection and result returned
            test_func.assert_called_once_with(mock_connection)
            assert result == "test_result"
            mock_pool.get_connection.assert_called_once()
            mock_pool.release_connection.assert_called_once_with(mock_connection, "test_conn_id")
    
    def test_get_or_create_table_with_pool(self):
        """Test _get_or_create_table using connection pool."""
        with patch('pygovpub.storage.providers.lancedb_provider.get_connection_pool') as mock_get_pool:
            mock_pool = MagicMock()
            mock_connection = MagicMock()
            mock_table = MagicMock()
            mock_pool.get_connection.return_value = (mock_connection, "test_conn_id")
            mock_get_pool.return_value = mock_pool
            
            # Set up mock table
            mock_connection.table_names.return_value = ["test_table"]
            mock_connection.open_table.return_value = mock_table
            mock_table.schema = MagicMock()
            
            # Create provider with connection pooling
            provider = LanceDBProvider(
                uri="/path/to/db", 
                use_connection_pool=True
            )
            
            # Mock the _check_table_has_vector_index method
            provider._check_table_has_vector_index = MagicMock(return_value=True)
            
            # Get an existing table
            table = provider._get_or_create_table("test_table")
            
            # Verify connection used correctly
            mock_pool.get_connection.assert_called_once()
            mock_connection.table_names.assert_called_once()
            mock_connection.open_table.assert_called_once_with("test_table")
            mock_pool.release_connection.assert_called_once_with(mock_connection, "test_conn_id")
            assert table is mock_table