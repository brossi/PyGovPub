"""
Integration tests for search functionality.

These tests verify:
1. Integration between search manager, providers, and API clients
2. Cross-source search with normalization of results
3. Search query parameter validation across all provider types
4. Performance characteristics of search operations
"""

import asyncio
import logging
import os
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from unittest.mock import patch, AsyncMock

import pytest
from httpx import Response
from pydantic import BaseModel

from pygovpub.auth.auth_manager import AuthManager
from pygovpub.auth.models import ApiSource, AuthRequest
from pygovpub.api.clients.congress import CongressClient
from pygovpub.api.clients.govinfo import GovInfoClient
from pygovpub.search.core import (
    SearchManager, SearchProvider, SearchQuery, SearchResult, 
    SearchResults, SearchResultType, SearchOperator, QueryComponent
)
from pygovpub.search.factory import create_search_manager, create_local_search_manager
from pygovpub.search.providers import LocalProvider, GovInfoProvider, CongressProvider


class MockAuthManager:
    """Mock authentication manager for testing."""
    
    def __init__(self, api_keys: Dict[str, str] = None):
        """Initialize with predefined API keys."""
        self.api_keys = api_keys or {
            "congress": "test_congress_key",
            "govinfo": "test_govinfo_key"
        }
        self.calls = []
    
    async def authenticate_request(self, source: ApiSource, endpoint: str) -> AuthRequest:
        """Provide mock authentication for the specified source."""
        self.calls.append((source, endpoint))
        
        if source == ApiSource.CONGRESS:
            return AuthRequest(
                api_key=self.api_keys.get("congress"),
                headers={"X-API-Key": self.api_keys.get("congress")},
                params={},
                source=source
            )
        elif source == ApiSource.GOVINFO:
            return AuthRequest(
                api_key=self.api_keys.get("govinfo"),
                headers={},
                params={"api_key": self.api_keys.get("govinfo")},
                source=source
            )
        
        return None


class MockCongressClient:
    """Mock Congress.gov API client for testing."""
    
    def __init__(self, auth_manager=None):
        """Initialize mock client."""
        self.auth_manager = auth_manager
        self.search_called = False
        self.search_params = None
        self.mock_results = []
    
    def set_mock_results(self, results: List[Dict[str, Any]]):
        """Set mock results for search."""
        self.mock_results = results
    
    async def search(self, query: str, **params) -> Dict[str, Any]:
        """Simulate search operation."""
        self.search_called = True
        self.search_params = {"query": query, **params}
        
        # Return mock response structure
        return {
            "pagination": {
                "count": len(self.mock_results),
                "offset": params.get("offset", 0),
                "limit": params.get("limit", 20)
            },
            "results": self.mock_results
        }


class MockGovInfoClient:
    """Mock GovInfo.gov API client for testing."""
    
    def __init__(self, auth_manager=None):
        """Initialize mock client."""
        self.auth_manager = auth_manager
        self.search_called = False
        self.search_params = None
        self.mock_results = []
    
    def set_mock_results(self, results: List[Dict[str, Any]]):
        """Set mock results for search."""
        self.mock_results = results
    
    async def search_packages(self, query: str, **params) -> Dict[str, Any]:
        """Simulate search operation."""
        self.search_called = True
        self.search_params = {"query": query, **params}
        
        # Return mock response structure
        return {
            "count": len(self.mock_results),
            "offset": params.get("offset", 0),
            "pageSize": params.get("pageSize", 20),
            "packages": self.mock_results
        }


@pytest.fixture
def mock_auth_manager():
    """Create a mock authentication manager."""
    return MockAuthManager()


@pytest.fixture
def mock_congress_client(mock_auth_manager):
    """Create a mock Congress client."""
    client = MockCongressClient(auth_manager=mock_auth_manager)
    
    # Set up some mock search results
    client.set_mock_results([
        {
            "id": "hr1234-117",
            "title": "Mock HR Bill",
            "congress": 117,
            "type": "hr",
            "number": "1234",
            "updateDate": "2025-01-15",
            "url": "https://api.congress.gov/v3/bill/117/hr/1234"
        },
        {
            "id": "s5678-117",
            "title": "Mock Senate Bill",
            "congress": 117,
            "type": "s",
            "number": "5678",
            "updateDate": "2025-02-10",
            "url": "https://api.congress.gov/v3/bill/117/s/5678"
        }
    ])
    
    return client


