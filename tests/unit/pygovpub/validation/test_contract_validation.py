"""
Tests for API contract validation.

This module tests the contract validation utilities for ensuring API contracts.
"""

import json
import os
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, mock_open, MagicMock

import jsonschema
from jsonschema import Draft7Validator

from pygovpub.validation.test_contract import (
    ApiSource,
    ContractValidator,
    validate_request,
    validate_response,
    create_schema_from_response
)


class TestContractValidator:
    """Tests for the ContractValidator class."""

    def test_init(self):
        """Test initializing the validator."""
        # Test with default schema directory
        validator = ContractValidator()
        assert validator.schema_dir.name == "schemas"
        
        # Test with custom schema directory
        custom_dir = "/tmp/schemas"
        validator = ContractValidator(schema_dir=custom_dir)
        assert str(validator.schema_dir) == custom_dir
        
    def test_discover_schemas(self, tmp_path):
        """Test schema discovery."""
        # Create test schema files
        schema_dir = tmp_path / "schemas"
        os.makedirs(schema_dir, exist_ok=True)
        
        # Valid schema file
        valid_schema = {
            "api_source": "congress",
            "endpoint": "bills",
            "schema": {"type": "object"}
        }
        with open(schema_dir / "congress_bills.json", "w") as f:
            json.dump(valid_schema, f)
            
        # Invalid schema file (missing endpoint)
        invalid_schema = {"api_source": "govinfo"}
        with open(schema_dir / "invalid.json", "w") as f:
            json.dump(invalid_schema, f)
            
        # Non-JSON file
        with open(schema_dir / "not_json.json", "w") as f:
            f.write("not json")
            
        # Create validator with test directory
        validator = ContractValidator(schema_dir=str(schema_dir))
        discovered = validator._discover_schemas()
        
        # Should only find the valid schema
        assert len(discovered) == 1
        assert "congress:bills" in discovered
        assert discovered["congress:bills"] == schema_dir / "congress_bills.json"
        
    def test_load_schema(self, tmp_path):
        """Test schema loading."""
        # Create test schema file
        schema_dir = tmp_path / "schemas"
        os.makedirs(schema_dir, exist_ok=True)
        
        test_schema = {
            "api_source": "congress",
            "endpoint": "bills",
            "schema": {"type": "object", "properties": {"test": {"type": "string"}}}
        }
        with open(schema_dir / "congress_bills.json", "w") as f:
            json.dump(test_schema, f)
            
        # Create validator with test directory
        validator = ContractValidator(schema_dir=str(schema_dir))
        
        # Load existing schema
        schema = validator._load_schema("congress", "bills")
        assert schema is not None
        assert schema == test_schema["schema"]
        
        # Test caching
        assert "congress:bills" in validator._schemas
        assert validator._schemas["congress:bills"] == test_schema["schema"]
        
        # Load non-existent schema
        schema = validator._load_schema("congress", "members")
        assert schema is None
        
    def test_validate_request_congress(self):
        """Test validating Congress API requests."""
        validator = ContractValidator()
        
        # Test valid bill request
        valid_bill = {
            "congress": "117",
            "bill_type": "hr",
            "bill_number": "1"
        }
        is_valid, errors = validator.validate_request("congress", "bill", valid_bill)
        assert is_valid
        assert not errors
        
        # Test invalid bill request (missing bill_type)
        invalid_bill = {
            "congress": "117",
            "bill_number": "1"
        }
        is_valid, errors = validator.validate_request("congress", "bill", invalid_bill)
        assert not is_valid
        assert len(errors) == 1
        assert "bill_type" in errors[0]
        
        # Test valid member request
        valid_member = {
            "bioguide_id": "S000148"
        }
        is_valid, errors = validator.validate_request("congress", "member", valid_member)
        assert is_valid
        assert not errors
        
        # Test invalid member request
        invalid_member = {}
        is_valid, errors = validator.validate_request("congress", "member", invalid_member)
        assert not is_valid
        assert len(errors) == 1
        assert "bioguide_id" in errors[0]
        
        # Test valid committee request
        valid_committee = {
            "congress": "117",
            "chamber": "house",
            "committee_code": "hsju"
        }
        is_valid, errors = validator.validate_request("congress", "committee", valid_committee)
        assert is_valid
        assert not errors
        
        # Test invalid committee request
        invalid_committee = {
            "congress": "117",
            # Missing chamber and committee_code
        }
        is_valid, errors = validator.validate_request("congress", "committee", invalid_committee)
        assert not is_valid
        assert len(errors) == 1
        assert "chamber" in errors[0]
        
        # Test another invalid committee request
        invalid_committee2 = {
            "congress": "117",
            "chamber": "house",
            # Missing committee_code
        }
        is_valid, errors = validator.validate_request("congress", "committee", invalid_committee2)
        assert not is_valid
        assert len(errors) == 1
        assert "committee_code" in errors[0]
        
    def test_validate_request_govinfo(self):
        """Test validating GovInfo API requests."""
        validator = ContractValidator()
        
        # Test valid package request
        valid_package = {
            "package_id": "BILLS-117hr1-enr"
        }
        is_valid, errors = validator.validate_request("govinfo", "packages", valid_package)
        assert is_valid
        assert not errors
        
        # Test invalid package request
        invalid_package = {}
        is_valid, errors = validator.validate_request("govinfo", "packages", invalid_package)
        assert not is_valid
        assert len(errors) == 1
        assert "package_id" in errors[0]
        
        # Test collections request (no required params)
        collections = {}
        is_valid, errors = validator.validate_request("govinfo", "collections", collections)
        assert is_valid
        assert not errors
        
    def test_validate_response(self, tmp_path):
        """Test validating API responses."""
        # Create test schema file
        schema_dir = tmp_path / "schemas"
        os.makedirs(schema_dir, exist_ok=True)
        
        bill_schema = {
            "api_source": "congress",
            "endpoint": "bill",
            "schema": {
                "$schema": "http://json-schema.org/schema#",
                "type": "object",
                "properties": {
                    "bill": {
                        "type": "object",
                        "properties": {
                            "congress": {"type": "integer"},
                            "type": {"type": "string"},
                            "number": {"type": "string"},
                            "title": {"type": "string"}
                        },
                        "required": ["congress", "type", "number", "title"]
                    }
                },
                "required": ["bill"]
            }
        }
        with open(schema_dir / "congress_bill.json", "w") as f:
            json.dump(bill_schema, f)
            
        # Create validator with test directory
        validator = ContractValidator(schema_dir=str(schema_dir))
        
        # Test valid response
        valid_response = {
            "bill": {
                "congress": 117,
                "type": "hr",
                "number": "1",
                "title": "Test Bill"
            }
        }
        is_valid, errors = validator.validate_response("congress", "bill", valid_response)
        assert is_valid
        assert not errors
        
        # Test invalid response (missing title)
        invalid_response = {
            "bill": {
                "congress": 117,
                "type": "hr",
                "number": "1"
                # Missing title
            }
        }
        is_valid, errors = validator.validate_response("congress", "bill", invalid_response)
        assert not is_valid
        assert len(errors) == 1
        assert "title" in errors[0]
        
        # Test response with no schema
        no_schema_response = {"test": "data"}
        is_valid, errors = validator.validate_response("govinfo", "nonexistent", no_schema_response)
        assert is_valid  # Passes by default if no schema
        assert not errors
        
        # Test with validator error
        with patch('jsonschema.Draft7Validator') as mock_validator:
            mock_instance = MagicMock()
            mock_validator.return_value = mock_instance
            mock_instance.iter_errors.side_effect = Exception("Test error")
            
            # Also patch the validate_response function to directly return False and error
            with patch('pygovpub.validation.test_contract.logger'):
                # Mock the try/except behavior to force the error path
                with patch.object(validator, '_load_schema', return_value={"type": "object"}):
                    # Force the exception to be raised and caught
                    with patch.object(Draft7Validator, '__init__', side_effect=Exception("Test error")):
                        is_valid, errors = validator.validate_response("congress", "bill", valid_response)
                        assert not is_valid
                        assert len(errors) == 1
                        assert "Test error" in errors[0]
            
    def test_create_schema_from_response(self, tmp_path):
        """Test creating schema from sample response."""
        # Create test schema directory
        schema_dir = tmp_path / "schemas"
        os.makedirs(schema_dir, exist_ok=True)
        
        # Create validator with test directory
        validator = ContractValidator(schema_dir=str(schema_dir))
        
        # Sample response data
        sample_response = {
            "bill": {
                "congress": 117,
                "type": "hr",
                "number": "1",
                "title": "Test Bill",
                "introducedDate": "2023-01-01",
                "sponsors": [
                    {"name": "Test Sponsor", "party": "D"}
                ]
            }
        }
        
        # Create schema from response
        schema_path = validator.create_schema_from_response(
            "congress", "bill", sample_response, "v3"
        )
        
        # Verify schema file was created
        assert os.path.exists(schema_path)
        
        # Load and verify schema content
        with open(schema_path, "r") as f:
            schema_data = json.load(f)
            
        assert schema_data["api_source"] == "congress"
        assert schema_data["endpoint"] == "bill"
        assert "schema" in schema_data
        assert schema_data["version"]["version_string"] == "v3"
        
        # Verify schema structure matches the sample response
        schema = schema_data["schema"]
        assert schema["type"] == "object"
        assert "bill" in schema["properties"]
        assert schema["properties"]["bill"]["type"] == "object"
        assert "congress" in schema["properties"]["bill"]["properties"]
        assert schema["properties"]["bill"]["properties"]["congress"]["type"] == "integer"
        assert "sponsors" in schema["properties"]["bill"]["properties"]
        assert schema["properties"]["bill"]["properties"]["sponsors"]["type"] == "array"
        
    def test_generate_schema(self):
        """Test schema generation from sample data."""
        validator = ContractValidator()
        
        # Test object schema generation
        obj_data = {"name": "test", "value": 123, "active": True}
        obj_schema = validator._generate_schema(obj_data)
        assert obj_schema["type"] == "object"
        assert "properties" in obj_schema
        assert "name" in obj_schema["properties"]
        assert obj_schema["properties"]["name"]["type"] == "string"
        assert obj_schema["properties"]["value"]["type"] == "integer"
        assert obj_schema["properties"]["active"]["type"] == "boolean"
        assert "required" in obj_schema
        assert set(obj_schema["required"]) == {"name", "value", "active"}
        
        # Test array schema generation
        array_data = [1, 2, 3]
        array_schema = validator._generate_schema(array_data)
        assert array_schema["type"] == "array"
        assert "items" in array_schema
        assert array_schema["items"]["type"] == "integer"
        
        # Test empty array
        empty_array = []
        empty_schema = validator._generate_schema(empty_array)
        assert empty_schema["type"] == "array"
        assert "items" in empty_schema
        assert empty_schema["items"] == {}
        
        # Test primitive types
        assert validator._generate_schema("test")["type"] == "string"
        assert validator._generate_schema(123)["type"] == "integer"
        assert validator._generate_schema(123.45)["type"] == "number"
        assert validator._generate_schema(True)["type"] == "boolean"
        assert validator._generate_schema(None)["type"] == "null"
        
        # Test complex nested structure
        complex_data = {
            "items": [
                {"id": 1, "name": "Item 1"},
                {"id": 2, "name": "Item 2"}
            ],
            "metadata": {
                "count": 2,
                "page": 1,
                "hasMore": False
            }
        }
        complex_schema = validator._generate_schema(complex_data)
        assert complex_schema["type"] == "object"
        assert "items" in complex_schema["properties"]
        assert complex_schema["properties"]["items"]["type"] == "array"
        assert complex_schema["properties"]["items"]["items"]["type"] == "object"
        assert "metadata" in complex_schema["properties"]
        assert complex_schema["properties"]["metadata"]["type"] == "object"
        assert complex_schema["properties"]["metadata"]["properties"]["hasMore"]["type"] == "boolean"
        
    def test_hash_schema(self):
        """Test schema hashing."""
        validator = ContractValidator()
        
        # Test basic hashing
        schema1 = {"type": "object", "properties": {"name": {"type": "string"}}}
        hash1 = validator._hash_schema(schema1)
        assert len(hash1) == 16
        assert isinstance(hash1, str)
        
        # Test that different schemas have different hashes
        schema2 = {"type": "object", "properties": {"age": {"type": "integer"}}}
        hash2 = validator._hash_schema(schema2)
        assert hash1 != hash2
        
        # Test that order doesn't matter
        schema3 = {"properties": {"name": {"type": "string"}}, "type": "object"}
        hash3 = validator._hash_schema(schema3)
        assert hash1 == hash3
        
    def test_get_iso_timestamp(self):
        """Test ISO timestamp generation."""
        validator = ContractValidator()
        timestamp = validator._get_iso_timestamp()
        
        # Test format
        assert "T" in timestamp  # ISO format separator
        assert "+" in timestamp or "Z" in timestamp  # timezone indicator


