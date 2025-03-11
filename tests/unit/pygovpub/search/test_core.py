"""
Unit tests for the search core module.
"""

import asyncio
import logging
from datetime import datetime
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
from pydantic import ValidationError

from pygovpub.search.core import (
    SearchManager, SearchProvider, SearchQuery, SearchResult, 
    SearchResults, SearchResultType, SearchOperator, 
    QueryComponent, Highlight, Facet
)


class MockSearchProvider(SearchProvider):
    """Mock search provider for testing."""
    
    provider_name = "mock"
    supported_types = [SearchResultType.BILL, SearchResultType.DOCUMENT]
    
    def __init__(self):
        """Initialize mock provider."""
        self.search_called = False
        self.initialize_called = False
        self.shutdown_called = False
        self.mock_results = None
    
    def set_mock_results(self, results):
        """Set mock results to return."""
        self.mock_results = results
    
    async def search(self, query: SearchQuery) -> SearchResults:
        """Execute mock search."""
        self.search_called = True
        
        if self.mock_results:
            return self.mock_results
        
        # Return empty results by default
        return SearchResults(
            total=0,
            query=query,
            results=[],
            execution_time_ms=10
        )
    
    async def initialize(self) -> None:
        """Mock initialization."""
        self.initialize_called = True
    
    async def shutdown(self) -> None:
        """Mock shutdown."""
        self.shutdown_called = True


class ErrorSearchProvider(SearchProvider):
    """Search provider that raises errors for testing."""
    
    provider_name = "error"
    supported_types = [SearchResultType.DOCUMENT]
    
    async def search(self, query: SearchQuery) -> SearchResults:
        """Raise an exception when searching."""
        raise ValueError("Mock search error")
    
    async def initialize(self) -> None:
        """Raise an exception when initializing."""
        raise ValueError("Mock initialization error")
    
    async def shutdown(self) -> None:
        """Raise an exception when shutting down."""
        raise ValueError("Mock shutdown error")


class TestSearchQuery:
    """Tests for the SearchQuery model."""
    
    def test_search_query_validation(self):
        """Test search query validation."""
        # Valid query with text
        query = SearchQuery(query_text="test")
        assert query.query_text == "test"
        assert len(query.components) == 0
        
        # Valid query with components
        query = SearchQuery(components=[
            QueryComponent(field="title", value="test")
        ])
        assert query.query_text is None
        assert len(query.components) == 1
        
        # Valid query with both
        query = SearchQuery(
            query_text="test",
            components=[QueryComponent(field="title", value="advanced")]
        )
        assert query.query_text == "test"
        assert len(query.components) == 1
        
        # Invalid query with neither
        with pytest.raises(ValidationError):
            SearchQuery(query_text=None, components=[])
    
    def test_query_component(self):
        """Test query component creation."""
        # Basic component
        component = QueryComponent(field="title", value="test")
        assert component.field == "title"
        assert component.value == "test"
        assert component.operator == SearchOperator.AND
        assert component.boost == 1.0
        
        # Component with custom operator and boost
        component = QueryComponent(
            field="content", 
            value="test",
            operator=SearchOperator.OR,
            boost=2.0
        )
        assert component.operator == SearchOperator.OR
        assert component.boost == 2.0
        
        # Component with sub-components
        component = QueryComponent(
            operator=SearchOperator.OR,
            sub_components=[
                QueryComponent(field="title", value="test"),
                QueryComponent(field="content", value="example")
            ]
        )
        assert len(component.sub_components) == 2
        assert component.sub_components[0].field == "title"


class TestSearchProvider:
    """Tests for the SearchProvider base class."""
    
    def test_provider_initialization(self):
        """Test provider initialization."""
        provider = MockSearchProvider()
        assert provider.provider_name == "mock"
        assert SearchResultType.BILL in provider.supported_types
        assert SearchResultType.DOCUMENT in provider.supported_types
    
    async def test_can_handle(self):
        """Test can_handle method."""
        provider = MockSearchProvider()
        
        # Should handle query with no sources specified
        query = SearchQuery(query_text="test")
        assert provider.can_handle(query) is True
        
        # Should handle query with matching source
        query = SearchQuery(query_text="test", sources=["mock"])
        assert provider.can_handle(query) is True
        
        # Should not handle query with non-matching source
        query = SearchQuery(query_text="test", sources=["other"])
        assert provider.can_handle(query) is False
        
        # Should handle query with multiple sources including match
        query = SearchQuery(query_text="test", sources=["other", "mock"])
        assert provider.can_handle(query) is True


