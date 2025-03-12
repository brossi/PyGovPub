"""
Tests for API accessibility features.

These tests verify that API endpoints and responses meet accessibility requirements
for Section 508 compliance and follow best practices for accessible API design.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from pygovpub.validation.test_accessibility import (
    validate_response_accessibility,
    AccessibleResponseMixin
)
from pygovpub.api.app import create_app
from pygovpub.models.response import ApiResponse


class TestAPIResponseAccessibility:
    """Test API response accessibility."""
    
    def test_api_response_includes_metadata(self):
        """Test that ApiResponse includes metadata for accessibility."""
        # Create a response
        response = ApiResponse(
            data={"id": 1, "title": "Test Document"},
            metadata={
                "description": "Test document data",
                "lang": "en-US"
            }
        )
        
        # Convert to dict
        response_dict = response.model_dump()
        
        # Check that metadata is included
        assert "metadata" in response_dict
        assert "description" in response_dict["metadata"]
        assert "lang" in response_dict["metadata"]
    
    def test_error_response_accessibility(self):
        """Test that error responses include accessible details."""
        # Create an error response
        response = ApiResponse(
            success=False,
            error={
                "code": "NOT_FOUND", 
                "message": "Resource not found",
                "details": "The requested document with ID 123 does not exist"
            }
        )
        
        # Convert to dict
        response_dict = response.model_dump()
        
        # Check error structure
        assert not response_dict["success"]
        assert "error" in response_dict
        assert "message" in response_dict["error"]
        assert "details" in response_dict["error"]
        
        # Validate with accessibility validator
        validation = validate_response_accessibility(response_dict)
        assert validation["valid"] is True
    
    @patch("pygovpub.api.app.get_auth_manager")
    def test_api_endpoints_documentation(self, mock_auth):
        """Test that API endpoints have proper accessibility documentation."""
        # Mock auth manager
        mock_auth.return_value = MagicMock()
        
        # Create test app
        app = create_app()
        
        # Get OpenAPI schema
        openapi_schema = app.openapi()
        
        # Check info section
        assert "info" in openapi_schema
        assert "title" in openapi_schema["info"]
        assert "description" in openapi_schema["info"]
        
        # Check paths for descriptions
        for path, path_item in openapi_schema["paths"].items():
            for method, operation in path_item.items():
                if method in ["get", "post", "put", "delete", "patch"]:
                    # Every operation should have a description or summary
                    assert "description" in operation or "summary" in operation
    
    @patch("pygovpub.api.app.get_auth_manager")
    def test_pagination_accessibility(self, mock_auth):
        """Test pagination accessibility in API responses."""
        # Mock auth manager
        mock_auth.return_value = MagicMock()
        
        # Create test client
        app = create_app()
        client = TestClient(app)
        
        # Mock response for a paginated endpoint
        with patch("pygovpub.api.router.route_request") as mock_route:
            # Prepare mock paginated response
            mock_route.return_value = {
                "data": [{"id": 1, "title": "Test Document"}],
                "metadata": {"description": "Test documents"},
                "pagination": {
                    "total": 100,
                    "page": 1,
                    "per_page": 10,
                    "next_page": 2,
                    "prev_page": None
                }
            }
            
            # Make request to an endpoint that would use pagination
            response = client.get("/api/v1/documents?page=1&per_page=10")
            
            # Check response
            assert response.status_code == 200
            data = response.json()
            
            # Verify pagination information
            assert "pagination" in data
            pagination = data["pagination"]
            assert "total" in pagination
            assert "page" in pagination
            assert "per_page" in pagination
            
            # Check for navigation links
            assert "next_page" in pagination
            assert "prev_page" in pagination


class TestAPIAccessibilityHelpers:
    """Test API accessibility helper functions and models."""
    
    def test_accessible_mixin_integration(self):
        """Test integrating AccessibleResponseMixin with API models."""
        # Create a model with accessibility mixin
        class DocumentModel(AccessibleResponseMixin, BaseModel):
            id: int
            title: str
        
        # Create an instance with accessibility metadata
        document = DocumentModel(
            id=1,
            title="Accessible Document",
            description="This is an accessible document",
            alt_text="Document icon with text",
            semantic_context="Legislative document",
            lang="en-US"
        )
        
        # Verify accessibility fields are present
        assert document.description == "This is an accessible document"
        assert document.alt_text == "Document icon with text"
        assert document.semantic_context == "Legislative document"
        assert document.lang == "en-US"
        
        # Check serialization includes accessibility fields
        json_data = document.model_dump_json()
        data_dict = json.loads(json_data)
        
        assert "description" in data_dict
        assert "alt_text" in data_dict
        assert "semantic_context" in data_dict
        assert "lang" in data_dict
    
    @patch("pygovpub.api.app.get_auth_manager")
    def test_content_type_headers(self, mock_auth):
        """Test that API sets proper content type headers for accessibility."""
        # Mock auth manager
        mock_auth.return_value = MagicMock()
        
        # Create test client
        app = create_app()
        client = TestClient(app)
        
        # Mock response
        with patch("pygovpub.api.router.route_request") as mock_route:
            mock_route.return_value = {"data": []}
            
            # Test JSON response
            response = client.get("/api/v1/documents", headers={"Accept": "application/json"})
            
            # Check content type header
            assert response.status_code == 200
            assert response.headers["content-type"] == "application/json"
    
    @patch("pygovpub.api.app.get_auth_manager")
    def test_http_status_codes(self, mock_auth):
        """Test that API returns proper HTTP status codes for accessibility."""
        # Mock auth manager
        mock_auth.return_value = MagicMock()
        
        # Create test client
        app = create_app()
        client = TestClient(app)
        
        # Test different error scenarios
        with patch("pygovpub.api.router.route_request") as mock_route:
            # 404 Not Found
            mock_route.side_effect = Exception("Not found")
            response = client.get("/api/v1/documents/999")
            
            # Check status code and error structure
            assert response.status_code in [404, 400, 500]  # Depending on error handling
            data = response.json()
            assert not data["success"]
            assert "error" in data
            assert "message" in data["error"]
    
    @patch("pygovpub.api.app.get_auth_manager")
    def test_api_version_header(self, mock_auth):
        """Test that API includes version header for accessibility."""
        # Mock auth manager
        mock_auth.return_value = MagicMock()
        
        # Create test client
        app = create_app()
        client = TestClient(app)
        
        # Mock response
        with patch("pygovpub.api.router.route_request") as mock_route:
            mock_route.return_value = {"data": []}
            
            # Make request
            response = client.get("/api/v1/documents")
            
            # API should include version information
            headers = response.headers
            assert any(h.lower().startswith("x-api-version") for h in headers) or \
                   "api-version" in response.json() or \
                   "version" in response.json()
    
    def test_langauge_support(self):
        """Test API support for language specification."""
        # Create accessible response with language
        response = ApiResponse(
            data={"id": 1, "title": "Test"},
            metadata={"lang": "en-US"}
        )
        
        # Convert to dict
        response_dict = response.model_dump()
        
        # Check language metadata
        assert "metadata" in response_dict
        assert "lang" in response_dict["metadata"]
        assert response_dict["metadata"]["lang"] == "en-US"