"""
Tests for data transformation utilities.

This module tests the transformation functions that convert different 
API response formats to the unified PyGovPub format.
"""

import pytest
from datetime import datetime, timezone
from typing import Any, Dict, List
import tempfile
import os
import json
import warnings
from contextlib import contextmanager

# Context manager to suppress specific jsonschema warnings
@contextmanager
def suppress_jsonschema_warnings():
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="The metaschema specified by \\$schema was not found.*",
            category=DeprecationWarning
        )
        yield

from pygovpub.auth.models import ApiSource
from pygovpub.models.response import ApiResponse
from pygovpub.models.transformers import (
    transform_congress_response,
    transform_govinfo_response,
    create_error_response
)
from pygovpub.core.schema_monitor import SchemaMonitor


class TestCongressTransformer:
    """Tests for Congress.gov API response transformation."""
    
    def test_transform_congress_empty_response(self):
        """Test transformation of an empty Congress.gov response."""
        # Mock Congress.gov API empty response
        congress_response = {
            "pagination": {
                "count": 0,
                "nextPage": None
            },
            "request": {
                "contentType": "application/json",
                "format": ""
            },
            "results": []
        }
        
        # Transform the response
        result = transform_congress_response(congress_response, "bills")
        
        # Verify the transformed response
        assert isinstance(result, ApiResponse)
        assert result.is_success is True
        assert result.metadata.source == ApiSource.CONGRESS
        assert result.pagination.count == 0
        assert result.pagination.total_count == 0
        assert result.pagination.offset == 0
        assert result.pagination.has_next_page is False
        assert result.data == []
    
    def test_transform_congress_bill_response(self):
        """Test transformation of a Congress.gov bills response."""
        # Mock Congress.gov API bill response
        congress_response = {
            "pagination": {
                "count": 2,
                "nextPage": "https://api.congress.gov/v3/bill?offset=2&limit=2"
            },
            "request": {
                "contentType": "application/json",
                "format": ""
            },
            "results": [
                {
                    "congress": 117,
                    "number": "1234",
                    "type": "HR",
                    "title": "Test Bill 1",
                    "updateDate": "2023-05-15",
                    "updateDateIncludingText": "2023-05-20",
                    "originChamber": "House",
                    "introducedDate": "2023-01-10"
                },
                {
                    "congress": 117,
                    "number": "5678",
                    "type": "S",
                    "title": "Test Bill 2",
                    "updateDate": "2023-05-16",
                    "updateDateIncludingText": "2023-05-21",
                    "originChamber": "Senate",
                    "introducedDate": "2023-01-11"
                }
            ]
        }
        
        # Transform the response
        result = transform_congress_response(congress_response, "bills")
        
        # Verify the transformed response
        assert isinstance(result, ApiResponse)
        assert result.is_success is True
        assert result.metadata.source == ApiSource.CONGRESS
        assert result.pagination.count == 2
        assert result.pagination.next_page_url == "https://api.congress.gov/v3/bill?offset=2&limit=2"
        assert len(result.data) == 2
        
        # Verify the data is preserved
        assert result.data[0]["congress"] == 117
        assert result.data[0]["number"] == "1234"
        assert result.data[0]["type"] == "HR"
        assert result.data[0]["title"] == "Test Bill 1"
        
        # Verify source attribution is added
        assert result.metadata.source == ApiSource.CONGRESS
        
        # Verify original update date is included (should be the most recent date)
        source_date = datetime.strptime("2023-05-21", "%Y-%m-%d").date()
        assert result.metadata.source_updated_at.date() == source_date
    
    def test_transform_congress_member_response(self):
        """Test transformation of a Congress.gov members response."""
        # Mock Congress.gov API member response
        congress_response = {
            "pagination": {
                "count": 1,
                "nextPage": None
            },
            "request": {
                "contentType": "application/json",
                "format": ""
            },
            "results": [
                {
                    "bioguideID": "S000148",
                    "firstName": "Bernie",
                    "lastName": "Sanders",
                    "state": "VT",
                    "party": "Independent",
                    "chamber": "Senate",
                    "updateDate": "2023-05-01",
                    "terms": [
                        {
                            "congress": 117,
                            "chamber": "Senate",
                            "stateCode": "VT"
                        }
                    ]
                }
            ]
        }
        
        # Transform the response
        result = transform_congress_response(congress_response, "members")
        
        # Verify the transformed response
        assert isinstance(result, ApiResponse)
        assert result.is_success is True
        assert result.metadata.source == ApiSource.CONGRESS
        assert result.pagination.count == 1
        assert result.pagination.next_page_url is None
        assert len(result.data) == 1
        
        # Verify the data is preserved
        assert result.data[0]["bioguideID"] == "S000148"
        assert result.data[0]["firstName"] == "Bernie"
        assert result.data[0]["lastName"] == "Sanders"
        assert result.data[0]["state"] == "VT"
        
        # Verify source attribution
        assert result.metadata.source == ApiSource.CONGRESS
    
    # STUB: Test transformation of a Congress.gov committees response
    # This stub tests lines 60-75 in transformers.py
    
    # STUB: Test transformation of a Congress.gov empty response with pagination
    # This stub tests lines 80-95 in transformers.py


