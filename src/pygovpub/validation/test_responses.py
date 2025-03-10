"""
Response format validation.

This module validates that API responses conform to expected formats.
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import fastapi
import pydantic
from fastapi.testclient import TestClient

from pygovpub.auth.models import ApiSource
from pygovpub.models.response import ApiResponse


def validate_response(response_data: Dict[str, Any], response_type: str) -> bool:
    """
    Validate that a response matches expected format.
    
    Args:
        response_data: The response data to validate
        response_type: The type of response (bill, member, etc.)
        
    Returns:
        True if valid, False otherwise
    """
    try:
        if response_type == "bill":
            # Validate bill response
            required_fields = ["congress", "type", "number", "title"]
            for field in required_fields:
                if field not in response_data:
                    print(f"Missing required field: {field}")
                    return False
                    
        elif response_type == "member":
            # Validate member response
            required_fields = ["bioguideID", "firstName", "lastName", "state"]
            for field in required_fields:
                if field not in response_data:
                    print(f"Missing required field: {field}")
                    return False
                    
        elif response_type == "committee":
            # Validate committee response
            required_fields = ["name", "chamber"]
            for field in required_fields:
                if field not in response_data:
                    print(f"Missing required field: {field}")
                    return False
                    
        elif response_type == "document":
            # Validate document response
            required_fields = ["packageId", "title", "congress"]
            for field in required_fields:
                if field not in response_data:
                    print(f"Missing required field: {field}")
                    return False
                    
        return True
        
    except Exception as e:
        print(f"Validation error: {e}")
        return False


def validate_api_response_model(data: Any) -> bool:
    """
    Validate that data can be parsed into an ApiResponse.
    
    Args:
        data: The data to validate
        
    Returns:
        True if valid, False otherwise
    """
    try:
        # Try to parse as ApiResponse
        if isinstance(data, dict):
            ApiResponse.model_validate(data)
            return True
            
        return False
        
    except pydantic.ValidationError as e:
        print(f"API response validation error: {e}")
        return False


def main() -> int:
    """
    Run all response validation tests.
    
    Returns:
        0 for success, 1 for failure
    """
    # Test bill response
    bill_data = {
        "congress": 117,
        "type": "HR",
        "number": "1234",
        "title": "Test Bill 1",
        "updateDate": "2023-05-15",
        "originChamber": "House",
        "introducedDate": "2023-01-10"
    }
    if not validate_response(bill_data, "bill"):
        return 1
        
    # Test member response
    member_data = {
        "bioguideID": "S000148",
        "firstName": "Bernie",
        "lastName": "Sanders",
        "state": "VT",
        "party": "Independent",
        "chamber": "Senate",
        "updateDate": "2023-05-01"
    }
    if not validate_response(member_data, "member"):
        return 1
        
    # Test API response model
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
        "data": [bill_data, bill_data]
    }
    if not validate_api_response_model(api_response_data):
        return 1
        
    print("All response validations passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())