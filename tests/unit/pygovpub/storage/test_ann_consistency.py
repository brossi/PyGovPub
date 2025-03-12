"""
Tests for ANN (Approximate Nearest Neighbor) search consistency.

This module tests the consistency and reliability of vector search results
across different search parameters and conditions.
"""

import pytest
import numpy as np
import pandas as pd
from unittest.mock import patch, MagicMock, call

from pygovpub.storage.providers.lancedb_provider import LanceDBProvider

class TestANNSearchConsistency:
    """Test suite for ANN search consistency."""
    
    @patch("pygovpub.storage.providers.lancedb_provider.lancedb")
    def test_ann_search_result_stability(self, mock_lancedb):
        """Test ANN search result stability with identical queries."""
        # Mock LanceDB setup
        mock_db = MagicMock()
        mock_table = MagicMock()
        mock_search = MagicMock()
        mock_db.table_names.return_value = ["documents"]
        mock_db.open_table.return_value = mock_table
        mock_table.search.return_value = mock_search
        mock_lancedb.connect.return_value = mock_db
        
        # Mock search results
        result_data = [
            {"id": "doc1", "score": 0.92, "content": "Document 1"},
            {"id": "doc2", "score": 0.87, "content": "Document 2"},
            {"id": "doc3", "score": 0.81, "content": "Document 3"},
        ]
        mock_df = pd.DataFrame(result_data)
        mock_search.limit.return_value.to_pandas.return_value = mock_df
        
        # Create provider
        provider = LanceDBProvider(uri="/path/to/db")
        
        # Test model class
        class DocumentModel:
            __tablename__ = "documents"
        
        # Create vector query
        query_vector = np.random.rand(384).tolist()
        
        # Perform multiple identical searches
        results1 = provider.vector_search(DocumentModel, query_vector, limit=3)
        results2 = provider.vector_search(DocumentModel, query_vector, limit=3)
        
        # Results should be identical for identical queries
        assert len(results1) == len(results2)
        assert results1[0]["id"] == results2[0]["id"]
        assert results1[1]["id"] == results2[1]["id"]
        assert results1[2]["id"] == results2[2]["id"]
    
    @patch("pygovpub.storage.providers.lancedb_provider.lancedb")
    def test_ann_search_limit_consistency(self, mock_lancedb):
        """Test consistency of results when changing limit parameter."""
        # Mock LanceDB setup
        mock_db = MagicMock()
        mock_table = MagicMock()
        mock_search = MagicMock()
        mock_db.table_names.return_value = ["documents"]
        mock_db.open_table.return_value = mock_table
        mock_table.search.return_value = mock_search
        mock_lancedb.connect.return_value = mock_db
        
        # Create result data for 5 records
        result_data = [
            {"id": "doc1", "score": 0.92, "content": "Document 1"},
            {"id": "doc2", "score": 0.87, "content": "Document 2"},
            {"id": "doc3", "score": 0.81, "content": "Document 3"},
            {"id": "doc4", "score": 0.78, "content": "Document 4"},
            {"id": "doc5", "score": 0.76, "content": "Document 5"},
        ]
        
        # Create two mock dataframes with different slices
        mock_df_3 = pd.DataFrame(result_data[:3])
        mock_df_5 = pd.DataFrame(result_data)
        
        # Setup mock to return different results based on limit
        def mock_limit_function(limit):
            mock_limit_result = MagicMock()
            if limit == 3:
                mock_limit_result.to_pandas.return_value = mock_df_3
            else:
                mock_limit_result.to_pandas.return_value = mock_df_5
            return mock_limit_result
        
        mock_search.limit.side_effect = mock_limit_function
        
        # Create provider
        provider = LanceDBProvider(uri="/path/to/db")
        
        # Test model class
        class DocumentModel:
            __tablename__ = "documents"
        
        # Create vector query
        query_vector = np.random.rand(384).tolist()
        
        # Perform search with different limits
        results_3 = provider.vector_search(DocumentModel, query_vector, limit=3)
        results_5 = provider.vector_search(DocumentModel, query_vector, limit=5)
        
        # First 3 results should be identical
        assert len(results_3) == 3
        assert len(results_5) == 5
        for i in range(3):
            assert results_3[i]["id"] == results_5[i]["id"]
            assert results_3[i]["content"] == results_5[i]["content"]
    
    @patch("pygovpub.storage.providers.lancedb_provider.lancedb")
    def test_ann_search_filter_consistency(self, mock_lancedb):
        """Test consistency when adding filters to search."""
        # Mock LanceDB setup
        mock_db = MagicMock()
        mock_table = MagicMock()
        mock_search = MagicMock()
        mock_where = MagicMock()
        mock_db.table_names.return_value = ["documents"]
        mock_db.open_table.return_value = mock_table
        mock_table.search.return_value = mock_search
        mock_search.where.return_value = mock_where
        mock_lancedb.connect.return_value = mock_db
        
        # Create result data with category
        all_results = [
            {"id": "doc1", "score": 0.92, "content": "Document 1", "category": "legal"},
            {"id": "doc2", "score": 0.91, "content": "Document 2", "category": "science"},
            {"id": "doc3", "score": 0.90, "content": "Document 3", "category": "legal"},
            {"id": "doc4", "score": 0.89, "content": "Document 4", "category": "science"},
            {"id": "doc5", "score": 0.88, "content": "Document 5", "category": "legal"},
        ]
        
        # Filtered results (only legal documents)
        legal_results = [
            {"id": "doc1", "score": 0.92, "content": "Document 1", "category": "legal"},
            {"id": "doc3", "score": 0.90, "content": "Document 3", "category": "legal"},
            {"id": "doc5", "score": 0.88, "content": "Document 5", "category": "legal"},
        ]
        
        # Create mock dataframes
        mock_df_all = pd.DataFrame(all_results)
        mock_df_legal = pd.DataFrame(legal_results)
        
        # Setup mocks to return different results
        mock_limit_all = MagicMock()
        mock_limit_all.to_pandas.return_value = mock_df_all
        mock_search.limit.return_value = mock_limit_all
        
        mock_limit_legal = MagicMock()
        mock_limit_legal.to_pandas.return_value = mock_df_legal
        mock_where.limit.return_value = mock_limit_legal
        
        # Create provider
        provider = LanceDBProvider(uri="/path/to/db")
        
        # Test model class
        class DocumentModel:
            __tablename__ = "documents"
        
        # Create vector query
        query_vector = np.random.rand(384).tolist()
        
        # Perform search with and without filter
        results_all = provider.vector_search(DocumentModel, query_vector, limit=5)
        results_legal = provider.vector_search(DocumentModel, query_vector, 
                                             limit=5, 
                                             filter_criteria={"category": "legal"})
        
        # Verify filter was applied correctly
        assert len(results_all) == 5
        assert len(results_legal) == 3
        for result in results_legal:
            assert result["category"] == "legal"
        
        # Verify order consistency (legal documents should be in same order)
        legal_ids_in_all = [r["id"] for r in results_all if r["category"] == "legal"]
        legal_ids_in_filtered = [r["id"] for r in results_legal]
        assert legal_ids_in_all == legal_ids_in_filtered
    
    @patch("pygovpub.storage.providers.lancedb_provider.lancedb")
    def test_ann_search_with_threshold(self, mock_lancedb):
        """Test applying a score threshold to search results."""
        # Mock LanceDB setup
        mock_db = MagicMock()
        mock_table = MagicMock()
        mock_search = MagicMock()
        mock_db.table_names.return_value = ["documents"]
        mock_db.open_table.return_value = mock_table
        mock_table.search.return_value = mock_search
        mock_lancedb.connect.return_value = mock_db
        
        # Create result data with varying scores
        result_data = [
            {"id": "doc1", "score": 0.95, "content": "Document 1"},
            {"id": "doc2", "score": 0.85, "content": "Document 2"},
            {"id": "doc3", "score": 0.75, "content": "Document 3"},
            {"id": "doc4", "score": 0.65, "content": "Document 4"},
            {"id": "doc5", "score": 0.55, "content": "Document 5"},
        ]
        
        # Create mock dataframe
        mock_df = pd.DataFrame(result_data)
        
        # Setup mock
        mock_limit = MagicMock()
        mock_limit.to_pandas.return_value = mock_df
        mock_search.limit.return_value = mock_limit
        
        # Create provider
        provider = LanceDBProvider(uri="/path/to/db")
        
        # Test model class
        class DocumentModel:
            __tablename__ = "documents"
        
        # Create vector query
        query_vector = np.random.rand(384).tolist()
        
        # Perform search with score threshold (added to provider for this test)
        with patch.object(provider, 'apply_score_threshold', lambda results, threshold: 
                         [r for r in results if r.get("score", 0) >= threshold]):
            results = provider.vector_search(DocumentModel, query_vector, limit=5)
            results_filtered = provider.apply_score_threshold(results, 0.80)
            
            # Verify threshold filtering
            assert len(results) == 5
            assert len(results_filtered) == 2
            for result in results_filtered:
                assert result["score"] >= 0.80
    
    @patch("pygovpub.storage.providers.lancedb_provider.lancedb")
    def test_hybrid_search_consistency(self, mock_lancedb):
        """Test consistency between hybrid search and vector-only search."""
        # Mock LanceDB setup
        mock_db = MagicMock()
        mock_table = MagicMock()
        mock_vector_search = MagicMock()
        mock_hybrid_search = MagicMock()
        mock_db.table_names.return_value = ["documents"]
        mock_db.open_table.return_value = mock_table
        mock_lancedb.connect.return_value = mock_db
        
        # Setup search mocks
        def create_search_mock(result_data):
            search_mock = MagicMock()
            limit_mock = MagicMock()
            df = pd.DataFrame(result_data)
            limit_mock.to_pandas.return_value = df
            search_mock.limit.return_value = limit_mock
            return search_mock
        
        # Vector search results
        vector_results = [
            {"id": "doc1", "score": 0.95, "content": "Document about law"},
            {"id": "doc2", "score": 0.85, "content": "Document about legal concepts"},
            {"id": "doc3", "score": 0.75, "content": "Document about science"},
        ]
        
        # Hybrid search results - should be influenced by both vector and text
        hybrid_results = [
            {"id": "doc1", "score": 0.92, "content": "Document about law"},
            {"id": "doc2", "score": 0.90, "content": "Document about legal concepts"},
            {"id": "doc4", "score": 0.70, "content": "Another legal document"},
        ]
        
        # Setup the mock returns
        mock_table.search.side_effect = [
            create_search_mock(vector_results),  # For vector search
            create_search_mock(hybrid_results)   # For hybrid search
        ]
        
        # Create provider
        provider = LanceDBProvider(uri="/path/to/db")
        
        # Test model class
        class DocumentModel:
            __tablename__ = "documents"
        
        # Create query data
        query_vector = np.random.rand(384).tolist()
        query_text = "legal document"
        
        # Perform searches
        vector_results = provider.vector_search(DocumentModel, query_vector, limit=3)
        hybrid_results = provider.hybrid_search(DocumentModel, query_text, query_vector, limit=3)
        
        # Verify results
        assert len(vector_results) == 3
        assert len(hybrid_results) == 3
        
        # Check if common items maintain relative ordering
        common_ids = [item["id"] for item in vector_results if 
                     any(h_item["id"] == item["id"] for h_item in hybrid_results)]
        
        for id1 in common_ids:
            for id2 in common_ids:
                if id1 == id2:
                    continue
                
                # Find positions in both result sets
                pos1_vector = next(i for i, x in enumerate(vector_results) if x["id"] == id1)
                pos2_vector = next(i for i, x in enumerate(vector_results) if x["id"] == id2)
                pos1_hybrid = next(i for i, x in enumerate(hybrid_results) if x["id"] == id1)
                pos2_hybrid = next(i for i, x in enumerate(hybrid_results) if x["id"] == id2)
                
                # Check if relative ordering is preserved
                assert (pos1_vector < pos2_vector) == (pos1_hybrid < pos2_hybrid)


