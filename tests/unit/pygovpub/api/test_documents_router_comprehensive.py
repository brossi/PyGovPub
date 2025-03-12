"""
Tests for the documents router.

These tests cover the document endpoints in more detail.
"""

import json
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException

from pygovpub.api.routers.documents import (
    router, list_collections, get_collection, get_document, 
    get_document_content, search_documents
)
from pygovpub.auth.models import ApiSource
from pygovpub.exceptions import RouterError, ApiError, RouteNotFoundError, SourceUnavailableError

# Define the API router dependency
def get_api_router():
    """Mock get_api_router."""
    return AsyncMock()

# Test data
COLLECTION_DATA = {
    "collection_code": "BILLS",
    "collection_name": "Congressional Bills",
    "package_count": 100,
    "update_frequency": "daily",
    "granularity": True,
    "description": "Congressional bills and resolutions"
}

DOCUMENT_DATA = {
    "packageId": "BILLS-117hr1234ih",
    "title": "Test Bill",
    "collection": "BILLS",
    "congress": 117,
    "dateIssued": "2023-01-01",
    "lastModified": "2023-01-01",
    "download": {
        "pdfLink": "https://www.govinfo.gov/content/pkg/BILLS-117hr1234ih/pdf/BILLS-117hr1234ih.pdf"
    },
    "metadata": {
        "bill_type": "hr",
        "bill_number": "1234",
        "version": "ih"
    }
}

DOCUMENT_CONTENT = {
    "package_id": "BILLS-117hr1234ih",
    "content_type": "text/html",
    "content": "<html><body>Bill content</body></html>",
    "size": 1024,
    "last_modified": "2023-01-01"
}

@pytest.fixture
def mock_api_router():
    """Create a mock API router."""
    mock_router = MagicMock()
    
    # Create mock client
    mock_client = MagicMock()
    
    # Add async methods to client
    async def mock_list_collections():
        return {
            "collections": [COLLECTION_DATA]
        }
        
    async def mock_get_collection(collection_code=None):
        return COLLECTION_DATA
        
    async def mock_get_package_summary(package_id=None):
        return DOCUMENT_DATA
        
    async def mock_get_package_content(package_id=None, content_type=None, granule_id=None):
        return DOCUMENT_CONTENT
    
    async def mock_search_packages(**kwargs):
        return {
            "packages": [DOCUMENT_DATA],
            "count": 1,
            "offset": 0,
            "limit": 20
        }
    
    # Assign methods to the mock
    mock_client.list_collections = mock_list_collections
    mock_client.get_collection = mock_get_collection
    mock_client.get_package_summary = mock_get_package_summary
    mock_client.get_package_content = mock_get_package_content
    mock_client.search_packages = mock_search_packages
    
    # Configure the router's get_client method
    mock_router.get_client = MagicMock(return_value=mock_client)
    
    return mock_router


async def test_list_collections(mock_api_router):
    """Test listing collections."""
    result = await list_collections(
        api_router=mock_api_router
    )
    
    assert len(result) == 1
    assert result[0].collection_code == "BILLS"
    assert result[0].collection_name == "Congressional Bills"
    
    # We can only verify that get_client was called
    mock_api_router.get_client.assert_called_once_with(ApiSource.GOVINFO)


async def test_list_collections_error(mock_api_router):
    """Test listing collections with error."""
    # Save original get_client and replace it with one that raises an error
    original_get_client = mock_api_router.get_client
    mock_api_router.get_client = MagicMock(side_effect=SourceUnavailableError(
        "Source unavailable",
        source=ApiSource.GOVINFO
    ))
    
    with pytest.raises(HTTPException) as excinfo:
        await list_collections(
            api_router=mock_api_router
        )
    
    assert excinfo.value.status_code == 503
    assert "Source unavailable" in excinfo.value.detail
    
    # Restore original get_client
    mock_api_router.get_client = original_get_client


async def test_get_collection(mock_api_router):
    """Test getting a collection."""
    result = await get_collection(
        collection_code="BILLS",
        api_router=mock_api_router
    )
    
    assert result.collection_code == "BILLS"
    assert result.collection_name == "Congressional Bills"
    assert result.package_count == 100
    
    # We can only verify that get_client was called
    mock_api_router.get_client.assert_called_once_with(ApiSource.GOVINFO)


