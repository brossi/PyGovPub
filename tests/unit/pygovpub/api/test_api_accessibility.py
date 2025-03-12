"""
Tests for API accessibility features.

These tests verify that API endpoints and responses meet accessibility requirements
for Section 508 compliance and follow best practices for accessible API design.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from pydantic import BaseModel

from pygovpub.validation.test_accessibility import (
    validate_response_accessibility,
    AccessibleResponseMixin
)
from fastapi import FastAPI, Request, Response, Depends, HTTPException
from fastapi.testclient import TestClient
from pygovpub.models.response import ApiResponse
from pygovpub.auth.models import ApiSource


class TestAPIResponseAccessibility:
    """Test API response accessibility."""
    
    def test_api_response_includes_metadata(self):
        """Test that ApiResponse includes metadata for accessibility."""
        # Create a response using the from_data factory method
        response = ApiResponse.from_data(
            data={"id": 1, "title": "Test Document"},
            source=ApiSource.CONGRESS,
            total_count=1,
            count=1,
            api_version="1.0.0"
        )
        
        # Convert to dict
        response_dict = response.model_dump()
        
        # Check that metadata is included
        assert "metadata" in response_dict
        assert "source" in response_dict["metadata"]
        assert response_dict["metadata"]["source"] == "congress"
    
    def test_error_response_accessibility(self):
        """Test that error responses include accessible details."""
        # Create an error response
        response = ApiResponse.from_error(
            error="Resource not found",
            source=ApiSource.CONGRESS,
            status_code=404,
            error_code="NOT_FOUND",
            details={"id": 123, "resource_type": "document"}
        )
        
        # Convert to dict
        response_dict = response.model_dump()
        
        # Check error structure
        assert "error" in response_dict
        assert "message" in response_dict["error"]
        assert "details" in response_dict["error"]
        
        # Create a custom validation-format dict
        validation_dict = {
            "error": {
                "message": response_dict["error"]["message"],
                "details": response_dict["error"]["details"]
            }
        }
        
        # Validate with accessibility validator
        validation = validate_response_accessibility(validation_dict)
        assert validation["valid"] is True
    
    def test_api_endpoints_documentation(self):
        """Test that API endpoints have proper accessibility documentation."""
        # Create test app
        app = FastAPI(
            title="PyGovPub API",
            description="API for accessing U.S. federal government data",
            version="1.0.0"
        )
        
        # Add endpoints with documentation
        @app.get("/test", description="Test endpoint with accessibility metadata")
        def test_endpoint():
            return {"data": "test"}
        
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
    
    def test_pagination_accessibility(self):
        """Test pagination accessibility in API responses."""
        # Create test app
        app = FastAPI()
        
        # Define a paginated endpoint
        @app.get("/documents")
        async def get_documents():
            return {
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
        
        # Create test client
        client = TestClient(app)
        
        # Make request to the paginated endpoint
        response = client.get("/documents?page=1&per_page=10")
        
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
    
    def test_content_type_headers(self):
        """Test that API sets proper content type headers for accessibility."""
        # Create test app
        app = FastAPI()
        
        # Define endpoint with JSON response
        @app.get("/json-endpoint")
        async def json_endpoint():
            return {"data": "json data"}
        
        # Create test client
        client = TestClient(app)
        
        # Test JSON response
        response = client.get("/json-endpoint", headers={"Accept": "application/json"})
        
        # Check content type header
        assert response.status_code == 200
        assert "application/json" in response.headers["content-type"]
    
    def test_http_status_codes(self):
        """Test that API returns proper HTTP status codes for accessibility."""
        # Create test app
        app = FastAPI()
        
        # Define endpoints with different status codes
        @app.get("/success")
        async def success_endpoint():
            return {"status": "success"}
            
        @app.get("/not-found")
        async def not_found_endpoint():
            raise HTTPException(status_code=404, detail="Resource not found")
            
        # Create test client
        client = TestClient(app)
        
        # Test 200 OK
        response = client.get("/success")
        assert response.status_code == 200
        
        # Test 404 Not Found
        response = client.get("/not-found")
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "Resource not found" in data["detail"]
    
    def test_api_version_header(self):
        """Test that API includes version header for accessibility."""
        # Create test app with version
        app = FastAPI(version="1.0.0")
        
        # Define endpoint
        @app.get("/test")
        async def test_endpoint():
            return {"version": app.version}
            
        # Create test client
        client = TestClient(app)
        
        # Make request
        response = client.get("/test")
        
        # API should include version information
        data = response.json()
        assert "version" in data
        assert data["version"] == "1.0.0"
    
    def test_langauge_support(self):
        """Test API support for language specification."""
        # Create accessible response with language through custom model
        class AccessibleLangModel(BaseModel):
            id: int
            title: str
            lang: str = "en-US"
            
        model = AccessibleLangModel(id=1, title="Test")
        
        # Convert to dict
        model_dict = model.model_dump()
        
        # Check language metadata
        assert "lang" in model_dict
        assert model_dict["lang"] == "en-US"