class TestSearchManager:
    """Tests for the SearchManager class."""
    
    @pytest.fixture
    def search_manager(self):
        """Create a search manager for testing."""
        return SearchManager()
    
    @pytest.fixture
    def mock_provider(self):
        """Create a mock search provider."""
        return MockSearchProvider()
    
    @pytest.fixture
    def error_provider(self):
        """Create an error-raising search provider."""
        return ErrorSearchProvider()
    
    @pytest.fixture
    def sample_query(self):
        """Create a sample search query."""
        return SearchQuery(query_text="test")
    
    @pytest.fixture
    def sample_results(self, sample_query):
        """Create sample search results."""
        results = [
            SearchResult(
                result_id="1",
                type=SearchResultType.BILL,
                source="mock",
                title="Test Bill",
                score=0.9,
                metadata={"congress": 117, "bill_type": "hr", "number": 1234}
            ),
            SearchResult(
                result_id="2",
                type=SearchResultType.DOCUMENT,
                source="mock",
                title="Test Document",
                score=0.8,
                date=datetime.now(),
                metadata={"document_type": "report"}
            )
        ]
        
        return SearchResults(
            total=2,
            query=sample_query,
            results=results,
            execution_time_ms=50,
            source_counts={"mock": 2}
        )
    
    def test_initialization(self, search_manager):
        """Test SearchManager initialization."""
        assert search_manager.providers == {}
        assert search_manager.initialized is False
    
    def test_register_provider(self, search_manager, mock_provider):
        """Test registering a provider."""
        search_manager.register_provider(mock_provider)
        
        assert "mock" in search_manager.providers
        assert search_manager.providers["mock"] is mock_provider
    
    async def test_initialize(self, search_manager, mock_provider):
        """Test initializing providers."""
        # Register provider
        search_manager.register_provider(mock_provider)
        
        # Initialize
        await search_manager.initialize()
        
        # Verify provider was initialized
        assert mock_provider.initialize_called is True
        assert search_manager.initialized is True
        
        # Initialize again should be a no-op
        mock_provider.initialize_called = False
        await search_manager.initialize()
        assert mock_provider.initialize_called is False
    
    async def test_initialize_with_error(self, search_manager, mock_provider, error_provider, caplog):
        """Test initializing providers with one that raises an error."""
        # Register providers
        search_manager.register_provider(mock_provider)
        search_manager.register_provider(error_provider)
        
        # Initialize with caplog to capture log messages
        with caplog.at_level(logging.ERROR):
            await search_manager.initialize()
        
        # Verify successful provider was initialized
        assert mock_provider.initialize_called is True
        
        # Verify error was logged
        assert "Failed to initialize search provider error" in caplog.text
        
        # Verify manager is still marked as initialized
        assert search_manager.initialized is True
    
    async def test_shutdown(self, search_manager, mock_provider):
        """Test shutting down providers."""
        # Register and initialize provider
        search_manager.register_provider(mock_provider)
        await search_manager.initialize()
        
        # Shutdown
        await search_manager.shutdown()
        
        # Verify provider was shut down
        assert mock_provider.shutdown_called is True
        assert search_manager.initialized is False
    
    async def test_shutdown_with_error(self, search_manager, mock_provider, error_provider, caplog):
        """Test shutting down providers with one that raises an error."""
        # Register providers
        search_manager.register_provider(mock_provider)
        search_manager.register_provider(error_provider)
        await search_manager.initialize()
        
        # Shutdown with caplog to capture log messages
        with caplog.at_level(logging.ERROR):
            await search_manager.shutdown()
        
        # Verify successful provider was shut down
        assert mock_provider.shutdown_called is True
        
        # Verify error was logged
        assert "Failed to shut down search provider error" in caplog.text
        
        # Verify manager is marked as not initialized
        assert search_manager.initialized is False
    
    async def test_search_empty(self, search_manager, sample_query):
        """Test search with no providers."""
        # Search without any providers
        results = await search_manager.search(sample_query)
        
        # Verify empty results
        assert results.total == 0
        assert len(results.results) == 0
    
    async def test_search_single_provider(self, search_manager, mock_provider, sample_query, sample_results):
        """Test search with a single provider."""
        # Register provider and set mock results
        search_manager.register_provider(mock_provider)
        mock_provider.set_mock_results(sample_results)
        
        # Search
        results = await search_manager.search(sample_query)
        
        # Verify provider was initialized and searched
        assert mock_provider.initialize_called is True
        assert mock_provider.search_called is True
        
        # Verify results
        assert results.total == 2
        assert len(results.results) == 2
        assert results.results[0].result_id == "1"
        assert results.results[1].result_id == "2"
        assert "mock" in results.source_counts
        assert results.source_counts["mock"] == 2
    
    async def test_search_multiple_providers(self, search_manager, mock_provider, sample_query):
        """Test search with multiple providers."""
        # Create two providers with different results
        provider1 = MockSearchProvider()
        provider1.provider_name = "mock1"
        provider1.set_mock_results(SearchResults(
            total=1,
            query=sample_query,
            results=[
                SearchResult(
                    result_id="1",
                    type=SearchResultType.BILL,
                    source="mock1",
                    title="Result from Provider 1",
                    score=0.9
                )
            ],
            execution_time_ms=10,
            source_counts={"mock1": 1}
        ))
        
        provider2 = MockSearchProvider()
        provider2.provider_name = "mock2"
        provider2.set_mock_results(SearchResults(
            total=1,
            query=sample_query,
            results=[
                SearchResult(
                    result_id="2",
                    type=SearchResultType.DOCUMENT,
                    source="mock2",
                    title="Result from Provider 2",
                    score=0.8
                )
            ],
            execution_time_ms=20,
            source_counts={"mock2": 1}
        ))
        
        # Register providers
        search_manager.register_provider(provider1)
        search_manager.register_provider(provider2)
        
        # Search
        results = await search_manager.search(sample_query)
        
        # Verify results
        assert results.total == 2
        assert len(results.results) == 2
        
        # Results should be sorted by score (highest first)
        assert results.results[0].result_id == "1"
        assert results.results[0].score == 0.9
        assert results.results[1].result_id == "2"
        assert results.results[1].score == 0.8
        
        # Source counts should include both providers
        assert results.source_counts["mock1"] == 1
        assert results.source_counts["mock2"] == 1
    
    async def test_search_with_filters(self, search_manager, mock_provider, sample_results):
        """Test search with filtered providers."""
        # Register provider
        search_manager.register_provider(mock_provider)
        mock_provider.set_mock_results(sample_results)
        
        # Create query that filters out the mock provider
        query = SearchQuery(query_text="test", sources=["other"])
        
        # Search
        results = await search_manager.search(query)
        
        # Verify provider was not searched
        assert mock_provider.search_called is False
        
        # Verify empty results
        assert results.total == 0
        assert len(results.results) == 0
    
    async def test_search_with_provider_error(self, search_manager, mock_provider, error_provider, sample_query, caplog):
        """Test search with a provider that raises an error."""
        # Register both providers
        search_manager.register_provider(mock_provider)
        search_manager.register_provider(error_provider)
        
        # Set mock results for the successful provider
        mock_provider.set_mock_results(SearchResults(
            total=1,
            query=sample_query,
            results=[
                SearchResult(
                    result_id="1",
                    type=SearchResultType.BILL,
                    source="mock",
                    title="Test Result",
                    score=0.9
                )
            ],
            execution_time_ms=10,
            source_counts={"mock": 1}
        ))
        
        # Search with caplog to capture log messages
        with caplog.at_level(logging.ERROR):
            results = await search_manager.search(sample_query)
        
        # Verify successful provider was searched
        assert mock_provider.search_called is True
        
        # Verify error was logged
        assert "Error searching with provider error" in caplog.text
        
        # Verify results from successful provider
        assert results.total == 1
        assert len(results.results) == 1
        assert results.results[0].result_id == "1"
        assert "mock" in results.source_counts
    
    async def test_search_pagination(self, search_manager, mock_provider, sample_query):
        """Test search pagination."""
        # Create many results
        results = []
        for i in range(30):
            results.append(SearchResult(
                result_id=str(i),
                type=SearchResultType.DOCUMENT,
                source="mock",
                title=f"Result {i}",
                score=1.0 - (i * 0.01)  # Decreasing scores
            ))
        
        # Set up provider
        search_manager.register_provider(mock_provider)
        mock_provider.set_mock_results(SearchResults(
            total=30,
            query=sample_query,
            results=results,
            execution_time_ms=100,
            source_counts={"mock": 30}
        ))
        
        # Test first page (default is 20 items)
        results = await search_manager.search(sample_query)
        assert len(results.results) == 20
        assert results.results[0].result_id == "0"  # Highest score
        assert results.results[19].result_id == "19"
        
        # Test second page
        query = SearchQuery(query_text="test", offset=20, limit=10)
        results = await search_manager.search(query)
        assert len(results.results) == 10
        assert results.results[0].result_id == "20"
        assert results.results[9].result_id == "29"


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])