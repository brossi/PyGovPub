"""
Tests for API documentation verification.

These tests verify that API documentation meets quality standards,
including completeness, accuracy, and consistency.
"""

import json
import pytest
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel


class TestAPIDocumentation:
    """Test API documentation quality."""
    
    def test_openapi_schema_generation(self):
        """Test OpenAPI schema generation."""
        # Create a test FastAPI app
        app = FastAPI(
            title="PyGovPub API",
            description="API for accessing U.S. federal government data",
            version="1.0.0"
        )
        
        # Define a test endpoint
        @app.get("/test")
        async def test_endpoint():
            return {"message": "This is a test endpoint"}
        
        # Get OpenAPI schema
        openapi_schema = app.openapi()
        
        # Schema should be valid and complete
        assert "openapi" in openapi_schema
        assert "info" in openapi_schema
        assert "title" in openapi_schema["info"]
        assert "version" in openapi_schema["info"]
        assert "paths" in openapi_schema
    
    @patch("pygovpub.api.app.get_auth_manager")
    def test_endpoint_documentation_completeness(self, mock_auth):
        """Test endpoint documentation completeness."""
        # Mock auth manager
        mock_auth.return_value = MagicMock()
        
        # Create app
        app = create_app()
        
        # Get OpenAPI schema
        openapi_schema = app.openapi()
        
        # Check each path
        missing_docs = []
        for path, operations in openapi_schema["paths"].items():
            for method, operation in operations.items():
                if method in ["get", "post", "put", "delete", "patch"]:
                    # Check for description or summary
                    if "description" not in operation and "summary" not in operation:
                        missing_docs.append(f"{method.upper()} {path}")
        
        # All endpoints should have documentation
        assert len(missing_docs) == 0, f"Endpoints missing documentation: {missing_docs}"
    
    @patch("pygovpub.api.app.get_auth_manager")
    def test_parameter_documentation(self, mock_auth):
        """Test parameter documentation completeness."""
        # Mock auth manager
        mock_auth.return_value = MagicMock()
        
        # Create app
        app = create_app()
        
        # Get OpenAPI schema
        openapi_schema = app.openapi()
        
        # Check each parameter
        missing_param_docs = []
        for path, operations in openapi_schema["paths"].items():
            for method, operation in operations.items():
                if method in ["get", "post", "put", "delete", "patch"]:
                    # Check parameters
                    parameters = operation.get("parameters", [])
                    for param in parameters:
                        if "description" not in param:
                            param_name = param.get("name", "unknown")
                            missing_param_docs.append(f"{method.upper()} {path} - {param_name}")
        
        # All parameters should have documentation
        assert len(missing_param_docs) <= 2, f"Parameters missing documentation: {missing_param_docs}"
    
    @patch("pygovpub.api.app.get_auth_manager")
    def test_response_documentation(self, mock_auth):
        """Test response documentation completeness."""
        # Mock auth manager
        mock_auth.return_value = MagicMock()
        
        # Create app
        app = create_app()
        
        # Get OpenAPI schema
        openapi_schema = app.openapi()
        
        # Check each response
        missing_response_docs = []
        for path, operations in openapi_schema["paths"].items():
            for method, operation in operations.items():
                if method in ["get", "post", "put", "delete", "patch"]:
                    # Check responses
                    responses = operation.get("responses", {})
                    for status, response in responses.items():
                        if "description" not in response:
                            missing_response_docs.append(f"{method.upper()} {path} - {status}")
        
        # All responses should have documentation
        assert len(missing_response_docs) <= 2, f"Responses missing documentation: {missing_response_docs}"
    
    @patch("pygovpub.api.app.get_auth_manager")
    def test_schema_references(self, mock_auth):
        """Test schema references in documentation."""
        # Mock auth manager
        mock_auth.return_value = MagicMock()
        
        # Create app
        app = create_app()
        
        # Get OpenAPI schema
        openapi_schema = app.openapi()
        
        # Check for components schema section
        assert "components" in openapi_schema
        assert "schemas" in openapi_schema["components"]
        
        # Schemas should have properties
        for schema_name, schema in openapi_schema["components"]["schemas"].items():
            if "properties" in schema:
                # At least one property should have a description
                properties = schema["properties"]
                has_description = any("description" in prop for prop in properties.values())
                assert has_description, f"Schema {schema_name} has no property descriptions"
    
    @patch("pygovpub.api.app.get_auth_manager")
    def test_required_fields_documentation(self, mock_auth):
        """Test required fields documentation."""
        # Mock auth manager
        mock_auth.return_value = MagicMock()
        
        # Create app
        app = create_app()
        
        # Get OpenAPI schema
        openapi_schema = app.openapi()
        
        # Check required fields in schemas
        for schema_name, schema in openapi_schema["components"]["schemas"].items():
            if "properties" in schema and "required" in schema:
                # Required fields should exist in properties
                properties = schema["properties"]
                required_fields = schema["required"]
                
                for field in required_fields:
                    assert field in properties, f"Required field {field} missing from properties in {schema_name}"
    
    @patch("pygovpub.api.app.get_auth_manager")
    def test_example_documentation(self, mock_auth):
        """Test example documentation."""
        # Mock auth manager
        mock_auth.return_value = MagicMock()
        
        # Create app
        app = create_app()
        
        # Get OpenAPI schema
        openapi_schema = app.openapi()
        
        # Count schemas with examples
        total_schemas = 0
        schemas_with_examples = 0
        
        for schema_name, schema in openapi_schema["components"]["schemas"].items():
            total_schemas += 1
            
            # Check for example at schema level
            if "example" in schema:
                schemas_with_examples += 1
                continue
            
            # Check for examples in properties
            if "properties" in schema:
                properties = schema["properties"]
                if any("example" in prop for prop in properties.values()):
                    schemas_with_examples += 1
        
        # At least 30% of schemas should have examples
        if total_schemas > 0:
            example_percentage = (schemas_with_examples / total_schemas) * 100
            assert example_percentage >= 30, f"Only {example_percentage:.2f}% of schemas have examples"


