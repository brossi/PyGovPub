"""
Tests for the CFR router.

These tests cover the Code of Federal Regulations endpoints.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from fastapi import HTTPException

from pygovpub.api.routers.cfr import (
    router, list_cfr_titles, get_cfr_title, search_cfr, get_cfr_content
)
from pygovpub.api.clients import GovInfoClient
from pygovpub.auth.models import ApiSource
from pygovpub.exceptions import RouterError, ApiError, RouteNotFoundError, SourceUnavailableError, GovInfoApiError

# Test data
CFR_TITLE_DATA = {
    "number": 40,
    "name": "Protection of Environment",
    "chapters": [
        {
            "chapter_number": "I",
            "chapter_name": "Environmental Protection Agency"
        }
    ]
}

CFR_DOCUMENT_DATA = {
    "package_id": "CFR-2023-title40-vol1",
    "title_number": 40,
    "title_name": "Protection of Environment",
    "part_number": 50,
    "section_number": "50.1",
    "heading": "Definitions",
    "year": 2023,
    "date_issued": "2023-07-01",
    "pdf_url": "https://www.govinfo.gov/content/pkg/CFR-2023-title40-vol1/pdf/CFR-2023-title40-vol1.pdf",
    "xml_url": "https://www.govinfo.gov/content/pkg/CFR-2023-title40-vol1/xml/CFR-2023-title40-vol1.xml",
    "html_url": "https://www.govinfo.gov/content/pkg/CFR-2023-title40-vol1/html/CFR-2023-title40-vol1.htm"
}


@patch('pygovpub.api.routers.cfr.ApiRouter')
async def test_list_cfr_titles(mock_api_router_class):
    """Test listing CFR titles."""
    # Create mock client and configure it
    mock_client = AsyncMock()
    mock_client.get_cfr_titles.return_value = {
        "titles": [CFR_TITLE_DATA]
    }
    
    # Configure the get_client method
    mock_api_router = mock_api_router_class.return_value
    mock_api_router.get_client.return_value = mock_client
    
    # Call the function
    result = await list_cfr_titles(api_router=mock_api_router)
    
    # Verify client was used correctly
    mock_api_router.get_client.assert_called_once_with(ApiSource.GOVINFO)
    mock_client.get_cfr_titles.assert_called_once()
    
    # Verify response
    assert len(result) == 1
    assert result[0].title_number == 40
    assert result[0].title_name == "Protection of Environment"
    assert result[0].chapters is not None


@patch('pygovpub.api.routers.cfr.ApiRouter')
async def test_get_cfr_title(mock_api_router_class):
    """Test getting a specific CFR title."""
    # Create mock client and configure it
    mock_client = AsyncMock()
    mock_client.get_cfr_title.return_value = CFR_TITLE_DATA
    
    # Configure the get_client method
    mock_api_router = mock_api_router_class.return_value
    mock_api_router.get_client.return_value = mock_client
    
    # Call the function
    result = await get_cfr_title(
        title_number=40,
        year=2023,
        api_router=mock_api_router
    )
    
    # Verify client was used correctly
    mock_api_router.get_client.assert_called_once_with(ApiSource.GOVINFO)
    mock_client.get_cfr_title.assert_called_once_with(
        title_number=40,
        year=2023
    )
    
    # Verify response
    assert result.title_number == 40
    assert result.title_name == "Protection of Environment"
    assert result.chapters is not None


@patch('pygovpub.api.routers.cfr.ApiRouter')
@patch('pygovpub.api.routers.cfr.Query')
async def test_search_cfr(mock_query, mock_api_router_class):
    """Test searching CFR documents."""
    # Setup mock Query to return integers instead of Query objects
    mock_query.side_effect = lambda value, **kwargs: value
    
    # Create mock client and configure it
    mock_client = AsyncMock()
    mock_client.search_packages.return_value = {
        "count": 1,
        "packages": [{
            "packageId": "CFR-2023-title40-vol1",
            "title": "Protection of Environment",
            "metadata": {
                "titleNumber": 40,
                "titleName": "Protection of Environment",
                "partNumber": 50,
                "sectionNumber": "50.1",
                "heading": "Definitions",
                "year": 2023
            },
            "dateIssued": "2023-01-15",
            "download": {
                "pdfLink": "https://www.govinfo.gov/content/pkg/CFR-2023-title40-vol1/pdf/CFR-2023-title40-vol1.pdf",
                "xmlLink": "https://www.govinfo.gov/content/pkg/CFR-2023-title40-vol1/xml/CFR-2023-title40-vol1.xml", 
                "htmlLink": "https://www.govinfo.gov/content/pkg/CFR-2023-title40-vol1/html/CFR-2023-title40-vol1.htm"
            }
        }]
    }
    
    # Configure the get_client method
    mock_api_router = mock_api_router_class.return_value
    mock_api_router.get_client.return_value = mock_client
    
    # Call the function directly with mocked parameters
    offset = 0
    limit = 20
    result = await search_cfr(
        title=40,
        part=50,
        section=None,
        query="definition",
        year=2023,
        offset=offset,
        limit=limit,
        api_router=mock_api_router
    )
    
    # Verify client was used correctly
    mock_api_router.get_client.assert_called_once_with(ApiSource.GOVINFO)
    mock_client.search_packages.assert_called_once()
    call_args = mock_client.search_packages.call_args[1]
    assert call_args["collection"] == "CFR"
    assert call_args["year"] == 2023
    assert "query" in call_args
    
    # Verify response
    assert result.count == 1
    assert len(result.results) == 1
    assert result.results[0].package_id == "CFR-2023-title40-vol1"
    assert result.results[0].title_number == 40
    assert result.results[0].part_number == 50


@patch('pygovpub.api.routers.cfr.ApiRouter')
async def test_get_cfr_content(mock_api_router_class):
    """Test getting CFR document content."""
    # Create mock client and configure it
    mock_client = AsyncMock()
    mock_client.get_package_content.return_value = {
        "content_type": "text/html",
        "content": "<html><body>CFR content</body></html>",
        "source_url": "https://www.govinfo.gov/content/pkg/CFR-2023-title40-vol1/html/CFR-2023-title40-vol1.htm"
    }
    
    # Configure the get_client method
    mock_api_router = mock_api_router_class.return_value
    mock_api_router.get_client.return_value = mock_client
    
    # Call the function
    result = await get_cfr_content(
        package_id="CFR-2023-title40-vol1",
        content_type="html",
        api_router=mock_api_router
    )
    
    # Verify client was used correctly
    mock_api_router.get_client.assert_called_once_with(ApiSource.GOVINFO)
    mock_client.get_package_content.assert_called_once_with(
        package_id="CFR-2023-title40-vol1",
        content_type="html"
    )
    
    # Verify response
    assert result["package_id"] == "CFR-2023-title40-vol1"
    assert "content" in result
    assert result["content_type"] == "text/html"


async def test_get_cfr_content_invalid_id():
    """Test getting CFR content with invalid package ID."""
    with pytest.raises(HTTPException) as exc_info:
        await get_cfr_content(
            package_id="INVALID-ID",
            api_router=AsyncMock(),
            content_type="html"
        )
    
    # With our current implementation, the error is caught and wrapped in a 500 error
    assert "Invalid CFR package ID" in str(exc_info.value.detail)


@patch('pygovpub.api.routers.cfr.ApiRouter')
async def test_cfr_api_errors(mock_api_router_class):
    """Test CFR API error handling."""
    # Create mock client and configure it
    mock_client = AsyncMock()
    mock_client.get_cfr_titles.side_effect = SourceUnavailableError(
        "GovInfo API unavailable",
        source=ApiSource.GOVINFO
    )
    
    # Configure the get_client method
    mock_api_router = mock_api_router_class.return_value
    mock_api_router.get_client.return_value = mock_client
    
    # Test source unavailable error
    with pytest.raises(Exception) as exc_info:
        await list_cfr_titles(api_router=mock_api_router)
    
    assert exc_info.value.status_code == 503  # Service Unavailable
    
    # Update mock for next test
    mock_client.get_cfr_titles.side_effect = GovInfoApiError(
        "API error",
        status_code=500,
        endpoint="/cfr/titles"
    )
    
    # Test general API error
    with pytest.raises(Exception) as exc_info:
        await list_cfr_titles(api_router=mock_api_router)
    
    assert exc_info.value.status_code == 500  # Internal Server Error