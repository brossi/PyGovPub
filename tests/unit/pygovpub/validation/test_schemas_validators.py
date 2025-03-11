"""
Tests for schema validation.

This module tests the schema validation utilities for API responses.
"""

import json
import pytest
from unittest.mock import patch, MagicMock

import jsonschema
from pygovpub.validation.test_schemas import (
    validate_against_schema, main, 
    BILL_SCHEMA, MEMBER_SCHEMA, DOCUMENT_SCHEMA, API_RESPONSE_SCHEMA
)


class TestSchemaValidation:
    """Tests for schema validation utilities."""
    
    def test_validate_against_bill_schema_valid(self):
        """Test validating valid data against the bill schema."""
        # Valid bill data
        bill_data = {
            "congress": 117,
            "type": "HR",
            "number": "1234",
            "title": "Test Bill 1",
            "updateDate": "2023-05-15",
            "originChamber": "House",
            "introducedDate": "2023-01-10"
        }
        
        # Validate against schema
        result = validate_against_schema(bill_data, BILL_SCHEMA)
        
        # Verify validation passed
        assert result is True
    
    def test_validate_against_bill_schema_invalid(self):
        """Test validating invalid data against the bill schema."""
        # Invalid bill data (wrong type for congress)
        bill_data = {
            "congress": "117",  # Should be an integer
            "type": "HR",
            "number": "1234",
            "title": "Test Bill 1"
        }
        
        # Mock print to capture output
        with patch('builtins.print') as mock_print:
            # Validate against schema
            result = validate_against_schema(bill_data, BILL_SCHEMA)
            
            # Verify validation failed
            assert result is False
            assert mock_print.called
            # Check that error message contains expected text
            assert "Schema validation error" in mock_print.call_args[0][0]
    
    def test_validate_against_member_schema_valid(self):
        """Test validating valid data against the member schema."""
        # Valid member data
        member_data = {
            "bioguideID": "S000148",
            "firstName": "Bernie",
            "lastName": "Sanders",
            "state": "VT",
            "party": "Independent",
            "chamber": "Senate",
            "updateDate": "2023-05-01"
        }
        
        # Validate against schema
        result = validate_against_schema(member_data, MEMBER_SCHEMA)
        
        # Verify validation passed
        assert result is True
    
    def test_validate_against_member_schema_invalid(self):
        """Test validating invalid data against the member schema."""
        # Invalid member data (missing required field)
        member_data = {
            "bioguideID": "S000148",
            "firstName": "Bernie",
            # Missing "lastName" field
            "state": "VT"
        }
        
        # Mock print to capture output
        with patch('builtins.print') as mock_print:
            # Validate against schema
            result = validate_against_schema(member_data, MEMBER_SCHEMA)
            
            # Verify validation failed
            assert result is False
            assert mock_print.called
    
    def test_validate_against_document_schema_valid(self):
        """Test validating valid data against the document schema."""
        # Valid document data
        document_data = {
            "packageId": "BILLS-117hr1234ih",
            "title": "A Bill 1",
            "congress": 117,
            "lastModified": "2023-01-15T10:30:00Z",
            "dateIssued": "2023-01-10"
        }
        
        # Validate against schema
        result = validate_against_schema(document_data, DOCUMENT_SCHEMA)
        
        # Verify validation passed
        assert result is True
    
    def test_validate_against_document_schema_invalid(self):
        """Test validating invalid data against the document schema."""
        # In this test, we'll mock jsonschema.validate to force a validation error
        with patch('jsonschema.validate') as mock_validate:
            mock_validate.side_effect = jsonschema.exceptions.ValidationError("Invalid format")
            
            # Invalid document data (wrong format for lastModified)
            document_data = {
                "packageId": "BILLS-117hr1234ih",
                "title": "A Bill 1",
                "congress": 117,
                "lastModified": "not-a-date-time",  # Invalid format
                "dateIssued": "2023-01-10"
            }
            
            # Mock print to capture output
            with patch('builtins.print') as mock_print:
                # Validate against schema
                result = validate_against_schema(document_data, DOCUMENT_SCHEMA)
                
                # Verify validation failed
                assert result is False
                # Verify error message was logged
                mock_print.assert_called_with("Schema validation error: Invalid format")
    
    def test_validate_against_api_response_schema_valid(self):
        """Test validating valid data against the API response schema."""
        # Valid API response data
        api_response_data = {
            "metadata": {
                "source": "congress",
                "timestamp": "2023-05-15T10:30:00Z",
                "request_id": "req-12345",
                "processing_time_ms": 120,
                "count": 2,
                "source_updated_at": "2023-05-14T10:00:00Z",
                "api_version": "v3",
                "schema_version": "1.0.0"
            },
            "pagination": {
                "total_count": 10,
                "count": 2,
                "offset": 0,
                "limit": 2,
                "next_page_url": "https://api.example.com?page=2",
                "previous_page_url": None
            },
            "data": [
                {"id": 1, "name": "Test 1"},
                {"id": 2, "name": "Test 2"}
            ]
        }
        
        # Validate against schema
        result = validate_against_schema(api_response_data, API_RESPONSE_SCHEMA)
        
        # Verify validation passed
        assert result is True
    
    def test_validate_against_api_response_schema_invalid(self):
        """Test validating invalid data against the API response schema."""
        # Invalid API response data (missing required field in metadata)
        api_response_data = {
            "metadata": {
                # Missing "source" field
                "timestamp": "2023-05-15T10:30:00Z"
            },
            "data": []
        }
        
        # Mock print to capture output
        with patch('builtins.print') as mock_print:
            # Validate against schema
            result = validate_against_schema(api_response_data, API_RESPONSE_SCHEMA)
            
            # Verify validation failed
            assert result is False
            assert mock_print.called
    
    def test_validate_against_schema_with_jsonschema_error(self):
        """Test validation handling of jsonschema errors."""
        # Mock jsonschema.validate to raise a ValidationError
        with patch('jsonschema.validate') as mock_validate:
            mock_validate.side_effect = jsonschema.exceptions.ValidationError("Test validation error")
            
            # Mock print to capture output
            with patch('builtins.print') as mock_print:
                # Validate against schema
                result = validate_against_schema({}, {})
                
                # Verify validation failed and error was logged
                assert result is False
                mock_print.assert_called_with("Schema validation error: Test validation error")


