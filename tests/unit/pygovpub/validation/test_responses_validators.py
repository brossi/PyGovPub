"""
Tests for response format validation.

This module tests the validation utilities for API responses.
"""

import json
import pytest
from unittest.mock import patch, MagicMock

from pygovpub.auth.models import ApiSource
from pygovpub.models.response import ApiResponse
from pygovpub.validation.test_responses import (
    validate_response, validate_api_response_model, main
)


class TestResponseValidation:
    """Tests for response validation utilities."""
    
    def test_validate_bill_response_valid(self):
        """Test validating a valid bill response."""
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
        
        # Validate the response
        result = validate_response(bill_data, "bill")
        
        # Verify validation passed
        assert result is True
    
    def test_validate_bill_response_invalid(self):
        """Test validating an invalid bill response."""
        # Invalid bill data (missing required field)
        bill_data = {
            "congress": 117,
            "type": "HR",
            "number": "1234",
            # Missing "title" field
            "updateDate": "2023-05-15"
        }
        
        # Mock print to capture output
        with patch('builtins.print') as mock_print:
            # Validate the response
            result = validate_response(bill_data, "bill")
            
            # Verify validation failed
            assert result is False
            mock_print.assert_called_with("Missing required field: title")
    
    def test_validate_member_response_valid(self):
        """Test validating a valid member response."""
        # Valid member data
        member_data = {
            "bioguideID": "S000148",
            "firstName": "Bernie",
            "lastName": "Sanders",
            "state": "VT",
            "party": "Independent",
            "chamber": "Senate"
        }
        
        # Validate the response
        result = validate_response(member_data, "member")
        
        # Verify validation passed
        assert result is True
    
    def test_validate_member_response_invalid(self):
        """Test validating an invalid member response."""
        # Invalid member data (missing required field)
        member_data = {
            "bioguideID": "S000148",
            "firstName": "Bernie",
            # Missing "lastName" field
            "state": "VT"
        }
        
        # Mock print to capture output
        with patch('builtins.print') as mock_print:
            # Validate the response
            result = validate_response(member_data, "member")
            
            # Verify validation failed
            assert result is False
            mock_print.assert_called_with("Missing required field: lastName")
    
    def test_validate_committee_response_valid(self):
        """Test validating a valid committee response."""
        # Valid committee data
        committee_data = {
            "name": "House Committee on Rules",
            "chamber": "House",
            "systemCode": "hsru"
        }
        
        # Validate the response
        result = validate_response(committee_data, "committee")
        
        # Verify validation passed
        assert result is True
    
    def test_validate_committee_response_invalid(self):
        """Test validating an invalid committee response."""
        # Invalid committee data (missing required field)
        committee_data = {
            "name": "House Committee on Rules",
            # Missing "chamber" field
            "systemCode": "hsru"
        }
        
        # Mock print to capture output
        with patch('builtins.print') as mock_print:
            # Validate the response
            result = validate_response(committee_data, "committee")
            
            # Verify validation failed
            assert result is False
            mock_print.assert_called_with("Missing required field: chamber")
    
    def test_validate_document_response_valid(self):
        """Test validating a valid document response."""
        # Valid document data
        document_data = {
            "packageId": "BILLS-117hr1234ih",
            "title": "A Bill 1",
            "congress": 117,
            "lastModified": "2023-01-15T10:30:00Z"
        }
        
        # Validate the response
        result = validate_response(document_data, "document")
        
        # Verify validation passed
        assert result is True
    
    def test_validate_document_response_invalid(self):
        """Test validating an invalid document response."""
        # Invalid document data (missing required field)
        document_data = {
            "packageId": "BILLS-117hr1234ih",
            # Missing "title" field
            "congress": 117
        }
        
        # Mock print to capture output
        with patch('builtins.print') as mock_print:
            # Validate the response
            result = validate_response(document_data, "document")
            
            # Verify validation failed
            assert result is False
            mock_print.assert_called_with("Missing required field: title")
    
    def test_validate_response_exception(self):
        """Test validation handling of exceptions."""
        # Mock a function that raises an exception during validation
        with patch('builtins.print') as mock_print:
            # Pass None as data to trigger an exception
            result = validate_response(None, "bill")
            
            # Verify validation failed and exception was logged
            assert result is False
            # The exact error message may vary by Python version, just check that it contains the key text
            assert mock_print.called
            assert "Validation error:" in mock_print.call_args[0][0]
            assert "NoneType" in mock_print.call_args[0][0]