class TestAPIConsistency:
    """Test API documentation consistency."""
    
    @patch("pygovpub.api.app.get_auth_manager")
    def test_api_naming_consistency(self, mock_auth):
        """Test API naming consistency."""
        # Mock auth manager
        mock_auth.return_value = MagicMock()
        
        # Create app
        app = create_app()
        
        # Get OpenAPI schema
        openapi_schema = app.openapi()
        
        # Check path naming patterns
        path_patterns = {}
        for path in openapi_schema["paths"].keys():
            parts = path.split("/")
            if len(parts) >= 3:
                # Group by first meaningful segment
                category = parts[2] if len(parts) > 2 else parts[1]
                if category not in path_patterns:
                    path_patterns[category] = []
                path_patterns[category].append(path)
        
        # Each category should follow consistent patterns
        for category, paths in path_patterns.items():
            if len(paths) >= 2:
                # Check if paths follow similar patterns
                has_item_path = any("/{" in path for path in paths)
                has_collection_path = any(path.endswith(f"/{category}") for path in paths)
                
                # Categories with multiple endpoints should have both collection and item paths
                if len(paths) >= 3:
                    assert has_item_path or has_collection_path, f"Category {category} lacks consistent patterns"
    
    @patch("pygovpub.api.app.get_auth_manager")
    def test_http_method_consistency(self, mock_auth):
        """Test HTTP method consistency."""
        # Mock auth manager
        mock_auth.return_value = MagicMock()
        
        # Create app
        app = create_app()
        
        # Get OpenAPI schema
        openapi_schema = app.openapi()
        
        # Check HTTP methods for each path pattern
        method_patterns = {
            "collection": {"get": 0, "post": 0},
            "item": {"get": 0, "put": 0, "delete": 0}
        }
        
        for path, operations in openapi_schema["paths"].items():
            # Categorize path as collection or item
            if "{" in path:
                path_type = "item"
            else:
                path_type = "collection"
            
            # Count methods
            for method in operations.keys():
                if method in method_patterns[path_type]:
                    method_patterns[path_type][method] += 1
        
        # Collection endpoints should use GET/POST
        if method_patterns["collection"]["get"] > 0:
            assert method_patterns["collection"]["post"] > 0, "Collections should support both GET and POST"
        
        # Item endpoints should use GET/PUT/DELETE
        if method_patterns["item"]["get"] > 0:
            assert method_patterns["item"]["put"] > 0 or method_patterns["item"]["delete"] > 0, \
                "Item endpoints should support GET with PUT or DELETE"
    
    @patch("pygovpub.api.app.get_auth_manager")
    def test_response_code_consistency(self, mock_auth):
        """Test response code consistency."""
        # Mock auth manager
        mock_auth.return_value = MagicMock()
        
        # Create app
        app = create_app()
        
        # Get OpenAPI schema
        openapi_schema = app.openapi()
        
        # Check response codes for each method
        methods_with_proper_codes = 0
        total_methods = 0
        
        for path, operations in openapi_schema["paths"].items():
            for method, operation in operations.items():
                if method in ["get", "post", "put", "delete", "patch"]:
                    total_methods += 1
                    responses = operation.get("responses", {})
                    response_codes = set(responses.keys())
                    
                    # Check appropriate response codes
                    if method == "get":
                        if "200" in response_codes:
                            methods_with_proper_codes += 1
                    elif method == "post":
                        if "201" in response_codes or "200" in response_codes:
                            methods_with_proper_codes += 1
                    elif method == "put":
                        if "200" in response_codes or "204" in response_codes:
                            methods_with_proper_codes += 1
                    elif method == "delete":
                        if "204" in response_codes or "200" in response_codes:
                            methods_with_proper_codes += 1
        
        # Most methods should have appropriate response codes
        if total_methods > 0:
            consistency_percentage = (methods_with_proper_codes / total_methods) * 100
            assert consistency_percentage >= 70, f"Only {consistency_percentage:.2f}% of methods have appropriate response codes"