@pytest.fixture
def mock_govinfo_client(mock_auth_manager):
    """Create a mock GovInfo client."""
    client = MockGovInfoClient(auth_manager=mock_auth_manager)
    
    # Set up some mock search results
    client.set_mock_results([
        {
            "packageId": "BILLS-117hr1234ih",
            "title": "Mock HR Bill - GovInfo Version",
            "lastModified": "2025-01-20",
            "packageLink": "https://api.govinfo.gov/packages/BILLS-117hr1234ih",
            "docClass": "billStatus",
            "congress": 117,
            "billType": "hr",
            "billNumber": "1234"
        },
        {
            "packageId": "CRPT-117hrpt123",
            "title": "Mock Committee Report",
            "lastModified": "2025-03-01",
            "packageLink": "https://api.govinfo.gov/packages/CRPT-117hrpt123",
            "docClass": "crpt"
        }
    ])
    
    return client


@pytest.fixture
def patched_clients(mock_congress_client, mock_govinfo_client):
    """
    Patch the client creation functions to return mock clients.
    
    This allows the search factory to create search providers with
    mock clients instead of real ones that would try to access external APIs.
    """
    with patch("pygovpub.search.factory.CongressClient", return_value=mock_congress_client):
        with patch("pygovpub.search.factory.GovInfoClient", return_value=mock_govinfo_client):
            yield {
                "congress": mock_congress_client,
                "govinfo": mock_govinfo_client
            }


@pytest.mark.asyncio
async def test_search_manager_creation(mock_auth_manager, patched_clients):
    """Test creating a search manager with all provider types."""
    # Create a search manager through the factory
    manager = await create_search_manager(
        auth_manager=mock_auth_manager,
        include_local=True,
        include_govinfo=True,
        include_congress=True
    )
    
    # Verify all providers were registered
    assert len(manager.providers) == 3
    assert "local" in manager.providers
    assert "govinfo" in manager.providers
    assert "congress" in manager.providers
    
    # Verify authentication was called for both API clients
    assert len(mock_auth_manager.calls) == 2
    assert (ApiSource.GOVINFO, "/") in mock_auth_manager.calls
    assert (ApiSource.CONGRESS, "/") in mock_auth_manager.calls
    
    # Cleanup
    await manager.shutdown()


@pytest.mark.asyncio
async def test_search_across_providers(mock_auth_manager, patched_clients):
    """Test searching across multiple providers."""
    # Create a search manager
    manager = await create_search_manager(
        auth_manager=mock_auth_manager,
        include_local=True,
        include_govinfo=True,
        include_congress=True
    )
    
    # Add a document to the local provider for more comprehensive results
    local_provider = manager.providers["local"]
    await local_provider.add_document(
        id="local-doc-1",
        title="Mock Local Document",
        content="This is a test document for local search",
        metadata={"source": "local"},
        type=SearchResultType.DOCUMENT
    )
    
    # Perform a search across all providers
    query = SearchQuery(query_text="mock")
    results = await manager.search(query)
    
    # Verify results include items from all providers
    assert results.total == 5  # 2 from Congress + 2 from GovInfo + 1 from local
    
    # Verify the sources of results
    sources = {result.source for result in results.results}
    assert sources == {"congress", "govinfo", "local"}
    
    # Verify source counts
    assert results.source_counts["congress"] == 2
    assert results.source_counts["govinfo"] == 2
    assert results.source_counts["local"] == 1
    
    # Verify results were sorted by score
    assert all(results.results[i].score >= results.results[i+1].score 
               for i in range(len(results.results)-1))
    
    # Cleanup
    await manager.shutdown()