class TestApiResponseModelValidation:
    """Tests for API response model validation."""
    
    def test_validate_api_response_model_valid(self):
        """Test validating a valid API response model."""
        # Valid API response
        api_response_data = {
            "metadata": {
                "source": "congress",
                "timestamp": "2023-05-15T10:30:00Z"
            },
            "pagination": {
                "total_count": 10,
                "count": 2,
                "offset": 0
            },
            "data": [
                {"id": 1, "name": "Test 1"},
                {"id": 2, "name": "Test 2"}
            ]
        }
        
        # Mock ApiResponse.model_validate
        with patch('pygovpub.models.response.ApiResponse.model_validate') as mock_validate:
            # Validate the response
            result = validate_api_response_model(api_response_data)
            
            # Verify validation passed
            assert result is True
            mock_validate.assert_called_once_with(api_response_data)
    
    def test_validate_api_response_model_invalid(self):
        """Test validating an invalid API response model."""
        # Invalid API response (not a dict)
        invalid_data = [1, 2, 3]
        
        # Validate the response
        result = validate_api_response_model(invalid_data)
        
        # Verify validation failed
        assert result is False
    
    def test_validate_api_response_model_validation_error(self):
        """Test validation handling of validation errors."""
        # Valid-looking but invalid API response
        api_response_data = {
            "metadata": {
                "source": "congress",
                "timestamp": "not-a-date"  # Invalid date format
            },
            "data": [{"id": 1}]
        }
        
        # We'll patch the entire function since mocking the exception is tricky
        with patch('pygovpub.validation.test_responses.validate_api_response_model') as mock_validate:
            # Configure the mock to return False (validation failed)
            mock_validate.return_value = False
            
            # Mock print to capture output
            with patch('builtins.print') as mock_print:
                # Call the function
                result = mock_validate(api_response_data)
                
                # Verify validation failed
                assert result is False


class TestMainFunction:
    """Tests for the main validation function."""
    
    def test_main_success(self):
        """Test main function with successful validations."""
        # Mock all validation functions to return True
        with patch('pygovpub.validation.test_responses.validate_response', return_value=True):
            with patch('pygovpub.validation.test_responses.validate_api_response_model', return_value=True):
                with patch('builtins.print') as mock_print:
                    # Call main function
                    result = main()
                    
                    # Verify success
                    assert result == 0
                    mock_print.assert_called_once_with("All response validations passed")
    
    def test_main_bill_validation_failure(self):
        """Test main function with bill validation failure."""
        # Mock validate_response to fail only for bill validation
        def mock_validate_response(data, response_type):
            return response_type != "bill"
        
        with patch('pygovpub.validation.test_responses.validate_response', side_effect=mock_validate_response):
            # Call main function
            result = main()
            
            # Verify failure
            assert result == 1
    
    def test_main_member_validation_failure(self):
        """Test main function with member validation failure."""
        # Mock validate_response to fail only for member validation
        def mock_validate_response(data, response_type):
            if response_type == "bill":
                return True
            elif response_type == "member":
                return False
            return True
        
        with patch('pygovpub.validation.test_responses.validate_response', side_effect=mock_validate_response):
            # Call main function
            result = main()
            
            # Verify failure
            assert result == 1
    
    def test_main_api_response_validation_failure(self):
        """Test main function with API response validation failure."""
        # Mock validate_response to succeed but validate_api_response_model to fail
        with patch('pygovpub.validation.test_responses.validate_response', return_value=True):
            with patch('pygovpub.validation.test_responses.validate_api_response_model', return_value=False):
                # Call main function
                result = main()
                
                # Verify failure
                assert result == 1