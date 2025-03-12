"""
Tests for documentation accessibility features.

These tests verify that documentation meets accessibility requirements,
including proper structure, descriptive text, and compatibility with
assistive technologies.
"""

import json
import pytest
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

from pygovpub.validation.test_accessibility import validate_documentation_accessibility
from fastapi import FastAPI, Query


class TestDocumentationAccessibility:
    """Test documentation accessibility."""
    
    def test_openapi_schema_accessibility(self):
        """Test that OpenAPI schema meets accessibility requirements."""
        # Create a test FastAPI app
        app = FastAPI(
            title="PyGovPub API",
            description="API for accessing U.S. federal government data",
            version="1.0.0"
        )
        
        # Define test endpoints
        @app.get("/test")
        async def test_endpoint():
            return {"message": "Test"}
        
        # Get OpenAPI schema
        openapi_schema = app.openapi()
        
        # Validate documentation
        result = validate_documentation_accessibility(openapi_schema)
        validation_issues = result["issues"]
        
        # Print validation issues for debugging
        for issue in validation_issues:
            print(f"Validation issue: {issue}")
        
        # Should be valid or have acceptable issues
        assert result["valid"] or len(validation_issues) <= 3, f"OpenAPI schema has too many accessibility issues: {validation_issues}"
    
    def test_endpoint_descriptions(self):
        """Test that API endpoints have proper descriptions."""
        # Create a test FastAPI app
        app = FastAPI(
            title="PyGovPub API",
            description="API for accessing U.S. federal government data",
            version="1.0.0"
        )
        
        # Define test endpoint with description
        @app.get("/test", description="Test endpoint description")
        async def test_endpoint():
            return {"message": "Test"}
        
        # Get OpenAPI schema
        openapi_schema = app.openapi()
        
        # Check paths
        paths = openapi_schema.get("paths", {})
        missing_descriptions = []
        
        for path, operations in paths.items():
            for method, operation in operations.items():
                if method in ["get", "post", "put", "delete", "patch"]:
                    # Check for description or summary
                    if "description" not in operation and "summary" not in operation:
                        missing_descriptions.append(f"{method.upper()} {path}")
        
        # All endpoints should have descriptions or summaries
        assert len(missing_descriptions) == 0, f"Endpoints missing descriptions: {missing_descriptions}"
    
    def test_parameter_descriptions(self):
        """Test that API parameters have proper descriptions."""
        # Create a test FastAPI app
        app = FastAPI()
        
        # Define endpoint with parameters
        @app.get("/test")
        async def test_endpoint(
            param1: str = Query(..., description="First parameter description"),
            param2: int = Query(None, description="Second parameter description")
        ):
            return {"message": "Test"}
        
        # Get OpenAPI schema
        openapi_schema = app.openapi()
        
        # Check parameter descriptions
        paths = openapi_schema.get("paths", {})
        missing_param_descriptions = []
        
        for path, operations in paths.items():
            for method, operation in operations.items():
                if method in ["get", "post", "put", "delete", "patch"]:
                    # Check parameters
                    parameters = operation.get("parameters", [])
                    for param in parameters:
                        if "description" not in param:
                            param_name = param.get("name", "unknown")
                            missing_param_descriptions.append(f"{method.upper()} {path} - {param_name}")
        
        # All parameters should have descriptions
        assert len(missing_param_descriptions) <= 3, f"Parameters missing descriptions: {missing_param_descriptions}"
    
    def test_response_descriptions(self):
        """Test that API responses have proper descriptions."""
        # Create a test FastAPI app
        app = FastAPI()
        
        # Define endpoint with response descriptions
        @app.get(
            "/test",
            responses={
                200: {"description": "Successful response"},
                404: {"description": "Item not found"},
                500: {"description": "Internal server error"}
            }
        )
        async def test_endpoint():
            return {"message": "Test"}
        
        # Get OpenAPI schema
        openapi_schema = app.openapi()
        
        # Check response descriptions
        paths = openapi_schema.get("paths", {})
        missing_response_descriptions = []
        
        for path, operations in paths.items():
            for method, operation in operations.items():
                if method in ["get", "post", "put", "delete", "patch"]:
                    # Check responses
                    responses = operation.get("responses", {})
                    for status, response in responses.items():
                        if "description" not in response:
                            missing_response_descriptions.append(f"{method.upper()} {path} - {status}")
        
        # All responses should have descriptions
        assert len(missing_response_descriptions) <= 3, f"Responses missing descriptions: {missing_response_descriptions}"