@pytest.mark.asyncio
async def test_search_with_filtering(mock_auth_manager, patched_clients):
    """Test search with filtering by source and result type."""
    # Create a search manager
    manager = await create_search_manager(
        auth_manager=mock_auth_manager,
        include_local=True,
        include_govinfo=True,
        include_congress=True
    )
    
    # Test filtering by source
    congress_query = SearchQuery(
        query_text="mock", 
        sources=["congress"]
    )
    congress_results = await manager.search(congress_query)
    
    # Verify only Congress results
    assert congress_results.total == 2
    assert all(result.source == "congress" for result in congress_results.results)
    
    # Test filtering by result type
    bill_query = SearchQuery(
        query_text="mock", 
        result_types=[SearchResultType.BILL]
    )
    bill_results = await manager.search(bill_query)
    
    # Verify only bill results
    assert all(result.type == SearchResultType.BILL for result in bill_results.results)
    
    # Cleanup
    await manager.shutdown()


@pytest.mark.asyncio
async def test_advanced_query_components(mock_auth_manager, patched_clients):
    """Test search with advanced query components."""
    # Create a search manager
    manager = await create_search_manager(
        auth_manager=mock_auth_manager,
        include_local=True,
        include_govinfo=True,
        include_congress=True
    )
    
    # Add some local documents for testing with specific fields
    local_provider = manager.providers["local"]
    await local_provider.add_document(
        id="local-hr-1000",
        title="HR 1000 - Test Bill",
        content="This is a test bill for advanced queries",
        metadata={"congress": 117, "billType": "hr", "billNumber": "1000"},
        type=SearchResultType.BILL
    )
    await local_provider.add_document(
        id="local-s-2000",
        title="S 2000 - Another Test Bill",
        content="This is another test bill for advanced queries",
        metadata={"congress": 117, "billType": "s", "billNumber": "2000"},
        type=SearchResultType.BILL
    )
    
    # Create an advanced query using components
    query = SearchQuery(
        components=[
            QueryComponent(
                operator=SearchOperator.AND,
                sub_components=[
                    QueryComponent(field="title", value="bill", boost=2.0),
                    QueryComponent(
                        operator=SearchOperator.OR,
                        sub_components=[
                            QueryComponent(field="metadata.billType", value="hr"),
                            QueryComponent(field="metadata.billType", value="s")
                        ]
                    )
                ]
            )
        ]
    )
    
    # Execute the search
    results = await manager.search(query)
    
    # Verify we got structured search results
    assert results.total > 0
    
    # Cleanup
    await manager.shutdown()


@pytest.mark.asyncio
async def test_search_performance(mock_auth_manager, patched_clients):
    """Test search performance characteristics."""
    # Create a search manager
    manager = await create_search_manager(
        auth_manager=mock_auth_manager,
        include_local=True,
        include_govinfo=True,
        include_congress=True
    )
    
    # Add a larger number of documents to local provider for performance testing
    local_provider = manager.providers["local"]
    for i in range(100):
        await local_provider.add_document(
            id=f"local-doc-{i}",
            title=f"Performance Test Document {i}",
            content=f"This is document {i} for performance testing with some common keywords",
            metadata={"index": i, "category": "performance"},
            type=SearchResultType.DOCUMENT
        )
    
    # Measure search execution time
    start_time = time.time()
    
    query = SearchQuery(query_text="performance")
    results = await manager.search(query)
    
    end_time = time.time()
    execution_time_ms = (end_time - start_time) * 1000
    
    # Verify we got results
    assert results.total > 0
    
    # Check that execution time is reasonable (< 500ms for local search)
    # This is a soft assertion since actual performance depends on the environment
    assert execution_time_ms < 500, f"Search took too long: {execution_time_ms:.2f}ms"
    
    # Verify each provider reported its execution time
    assert results.execution_time_ms > 0
    
    # Check pagination performance
    start_time = time.time()
    
    paginated_query = SearchQuery(query_text="performance", offset=50, limit=10)
    paginated_results = await manager.search(paginated_query)
    
    end_time = time.time()
    pagination_time_ms = (end_time - start_time) * 1000
    
    # Verify pagination worked correctly
    assert paginated_results.total == results.total  # Same total count
    assert len(paginated_results.results) == 10  # Limited to 10 results
    
    # Cleanup
    await manager.shutdown()


