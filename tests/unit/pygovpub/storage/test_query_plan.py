"""
Tests for query plan analysis and optimization for vector search operations.

This module tests query plan generation, analysis, and optimization
functionality for vector search operations across different providers.
"""

import pytest
from unittest.mock import patch, MagicMock, call

import numpy as np
import pandas as pd

from pygovpub.storage.providers.lancedb_provider import LanceDBProvider
from pygovpub.storage.query_plan import (
    QueryPlanAnalyzer,
    QueryPlan,
    VectorSearchPlan,
    HybridSearchPlan,
    QueryOptimizer
)


class TestQueryPlan:
    """Test suite for query plan data structures."""
    
    def test_query_plan_creation(self):
        """Test creating a basic query plan."""
        plan = QueryPlan(
            provider_type="lancedb",
            operation="vector_search",
            estimated_cost=10.5,
            estimated_time_ms=150
        )
        
        assert plan.provider_type == "lancedb"
        assert plan.operation == "vector_search"
        assert plan.estimated_cost == 10.5
        assert plan.estimated_time_ms == 150
        assert plan.optimizations == []
    
    def test_vector_search_plan_creation(self):
        """Test creating a specialized vector search plan."""
        plan = VectorSearchPlan(
            provider_type="lancedb",
            table_name="documents",
            vector_dim=384,
            filter_count=2,
            has_index=True,
            estimated_result_count=50,
            estimated_cost=10.5,
            estimated_time_ms=150
        )
        
        assert plan.provider_type == "lancedb"
        assert plan.operation == "vector_search"  # Should be set automatically
        assert plan.table_name == "documents"
        assert plan.vector_dim == 384
        assert plan.filter_count == 2
        assert plan.has_index is True
        assert plan.estimated_result_count == 50
        assert plan.estimated_cost == 10.5
        assert plan.estimated_time_ms == 150
    
    def test_hybrid_search_plan_creation(self):
        """Test creating a specialized hybrid search plan."""
        plan = HybridSearchPlan(
            provider_type="lancedb",
            table_name="documents",
            vector_dim=384,
            text_query_length=10,
            filter_count=2,
            has_index=True,
            estimated_result_count=50,
            estimated_cost=12.5,
            estimated_time_ms=180
        )
        
        assert plan.provider_type == "lancedb"
        assert plan.operation == "hybrid_search"  # Should be set automatically
        assert plan.table_name == "documents"
        assert plan.vector_dim == 384
        assert plan.text_query_length == 10
        assert plan.filter_count == 2
        assert plan.has_index is True
        assert plan.estimated_result_count == 50
        assert plan.estimated_cost == 12.5
        assert plan.estimated_time_ms == 180
    
    def test_query_plan_add_optimization(self):
        """Test adding optimization to a query plan."""
        plan = QueryPlan(
            provider_type="lancedb",
            operation="vector_search",
            estimated_cost=10.5,
            estimated_time_ms=150
        )
        
        # Add optimization
        plan.add_optimization("use_index", "Use vector index for faster search", cost_reduction=5.0)
        
        assert len(plan.optimizations) == 1
        assert plan.optimizations[0]["name"] == "use_index"
        assert "faster search" in plan.optimizations[0]["description"]
        assert plan.optimizations[0]["cost_reduction"] == 5.0