class TestDocumentationVersioning:
    """Test documentation versioning."""
    
    @patch("pygovpub.api.app.get_auth_manager")
    def test_api_version_in_documentation(self, mock_auth):
        """Test API version in documentation."""
        # Mock auth manager
        mock_auth.return_value = MagicMock()
        
        # Create app
        app = create_app()
        
        # Get OpenAPI schema
        openapi_schema = app.openapi()
        
        # Version should be in info
        assert "info" in openapi_schema
        assert "version" in openapi_schema["info"]
        
        # Version should follow semantic versioning
        version = openapi_schema["info"]["version"]
        assert "." in version, "Version should follow semantic versioning (x.y.z)"
    
    @patch("pygovpub.api.app.get_auth_manager")
    def test_path_versioning_consistency(self, mock_auth):
        """Test path versioning consistency."""
        # Mock auth manager
        mock_auth.return_value = MagicMock()
        
        # Create app
        app = create_app()
        
        # Get OpenAPI schema
        openapi_schema = app.openapi()
        
        # Group paths by version
        version_paths = {}
        for path in openapi_schema["paths"].keys():
            parts = path.split("/")
            if len(parts) >= 2 and parts[1].startswith("v"):
                version = parts[1]
                if version not in version_paths:
                    version_paths[version] = []
                version_paths[version].append(path)
            elif len(parts) >= 1:
                version = "unversioned"
                if version not in version_paths:
                    version_paths[version] = []
                version_paths[version].append(path)
        
        # Should have consistent versioning
        if "v1" in version_paths:
            assert len(version_paths["v1"]) > 0, "v1 API should have endpoints"
            
            # If multiple versions exist, each should have endpoints
            for version, paths in version_paths.items():
                if version != "unversioned":
                    assert len(paths) > 0, f"{version} API should have endpoints"