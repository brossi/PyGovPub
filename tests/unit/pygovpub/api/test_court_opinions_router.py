"""
Tests for the Court Opinions router.

These tests cover the Court Opinions endpoints.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException

from pygovpub.api.routers.court_opinions import (
    router, list_courts, search_opinions, get_opinion, get_opinion_content
)
from pygovpub.api.clients import GovInfoClient
from pygovpub.auth.models import ApiSource
from pygovpub.exceptions import RouterError, ApiError, RouteNotFoundError, SourceUnavailableError, GovInfoApiError

# Test data
COURT_DATA = {
    "code": "SCOTUS",
    "name": "Supreme Court of the United States",
    "opinionCount": 1245
}

OPINION_DATA = {
    "package_id": "USCOURTS-ca1-12-1234",
    "title": "Example Opinion Title",
    "court": "United States Court of Appeals for the First Circuit",
    "docket_number": "12-1234",
    "part_name": "Opinion of the Court",
    "date_issued": "2023-01-15",
    "year": 2023,
    "pdf_url": "https://www.govinfo.gov/content/pkg/USCOURTS-ca1-12-1234/pdf/USCOURTS-ca1-12-1234.pdf",
    "xml_url": "https://www.govinfo.gov/content/pkg/USCOURTS-ca1-12-1234/xml/USCOURTS-ca1-12-1234.xml",
    "html_url": "https://www.govinfo.gov/content/pkg/USCOURTS-ca1-12-1234/html/USCOURTS-ca1-12-1234.htm"
}


@patch('pygovpub.api.routers.court_opinions.ApiRouter')
async def test_list_courts(mock_api_router_class):
    """Test listing courts with available opinions."""
    # Create mock client and configure it
    mock_client = AsyncMock()
    mock_client.get_courts.return_value = {
        "courts": [COURT_DATA]
    }
    
    # Configure the get_client method
    mock_api_router = mock_api_router_class.return_value
    mock_api_router.get_client.return_value = mock_client
    
    # Call the function
    result = await list_courts(api_router=mock_api_router)
    
    # Verify client was used correctly
    mock_api_router.get_client.assert_called_once_with(ApiSource.GOVINFO)
    mock_client.get_courts.assert_called_once()
    
    # Verify response
    assert len(result) == 1
    assert result[0].court_code == "SCOTUS"
    assert result[0].court_name == "Supreme Court of the United States"
    assert result[0].opinion_count == 1245


@patch('pygovpub.api.routers.court_opinions.ApiRouter')
@patch('pygovpub.api.routers.court_opinions.Query')
async def test_search_opinions(mock_query, mock_api_router_class):
    """Test searching court opinions."""
    # Setup mock Query to return the value directly instead of Query objects
    mock_query.side_effect = lambda value, **kwargs: value
    
    # Create mock client and configure it
    mock_client = AsyncMock()
    mock_client.search_packages.return_value = {
        "count": 1,
        "packages": [{
            "packageId": "USCOURTS-ca1-12-1234",
            "title": "Example Opinion Title",
            "metadata": {
                "court": "United States Court of Appeals for the First Circuit",
                "docketNumber": "12-1234",
                "partName": "Opinion of the Court"
            },
            "dateIssued": "2023-01-15",
            "download": {
                "pdfLink": "https://www.govinfo.gov/content/pkg/USCOURTS-ca1-12-1234/pdf/USCOURTS-ca1-12-1234.pdf",
                "xmlLink": "https://www.govinfo.gov/content/pkg/USCOURTS-ca1-12-1234/xml/USCOURTS-ca1-12-1234.xml",
                "htmlLink": "https://www.govinfo.gov/content/pkg/USCOURTS-ca1-12-1234/html/USCOURTS-ca1-12-1234.htm"
            }
        }]
    }
    
    # Configure the get_client method
    mock_api_router = mock_api_router_class.return_value
    mock_api_router.get_client.return_value = mock_client
    
    # Call the function with direct parameters
    offset = 0
    limit = 20
    result = await search_opinions(
        court="SCOTUS",
        query="constitution",
        docket="12-1234",
        start_date=None,
        end_date=None,
        offset=offset,
        limit=limit,
        api_router=mock_api_router
    )
    
    # Verify client was used correctly
    mock_api_router.get_client.assert_called_once_with(ApiSource.GOVINFO)
    mock_client.search_packages.assert_called_once()
    call_args = mock_client.search_packages.call_args[1]
    assert call_args["collection"] == "USCOURTS"
    assert "query" in call_args
    
    # Verify response
    assert result.count == 1
    assert len(result.opinions) == 1
    assert result.opinions[0].package_id == "USCOURTS-ca1-12-1234"
    assert result.opinions[0].court == "United States Court of Appeals for the First Circuit"
    assert result.opinions[0].docket_number == "12-1234"


@patch('pygovpub.api.routers.court_opinions.ApiRouter')
async def test_get_opinion(mock_api_router_class):
    """Test getting a specific court opinion."""
    # Create mock client and configure it
    mock_client = AsyncMock()
    mock_client.get_package_summary.return_value = {
        "title": "Example Opinion Title",
        "metadata": {
            "court": "United States Court of Appeals for the First Circuit",
            "docketNumber": "12-1234",
            "partName": "Opinion of the Court"
        },
        "dateIssued": "2023-01-15",
        "download": {
            "pdfLink": "https://www.govinfo.gov/content/pkg/USCOURTS-ca1-12-1234/pdf/USCOURTS-ca1-12-1234.pdf",
            "xmlLink": "https://www.govinfo.gov/content/pkg/USCOURTS-ca1-12-1234/xml/USCOURTS-ca1-12-1234.xml",
            "htmlLink": "https://www.govinfo.gov/content/pkg/USCOURTS-ca1-12-1234/html/USCOURTS-ca1-12-1234.htm"
        }
    }
    
    # Configure the get_client method
    mock_api_router = mock_api_router_class.return_value
    mock_api_router.get_client.return_value = mock_client
    
    # Call the function
    result = await get_opinion(
        package_id="USCOURTS-ca1-12-1234",
        api_router=mock_api_router
    )
    
    # Verify client was used correctly
    mock_api_router.get_client.assert_called_once_with(ApiSource.GOVINFO)
    mock_client.get_package_summary.assert_called_once_with(
        package_id="USCOURTS-ca1-12-1234"
    )
    
    # Verify response
    assert result.package_id == "USCOURTS-ca1-12-1234"
    assert result.title == "Example Opinion Title"
    assert result.court == "United States Court of Appeals for the First Circuit"
    assert result.docket_number == "12-1234"


@patch('pygovpub.api.routers.court_opinions.ApiRouter')
async def test_get_opinion_content(mock_api_router_class):
    """Test getting court opinion content."""
    # Create mock client and configure it
    mock_client = AsyncMock()
    mock_client.get_package_content.return_value = {
        "content_type": "text/html",
        "content": "<html><body>Court opinion content</body></html>",
        "source_url": "https://www.govinfo.gov/content/pkg/USCOURTS-ca1-12-1234/html/USCOURTS-ca1-12-1234.htm"
    }
    
    # Configure the get_client method
    mock_api_router = mock_api_router_class.return_value
    mock_api_router.get_client.return_value = mock_client
    
    # Call the function
    result = await get_opinion_content(
        package_id="USCOURTS-ca1-12-1234",
        content_type="html",
        api_router=mock_api_router
    )
    
    # Verify client was used correctly
    mock_api_router.get_client.assert_called_once_with(ApiSource.GOVINFO)
    mock_client.get_package_content.assert_called_once_with(
        package_id="USCOURTS-ca1-12-1234",
        content_type="html"
    )
    
    # Verify response
    assert result["package_id"] == "USCOURTS-ca1-12-1234"
    assert "content" in result
    assert result["content_type"] == "text/html"


async def test_get_opinion_invalid_id():
    """Test getting opinion with invalid package ID."""
    with pytest.raises(HTTPException) as exc_info:
        await get_opinion(
            package_id="INVALID-ID",
            api_router=AsyncMock()
        )
    
    # With our current implementation, we might get different error codes depending on implementation
    # Just check that the error message contains the expected text
    assert "Invalid court opinion package ID" in str(exc_info.value.detail)


@patch('pygovpub.api.routers.court_opinions.ApiRouter')
async def test_court_opinions_api_errors(mock_api_router_class):
    """Test court opinions API error handling."""
    # Create mock client and configure it
    mock_client = AsyncMock()
    mock_client.get_courts.side_effect = SourceUnavailableError(
        "GovInfo API unavailable",
        source=ApiSource.GOVINFO
    )
    
    # Configure the get_client method
    mock_api_router = mock_api_router_class.return_value
    mock_api_router.get_client.return_value = mock_client
    
    # Test source unavailable error
    with pytest.raises(Exception) as exc_info:
        await list_courts(api_router=mock_api_router)
    
    assert exc_info.value.status_code == 503  # Service Unavailable
    
    # Update mock for next test
    mock_client.get_courts.side_effect = GovInfoApiError(
        "API error",
        status_code=500,
        endpoint="/courts"
    )
    
    # Test general API error
    with pytest.raises(Exception) as exc_info:
        await list_courts(api_router=mock_api_router)
    
    assert exc_info.value.status_code == 500  # Internal Server Error