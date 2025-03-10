"""
Unit tests for the API router.

Tests the functionality of the router to direct requests to the
appropriate data source based on defined rules.
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from pygovpub.api.router import ApiRouter
from pygovpub.api.clients import CongressClient, GovInfoClient
from pygovpub.auth.models import ApiSource
from pygovpub.exceptions import (
    ApiError, RateLimitExceededError, RouterError, SourceUnavailableError,
    RouteNotFoundError, ApiErrorSource
)
from pygovpub.models.legislative import BillType


class TestApiRouter:
    """Tests for the API router."""
    
    @pytest.fixture
    def mock_congress_client(self):
        """Create a mock Congress client."""
        client = MagicMock(spec=CongressClient)
        client.api_source = ApiSource.CONGRESS
        client.get_bill = AsyncMock()
        client.search_bills = AsyncMock()
        client.get_bill_status = AsyncMock()
        client.get_bill_actions = AsyncMock()
        client.get_bill_amendments = AsyncMock()
        client.get_bill_cosponsors = AsyncMock()
        client.get_member = AsyncMock()
        client.search_members = AsyncMock()
        client.get_member_sponsored_bills = AsyncMock()
        client.get_member_cosponsored_bills = AsyncMock()
        client.get_committee = AsyncMock()
        client.list_committees = AsyncMock()
        client.get_committee_hearings = AsyncMock()
        client.get_committee_reports = AsyncMock()
        
        # Add auth_manager with check_rate_limit method
        client.auth_manager = MagicMock()
        client.auth_manager.check_rate_limit = AsyncMock(return_value=True)
        
        return client
    
    @pytest.fixture
    def mock_govinfo_client(self):
        """Create a mock GovInfo client."""
        client = MagicMock(spec=GovInfoClient)
        client.api_source = ApiSource.GOVINFO
        client.get_package_summary = AsyncMock()
        client.get_package_content = AsyncMock()
        client.list_collections = AsyncMock()
        client.resolve_bill_package_id = AsyncMock()
        
        # Add auth_manager with check_rate_limit method
        client.auth_manager = MagicMock()
        client.auth_manager.check_rate_limit = AsyncMock(return_value=True)
        
        return client
    
    @pytest.fixture
    def router(self, mock_congress_client, mock_govinfo_client):
        """Create a router with mock clients."""
        router = ApiRouter()
        router.register_client(mock_congress_client)
        router.register_client(mock_govinfo_client)
        return router
    
    async def test_router_initialization(self):
        """Test that the router initializes properly."""
        router = ApiRouter()
        assert router is not None
        assert isinstance(router.clients, dict)
        assert len(router.clients) == 0
    
    async def test_client_registration(self, mock_congress_client, mock_govinfo_client):
        """Test registering clients with the router."""
        router = ApiRouter()
        
        # Register clients
        router.register_client(mock_congress_client)
        router.register_client(mock_govinfo_client)
        
        # Verify they were registered
        assert ApiSource.CONGRESS in router.clients
        assert ApiSource.GOVINFO in router.clients
        assert router.clients[ApiSource.CONGRESS] == mock_congress_client
        assert router.clients[ApiSource.GOVINFO] == mock_govinfo_client
    
    async def test_register_duplicate_client(self, mock_congress_client):
        """Test registering a duplicate client."""
        router = ApiRouter()
        
        # Register once
        router.register_client(mock_congress_client)
        
        # Register again - should overwrite
        duplicate_client = MagicMock(spec=CongressClient)
        duplicate_client.api_source = ApiSource.CONGRESS
        router.register_client(duplicate_client)
        
        # Verify it was replaced
        assert router.clients[ApiSource.CONGRESS] == duplicate_client
    
    async def test_basic_routing_for_bill(self, router, mock_congress_client):
        """Test basic routing for bill data."""
        # Setup return value
        mock_congress_client.get_bill.return_value = {"bill_id": "hr123-117"}
        
        # Route a request for bill data
        result = await router.route_request(
            request_type="bill",
            method="get_bill",
            congress=117,
            bill_type="hr",
            bill_number=123
        )
        
        # Verify the Congress client was used
        mock_congress_client.get_bill.assert_called_once_with(
            congress=117, bill_type="hr", bill_number=123
        )
        assert result == {"bill_id": "hr123-117"}
    
    async def test_basic_routing_for_document(self, router, mock_govinfo_client):
        """Test basic routing for document data."""
        # Setup return value
        mock_govinfo_client.get_package_summary.return_value = {"package_id": "BILLS-117hr123ih"}
        
        # Route a request for document data
        result = await router.route_request(
            request_type="document",
            method="get_package_summary",
            package_id="BILLS-117hr123ih"
        )
        
        # Verify the GovInfo client was used
        mock_govinfo_client.get_package_summary.assert_called_once_with(
            package_id="BILLS-117hr123ih"
        )
        assert result == {"package_id": "BILLS-117hr123ih"}
    
    async def test_routing_to_unavailable_source(self, router):
        """Test routing when a source is not available."""
        # Remove the client
        router.clients.pop(ApiSource.CONGRESS)
        
        # Route a request for bill data
        with pytest.raises(SourceUnavailableError):
            await router.route_request(
                request_type="bill",
                method="get_bill",
                congress=117,
                bill_type="hr",
                bill_number=123
            )
    
    async def test_routing_with_method_error(self, router, mock_congress_client):
        """Test routing when the method raises an error."""
        # Make the method raise an error
        mock_congress_client.get_bill.side_effect = ApiError(
            message="API error", 
            status_code=500,
            api_name="congress",
            endpoint="/bills"
        )
        
        # Route a request that will fail
        with pytest.raises(ApiError):
            await router.route_request(
                request_type="bill",
                method="get_bill",
                congress=117,
                bill_type="hr",
                bill_number=123
            )
    
    async def test_routing_with_rate_limit_error_no_fallback(self, router, mock_congress_client):
        """Test routing with rate limit error when there's no fallback."""
        # Make the method raise a rate limit error
        mock_congress_client.get_bill.side_effect = RateLimitExceededError(
            message="Rate limit exceeded", 
            retry_after=3600,
            api_source=ApiErrorSource.CONGRESS
        )
        
        # Route a request that will hit rate limit
        with pytest.raises(RateLimitExceededError):
            await router.route_request(
                request_type="bill",
                method="get_bill",
                congress=117,
                bill_type="hr",
                bill_number=123
            )
    
    async def test_routing_with_unknown_request_type(self, router):
        """Test routing with an unknown request type."""
        with pytest.raises(RouterError):
            await router.route_request(
                request_type="unknown",
                method="some_method",
                param1="value1"
            )
    
    async def test_routing_with_unknown_method(self, router):
        """Test routing with an unknown method."""
        with pytest.raises(RouterError):
            await router.route_request(
                request_type="bill",
                method="unknown_method",
                param1="value1"
            )
    
    async def test_route_document_request_by_criteria(self, router, mock_govinfo_client):
        """Test routing document request by criteria rather than direct method."""
        # Setup return value
        mock_govinfo_client.get_package_summary.return_value = {"package_id": "BILLS-117hr123ih"}
        
        # Route a request using criteria
        result = await router.route_document_request(
            document_type="bill",
            congress=117,
            bill_type="hr",
            bill_number=123,
            version_code="ih"
        )
        
        # Verify the method was called correctly
        mock_govinfo_client.get_package_summary.assert_called_once()
        assert result == {"package_id": "BILLS-117hr123ih"}
    
    async def test_check_source_availability(self, router):
        """Test checking source availability."""
        # All registered sources should be available
        assert router.is_source_available(ApiSource.CONGRESS)
        assert router.is_source_available(ApiSource.GOVINFO)
        
        # Unregistered source should not be available
        assert not router.is_source_available("UNKNOWN")

    async def test_get_client_for_source(self, router, mock_congress_client, mock_govinfo_client):
        """Test getting client for a source."""
        # Get client for registered sources
        assert router.get_client(ApiSource.CONGRESS) == mock_congress_client
        assert router.get_client(ApiSource.GOVINFO) == mock_govinfo_client
        
        # Get client for unregistered source
        with pytest.raises(SourceUnavailableError):
            router.get_client("UNKNOWN")
    
    async def test_document_source_selection(self, router, mock_govinfo_client):
        """Test document source selection."""
        # Setup return value
        mock_govinfo_client.get_package_summary.return_value = {"package_id": "BILLS-117hr123ih"}
        
        # Test that document requests are routed to GovInfo
        await router.route_request(
            request_type="document",
            method="get_package_summary",
            package_id="BILLS-117hr123ih"
        )
        
        # Verify GovInfo client was used
        mock_govinfo_client.get_package_summary.assert_called_once_with(
            package_id="BILLS-117hr123ih"
        )
    
    async def test_status_source_selection(self, router, mock_congress_client):
        """Test status source selection."""
        # Setup return value
        mock_congress_client.get_bill_status.return_value = {"bill_id": "hr123-117", "status": "Introduced"}
        
        # Test that status requests are routed to Congress.gov
        await router.route_request(
            request_type="bill",
            method="get_bill_status",
            congress=117,
            bill_type="hr",
            bill_number=123
        )
        
        # Verify Congress client was used
        mock_congress_client.get_bill_status.assert_called_once_with(
            congress=117, bill_type="hr", bill_number=123
        )
    
    async def test_member_source_selection(self, router, mock_congress_client):
        """Test member source selection."""
        # Setup return value
        mock_congress_client.get_member.return_value = {"member_id": "S123", "name": "Test Member"}
        
        # Test that member requests are routed to Congress.gov
        await router.route_request(
            request_type="member",
            method="get_member",
            member_id="S123"
        )
        
        # Verify Congress client was used
        mock_congress_client.get_member.assert_called_once_with(
            member_id="S123"
        )
    
    async def test_response_mapping(self, router, mock_congress_client):
        """Test response mapping between different sources."""
        # Setup a custom bill response
        congress_bill = {
            "congress": 117,
            "bill_type": "hr",
            "bill_number": 123,
            "title": "Test Bill",
            "congress_gov_url": "https://www.congress.gov/bill/117th-congress/house-bill/123",
            "introduced_date": "2023-01-15",
            "sponsor": {"name": "Test Sponsor", "state": "CA"}
        }
        
        # Set up the mock to return our custom response
        mock_congress_client.get_bill.return_value = congress_bill
        
        # Get a normalized response
        result = await router.get_normalized_bill(
            congress=117,
            bill_type="hr",
            bill_number=123
        )
        
        # Verify the response is normalized to a common format
        assert "id" in result
        assert "title" in result
        assert "introduced_date" in result
        assert "source" in result
        assert "source_url" in result
        assert "sponsor" in result
        
        # Verify values are mapped correctly
        assert result["id"] == "hr123-117"
        assert result["title"] == "Test Bill"
        assert result["introduced_date"] == "2023-01-15"
        assert result["source"] == "congress"
        assert result["source_url"] == "https://www.congress.gov/bill/117th-congress/house-bill/123"
    
    async def test_field_normalization(self, router, mock_congress_client, mock_govinfo_client):
        """Test field normalization between different sources."""
        # Setup different representations of the same data
        congress_bill = {
            "congress": 117,
            "bill_type": "hr",
            "bill_number": 123,
            "title": "Test Bill",
            "latest_action": {"date": "2023-02-01", "text": "Referred to Committee"}
        }
        
        govinfo_bill = {
            "congress": "117",
            "billType": "hr",
            "billNumber": "123",
            "title": "Test Bill",
            "currentChamber": "House",
            "lastAction": {"actionDate": "2023-02-01", "actionDesc": "Referred to Committee"}
        }
        
        # Set up the mocks
        mock_congress_client.get_bill.return_value = congress_bill
        mock_govinfo_client.get_package_summary.return_value = govinfo_bill
        
        # Test getting normalized data from both sources
        congress_result = await router.get_normalized_bill(
            congress=117,
            bill_type="hr",
            bill_number=123,
            source=ApiSource.CONGRESS
        )
        
        govinfo_result = await router.get_normalized_bill(
            congress=117,
            bill_type="hr",
            bill_number=123,
            source=ApiSource.GOVINFO
        )
        
        # Verify both results have the same normalized structure
        assert "id" in congress_result
        assert "id" in govinfo_result
        assert "latest_action" in congress_result
        assert "latest_action" in govinfo_result
        
        # Verify that date formats and field values are normalized
        assert congress_result["id"] == govinfo_result["id"]
        assert congress_result["latest_action"]["date"] == govinfo_result["latest_action"]["date"]
        assert congress_result["latest_action"]["text"] == govinfo_result["latest_action"]["text"]
    
    async def test_model_transformation(self, router, mock_congress_client):
        """Test transformation to internal models."""
        # Setup a custom bill response
        congress_bill = {
            "congress": 117,
            "bill_type": "hr",
            "bill_number": 123,
            "title": "Test Bill",
            "congress_gov_url": "https://www.congress.gov/bill/117th-congress/house-bill/123",
            "introduced_date": "2023-01-15",
            "sponsor": {"name": "Test Sponsor", "state": "CA"}
        }
        
        # Set up the mock to return our custom response
        mock_congress_client.get_bill.return_value = congress_bill
        
        # Get a model-based response
        bill_model = await router.get_bill_model(
            congress=117,
            bill_type="hr",
            bill_number=123
        )
        
        # Verify we get back a proper model object
        assert hasattr(bill_model, "bill_id")
        assert hasattr(bill_model, "title")
        assert hasattr(bill_model, "introduced_date")
        assert hasattr(bill_model, "sponsor")
        
        # Verify values are correct
        assert bill_model.bill_id == "hr123-117"
        assert bill_model.title == "Test Bill"
        assert bill_model.bill_type == BillType.HOUSE_BILL
        assert bill_model.bill_number == 123
        assert bill_model.congress == 117
        
    async def test_rate_limit_checking(self, router, mock_congress_client, mock_govinfo_client):
        """Test rate limit checking."""
        # Setup rate limit info
        mock_congress_client.auth_manager.check_rate_limit = AsyncMock(return_value=True)
        mock_govinfo_client.auth_manager.check_rate_limit = AsyncMock(return_value=False)
        
        # Check rate limits
        assert await router.check_rate_limit(ApiSource.CONGRESS) is True
        assert await router.check_rate_limit(ApiSource.GOVINFO) is False
        
        # Verify the correct methods were called
        mock_congress_client.auth_manager.check_rate_limit.assert_called_once()
        mock_govinfo_client.auth_manager.check_rate_limit.assert_called_once()
        
    async def test_source_selection_based_on_limits(self, router, mock_congress_client, mock_govinfo_client):
        """Test source selection based on rate limits."""
        # Setup rate limit info
        mock_congress_client.auth_manager.check_rate_limit = AsyncMock(return_value=False)
        mock_govinfo_client.auth_manager.check_rate_limit = AsyncMock(return_value=True)
        
        # Setup return values for both clients
        mock_congress_client.get_bill.return_value = {"bill_id": "hr123-117", "source": "congress"}
        mock_govinfo_client.get_package_summary.return_value = {"packageId": "BILLS-117hr123ih", "source": "govinfo"}
        mock_govinfo_client.resolve_bill_package_id = AsyncMock(return_value="BILLS-117hr123ih")
        
        # Route a request that should use GovInfo due to rate limits
        result = await router.get_bill_with_rate_limit_aware_routing(
            congress=117,
            bill_type="hr",
            bill_number=123
        )
        
        # Verify GovInfo was used due to rate limits
        assert result.get("source") == "govinfo"
        mock_govinfo_client.get_package_summary.assert_called_once()
        mock_congress_client.get_bill.assert_not_called()
        
    async def test_limit_enforcement(self, router, mock_congress_client, mock_govinfo_client):
        """Test rate limit enforcement."""
        # Setup rate limit info - both sources rate limited
        mock_congress_client.auth_manager.check_rate_limit = AsyncMock(return_value=False)
        mock_govinfo_client.auth_manager.check_rate_limit = AsyncMock(return_value=False)
        
        # Attempt to route a request when all sources are rate limited
        with pytest.raises(RateLimitExceededError):
            await router.get_bill_with_rate_limit_aware_routing(
                congress=117,
                bill_type="hr",
                bill_number=123
            )
            
        # Verify both sources were checked
        mock_congress_client.auth_manager.check_rate_limit.assert_called_once()
        mock_govinfo_client.auth_manager.check_rate_limit.assert_called_once()