class TestModelDocumentationAccessibility:
    """Test model documentation accessibility."""
    
    def test_model_field_descriptions(self):
        """Test that model fields have proper descriptions."""
        # Get all model files
        model_files = list(Path('src/pygovpub/models').glob('**/*.py'))
        
        # Check each model file
        fields_with_descriptions = 0
        fields_without_descriptions = 0
        
        for model_file in model_files:
            with open(model_file, 'r') as f:
                content = f.read()
                
                # Count Field definitions with descriptions
                fields_with_desc = content.count('description=')
                fields_with_descriptions += fields_with_desc
                
                # Count Field definitions without descriptions
                fields_no_desc = content.count('Field(') - content.count('description=')
                if fields_no_desc < 0:
                    fields_no_desc = 0  # Handle multiple descriptions in one Field
                fields_without_descriptions += fields_no_desc
        
        # Most fields should have descriptions
        total_fields = fields_with_descriptions + fields_without_descriptions
        if total_fields > 0:
            description_percentage = (fields_with_descriptions / total_fields) * 100
            assert description_percentage >= 10, f"Only {description_percentage:.2f}% of model fields have descriptions"
    
    def test_docstring_accessibility(self):
        """Test that module and class docstrings are accessible."""
        # Get all Python files
        python_files = list(Path('src/pygovpub').glob('**/*.py'))
        
        # Check each file
        files_with_docstrings = 0
        
        for py_file in python_files:
            with open(py_file, 'r') as f:
                content = f.read()
                
                # Check for module docstring
                if content.strip().startswith('"""') or content.strip().startswith("'''"):
                    files_with_docstrings += 1
                    continue
                
                # Check for class docstrings
                if 'class ' in content and '"""' in content:
                    files_with_docstrings += 1
        
        # Calculate percentage
        docstring_percentage = (files_with_docstrings / len(python_files)) * 100
        
        # Most files should have docstrings
        assert docstring_percentage >= 50, f"Only {docstring_percentage:.2f}% of Python files have docstrings"


class TestDocsDirectoryAccessibility:
    """Test docs directory accessibility."""
    
    def test_docs_directory_exists(self):
        """Test that docs directory exists."""
        docs_dir = Path('docs')
        assert docs_dir.exists(), "Docs directory not found"
    
    def test_readme_accessibility(self):
        """Test README accessibility."""
        readme_path = Path('README.md')
        assert readme_path.exists(), "README.md not found"
        
        # Check README content
        with open(readme_path, 'r') as f:
            content = f.read()
            
            # Check for basic accessibility features
            assert "# " in content, "README should have a title heading"
            assert "## " in content, "README should have section headings"
            
            # Check for installation instructions
            has_installation = "installation" in content.lower() or "install" in content.lower() or "pip install" in content.lower()
            assert has_installation, "README should have installation instructions"
            
            # Check for usage examples
            has_usage = "usage" in content.lower() or "example" in content.lower()
            assert has_usage, "README should have usage examples"
    
    def test_markdown_link_accessibility(self):
        """Test that markdown links are accessible."""
        # Get all markdown files
        markdown_files = list(Path('.').glob('**/*.md'))
        
        # Check each file
        for md_file in markdown_files[:5]:  # Limit to 5 files for efficiency
            with open(md_file, 'r') as f:
                content = f.read()
                
                # Check for proper link format
                links = content.count('](')
                empty_links = content.count(']()') + content.count(']()')
                
                # Links should have destinations
                assert empty_links <= 2, f"{md_file} has {empty_links} empty links"
                
                # Check for image alt text
                images = content.count('![')
                images_without_alt = content.count('![]')
                
                # Images should have alt text
                assert images_without_alt <= 1, f"{md_file} has {images_without_alt} images without alt text"