class TestHelperFunctions:
    """Tests for the helper functions."""

    def test_validate_request(self):
        """Test the validate_request helper function."""
        # We'll mock the ContractValidator to isolate the test
        with patch('pygovpub.validation.test_contract.ContractValidator') as MockValidator:
            mock_instance = MagicMock()
            MockValidator.return_value = mock_instance
            mock_instance.validate_request.return_value = (True, [])
            
            # Test the helper function
            request_data = {"test": "data"}
            is_valid, errors = validate_request("congress", "test", request_data)
            
            # Verify the validator was called correctly
            MockValidator.assert_called_once()
            mock_instance.validate_request.assert_called_once_with("congress", "test", request_data)
            assert is_valid is True
            assert errors == []
            
    def test_validate_response(self):
        """Test the validate_response helper function."""
        # We'll mock the ContractValidator to isolate the test
        with patch('pygovpub.validation.test_contract.ContractValidator') as MockValidator:
            mock_instance = MagicMock()
            MockValidator.return_value = mock_instance
            mock_instance.validate_response.return_value = (False, ["Error"])
            
            # Test the helper function
            response_data = {"test": "data"}
            is_valid, errors = validate_response("govinfo", "test", response_data)
            
            # Verify the validator was called correctly
            MockValidator.assert_called_once()
            mock_instance.validate_response.assert_called_once_with("govinfo", "test", response_data)
            assert is_valid is False
            assert errors == ["Error"]
            
    def test_create_schema_from_response(self):
        """Test the create_schema_from_response helper function."""
        # We'll mock the ContractValidator to isolate the test
        with patch('pygovpub.validation.test_contract.ContractValidator') as MockValidator:
            mock_instance = MagicMock()
            MockValidator.return_value = mock_instance
            mock_instance.create_schema_from_response.return_value = "/test/path.json"
            
            # Test the helper function
            response_data = {"test": "data"}
            result = create_schema_from_response("congress", "test", response_data, "v2")
            
            # Verify the validator was called correctly
            MockValidator.assert_called_once()
            mock_instance.create_schema_from_response.assert_called_once_with(
                "congress", "test", response_data, "v2"
            )
            assert result == "/test/path.json"