class TestGovInfoTransformer:
    """Tests for GovInfo.gov API response transformation."""
    
    def test_transform_govinfo_package_response(self):
        """Test transformation of a GovInfo.gov package response."""
        # Mock GovInfo.gov API package response
        govinfo_response = {
            "count": 2,
            "offset": 0,
            "pageSize": 2,
            "nextPage": "https://api.govinfo.gov/collections/bills?offset=2&pageSize=2",
            "previousPage": None,
            "packages": [
                {
                    "packageId": "BILLS-117hr1234ih",
                    "lastModified": "2023-01-15T10:30:00Z",
                    "packageLink": "https://api.govinfo.gov/packages/BILLS-117hr1234ih/summary",
                    "title": "A Bill 1",
                    "congress": 117,
                    "dateIssued": "2023-01-10"
                },
                {
                    "packageId": "BILLS-117s5678is",
                    "lastModified": "2023-01-16T14:45:00Z",
                    "packageLink": "https://api.govinfo.gov/packages/BILLS-117s5678is/summary",
                    "title": "A Bill 2",
                    "congress": 117,
                    "dateIssued": "2023-01-11"
                }
            ]
        }
        
        # Transform the response
        result = transform_govinfo_response(govinfo_response, "packages")
        
        # Verify the transformed response
        assert isinstance(result, ApiResponse)
        assert result.is_success is True
        assert result.metadata.source == ApiSource.GOVINFO
        assert result.pagination.count == 2
        assert result.pagination.total_count == 2  # Same as count in this case
        assert result.pagination.offset == 0
        assert result.pagination.next_page_url == "https://api.govinfo.gov/collections/bills?offset=2&pageSize=2"
        assert len(result.data) == 2
        
        # Verify the data is transformed correctly
        assert result.data[0]["packageId"] == "BILLS-117hr1234ih"
        assert result.data[0]["title"] == "A Bill 1"
        assert result.data[0]["congress"] == 117
        
        # Verify source attribution and metadata
        assert result.metadata.source == ApiSource.GOVINFO
        source_date = datetime.strptime("2023-01-16T14:45:00Z", "%Y-%m-%dT%H:%M:%SZ")
        assert result.metadata.source_updated_at == source_date
    
    def test_transform_govinfo_granule_response(self):
        """Test transformation of a GovInfo.gov granules response."""
        # Mock GovInfo.gov API granules response
        govinfo_response = {
            "count": 2,
            "offset": 5,
            "pageSize": 2,
            "nextPage": "https://api.govinfo.gov/packages/BILLS-117hr1234ih/granules?offset=7&pageSize=2",
            "previousPage": "https://api.govinfo.gov/packages/BILLS-117hr1234ih/granules?offset=3&pageSize=2",
            "granules": [
                {
                    "granuleId": "BILLS-117hr1234ih-Section1",
                    "granuleLink": "https://api.govinfo.gov/packages/BILLS-117hr1234ih/granules/BILLS-117hr1234ih-Section1/summary",
                    "title": "Section 1: Short Title"
                },
                {
                    "granuleId": "BILLS-117hr1234ih-Section2",
                    "granuleLink": "https://api.govinfo.gov/packages/BILLS-117hr1234ih/granules/BILLS-117hr1234ih-Section2/summary",
                    "title": "Section 2: Definitions"
                }
            ]
        }
        
        # Transform the response
        result = transform_govinfo_response(govinfo_response, "granules")
        
        # Verify the transformed response
        assert isinstance(result, ApiResponse)
        assert result.is_success is True
        assert result.metadata.source == ApiSource.GOVINFO
        assert result.pagination.count == 2
        assert result.pagination.offset == 5
        assert result.pagination.next_page_url == "https://api.govinfo.gov/packages/BILLS-117hr1234ih/granules?offset=7&pageSize=2"
        assert result.pagination.previous_page_url == "https://api.govinfo.gov/packages/BILLS-117hr1234ih/granules?offset=3&pageSize=2"
        assert len(result.data) == 2
        
        # Verify the data is transformed correctly
        assert result.data[0]["granuleId"] == "BILLS-117hr1234ih-Section1"
        assert result.data[0]["title"] == "Section 1: Short Title"
        assert result.data[1]["granuleId"] == "BILLS-117hr1234ih-Section2"
        
        # Verify source attribution
        assert result.metadata.source == ApiSource.GOVINFO
    
    # STUB: Test transformation of a GovInfo.gov empty response
    # This stub tests lines 150-165 in transformers.py
    
    # STUB: Test transformation of a GovInfo.gov single item response
    # This stub tests lines 170-185 in transformers.py