class TestMainFunction:
    """Tests for the main validation function."""
    
    def test_main_success(self):
        """Test main function with successful validations."""
        # Mock validate_against_schema to always return True
        with patch('pygovpub.validation.test_schemas.validate_against_schema', return_value=True):
            with patch('builtins.print') as mock_print:
                # Call main function
                result = main()
                
                # Verify success
                assert result == 0
                mock_print.assert_called_once_with("All schema validations passed")
    
    def test_main_bill_schema_validation_failure(self):
        """Test main function with bill schema validation failure."""
        # Mock validate_against_schema to fail only for the first call (bill validation)
        mock_validate = MagicMock()
        mock_validate.side_effect = [False, True, True, True]
        
        with patch('pygovpub.validation.test_schemas.validate_against_schema', mock_validate):
            # Call main function
            result = main()
            
            # Verify failure
            assert result == 1
            assert mock_validate.call_count == 1  # Should stop after first failure
    
    def test_main_member_schema_validation_failure(self):
        """Test main function with member schema validation failure."""
        # Mock validate_against_schema to fail only for the second call (member validation)
        mock_validate = MagicMock()
        mock_validate.side_effect = [True, False, True, True]
        
        with patch('pygovpub.validation.test_schemas.validate_against_schema', mock_validate):
            # Call main function
            result = main()
            
            # Verify failure
            assert result == 1
            assert mock_validate.call_count == 2  # Should stop after second call
    
    def test_main_document_schema_validation_failure(self):
        """Test main function with document schema validation failure."""
        # Mock validate_against_schema to fail only for the third call (document validation)
        mock_validate = MagicMock()
        mock_validate.side_effect = [True, True, False, True]
        
        with patch('pygovpub.validation.test_schemas.validate_against_schema', mock_validate):
            # Call main function
            result = main()
            
            # Verify failure
            assert result == 1
            assert mock_validate.call_count == 3  # Should stop after third call
    
    def test_main_api_response_schema_validation_failure(self):
        """Test main function with API response schema validation failure."""
        # Mock validate_against_schema to fail only for the fourth call (API response validation)
        mock_validate = MagicMock()
        mock_validate.side_effect = [True, True, True, False]
        
        with patch('pygovpub.validation.test_schemas.validate_against_schema', mock_validate):
            # Call main function
            result = main()
            
            # Verify failure
            assert result == 1
            assert mock_validate.call_count == 4  # Should get to the fourth call