"""
Tests for integrating the storage interface with providers.

This module tests the integration between the core storage interface
and different database providers, especially LanceDB.
"""

import os
import pytest
from unittest.mock import patch, MagicMock

from pygovpub.storage.interface import StorageInterface
from pygovpub.storage.providers.lancedb_provider import LanceDBProvider


class TestLanceDBIntegration:
    """Test suite for LanceDB provider integration with StorageInterface."""
    
    @patch("pygovpub.storage.providers.lancedb_provider.LanceDBProvider")
    @patch("importlib.util.find_spec")
    def test_lancedb_detection(self, mock_find_spec, mock_lancedb_provider):
        """Test LanceDB detection in StorageInterface."""
        # Mock importlib.util.find_spec to indicate lancedb is available
        mock_find_spec.return_value = MagicMock()
        
        # Mock LanceDBProvider
        mock_provider_instance = MagicMock()
        mock_lancedb_provider.return_value = mock_provider_instance
        
        # Create interface with LanceDB connection
        interface = StorageInterface("lancedb:///path/to/db")
        
        # Check features
        assert interface.features.get('vector_operations') is True
        assert interface.features.get('hybrid_search') is True
        assert interface.features.get('full_text_search') is True
        assert interface.features.get('embedded_database') is True
        
        # Verify LanceDB provider was initialized
        mock_lancedb_provider.assert_called_once()
    
    @patch("importlib.util.find_spec")
    def test_lancedb_detection_unavailable(self, mock_find_spec):
        """Test StorageInterface behavior when LanceDB is not available."""
        # Mock importlib.util.find_spec to indicate lancedb is not available
        mock_find_spec.return_value = None
        
        # Create interface with LanceDB connection
        interface = StorageInterface("lancedb:///path/to/db")
        
        # Check features (should not have LanceDB features)
        assert interface.features.get('vector_operations') is not True
        assert interface.features.get('hybrid_search') is not True
        assert interface.features.get('full_text_search') is not True
        assert interface.features.get('embedded_database') is not True
    
    @patch("pygovpub.storage.providers.lancedb_provider.lancedb")
    @patch("importlib.util.find_spec")
    def test_lancedb_create_operation(self, mock_find_spec, mock_lancedb):
        """Test create operation with LanceDB provider."""
        # Mock importlib.util.find_spec to indicate lancedb is available
        mock_find_spec.return_value = MagicMock()
        
        # Mock LanceDB and its methods
        mock_db = MagicMock()
        mock_lancedb.connect.return_value = mock_db
        
        # Create interface with LanceDB connection
        with patch("pygovpub.storage.interface._initialize_lancedb_provider") as mock_init_provider:
            mock_provider = MagicMock()
            mock_provider.create.return_value = "test-id-123"
            mock_init_provider.return_value = mock_provider
            
            interface = StorageInterface("lancedb:///path/to/db")
            
            # Force LanceDB provider into _providers
            interface._providers = {"lancedb": mock_provider}
            
            # Create a test model and data
            model_class = MagicMock()
            data = {"field": "value"}
            
            # Override _get_provider to return our mock provider
            interface._get_provider = lambda: mock_provider
            
            # Call create with LanceDB provider
            result = interface.create_with_provider("lancedb", model_class, data)
            
            # Verify provider's create method was called
            mock_provider.create.assert_called_once_with(model_class, data)
            assert result == "test-id-123"
    
    @patch("pygovpub.storage.providers.lancedb_provider.lancedb")
    @patch("importlib.util.find_spec")
    def test_lancedb_vector_search_operation(self, mock_find_spec, mock_lancedb):
        """Test vector search operation with LanceDB provider."""
        # Mock importlib.util.find_spec to indicate lancedb is available
        mock_find_spec.return_value = MagicMock()
        
        # Mock LanceDB and its methods
        mock_db = MagicMock()
        mock_lancedb.connect.return_value = mock_db
        
        # Create interface with LanceDB connection
        with patch("pygovpub.storage.interface._initialize_lancedb_provider") as mock_init_provider:
            mock_provider = MagicMock()
            mock_provider.vector_search.return_value = [{"id": "result-1"}, {"id": "result-2"}]
            mock_init_provider.return_value = mock_provider
            
            interface = StorageInterface("lancedb:///path/to/db")
            
            # Force LanceDB provider into _providers
            interface._providers = {"lancedb": mock_provider}
            
            # Create test parameters
            model_class = MagicMock()
            query_vector = [0.1, 0.2, 0.3]
            filter_criteria = {"category": "test"}
            
            # Override _get_provider to return our mock provider
            interface._get_provider = lambda: mock_provider
            
            # Call vector search with LanceDB provider
            results = interface.vector_search_with_provider(
                "lancedb", model_class, query_vector, limit=5, filter_criteria=filter_criteria
            )
            
            # Verify provider's vector_search method was called
            mock_provider.vector_search.assert_called_once_with(
                model_class, query_vector, limit=5, filter_criteria=filter_criteria
            )
            assert len(results) == 2
            assert results[0]["id"] == "result-1"
    
    @patch("pygovpub.storage.providers.lancedb_provider.lancedb")
    @patch("importlib.util.find_spec")
    def test_lancedb_hybrid_search_operation(self, mock_find_spec, mock_lancedb):
        """Test hybrid search operation with LanceDB provider."""
        # Mock importlib.util.find_spec to indicate lancedb is available
        mock_find_spec.return_value = MagicMock()
        
        # Mock LanceDB and its methods
        mock_db = MagicMock()
        mock_lancedb.connect.return_value = mock_db
        
        # Create interface with LanceDB connection
        with patch("pygovpub.storage.interface._initialize_lancedb_provider") as mock_init_provider:
            mock_provider = MagicMock()
            mock_provider.hybrid_search.return_value = [{"id": "result-1", "content": "test content"}]
            mock_init_provider.return_value = mock_provider
            
            interface = StorageInterface("lancedb:///path/to/db")
            
            # Force LanceDB provider into _providers
            interface._providers = {"lancedb": mock_provider}
            
            # Create test parameters
            model_class = MagicMock()
            query_text = "test query"
            query_vector = [0.1, 0.2, 0.3]
            
            # Override _get_provider to return our mock provider
            interface._get_provider = lambda: mock_provider
            
            # Call hybrid search with LanceDB provider
            results = interface.hybrid_search_with_provider(
                "lancedb", model_class, query_text, query_vector
            )
            
            # Verify provider's hybrid_search method was called
            mock_provider.hybrid_search.assert_called_once_with(
                model_class, query_text, query_vector=query_vector, limit=10, filter_criteria=None
            )
            assert len(results) == 1
            assert results[0]["content"] == "test content"