class TestQueryPlanAnalyzer:
    """Test suite for query plan analysis."""
    
    def test_analyzer_creation(self):
        """Test creating a query plan analyzer."""
        analyzer = QueryPlanAnalyzer()
        
        assert analyzer is not None
        assert hasattr(analyzer, "analyze_vector_search")
        assert hasattr(analyzer, "analyze_hybrid_search")
    
    @patch("pygovpub.storage.providers.lancedb_provider.LanceDBProvider")
    def test_analyze_vector_search_with_lancedb(self, mock_lancedb_provider):
        """Test analyzing a vector search query for LanceDB."""
        # Setup mock provider
        mock_provider = mock_lancedb_provider.return_value
        mock_provider.db_type = "lancedb"
        mock_provider.table_info = {
            "documents": {
                "has_vector_index": True,
                "schema": MagicMock()
            }
        }
        
        # Create analyzer
        analyzer = QueryPlanAnalyzer()
        
        # Mock model class
        class DocumentModel:
            __tablename__ = "documents"
        
        # Create query vector
        query_vector = np.random.rand(384).tolist()
        
        # Analyze vector search
        plan = analyzer.analyze_vector_search(
            provider=mock_provider,
            model_class=DocumentModel,
            query_vector=query_vector,
            filter_criteria={"category": "legal"},
            limit=10
        )
        
        # Verify plan properties
        assert isinstance(plan, VectorSearchPlan)
        assert plan.provider_type == "lancedb"
        assert plan.table_name == "documents"
        assert plan.vector_dim == 384
        assert plan.filter_count == 1
        assert plan.has_index is True
        assert plan.estimated_result_count > 0
        assert plan.estimated_cost > 0
        assert plan.estimated_time_ms > 0
    
    @patch("pygovpub.storage.providers.lancedb_provider.LanceDBProvider")
    def test_analyze_hybrid_search_with_lancedb(self, mock_lancedb_provider):
        """Test analyzing a hybrid search query for LanceDB."""
        # Setup mock provider
        mock_provider = mock_lancedb_provider.return_value
        mock_provider.db_type = "lancedb"
        mock_provider.table_info = {
            "documents": {
                "has_vector_index": True,
                "schema": MagicMock()
            }
        }
        
        # Create analyzer
        analyzer = QueryPlanAnalyzer()
        
        # Mock model class
        class DocumentModel:
            __tablename__ = "documents"
        
        # Create query vector
        query_vector = np.random.rand(384).tolist()
        query_text = "legal precedent supreme court"
        
        # Analyze hybrid search
        plan = analyzer.analyze_hybrid_search(
            provider=mock_provider,
            model_class=DocumentModel,
            query_text=query_text,
            query_vector=query_vector,
            filter_criteria={"category": "legal"},
            limit=10
        )
        
        # Verify plan properties
        assert isinstance(plan, HybridSearchPlan)
        assert plan.provider_type == "lancedb"
        assert plan.table_name == "documents"
        assert plan.vector_dim == 384
        assert plan.text_query_length == len(query_text.split())
        assert plan.filter_count == 1
        assert plan.has_index is True
        assert plan.estimated_result_count > 0
        assert plan.estimated_cost > 0
        assert plan.estimated_time_ms > 0
    
    @patch("pygovpub.storage.providers.lancedb_provider.LanceDBProvider")
    def test_analyze_vector_search_without_index(self, mock_lancedb_provider):
        """Test analyzing a vector search query for LanceDB without an index."""
        # Setup mock provider with no vector index
        mock_provider = mock_lancedb_provider.return_value
        mock_provider.db_type = "lancedb"
        mock_provider.table_info = {
            "documents": {
                "has_vector_index": False,
                "schema": MagicMock()
            }
        }
        
        # Create analyzer
        analyzer = QueryPlanAnalyzer()
        
        # Mock model class
        class DocumentModel:
            __tablename__ = "documents"
        
        # Create query vector
        query_vector = np.random.rand(384).tolist()
        
        # Analyze vector search
        plan = analyzer.analyze_vector_search(
            provider=mock_provider,
            model_class=DocumentModel,
            query_vector=query_vector,
            limit=10
        )
        
        # Verify plan properties
        assert isinstance(plan, VectorSearchPlan)
        assert plan.has_index is False
        assert plan.estimated_cost > 0
        # Non-indexed search should have higher cost than indexed search
        assert plan.estimated_cost > 20  # Arbitrary threshold for higher cost


class TestQueryOptimizer:
    """Test suite for query optimization."""
    
    def test_optimizer_creation(self):
        """Test creating a query optimizer."""
        optimizer = QueryOptimizer()
        
        assert optimizer is not None
        assert hasattr(optimizer, "optimize")
    
    def test_optimize_vector_search_with_index(self):
        """Test optimizing a vector search query with an index."""
        # Create a vector search plan
        plan = VectorSearchPlan(
            provider_type="lancedb",
            table_name="documents",
            vector_dim=384,
            filter_count=3,
            has_index=True,
            estimated_result_count=100,
            estimated_cost=15.0,
            estimated_time_ms=200
        )
        
        # Create optimizer
        optimizer = QueryOptimizer()
        
        # Optimize plan
        optimized_plan = optimizer.optimize(plan)
        
        # Verify optimizations
        assert len(optimized_plan.optimizations) > 0
        assert any("index" in opt["description"].lower() for opt in optimized_plan.optimizations)
    
    def test_optimize_vector_search_without_index(self):
        """Test optimizing a vector search query without an index."""
        # Create a vector search plan with no index
        plan = VectorSearchPlan(
            provider_type="lancedb",
            table_name="documents",
            vector_dim=384,
            filter_count=0,
            has_index=False,
            estimated_result_count=100,
            estimated_cost=25.0,
            estimated_time_ms=350
        )
        
        # Create optimizer
        optimizer = QueryOptimizer()
        
        # Optimize plan
        optimized_plan = optimizer.optimize(plan)
        
        # Verify optimizations
        assert len(optimized_plan.optimizations) > 0
        assert any("create index" in opt["description"].lower() for opt in optimized_plan.optimizations)
    
    def test_optimize_hybrid_search_many_filters(self):
        """Test optimizing a hybrid search query with many filters."""
        # Create a hybrid search plan with many filters
        plan = HybridSearchPlan(
            provider_type="lancedb",
            table_name="documents",
            vector_dim=384,
            text_query_length=20,
            filter_count=8,  # Many filters
            has_index=True,
            estimated_result_count=10,
            estimated_cost=30.0,
            estimated_time_ms=450
        )
        
        # Create optimizer
        optimizer = QueryOptimizer()
        
        # Optimize plan
        optimized_plan = optimizer.optimize(plan)
        
        # Verify optimizations - should suggest reducing filters
        assert any("filter" in opt["description"].lower() for opt in optimized_plan.optimizations)
    
    def test_optimize_hybrid_search_long_text(self):
        """Test optimizing a hybrid search query with long text."""
        # Create a hybrid search plan with long text
        plan = HybridSearchPlan(
            provider_type="lancedb",
            table_name="documents",
            vector_dim=384,
            text_query_length=50,  # Very long query
            filter_count=1,
            has_index=True,
            estimated_result_count=5,
            estimated_cost=35.0,
            estimated_time_ms=500
        )
        
        # Create optimizer
        optimizer = QueryOptimizer()
        
        # Optimize plan
        optimized_plan = optimizer.optimize(plan)
        
        # Verify optimizations - should suggest reducing text length
        assert any("text" in opt["description"].lower() for opt in optimized_plan.optimizations)