@pytest.mark.asyncio
async def test_search_resilience(mock_auth_manager, patched_clients):
    """Test search resilience when a provider fails."""
    # Create a search manager
    manager = await create_search_manager(
        auth_manager=mock_auth_manager,
        include_local=True,
        include_govinfo=True,
        include_congress=True
    )
    
    # Add a document to the local provider
    local_provider = manager.providers["local"]
    await local_provider.add_document(
        id="local-doc-resilience",
        title="Resilience Test Document",
        content="This is a test document for resilience testing",
        metadata={"source": "local", "category": "resilience"},
        type=SearchResultType.DOCUMENT
    )
    
    # Make the GovInfo provider fail
    govinfo_provider = manager.providers["govinfo"]
    with patch.object(
        govinfo_provider, "search", 
        side_effect=Exception("Simulated GovInfo provider failure")
    ):
        # Search should still work, just with fewer results
        query = SearchQuery(query_text="test")
        results = await manager.search(query)
        
        # Verify we still got results from functioning providers
        assert results.total > 0
        assert "congress" in results.source_counts
        assert "local" in results.source_counts
        assert "govinfo" not in results.source_counts
    
    # Cleanup
    await manager.shutdown()


@pytest.mark.asyncio
async def test_cross_source_normalization(mock_auth_manager, patched_clients):
    """Test that results from different sources are normalized correctly."""
    # Create a search manager
    manager = await create_search_manager(
        auth_manager=mock_auth_manager,
        include_local=False,  # Exclude local to focus on API normalization
        include_govinfo=True,
        include_congress=True
    )
    
    # Search for a bill that exists in both sources
    query = SearchQuery(query_text="hr1234")
    results = await manager.search(query)
    
    # Find the same bill from different sources
    congress_bill = next((r for r in results.results if r.source == "congress" and "1234" in r.result_id), None)
    govinfo_bill = next((r for r in results.results if r.source == "govinfo" and "1234" in r.result_id), None)
    
    # Verify we found the bill in both sources
    assert congress_bill is not None
    assert govinfo_bill is not None
    
    # Verify the normalized fields match
    assert congress_bill.type == govinfo_bill.type == SearchResultType.BILL
    assert "HR Bill" in congress_bill.title
    assert "HR Bill" in govinfo_bill.title
    
    # Check that dates are properly normalized
    assert isinstance(congress_bill.date, datetime)
    assert isinstance(govinfo_bill.date, datetime)
    
    # Verify metadata normalization
    assert congress_bill.metadata.get("congress") == govinfo_bill.metadata.get("congress") == 117
    assert congress_bill.metadata.get("billType", "").lower() == "hr"
    assert govinfo_bill.metadata.get("billType", "").lower() == "hr"
    assert congress_bill.metadata.get("billNumber", "").lower() == "1234"
    assert govinfo_bill.metadata.get("billNumber", "").lower() == "1234"
    
    # Cleanup
    await manager.shutdown()


@pytest.mark.asyncio
async def test_local_only_search_factory():
    """Test creating a local-only search manager."""
    # Create a local-only search manager
    manager = await create_local_search_manager()
    
    # Verify only local provider was registered
    assert len(manager.providers) == 1
    assert "local" in manager.providers
    
    # Add a document
    local_provider = manager.providers["local"]
    await local_provider.add_document(
        id="local-only-doc",
        title="Local Only Test",
        content="This document is only in the local provider",
        metadata={},
        type=SearchResultType.DOCUMENT
    )
    
    # Search
    query = SearchQuery(query_text="local only")
    results = await manager.search(query)
    
    # Verify results
    assert results.total == 1
    assert results.results[0].title == "Local Only Test"
    
    # Cleanup
    await manager.shutdown()