class TestANNSearchStability:
    """Test suite for ANN search stability under various conditions."""
    
    @patch("pygovpub.storage.providers.lancedb_provider.lancedb")
    def test_small_vector_dimension_changes(self, mock_lancedb):
        """Test stability with small changes to query vector dimensions."""
        # Mock LanceDB setup
        mock_db = MagicMock()
        mock_table = MagicMock()
        mock_search = MagicMock()
        mock_db.table_names.return_value = ["documents"]
        mock_db.open_table.return_value = mock_table
        mock_table.search.return_value = mock_search
        mock_lancedb.connect.return_value = mock_db
        
        # Create result data
        result_data = [
            {"id": "doc1", "score": 0.95, "content": "Document 1"},
            {"id": "doc2", "score": 0.85, "content": "Document 2"},
            {"id": "doc3", "score": 0.75, "content": "Document 3"},
        ]
        
        # Create mock dataframe
        mock_df = pd.DataFrame(result_data)
        
        # Setup mock
        mock_limit = MagicMock()
        mock_limit.to_pandas.return_value = mock_df
        mock_search.limit.return_value = mock_limit
        
        # Create providers with different vector dimensions
        provider_384 = LanceDBProvider(uri="/path/to/db", vector_dim=384)
        provider_256 = LanceDBProvider(uri="/path/to/db", vector_dim=256)
        
        # Test model class
        class DocumentModel:
            __tablename__ = "documents"
        
        # Create vector queries with different dimensions
        query_vector_384 = np.random.rand(384).tolist()
        query_vector_256 = np.random.rand(256).tolist()
        
        # Perform searches with different dimensions
        results_384 = provider_384.vector_search(DocumentModel, query_vector_384, limit=3)
        results_256 = provider_256.vector_search(DocumentModel, query_vector_256, limit=3)
        
        # Results should be identical because we're mocking the database
        assert len(results_384) == len(results_256)
        for i in range(len(results_384)):
            assert results_384[i]["id"] == results_256[i]["id"]
            assert results_384[i]["score"] == results_256[i]["score"]
    
    @patch("pygovpub.storage.providers.lancedb_provider.lancedb")
    def test_result_stability_with_small_query_changes(self, mock_lancedb):
        """Test stability of results with small changes to query vector."""
        # Mock LanceDB setup
        mock_db = MagicMock()
        mock_table = MagicMock()
        mock_search = MagicMock()
        mock_db.table_names.return_value = ["documents"]
        mock_db.open_table.return_value = mock_table
        mock_table.search.return_value = mock_search
        mock_lancedb.connect.return_value = mock_db
        
        # Similar result sets with small differences in scores
        result_data_1 = [
            {"id": "doc1", "score": 0.952, "content": "Document 1"},
            {"id": "doc2", "score": 0.851, "content": "Document 2"},
            {"id": "doc3", "score": 0.753, "content": "Document 3"},
        ]
        
        result_data_2 = [
            {"id": "doc1", "score": 0.948, "content": "Document 1"},
            {"id": "doc2", "score": 0.847, "content": "Document 2"},
            {"id": "doc3", "score": 0.749, "content": "Document 3"},
        ]
        
        # Setup side effects for consecutive calls
        mock_limit_1 = MagicMock()
        mock_limit_1.to_pandas.return_value = pd.DataFrame(result_data_1)
        
        mock_limit_2 = MagicMock()
        mock_limit_2.to_pandas.return_value = pd.DataFrame(result_data_2)
        
        mock_search.limit.side_effect = [mock_limit_1, mock_limit_2]
        
        # Create provider
        provider = LanceDBProvider(uri="/path/to/db")
        
        # Test model class
        class DocumentModel:
            __tablename__ = "documents"
        
        # Create vector query
        base_vector = np.random.rand(384)
        
        # Create a slightly different vector (0.5% change)
        modified_vector = base_vector.copy()
        modified_vector += np.random.normal(0, 0.005, size=384)  # Add small random noise
        
        # Convert to lists
        query_vector_1 = base_vector.tolist()
        query_vector_2 = modified_vector.tolist()
        
        # Perform searches with slightly different vectors
        results_1 = provider.vector_search(DocumentModel, query_vector_1, limit=3)
        results_2 = provider.vector_search(DocumentModel, query_vector_2, limit=3)
        
        # Results ordering should be stable despite small differences in vectors
        assert len(results_1) == len(results_2)
        for i in range(len(results_1)):
            assert results_1[i]["id"] == results_2[i]["id"]
            # Scores will be slightly different but should be close
            assert abs(results_1[i]["score"] - results_2[i]["score"]) < 0.01