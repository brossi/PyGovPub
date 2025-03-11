"""
Tests for the search router endpoints.

This module tests the search router endpoints for metadata and combined search functionality.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI, APIRouter, Query
from typing import List, Optional, Dict, Any, Union

import pygovpub.api.routers.search as search_module
from pygovpub.api.router import ApiRouter
from pygovpub.auth.models import ApiSource
from pygovpub.exceptions import ApiError, SourceUnavailableError

# Create a test-specific router to override dependencies
test_router = APIRouter(
    prefix="/search",
    tags=["Search"],
    responses={
        404: {"description": "No results found"},
        429: {"description": "Rate limit exceeded"},
        503: {"description": "Source unavailable"}
    }
)

# Mock API router for dependency injection
mock_api_router = None


def setup_test_module():
    """Set up the test module with the mocked router."""
    # Copy all endpoint functions from the search_module to test_router
    # But override the dependency injection
    
    # Copy metadata search endpoint
    @test_router.get(
        "/metadata",
        response_model=search_module.MetadataSearchResponse,
        summary="Search by metadata",
        description="Search for documents using metadata fields and filters"
    )
    async def search_by_metadata(
        document_type: Optional[str] = Query(None, description="Document type (e.g., BILL, FR, CFR)"),
        source: Optional[str] = Query(None, description="Source API (govinfo, congress)"),
        start_date: Optional[str] = Query(None, description="Start date for filtering (YYYY-MM-DD)"),
        end_date: Optional[str] = Query(None, description="End date for filtering (YYYY-MM-DD)"),
        congress: Optional[int] = Query(None, description="Congress number (e.g., 117)"),
        bill_type: Optional[str] = Query(None, description="Bill type (e.g., hr, s)"),
        cfr_title: Optional[int] = Query(None, description="CFR title number"),
        court: Optional[str] = Query(None, description="Court identifier (e.g., SCOTUS, CA9)"),
        metadata_fields: Optional[List[str]] = Query(None, description="Metadata fields to return"),
        include_facets: bool = Query(False, description="Include facets in the response"),
        offset: int = Query(0, description="Result offset"),
        limit: int = Query(20, description="Result limit"),
    ):
        """Testing version of search by metadata."""
        global mock_api_router
        return await search_module.search_by_metadata(
            document_type=document_type,
            source=source,
            start_date=start_date,
            end_date=end_date,
            congress=congress,
            bill_type=bill_type,
            cfr_title=cfr_title,
            court=court,
            metadata_fields=metadata_fields,
            include_facets=include_facets,
            offset=offset,
            limit=limit,
            api_router=mock_api_router["router"]
        )
    
    # Copy combined search endpoint
    @test_router.get(
        "/combined",
        response_model=search_module.CombinedSearchResponse,
        summary="Combined search",
        description="Search across all data sources with both full-text and metadata filtering"
    )
    async def combined_search(
        query: str = Query(..., description="Search query text"),
        document_type: Optional[str] = Query(None, description="Document type (e.g., BILL, FR, CFR)"),
        source: Optional[str] = Query(None, description="Source API (govinfo, congress)"),
        start_date: Optional[str] = Query(None, description="Start date for filtering (YYYY-MM-DD)"),
        end_date: Optional[str] = Query(None, description="End date for filtering (YYYY-MM-DD)"),
        include_highlights: bool = Query(True, description="Include search term highlights"),
        include_facets: bool = Query(False, description="Include facets in the response"),
        offset: int = Query(0, description="Result offset"),
        limit: int = Query(20, description="Result limit"),
    ):
        """Testing version of combined search."""
        global mock_api_router
        return await search_module.combined_search(
            query=query,
            document_type=document_type,
            source=source,
            start_date=start_date,
            end_date=end_date,
            include_highlights=include_highlights,
            include_facets=include_facets,
            offset=offset,
            limit=limit,
            api_router=mock_api_router["router"]
        )


@pytest.fixture(scope="module", autouse=True)
def setup_test_app():
    """Set up the test app with our mocked router."""
    setup_test_module()
    app = FastAPI()
    app.include_router(test_router)
    client = TestClient(app)
    return client


@pytest.fixture
def test_client(setup_test_app):
    """Get the test client."""
    return setup_test_app


@pytest.fixture
def setup_mocks():
    """Set up mock clients."""
    global mock_api_router
    # Create mock govinfo client
    mock_govinfo_client = AsyncMock()
    mock_govinfo_client.search_packages = AsyncMock()
    
    # Create mock congress client
    mock_congress_client = AsyncMock()
    mock_congress_client.search_bills = AsyncMock()
    mock_congress_client.search_members = AsyncMock()
    mock_congress_client.search = AsyncMock()
    
    # Create mock router
    mock_router = MagicMock(spec=ApiRouter)
    mock_router.get_client = MagicMock()
    
    # Configure get_client to return appropriate mock client
    def mock_get_client(source):
        if source == ApiSource.GOVINFO:
            return mock_govinfo_client
        elif source == ApiSource.CONGRESS:
            return mock_congress_client
        return None
    
    mock_router.get_client.side_effect = mock_get_client
    
    mock_api_router = {
        "router": mock_router,
        "govinfo_client": mock_govinfo_client,
        "congress_client": mock_congress_client
    }
    
    return mock_api_router


# Test cases for the metadata search endpoint
@pytest.mark.asyncio
async def test_metadata_search_success(test_client, setup_mocks):
    """Test successful metadata search with both sources."""
    # Mock data
    govinfo_response = {
        "count": 2,
        "packages": [
            {
                "packageId": "BILLS-117hr1234ih",
                "title": "Example Bill Title",
                "dateIssued": "2023-01-15",
                "detailsLink": "https://www.govinfo.gov/app/details/BILLS-117hr1234ih",
                "metadata": {
                    "congress": "117",
                    "billType": "hr"
                }
            },
            {
                "packageId": "BILLS-117s5678is",
                "title": "Another Bill Title",
                "dateIssued": "2023-02-20",
                "detailsLink": "https://www.govinfo.gov/app/details/BILLS-117s5678is",
                "metadata": {
                    "congress": "117",
                    "billType": "s"
                }
            }
        ]
    }
    
    congress_bills_response = {
        "count": 1,
        "bills": [
            {
                "congress": 117,
                "type": "hr",
                "number": 9876,
                "title": "Congress API Bill",
                "introduced_date": "2023-03-10",
                "congress_gov_url": "https://www.congress.gov/bill/117/hr/9876",
                "sponsor": {
                    "name": "John Smith"
                }
            }
        ]
    }
    
    # Set up mock responses
    setup_mocks["govinfo_client"].search_packages.return_value = govinfo_response
    setup_mocks["congress_client"].search_bills.return_value = congress_bills_response
    
    # Make request
    response = test_client.get("/search/metadata?document_type=BILL&congress=117")
    
    # Assertions
    assert response.status_code == 200
    response_data = response.json()
    
    # Check basic structure
    assert "count" in response_data
    assert "results" in response_data
    assert len(response_data["results"]) == 3  # 2 from govinfo + 1 from congress

    # Call argument validation
    setup_mocks["govinfo_client"].search_packages.assert_called_once()
    setup_mocks["congress_client"].search_bills.assert_called_once()
    
    # Ensure source_params include the correct filter values
    call_args = setup_mocks["govinfo_client"].search_packages.call_args[1]
    assert "query" in call_args
    assert "collectionCode:BILLS" in call_args["query"]
    assert "congress:117" in call_args["query"]


@pytest.mark.asyncio
async def test_metadata_search_empty_results(test_client, setup_mocks):
    """Test metadata search with no results."""
    # Mock empty responses
    setup_mocks["govinfo_client"].search_packages.return_value = {"count": 0, "packages": []}
    setup_mocks["congress_client"].search_bills.return_value = {"count": 0, "bills": []}
    
    # Make request
    response = test_client.get("/search/metadata?document_type=BILL&congress=118")
    
    # Assertions
    assert response.status_code == 200
    response_data = response.json()
    
    # Check response structure for empty results
    assert response_data["count"] == 0
    assert len(response_data["results"]) == 0


@pytest.mark.asyncio
async def test_metadata_search_govinfo_error(test_client, setup_mocks):
    """Test metadata search with GovInfo error but Congress success."""
    # Mock GovInfo error
    setup_mocks["govinfo_client"].search_packages.side_effect = ApiError(
        message="GovInfo API error",
        status_code=500,
        api_name="govinfo"
    )
    
    # Mock Congress success
    setup_mocks["congress_client"].search_bills.return_value = {
        "count": 1,
        "bills": [
            {
                "congress": 117,
                "type": "hr",
                "number": 9876,
                "title": "Congress API Bill",
                "introduced_date": "2023-03-10",
                "congress_gov_url": "https://www.congress.gov/bill/117/hr/9876",
            }
        ]
    }
    
    # Make request
    response = test_client.get("/search/metadata?document_type=BILL&congress=117")
    
    # Assertions
    assert response.status_code == 200  # Should still succeed with partial results
    response_data = response.json()
    
    # Should only have Congress results
    assert response_data["count"] == 1
    assert len(response_data["results"]) == 1
    assert response_data["results"][0]["source"] == "congress"


@pytest.mark.asyncio
async def test_metadata_search_all_sources_error(test_client, setup_mocks):
    """Test metadata search with all sources unavailable."""
    # Mock errors for both sources
    setup_mocks["govinfo_client"].search_packages.side_effect = SourceUnavailableError(
        message="GovInfo unavailable",
        source="govinfo"
    )
    setup_mocks["congress_client"].search_bills.side_effect = SourceUnavailableError(
        message="Congress unavailable",
        source="congress"
    )
    
    # Make request
    response = test_client.get("/search/metadata?document_type=BILL&congress=117")
    
    # Assertions
    assert response.status_code == 503  # Source unavailable


@pytest.mark.asyncio
async def test_metadata_search_with_facets(test_client, setup_mocks):
    """Test metadata search with facets."""
    # Mock data with facets
    govinfo_response = {
        "count": 2,
        "packages": [
            {
                "packageId": "BILLS-117hr1234ih",
                "title": "Example Bill Title",
                "dateIssued": "2023-01-15",
                "metadata": {"congress": "117", "billType": "hr"}
            },
            {
                "packageId": "BILLS-117s5678is",
                "title": "Another Bill Title", 
                "dateIssued": "2023-02-20",
                "metadata": {"congress": "117", "billType": "s"}
            }
        ],
        "facets": {
            "document_type": {
                "BILL": 75,
                "FR": 30,
                "CFR": 20
            },
            "congress": {
                "117": 50,
                "116": 25
            }
        }
    }
    
    # Set up mock responses
    setup_mocks["govinfo_client"].search_packages.return_value = govinfo_response
    setup_mocks["congress_client"].search_bills.return_value = {"count": 0, "bills": []}
    
    # Make request
    response = test_client.get("/search/metadata?include_facets=true")
    
    # Assertions
    assert response.status_code == 200
    response_data = response.json()
    
    # Check facets are included
    assert "facets" in response_data
    assert "document_type" in response_data["facets"]
    assert "congress" in response_data["facets"]
    assert response_data["facets"]["document_type"]["BILL"] == 75


# Test cases for the combined search endpoint
@pytest.mark.asyncio
async def test_combined_search_success(test_client, setup_mocks):
    """Test successful combined search."""
    # Mock data
    govinfo_response = {
        "count": 1,
        "packages": [
            {
                "packageId": "BILLS-117hr1234ih",
                "title": "Example Bill with Environment",
                "dateIssued": "2023-01-15",
                "score": 0.95,
                "detailsLink": "https://www.govinfo.gov/app/details/BILLS-117hr1234ih",
                "metadata": {"congress": "117"},
                "highlights": {
                    "title": ["Example Bill with <em>Environment</em>"],
                    "text": ["Provisions related to <em>environmental</em> protection"]
                }
            }
        ]
    }
    
    congress_response = {
        "count": 1,
        "results": [
            {
                "type": "BILL",
                "id": "117hr5555",
                "title": "Environmental Protection Act",
                "date": "2023-02-10",
                "score": 0.85,
                "url": "https://www.congress.gov/bill/117/hr/5555",
                "congress": 117,
                "bill_type": "hr",
                "bill_number": 5555,
                "highlights": {
                    "title": ["<em>Environmental</em> Protection Act"],
                    "text": ["This bill addresses <em>environmental</em> concerns"]
                }
            }
        ]
    }
    
    # Set up mock responses
    setup_mocks["govinfo_client"].search_packages.return_value = govinfo_response
    setup_mocks["congress_client"].search.return_value = congress_response
    
    # Make request
    response = test_client.get("/search/combined?query=environment&document_type=BILL")
    
    # Assertions
    assert response.status_code == 200
    response_data = response.json()
    
    # Check response structure
    assert response_data["count"] == 2
    assert len(response_data["results"]) == 2
    assert "source_counts" in response_data
    assert response_data["source_counts"]["govinfo"] == 1
    assert response_data["source_counts"]["congress"] == 1
    
    # Check highlights are included
    assert "highlights" in response_data["results"][0]
    assert "<em>Environment</em>" in response_data["results"][0]["highlights"]["title"][0]
    
    # Verify sorted by relevance score
    assert response_data["results"][0]["relevance_score"] >= response_data["results"][1]["relevance_score"]


@pytest.mark.asyncio
async def test_combined_search_with_date_filter(test_client, setup_mocks):
    """Test combined search with date filtering."""
    # Mock data
    govinfo_response = {
        "count": 1,
        "packages": [
            {
                "packageId": "BILLS-117hr1234ih",
                "title": "Example Bill with Environment",
                "dateIssued": "2023-01-15",
                "score": 0.95,
                "metadata": {}
            }
        ]
    }
    
    # Set up mock responses
    setup_mocks["govinfo_client"].search_packages.return_value = govinfo_response
    setup_mocks["congress_client"].search.return_value = {"count": 0, "results": []}
    
    # Make request
    response = test_client.get("/search/combined?query=environment&start_date=2023-01-01&end_date=2023-12-31")
    
    # Assertions
    assert response.status_code == 200
    
    # Check call arguments
    call_args = setup_mocks["govinfo_client"].search_packages.call_args[1]
    assert call_args["query"] == "environment"
    assert call_args["start_date"] == "2023-01-01"
    assert call_args["end_date"] == "2023-12-31"


@pytest.mark.asyncio
async def test_combined_search_all_sources_error(test_client, setup_mocks):
    """Test combined search with all sources unavailable."""
    # Mock errors for both sources
    setup_mocks["govinfo_client"].search_packages.side_effect = SourceUnavailableError(
        message="GovInfo unavailable",
        source="govinfo"
    )
    setup_mocks["congress_client"].search.side_effect = SourceUnavailableError(
        message="Congress unavailable",
        source="congress"
    )
    
    # Make request
    response = test_client.get("/search/combined?query=environment")
    
    # Assertions
    assert response.status_code == 503  # Source unavailable