class TestErrorResponseCreation:
    """Tests for error response creation."""
    
    def test_create_error_response_from_exception(self):
        """Test creating an error response from an exception."""
        # Create mock exception
        try:
            raise ValueError("Test error message")
        except ValueError as exc:
            # Create error response
            result = create_error_response(
                exception=exc,
                status_code=400,
                source=ApiSource.CONGRESS,
                error_code="INVALID_REQUEST"
            )
        
        # Verify error response
        assert isinstance(result, ApiResponse)
        assert result.is_success is False
        assert result.metadata.source == ApiSource.CONGRESS
        assert result.pagination is None
        assert result.data is None
        assert result.error is not None
        assert result.error.message == "Test error message"
        assert result.error.status_code == 400
        assert result.error.error_code == "INVALID_REQUEST"
    
    def test_create_error_response_from_message(self):
        """Test creating an error response from a message."""
        # Create error response directly from message
        result = create_error_response(
            message="Resource not found",
            status_code=404,
            source=ApiSource.GOVINFO,
            error_code="RESOURCE_NOT_FOUND",
            details={"resource_id": "123", "resource_type": "bill"}
        )
        
        # Verify error response
        assert isinstance(result, ApiResponse)
        assert result.is_success is False
        assert result.metadata.source == ApiSource.GOVINFO
        assert result.pagination is None
        assert result.data is None
        assert result.error is not None
        assert result.error.message == "Resource not found"
        assert result.error.status_code == 404
        assert result.error.error_code == "RESOURCE_NOT_FOUND"
        assert result.error.details == {"resource_id": "123", "resource_type": "bill"}


class TestSchemaIntegration:
    """Tests for schema monitoring integration."""
    
    def test_schema_capture_during_transformation(self):
        """Test that schema is captured during transformation."""
        # Create a temporary schema directory
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a schema monitor with the temp directory
            monitor = SchemaMonitor(schema_dir=temp_dir)
            
            # Keep a reference to the original default monitor
            from pygovpub.core.schema_monitor import default_monitor
            original_monitor = default_monitor
            
            # Replace the default monitor with our test monitor
            import pygovpub.core.schema_monitor
            pygovpub.core.schema_monitor.default_monitor = monitor
            
            try:
                # Sample Congress.gov API response
                congress_response = {
                    "pagination": {
                        "count": 2,
                        "nextPage": "https://api.congress.gov/v3/bill?offset=2&limit=2"
                    },
                    "results": [
                        {
                            "congress": 117,
                            "type": "hr",
                            "number": "1",
                            "title": "Test Bill 1",
                            "updateDate": "2023-01-01"
                        },
                        {
                            "congress": 117,
                            "type": "hr",
                            "number": "2",
                            "title": "Test Bill 2",
                            "updateDate": "2023-01-02"
                        }
                    ]
                }
                
                # Transform the response
                with suppress_jsonschema_warnings():
                    response = transform_congress_response(
                        congress_response=congress_response,
                        resource_type="bill",
                        offset=0,
                        endpoint="v3/bill",
                        version_string="v3"
                    )
                
                # Check that schema was captured
                assert len(monitor.schemas) == 1
                assert "congress:v3/bill" in monitor.schemas
                
                # Check that API version info is included in response
                assert response.metadata.api_version == "v3"
                assert response.metadata.schema_version is not None
                
                # Check that schema file was created
                schema_file = os.path.join(temp_dir, "congress_v3_bill.json")
                assert os.path.exists(schema_file)
                
                # Verify schema content
                with open(schema_file, 'r') as f:
                    schema_data = json.load(f)
                    assert schema_data["api_source"] == "congress"
                    assert schema_data["endpoint"] == "v3/bill"
                    assert "schema" in schema_data
                    assert "properties" in schema_data["schema"]
                    
                # Now test with a changed schema (new field)
                modified_response = congress_response.copy()
                modified_response["results"][0]["description"] = "New field"
                
                # Transform the modified response
                with suppress_jsonschema_warnings():
                    response2 = transform_congress_response(
                        congress_response=modified_response,
                        resource_type="bill",
                        offset=0,
                        endpoint="v3/bill",
                        version_string="v3"
                    )
                
                # Check that schema changes were detected
                assert len(monitor.recent_changes) > 0
                
                # Check that hash changed in the response
                assert response.metadata.schema_version != response2.metadata.schema_version
                
            finally:
                # Restore the original default monitor
                pygovpub.core.schema_monitor.default_monitor = original_monitor