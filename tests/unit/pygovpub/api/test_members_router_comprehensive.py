"""
Tests for the members router.

These tests cover the members endpoints in more detail.
"""

import json
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException

from pygovpub.api.routers.members import (
    router, get_member, search_members, get_member_sponsored_bills, 
    get_member_cosponsored_bills
)
from pygovpub.auth.models import ApiSource
from pygovpub.exceptions import RouterError, ApiError, RouteNotFoundError, SourceUnavailableError

# Define the API router dependency
def get_api_router():
    """Mock get_api_router."""
    return AsyncMock()

# Test data
MEMBER_DATA = {
    "bioguide_id": "S000148",
    "first_name": "Chuck",
    "last_name": "Schumer",
    "state": "NY",
    "party": "D",
    "chamber": "Senate",
    "district": None,
    "term_start": "2023-01-03",
    "term_end": "2029-01-03",
    "leadership_position": "Majority Leader",
    "url": "https://www.congress.gov/member/charles-schumer/S000148"
}

BILL_DATA = {
    "bill_id": "s1234-117",
    "congress": 117,
    "bill_type": "s",
    "bill_number": 1234,
    "title": "Test Bill",
    "introduced_date": "2023-01-01",
    "sponsor": {
        "bioguide_id": "S000148",
        "name": "Sen. Chuck Schumer",
        "state": "NY",
        "party": "D"
    },
    "source": "congress",
    "source_url": "https://www.congress.gov/bill/117th-congress/senate-bill/1234",
    "status": "INTRODUCED"
}

@pytest.fixture
def mock_api_router():
    """Create a mock API router."""
    # Create base mock
    mock_router = MagicMock()
    
    # Create mock client with proper async methods
    mock_client = MagicMock()
    
    # Add async methods to client
    async def mock_search_members(**kwargs):
        return {
            "members": [MEMBER_DATA],
            "pagination": {
                "count": 1,
                "offset": 0,
                "limit": 20
            }
        }
    
    # Assign methods to the mock client
    mock_client.search_members = mock_search_members
    
    # Configure route_request
    async def mock_route_request(**kwargs):
        # We'll handle specific endpoints in the test
        if kwargs.get("method") == "get_member":
            return MEMBER_DATA
        elif kwargs.get("method") == "get_member_sponsored_bills":
            return {
                "bills": [BILL_DATA],
                "pagination": {
                    "count": 1,
                    "offset": 0,
                    "limit": 20
                }
            }
        elif kwargs.get("method") == "get_member_cosponsored_bills":
            return {
                "bills": [BILL_DATA],
                "pagination": {
                    "count": 1,
                    "offset": 0,
                    "limit": 20
                }
            }
        return {}
    
    # Update the mock
    mock_router.route_request = mock_route_request
    mock_router.get_client = MagicMock(return_value=mock_client)
    
    return mock_router


async def test_get_member(mock_api_router):
    """Test getting a member."""
    result = await get_member(
        bioguide_id="S000148",
        api_router=mock_api_router
    )
    
    assert result.bioguide_id == "S000148"
    assert result.first_name == "Chuck"
    assert result.last_name == "Schumer"
    assert result.state == "NY"
    assert result.party == "D"
    
    # No need to verify call to route_request since we're using a function


async def test_get_member_not_found(mock_api_router):
    """Test getting a member that doesn't exist."""
    # Create custom mock that raises RouterError
    original_route_request = mock_api_router.route_request
    
    async def mock_route_request_error(**kwargs):
        if kwargs.get("bioguide_id") == "INVALID":
            raise RouterError("Member not found")
        return await original_route_request(**kwargs)
    
    # Replace route_request
    mock_api_router.route_request = mock_route_request_error
    
    with pytest.raises(HTTPException) as excinfo:
        await get_member(
            bioguide_id="INVALID",
            api_router=mock_api_router
        )
    
    assert excinfo.value.status_code == 500
    assert "Member not found" in excinfo.value.detail
    
    # Restore original route_request
    mock_api_router.route_request = original_route_request


async def test_get_member_source_unavailable(mock_api_router):
    """Test getting a member with source unavailable."""
    # Create custom mock that raises SourceUnavailableError
    original_route_request = mock_api_router.route_request
    
    async def mock_route_request_error(**kwargs):
        raise SourceUnavailableError("Source unavailable", source=ApiSource.CONGRESS)
    
    # Replace route_request
    mock_api_router.route_request = mock_route_request_error
    
    with pytest.raises(HTTPException) as excinfo:
        await get_member(
            bioguide_id="S000148",
            api_router=mock_api_router
        )
    
    assert excinfo.value.status_code == 503
    assert "Source unavailable" in excinfo.value.detail
    
    # Restore original route_request
    mock_api_router.route_request = original_route_request


async def test_search_members(mock_api_router):
    """Test searching members."""
    # Mock already set up in fixture
    
    result = await search_members(
        name="Schumer",
        chamber=None,
        state=None,
        party=None,
        offset=0,
        limit=20,
        api_router=mock_api_router
    )
    
    assert result.count == 1
    assert len(result.members) == 1
    assert result.members[0].bioguide_id == "S000148"
    assert result.members[0].last_name == "Schumer"
    
    # We can only verify that get_client was called
    mock_api_router.get_client.assert_called_once_with(ApiSource.CONGRESS)


async def test_search_members_with_filters(mock_api_router):
    """Test searching members with filters."""
    # Mock already set up in fixture
    
    result = await search_members(
        name="Schumer",
        chamber="Senate",
        state="NY",
        party="D",
        offset=0,
        limit=20,
        api_router=mock_api_router
    )
    
    assert result.count == 1
    assert result.members[0].chamber == "Senate"
    assert result.members[0].state == "NY"
    assert result.members[0].party == "D"
    
    # We can only verify that get_client was called
    mock_api_router.get_client.assert_called_once_with(ApiSource.CONGRESS)


async def test_get_member_sponsored_bills(mock_api_router):
    """Test getting member sponsored bills."""
    # Mock already set up in fixture
    
    result = await get_member_sponsored_bills(
        bioguide_id="S000148",
        congress=117,
        offset=0,
        limit=20,
        api_router=mock_api_router
    )
    
    # Just check that we got something back
    assert "count" in result
    assert "bills" in result
    
    # No need to verify call to route_request since we're using a function


async def test_get_member_cosponsored_bills(mock_api_router):
    """Test getting member cosponsored bills."""
    # Mock already set up in fixture
    
    result = await get_member_cosponsored_bills(
        bioguide_id="S000148",
        congress=117,
        offset=0,
        limit=20,
        api_router=mock_api_router
    )
    
    # Just check that we got something back
    assert "count" in result
    assert "bills" in result
    
    # No need to verify call to route_request since we're using a function