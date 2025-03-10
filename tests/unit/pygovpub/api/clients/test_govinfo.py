"""
Unit tests for the GovInfo.gov API client.
"""

import asyncio
import json
from datetime import date, datetime
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from pygovpub.api.clients.govinfo import GovInfoClient
from pygovpub.auth.auth_manager import AuthManager
from pygovpub.auth.models import ApiSource
from pygovpub.exceptions import ApiError, GovInfoApiError, AuthenticationError, RateLimitExceededError
from pygovpub.models.documents import (
    Collection, Package, Granule, DocumentFormat, DocumentType, SourceReference
)


class TestGovInfoClient:
    """Tests for the GovInfo.gov API client."""
    
    @pytest.fixture
    def mock_auth_manager(self):
        """Create a mock auth manager."""
        auth_manager = MagicMock(spec=AuthManager)
        auth_manager.execute_request = AsyncMock()
        auth_manager.authenticate_request = MagicMock(return_value={
            "url": "https://api.govinfo.gov/test",
            "method": "GET",
            "params": {"api_key": "test_key"},
            "headers": {}
        })
        return auth_manager
    
    @pytest.fixture
    def client(self, mock_auth_manager):
        """Create a client with mock auth manager."""
        return GovInfoClient(auth_manager=mock_auth_manager)
    
    @pytest.fixture
    def mock_collections_response(self):
        """Create a mock collections response."""
        return {
            "collections": [
                {
                    "collectionCode": "BILLS",
                    "collectionName": "Congressional Bills",
                    "collectionSize": 12345,
                    "lastModified": "2023-02-01T12:34:56Z"
                },
                {
                    "collectionCode": "FR",
                    "collectionName": "Federal Register",
                    "collectionSize": 54321,
                    "lastModified": "2023-02-01T13:45:10Z"
                }
            ]
        }
    
    @pytest.fixture
    def mock_collection_response(self):
        """Create a mock collection response."""
        return {
            "count": 2,
            "nextPage": "https://api.govinfo.gov/collections/BILLS?offset=300&pageSize=150",
            "previousPage": None,
            "packages": [
                {
                    "packageId": "BILLS-117hr1234ih",
                    "lastModified": "2023-01-15T12:00:00Z",
                    "packageLink": "https://api.govinfo.gov/packages/BILLS-117hr1234ih/summary"
                },
                {
                    "packageId": "BILLS-117s5678is",
                    "lastModified": "2023-01-20T14:30:00Z",
                    "packageLink": "https://api.govinfo.gov/packages/BILLS-117s5678is/summary"
                }
            ]
        }
    
    @pytest.fixture
    def mock_package_summary_response(self):
        """Create a mock package summary response."""
        return {
            "dateIssued": "2023-01-15",
            "lastModified": "2023-01-15T12:00:00Z",
            "title": "A bill to amend the test act",
            "download": {
                "pdfLink": "https://api.govinfo.gov/packages/BILLS-117hr1234ih/pdf",
                "xmlLink": "https://api.govinfo.gov/packages/BILLS-117hr1234ih/xml",
                "modsLink": "https://api.govinfo.gov/packages/BILLS-117hr1234ih/mods"
            },
            "related": {
                "billStatus": "https://api.govinfo.gov/related/BILLS-117hr1234ih/billStatus"
            },
            "branch": "legislative",
            "congress": "117",
            "docClass": "bill",
            "billType": "hr",
            "billNumber": "1234"
        }
    
    @pytest.fixture
    def mock_granules_response(self):
        """Create a mock granules response."""
        return {
            "count": 2,
            "nextPage": None,
            "previousPage": None,
            "granules": [
                {
                    "granuleId": "CREC-2023-01-15-pt1-PgH123",
                    "title": "TEST LEGISLATION",
                    "granuleClass": "HOUSE",
                    "lastModified": "2023-01-15T12:00:00Z",
                    "granuleLink": "https://api.govinfo.gov/packages/CREC-2023-01-15/granules/CREC-2023-01-15-pt1-PgH123/summary"
                },
                {
                    "granuleId": "CREC-2023-01-15-pt1-PgH124",
                    "title": "ANNOUNCEMENTS",
                    "granuleClass": "HOUSE",
                    "lastModified": "2023-01-15T12:00:00Z",
                    "granuleLink": "https://api.govinfo.gov/packages/CREC-2023-01-15/granules/CREC-2023-01-15-pt1-PgH124/summary"
                }
            ]
        }
    
    @pytest.fixture
    def mock_granule_summary_response(self):
        """Create a mock granule summary response."""
        return {
            "dateIssued": "2023-01-15",
            "lastModified": "2023-01-15T12:00:00Z",
            "title": "TEST LEGISLATION",
            "download": {
                "pdfLink": "https://api.govinfo.gov/packages/CREC-2023-01-15/granules/CREC-2023-01-15-pt1-PgH123/pdf",
                "xmlLink": "https://api.govinfo.gov/packages/CREC-2023-01-15/granules/CREC-2023-01-15-pt1-PgH123/xml",
                "modsLink": "https://api.govinfo.gov/packages/CREC-2023-01-15/granules/CREC-2023-01-15-pt1-PgH123/mods"
            },
            "granuleClass": "HOUSE",
            "congress": "117",
            "docClass": "crec"
        }
    
    async def test_list_collections(self, client, mock_auth_manager, mock_collections_response):
        """Test listing collections."""
        # Set up the mock to return our test data
        mock_auth_manager.execute_request.return_value = mock_collections_response
        
        # Call the method under test
        collections = await client.list_collections()
        
        # Verify the auth manager was called correctly
        mock_auth_manager.execute_request.assert_called_once_with(
            source=ApiSource.GOVINFO,
            endpoint="/collections",
            method="GET",
            params=None,
            headers=None,
            json_data=None,
            timeout=30
        )
        
        # Verify the returned objects
        assert len(collections) == 2
        assert isinstance(collections[0], Collection)
        
        # First collection
        assert collections[0].code == "BILLS"
        assert collections[0].name == "Congressional Bills"
        assert collections[0].member_count == 12345
        assert collections[0].last_updated.replace(tzinfo=None) == datetime(2023, 2, 1, 12, 34, 56)
        
        # Second collection
        assert collections[1].code == "FR"
        assert collections[1].name == "Federal Register"
        assert collections[1].member_count == 54321
    
    async def test_get_collection(self, client, mock_auth_manager, mock_collection_response):
        """Test getting a collection."""
        # Set up the mock to return our test data
        mock_auth_manager.execute_request.return_value = mock_collection_response
        
        # Call the method under test
        result = await client.get_collection(
            collection_code="BILLS",
            offset=0,
            page_size=150
        )
        
        # Verify the auth manager was called correctly
        mock_auth_manager.execute_request.assert_called_once_with(
            source=ApiSource.GOVINFO,
            endpoint="/collections/BILLS",
            method="GET",
            params={"offset": 0, "pageSize": 150},
            headers=None,
            json_data=None,
            timeout=30
        )
        
        # Verify the returned objects
        assert "packages" in result
        assert "pagination" in result
        assert len(result["packages"]) == 2
        assert result["pagination"]["count"] == 2
        assert result["pagination"]["next_page"] == "https://api.govinfo.gov/collections/BILLS?offset=300&pageSize=150"
        
        # First package
        package1 = result["packages"][0]
        assert isinstance(package1, Package)
        assert package1.package_id == "BILLS-117hr1234ih"
        assert package1.collection_code == "BILLS"
        assert package1.last_modified.replace(tzinfo=None) == datetime(2023, 1, 15, 12, 0, 0)
        
        # Second package
        package2 = result["packages"][1]
        assert package2.package_id == "BILLS-117s5678is"
    
    async def test_get_collection_with_dates(self, client, mock_auth_manager, mock_collection_response):
        """Test getting a collection with date range."""
        # Set up the mock to return our test data
        mock_auth_manager.execute_request.return_value = mock_collection_response
        
        # Call the method under test with date parameters
        result = await client.get_collection(
            collection_code="BILLS",
            start_date="2023-01-01",
            end_date="2023-01-31",
            offset=0,
            page_size=150
        )
        
        # Verify the auth manager was called correctly with date parameters
        mock_auth_manager.execute_request.assert_called_once_with(
            source=ApiSource.GOVINFO,
            endpoint="/collections/BILLS/2023-01-01/2023-01-31",
            method="GET",
            params={"offset": 0, "pageSize": 150},
            headers=None,
            json_data=None,
            timeout=30
        )
        
        # Verify we get valid results
        assert "packages" in result
        assert "pagination" in result
    
    async def test_get_collection_with_date_objects(self, client, mock_auth_manager, mock_collection_response):
        """Test getting a collection with date objects."""
        # Set up the mock to return our test data
        mock_auth_manager.execute_request.return_value = mock_collection_response
        
        # Call the method with date objects
        start_date = date(2023, 1, 1)
        end_date = date(2023, 1, 31)
        
        result = await client.get_collection(
            collection_code="BILLS",
            start_date=start_date,
            end_date=end_date
        )
        
        # Verify the auth manager was called correctly with formatted dates
        mock_auth_manager.execute_request.assert_called_once_with(
            source=ApiSource.GOVINFO,
            endpoint="/collections/BILLS/2023-01-01/2023-01-31",
            method="GET",
            params={"offset": 0, "pageSize": 100},
            headers=None,
            json_data=None,
            timeout=30
        )
    
    async def test_get_package_summary(self, client, mock_auth_manager, mock_package_summary_response):
        """Test getting a package summary."""
        # Set up the mock to return our test data
        mock_auth_manager.execute_request.return_value = mock_package_summary_response
        
        # Call the method under test
        package = await client.get_package_summary(package_id="BILLS-117hr1234ih")
        
        # Verify the auth manager was called correctly
        mock_auth_manager.execute_request.assert_called_once_with(
            source=ApiSource.GOVINFO,
            endpoint="/packages/BILLS-117hr1234ih/summary",
            method="GET",
            params=None,
            headers=None,
            json_data=None,
            timeout=30
        )
        
        # Verify the returned object
        assert isinstance(package, Package)
        assert package.package_id == "BILLS-117hr1234ih"
        assert package.collection_code == "BILLS"
        assert package.title == "A bill to amend the test act"
        assert package.date_issued == date(2023, 1, 15)
        assert package.last_modified.replace(tzinfo=None) == datetime(2023, 1, 15, 12, 0, 0)
        assert package.pdf_url == "https://api.govinfo.gov/packages/BILLS-117hr1234ih/pdf"
        assert package.xml_url == "https://api.govinfo.gov/packages/BILLS-117hr1234ih/xml"
        assert package.mods_url == "https://api.govinfo.gov/packages/BILLS-117hr1234ih/mods"
        
        # Verify formats
        assert DocumentFormat.PDF in package.formats
        assert DocumentFormat.XML in package.formats
        assert DocumentFormat.MODS in package.formats
        
        # Verify source reference
        assert package.source_reference.source == ApiSource.GOVINFO
        assert package.source_reference.source_id == "BILLS-117hr1234ih"
    
    async def test_list_package_granules(self, client, mock_auth_manager, mock_granules_response):
        """Test listing package granules."""
        # Set up the mock to return our test data
        mock_auth_manager.execute_request.return_value = mock_granules_response
        
        # Call the method under test
        result = await client.list_package_granules(
            package_id="CREC-2023-01-15",
            offset=0,
            page_size=100
        )
        
        # Verify the auth manager was called correctly
        mock_auth_manager.execute_request.assert_called_once_with(
            source=ApiSource.GOVINFO,
            endpoint="/packages/CREC-2023-01-15/granules",
            method="GET",
            params={"offset": 0, "pageSize": 100},
            headers=None,
            json_data=None,
            timeout=30
        )
        
        # Verify the returned objects
        assert "granules" in result
        assert "pagination" in result
        assert len(result["granules"]) == 2
        assert result["pagination"]["count"] == 2
        
        # First granule
        granule1 = result["granules"][0]
        assert isinstance(granule1, Granule)
        assert granule1.granule_id == "CREC-2023-01-15-pt1-PgH123"
        assert granule1.package_id == "CREC-2023-01-15"
        assert granule1.title == "TEST LEGISLATION"
        assert granule1.last_modified.replace(tzinfo=None) == datetime(2023, 1, 15, 12, 0, 0)
        
        # Second granule
        granule2 = result["granules"][1]
        assert granule2.granule_id == "CREC-2023-01-15-pt1-PgH124"
        assert granule2.title == "ANNOUNCEMENTS"
    
    async def test_get_granule_summary(self, client, mock_auth_manager, mock_granule_summary_response):
        """Test getting a granule summary."""
        # Set up the mock to return our test data
        mock_auth_manager.execute_request.return_value = mock_granule_summary_response
        
        # Call the method under test
        granule = await client.get_granule_summary(
            package_id="CREC-2023-01-15",
            granule_id="CREC-2023-01-15-pt1-PgH123"
        )
        
        # Verify the auth manager was called correctly
        mock_auth_manager.execute_request.assert_called_once_with(
            source=ApiSource.GOVINFO,
            endpoint="/packages/CREC-2023-01-15/granules/CREC-2023-01-15-pt1-PgH123/summary",
            method="GET",
            params=None,
            headers=None,
            json_data=None,
            timeout=30
        )
        
        # Verify the returned object
        assert isinstance(granule, Granule)
        assert granule.granule_id == "CREC-2023-01-15-pt1-PgH123"
        assert granule.package_id == "CREC-2023-01-15"
        assert granule.title == "TEST LEGISLATION"
        assert granule.date_issued == date(2023, 1, 15)
        assert granule.last_modified.replace(tzinfo=None) == datetime(2023, 1, 15, 12, 0, 0)
        assert granule.pdf_url == "https://api.govinfo.gov/packages/CREC-2023-01-15/granules/CREC-2023-01-15-pt1-PgH123/pdf"
        assert granule.xml_url == "https://api.govinfo.gov/packages/CREC-2023-01-15/granules/CREC-2023-01-15-pt1-PgH123/xml"
        assert granule.mods_url == "https://api.govinfo.gov/packages/CREC-2023-01-15/granules/CREC-2023-01-15-pt1-PgH123/mods"
        
        # Verify formats
        assert DocumentFormat.PDF in granule.formats
        assert DocumentFormat.XML in granule.formats
        assert DocumentFormat.MODS in granule.formats
        
        # Verify source reference
        assert granule.source_reference.source == ApiSource.GOVINFO
        assert granule.source_reference.source_id == "CREC-2023-01-15/CREC-2023-01-15-pt1-PgH123"
    
    async def test_get_package_content(self, client, mock_auth_manager):
        """Test getting package content."""
        # The content retrieval method is a placeholder, so we'll just test the interface
        content = await client.get_package_content(
            package_id="BILLS-117hr1234ih",
            content_type=DocumentFormat.PDF
        )
        
        # Verify auth_manager.authenticate_request was called correctly
        mock_auth_manager.authenticate_request.assert_called_once_with(
            source=ApiSource.GOVINFO,
            endpoint="/packages/BILLS-117hr1234ih/pdf"
        )
        
        # Verify we get an empty bytes object (placeholder implementation)
        assert isinstance(content, bytes)
        assert len(content) == 0
    
    async def test_get_granule_content(self, client, mock_auth_manager):
        """Test getting granule content."""
        # The content retrieval method is a placeholder, so we'll just test the interface
        content = await client.get_granule_content(
            package_id="CREC-2023-01-15",
            granule_id="CREC-2023-01-15-pt1-PgH123",
            content_type=DocumentFormat.XML
        )
        
        # Verify auth_manager.authenticate_request was called correctly
        mock_auth_manager.authenticate_request.assert_called_once_with(
            source=ApiSource.GOVINFO,
            endpoint="/packages/CREC-2023-01-15/granules/CREC-2023-01-15-pt1-PgH123/xml"
        )
        
        # Verify we get an empty bytes object (placeholder implementation)
        assert isinstance(content, bytes)
        assert len(content) == 0
    
    async def test_resolve_bill_package_id(self, client):
        """Test resolving bill package ID."""
        # Call the method under test
        package_id = await client.resolve_bill_package_id(
            congress=117,
            bill_type="hr",
            bill_number=1234,
            version_code="ih"
        )
        
        # Verify the result
        assert package_id == "BILLS-117hr1234ih"
    
    async def test_resolve_bill_package_id_validation(self, client):
        """Test validation in bill package ID resolution."""
        # Test with missing parameters
        with pytest.raises(ValueError, match="All parameters are required"):
            await client.resolve_bill_package_id(
                congress=None,
                bill_type="hr",
                bill_number=1234,
                version_code="ih"
            )
    
    async def test_resolve_fr_package_id(self, client):
        """Test resolving Federal Register package ID."""
        # Call the method under test
        package_id = await client.resolve_fr_package_id(
            date_str="2023-02-15",
            fr_doc_number="2023-12345"
        )
        
        # Verify the result
        assert package_id == "FR-2023-02-15_2023-12345"
    
    async def test_resolve_fr_package_id_validation(self, client):
        """Test validation in FR package ID resolution."""
        # Test with missing parameters
        with pytest.raises(ValueError, match="Date and document number are required"):
            await client.resolve_fr_package_id(
                date_str="",
                fr_doc_number="2023-12345"
            )
    
    async def test_error_handling(self, client, mock_auth_manager):
        """Test error handling."""
        # Make the mock raise an error
        mock_auth_manager.execute_request.side_effect = GovInfoApiError("API error", status_code=500)
        
        # Verify that the error is propagated
        with pytest.raises(GovInfoApiError):
            await client.list_collections()
    
    async def test_invalid_response_validation(self, client, mock_auth_manager):
        """Test invalid response validation."""
        # Create a mock response missing required fields
        mock_response = {
            "request": {"url": "https://api.govinfo.gov/collections"}
            # Missing 'collections' field
        }
        
        # Setup mock
        mock_auth_manager.execute_request.return_value = mock_response
        
        # Test collections endpoint validation
        with pytest.raises(GovInfoApiError, match="Invalid collections response format"):
            await client.list_collections()
    
    async def test_all_endpoint_validations(self, client, mock_auth_manager):
        """Test validation errors for all endpoints."""
        # Create a mock invalid response
        mock_response = {
            "request": {"url": "https://api.govinfo.gov/endpoint"}
            # Missing required fields
        }
        
        # Setup mock
        mock_auth_manager.execute_request.return_value = mock_response
        
        # Test collection endpoint validation
        with pytest.raises(GovInfoApiError, match="Invalid collection response format"):
            await client.get_collection(collection_code="BILLS")
            
        # Test package summary endpoint validation
        with pytest.raises(GovInfoApiError, match="Invalid package summary response format"):
            await client.get_package_summary(package_id="BILLS-117hr1234ih")
            
        # Test granules endpoint validation
        with pytest.raises(GovInfoApiError, match="Invalid granules response format"):
            await client.list_package_granules(package_id="CREC-2023-01-15")
            
        # Test granule summary endpoint validation
        with pytest.raises(GovInfoApiError, match="Invalid granule summary response format"):
            await client.get_granule_summary(
                package_id="CREC-2023-01-15",
                granule_id="CREC-2023-01-15-pt1-PgH123"
            )
    
    def test_parse_date(self, client, monkeypatch):
        """Test date parsing."""
        # Save the original warning method
        import logging
        original_warning = logging.Logger.warning
        
        # Replace with a no-op for our test
        def mock_warning(self, msg, *args, **kwargs):
            # Don't do anything
            pass
            
        # Apply the monkeypatch
        monkeypatch.setattr(logging.Logger, "warning", mock_warning)
        
        try:
            # Test ISO date
            assert client._parse_date("2023-01-15") == date(2023, 1, 15)
            
            # Test ISO datetime
            assert client._parse_date("2023-01-15T12:34:56Z") == date(2023, 1, 15)
            
            # Test None
            assert client._parse_date(None) is None
            
            # Test invalid date - now without warning
            assert client._parse_date("not-a-date") is None
        finally:
            # Restore the original warning method
            monkeypatch.setattr(logging.Logger, "warning", original_warning)
    
    def test_parse_datetime(self, client, monkeypatch):
        """Test datetime parsing."""
        # Save the original warning method
        import logging
        original_warning = logging.Logger.warning
        
        # Replace with a no-op for our test
        def mock_warning(self, msg, *args, **kwargs):
            # Don't do anything
            pass
            
        # Apply the monkeypatch
        monkeypatch.setattr(logging.Logger, "warning", mock_warning)
        
        try:
            # Test ISO datetime
            dt = client._parse_datetime("2023-01-15T12:34:56Z")
            assert dt.replace(tzinfo=None) == datetime(2023, 1, 15, 12, 34, 56)
            
            # Test ISO date (should convert to datetime)
            dt = client._parse_datetime("2023-01-15")
            assert dt.date() == date(2023, 1, 15)
            assert dt.hour == 0
            assert dt.minute == 0
            
            # Test None
            assert client._parse_datetime(None) is None
            
            # Test invalid datetime
            assert client._parse_datetime("not-a-datetime") is None
        finally:
            # Restore the original warning method
            monkeypatch.setattr(logging.Logger, "warning", original_warning)
    
    def test_format_date(self, client):
        """Test date formatting."""
        # Test date object
        d = date(2023, 1, 15)
        assert client._format_date(d) == "2023-01-15"
        
        # Test datetime object
        dt = datetime(2023, 1, 15, 12, 34, 56)
        assert client._format_date(dt) == "2023-01-15T12:34:56Z"
    
    def test_get_document_type(self, client):
        """Test document type determination."""
        # Test various package IDs
        assert client._get_document_type("BILLS-117hr1234ih") == DocumentType.BILL
        assert client._get_document_type("FR-2023-01-15_2023-12345") == DocumentType.FEDERAL_REGISTER
        assert client._get_document_type("CREC-2023-01-15") == DocumentType.CONGRESSIONAL_RECORD
        assert client._get_document_type("CFR-2023-title10-vol1") == DocumentType.CODE_OF_FEDERAL_REGULATIONS
        assert client._get_document_type("STATUTE-123-123") == DocumentType.STATUTE
        assert client._get_document_type("PLAW-117publ123") == DocumentType.PUBLIC_LAW
        assert client._get_document_type("CHRG-117hhrg12345") == DocumentType.CONGRESSIONAL_HEARING
        assert client._get_document_type("CPRT-117sprt12345") == DocumentType.CONGRESSIONAL_REPORT
        assert client._get_document_type("CDOC-117hdoc12345") == DocumentType.CONGRESSIONAL_DOCUMENT
        assert client._get_document_type("USCOURTS-ca1-12-12345") == DocumentType.COURT_OPINION
        assert client._get_document_type("UNKNOWN-TYPE") == DocumentType.OTHER
    
    def test_transform_collections_response(self, client):
        """Test transforming collections response."""
        # Create test response
        response = {
            "collections": [
                {
                    "collectionCode": "BILLS",
                    "collectionName": "Congressional Bills",
                    "collectionSize": 12345,
                    "lastModified": "2023-02-01T12:34:56Z"
                }
            ]
        }
        
        # Call transform method
        collections = client._transform_collections_response(response)
        
        # Verify results
        assert len(collections) == 1
        assert isinstance(collections[0], Collection)
        assert collections[0].code == "BILLS"
        assert collections[0].name == "Congressional Bills"
        assert collections[0].member_count == 12345
        assert collections[0].last_updated.replace(tzinfo=None) == datetime(2023, 2, 1, 12, 34, 56)
    
    def test_transform_collection_response(self, client):
        """Test transforming collection response."""
        # Create test response
        response = {
            "count": 1,
            "nextPage": None,
            "previousPage": None,
            "packages": [
                {
                    "packageId": "BILLS-117hr1234ih",
                    "lastModified": "2023-01-15T12:00:00Z",
                    "packageLink": "https://api.govinfo.gov/packages/BILLS-117hr1234ih/summary"
                }
            ]
        }
        
        # Call transform method
        result = client._transform_collection_response(response, "BILLS")
        
        # Verify results
        assert "packages" in result
        assert "pagination" in result
        assert len(result["packages"]) == 1
        assert isinstance(result["packages"][0], Package)
        assert result["packages"][0].package_id == "BILLS-117hr1234ih"
        assert result["packages"][0].collection_code == "BILLS"
    
    def test_transform_package_summary_response(self, client):
        """Test transforming package summary response."""
        # Create test response
        response = {
            "dateIssued": "2023-01-15",
            "lastModified": "2023-01-15T12:00:00Z",
            "title": "A bill to amend the test act",
            "download": {
                "pdfLink": "https://api.govinfo.gov/packages/BILLS-117hr1234ih/pdf",
                "xmlLink": "https://api.govinfo.gov/packages/BILLS-117hr1234ih/xml"
            }
        }
        
        # Call transform method
        package = client._transform_package_summary_response(response, "BILLS-117hr1234ih")
        
        # Verify results
        assert isinstance(package, Package)
        assert package.package_id == "BILLS-117hr1234ih"
        assert package.collection_code == "BILLS"
        assert package.title == "A bill to amend the test act"
        assert package.date_issued == date(2023, 1, 15)
        assert package.last_modified.replace(tzinfo=None) == datetime(2023, 1, 15, 12, 0, 0)
        assert package.pdf_url == "https://api.govinfo.gov/packages/BILLS-117hr1234ih/pdf"
        assert package.xml_url == "https://api.govinfo.gov/packages/BILLS-117hr1234ih/xml"