async def test_get_collection_not_found(mock_api_router):
    """Test getting a collection that doesn't exist."""
    # Create new client with error behavior
    mock_client_with_error = MagicMock()
    
    # Configure the mock function to raise an exception
    async def mock_get_collection_error(collection_code=None):
        raise ApiError("Collection not found", status_code=404, api_name="govinfo")
    
    mock_client_with_error.get_collection = mock_get_collection_error
    
    # Replace the client temporarily
    original_get_client = mock_api_router.get_client
    mock_api_router.get_client = MagicMock(return_value=mock_client_with_error)
    
    with pytest.raises(HTTPException) as excinfo:
        await get_collection(
            collection_code="INVALID",
            api_router=mock_api_router
        )
    
    assert excinfo.value.status_code == 500
    assert "Collection not found" in excinfo.value.detail
    
    # Restore the original client
    mock_api_router.get_client = original_get_client


async def test_get_document(mock_api_router):
    """Test getting a document."""
    result = await get_document(
        package_id="BILLS-117hr1234ih",
        api_router=mock_api_router
    )
    
    assert result.package_id == "BILLS-117hr1234ih"
    assert result.title == "Test Bill"
    assert result.collection == "BILLS"
    
    # We can only verify that get_client was called
    mock_api_router.get_client.assert_called_once_with(ApiSource.GOVINFO)


async def test_get_document_not_found(mock_api_router):
    """Test getting a document that doesn't exist."""
    # Create new client with error behavior
    mock_client_with_error = MagicMock()
    
    # Configure the mock function to raise an exception
    async def mock_get_package_summary_error(package_id=None):
        raise ApiError("Document not found", status_code=404, api_name="govinfo")
    
    mock_client_with_error.get_package_summary = mock_get_package_summary_error
    
    # Replace the client temporarily
    original_get_client = mock_api_router.get_client
    mock_api_router.get_client = MagicMock(return_value=mock_client_with_error)
    
    with pytest.raises(HTTPException) as excinfo:
        await get_document(
            package_id="INVALID",
            api_router=mock_api_router
        )
    
    assert excinfo.value.status_code == 500 or excinfo.value.status_code == 404
    assert "Document not found" in excinfo.value.detail
    
    # Restore the original client
    mock_api_router.get_client = original_get_client


async def test_get_document_content(mock_api_router):
    """Test getting document content."""
    result = await get_document_content(
        package_id="BILLS-117hr1234ih",
        content_type="html",
        granule_id=None,
        api_router=mock_api_router
    )
    
    assert result["package_id"] == "BILLS-117hr1234ih"
    assert result["content_type"] == "text/html"
    assert "Bill content" in result["content"]
    
    # We can only verify that get_client was called
    mock_api_router.get_client.assert_called_once_with(ApiSource.GOVINFO)


async def test_get_document_content_with_granule(mock_api_router):
    """Test getting document content with granule ID."""
    result = await get_document_content(
        package_id="BILLS-117hr1234ih",
        content_type="html",
        granule_id="g001",
        api_router=mock_api_router
    )
    
    assert result["package_id"] == "BILLS-117hr1234ih"
    
    # Check the result
    assert result["package_id"] == "BILLS-117hr1234ih"


async def test_search_documents(mock_api_router):
    """Test searching documents."""
    result = await search_documents(
        query="test",
        collection=None,
        start_date=None,
        end_date=None,
        offset=0,
        limit=20,
        api_router=mock_api_router
    )
    
    assert result.count == 1
    assert len(result.documents) == 1
    assert result.documents[0].package_id == "BILLS-117hr1234ih"
    
    # We can only verify that get_client was called
    mock_api_router.get_client.assert_called_once_with(ApiSource.GOVINFO)


async def test_search_documents_with_filters(mock_api_router):
    """Test searching documents with filters."""
    result = await search_documents(
        query="test",
        collection="BILLS",
        start_date="2023-01-01",
        end_date="2023-01-31",
        offset=0,
        limit=20,
        api_router=mock_api_router
    )
    
    assert result.count == 1
    
    # Check the result
    assert result.count == 1