"""
Tests for API schema monitoring.

This module tests the core schema monitoring functionality for detecting
and handling API schema changes.
"""

import json
import os
import tempfile
import warnings
from datetime import datetime, timezone
from typing import Dict, Any, List
from contextlib import contextmanager

import pytest
from pydantic import BaseModel, ConfigDict

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
from pygovpub.core.schema_monitor import (
    SchemaMonitor,
    SchemaVersion,
    SchemaChange,
    validate_response,
    get_recent_changes,
    get_supported_versions
)


class TestSchemaMonitor:
    """Tests for SchemaMonitor class."""
    
    def test_init(self):
        """Test basic initialization."""
        # Create a temporary directory for schemas
        with tempfile.TemporaryDirectory() as temp_dir:
            monitor = SchemaMonitor(schema_dir=temp_dir)
            
            # Check that the directory exists
            assert os.path.exists(temp_dir)
            assert monitor.schema_dir == temp_dir
            assert monitor.track_changes is True
            assert monitor.alert_on_breaking is True
            assert monitor.schemas == {}
            assert monitor.versions == {}
            assert monitor.recent_changes == []

    def test_first_response_validation(self):
        """Test validation of first response for an endpoint."""
        with tempfile.TemporaryDirectory() as temp_dir:
            monitor = SchemaMonitor(schema_dir=temp_dir)
            
            # Simple response to validate
            response_data = {
                "count": 10,
                "offset": 0,
                "results": [
                    {"id": 1, "name": "Test 1"},
                    {"id": 2, "name": "Test 2"}
                ]
            }
            
            # Validate the response
            is_valid, changes = monitor.validate_response(
                api_source=ApiSource.CONGRESS,
                endpoint="test/endpoint",
                response_data=response_data,
                version_string="v3"
            )
            
            # First validation should always succeed and create schema
            assert is_valid is True
            assert changes == []
            
            # Check the schema was stored
            key = f"{ApiSource.CONGRESS.value}:test/endpoint"
            assert key in monitor.schemas
            assert key in monitor.versions
            
            # Verify version information
            version = monitor.versions[key]
            assert version.api_source == ApiSource.CONGRESS
            assert version.version_string == "v3"
            assert version.is_supported is True
            
            # Verify schema file was created
            schema_file = os.path.join(temp_dir, f"congress_test_endpoint.json")
            assert os.path.exists(schema_file)
            
            # Load and check schema file
            with open(schema_file, 'r') as f:
                stored_data = json.load(f)
                assert stored_data['api_source'] == ApiSource.CONGRESS.value
                assert stored_data['endpoint'] == "test/endpoint"
                assert 'schema' in stored_data
                assert 'version' in stored_data

    def test_schema_changes(self):
        """Test detection of schema changes using DeepDiff."""
        with tempfile.TemporaryDirectory() as temp_dir:
            monitor = SchemaMonitor(schema_dir=temp_dir)
            
            # Initial response
            initial_response = {
                "count": 10,
                "results": [
                    {"id": 1, "name": "Test 1"}
                ]
            }
            
            # Validate the initial response
            monitor.validate_response(
                api_source=ApiSource.CONGRESS,
                endpoint="test/endpoint",
                response_data=initial_response
            )
            
            # Get the initial schema hash
            key = f"{ApiSource.CONGRESS.value}:test/endpoint"
            initial_hash = monitor.versions[key].schema_hash
            
            # Modified response with new field
            modified_response = {
                "count": 10,
                "results": [
                    {"id": 1, "name": "Test 1", "description": "New field"}
                ]
            }
            
            # Validate the modified response
            is_valid, changes = monitor.validate_response(
                api_source=ApiSource.CONGRESS,
                endpoint="test/endpoint",
                response_data=modified_response
            )
            
            # Validation should succeed with changes detected
            assert is_valid is True
            
            # The hash should be updated
            new_hash = monitor.versions[key].schema_hash
            assert new_hash != initial_hash
            
            # Verify changes were detected (DeepDiff will produce different changes than our custom detector)
            assert len(monitor.recent_changes) > 0

    def test_schema_version_tracking(self):
        """Test tracking of API schema versions."""
        with tempfile.TemporaryDirectory() as temp_dir:
            monitor = SchemaMonitor(schema_dir=temp_dir)
            
            # Register two different endpoints with different versions
            congress_response = {"data": "test"}
            govinfo_response = {"content": "test"}
            
            monitor.validate_response(
                api_source=ApiSource.CONGRESS,
                endpoint="endpoint1",
                response_data=congress_response,
                version_string="v3"
            )
            
            monitor.validate_response(
                api_source=ApiSource.GOVINFO,
                endpoint="endpoint2",
                response_data=govinfo_response,
                version_string="2023-12"
            )
            
            # Get supported versions
            versions = monitor.get_supported_versions()
            
            # Verify tracking of both API sources
            assert ApiSource.CONGRESS.value in versions
            assert ApiSource.GOVINFO.value in versions
            
            # Verify version strings
            congress_versions = versions[ApiSource.CONGRESS.value]
            govinfo_versions = versions[ApiSource.GOVINFO.value]
            
            assert len(congress_versions) == 1
            assert len(govinfo_versions) == 1
            
            assert congress_versions[0].version_string == "v3"
            assert govinfo_versions[0].version_string == "2023-12"
            
            # Mark a version as unsupported
            monitor.mark_version_unsupported(
                api_source=ApiSource.CONGRESS,
                version_string="v3"
            )
            
            # Verify it's marked as unsupported
            versions = monitor.get_supported_versions()
            assert ApiSource.CONGRESS.value not in versions

    def test_json_schema_validation(self):
        """Test validation of responses against JSON Schema."""
        with tempfile.TemporaryDirectory() as temp_dir:
            monitor = SchemaMonitor(schema_dir=temp_dir)
            
            # Initial response
            initial_response = {
                "id": 1,
                "name": "Test",
                "tags": ["a", "b", "c"]
            }
            
            # Validate the initial response - should generate a schema
            with suppress_jsonschema_warnings():
                monitor.validate_response(
                    api_source=ApiSource.GOVINFO,
                    endpoint="test/item",
                    response_data=initial_response
                )
            
            # Invalid response (wrong type for tags)
            invalid_response = {
                "id": 1,
                "name": "Test",
                "tags": "not an array"  # Should be an array
            }
            
            # Validate the invalid response
            with suppress_jsonschema_warnings():
                is_valid, changes = monitor.validate_response(
                    api_source=ApiSource.GOVINFO,
                    endpoint="test/item",
                    response_data=invalid_response
                )
            
            # The genson schema builder is adaptive and will update the schema
            # to accommodate both array and string types, rather than failing
            assert len(changes) > 0  # Schema changes were detected
            
            # Schema should be updated to accept both formats
            key = f"{ApiSource.GOVINFO.value}:test/item"
            schema = monitor.schemas[key]
            
            # Genson will have updated the schema to accept either format
            # This might be a oneOf or directly accepting both types
            assert "tags" in schema["properties"]
            
            # Now validation should pass with either format
            with suppress_jsonschema_warnings():
                is_valid, _ = monitor.validate_response(
                    api_source=ApiSource.GOVINFO,
                    endpoint="test/item",
                    response_data=initial_response  # Original array format
                )
            assert is_valid is True
            
            with suppress_jsonschema_warnings():
                is_valid, _ = monitor.validate_response(
                    api_source=ApiSource.GOVINFO,
                    endpoint="test/item",
                    response_data=invalid_response  # String format
                )
            assert is_valid is True

# Test module-level functions
def test_module_functions():
    """Test the module-level convenience functions."""
    
    # Create a simple response
    response_data = {"test": "data"}
    
    # Test validate_response
    with suppress_jsonschema_warnings():
        is_valid, changes = validate_response(
            api_source=ApiSource.INTERNAL,
            endpoint="test",
            response_data=response_data
        )
    assert is_valid is True
    
    # Test get_recent_changes
    changes = get_recent_changes()
    assert isinstance(changes, list)
    
    # Test get_supported_versions
    versions = get_supported_versions()
    assert isinstance(versions, dict)