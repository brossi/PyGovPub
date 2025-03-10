"""
Schema validation.

This module validates JSON schemas for API responses.
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import jsonschema


# Define schemas for different response types
BILL_SCHEMA = {
    "type": "object",
    "required": ["congress", "type", "number", "title"],
    "properties": {
        "congress": {"type": "integer"},
        "type": {"type": "string"},
        "number": {"type": "string"},
        "title": {"type": "string"},
        "updateDate": {"type": "string", "format": "date"},
        "originChamber": {"type": "string"},
        "introducedDate": {"type": "string", "format": "date"}
    }
}

MEMBER_SCHEMA = {
    "type": "object",
    "required": ["bioguideID", "firstName", "lastName", "state"],
    "properties": {
        "bioguideID": {"type": "string"},
        "firstName": {"type": "string"},
        "lastName": {"type": "string"},
        "state": {"type": "string"},
        "party": {"type": "string"},
        "chamber": {"type": "string"},
        "updateDate": {"type": "string", "format": "date"}
    }
}

DOCUMENT_SCHEMA = {
    "type": "object",
    "required": ["packageId", "title", "congress"],
    "properties": {
        "packageId": {"type": "string"},
        "title": {"type": "string"},
        "congress": {"type": "integer"},
        "lastModified": {"type": "string", "format": "date-time"},
        "dateIssued": {"type": "string", "format": "date"}
    }
}

API_RESPONSE_SCHEMA = {
    "type": "object",
    "required": ["metadata", "data"],
    "properties": {
        "metadata": {
            "type": "object",
            "required": ["source", "timestamp"],
            "properties": {
                "source": {"type": "string"},
                "timestamp": {"type": "string", "format": "date-time"},
                "request_id": {"type": "string"},
                "processing_time_ms": {"type": "integer"},
                "count": {"type": "integer"},
                "source_updated_at": {"type": ["string", "null"], "format": "date-time"},
                "api_version": {"type": ["string", "null"]},
                "schema_version": {"type": ["string", "null"]}
            }
        },
        "pagination": {
            "type": "object",
            "required": ["total_count", "count", "offset"],
            "properties": {
                "total_count": {"type": "integer"},
                "count": {"type": "integer"},
                "offset": {"type": "integer"},
                "limit": {"type": ["integer", "null"]},
                "next_page_url": {"type": ["string", "null"]},
                "previous_page_url": {"type": ["string", "null"]}
            }
        },
        "data": {
            "anyOf": [
                {"type": "array"},
                {"type": "null"},
                {"type": "object"}
            ]
        },
        "error": {
            "type": "object",
            "required": ["message", "status_code"],
            "properties": {
                "message": {"type": "string"},
                "status_code": {"type": "integer"},
                "error_code": {"type": ["string", "null"]},
                "details": {"type": ["object", "null"]}
            }
        }
    }
}


def validate_against_schema(data: Dict[str, Any], schema: Dict[str, Any]) -> bool:
    """
    Validate data against a JSON schema.
    
    Args:
        data: The data to validate
        schema: The JSON schema to validate against
        
    Returns:
        True if valid, False otherwise
    """
    try:
        jsonschema.validate(instance=data, schema=schema)
        return True
    except jsonschema.exceptions.ValidationError as e:
        print(f"Schema validation error: {e}")
        return False


def main() -> int:
    """
    Run all schema validation tests.
    
    Returns:
        0 for success, 1 for failure
    """
    # Test bill schema
    bill_data = {
        "congress": 117,
        "type": "HR",
        "number": "1234",
        "title": "Test Bill 1",
        "updateDate": "2023-05-15",
        "originChamber": "House",
        "introducedDate": "2023-01-10"
    }
    if not validate_against_schema(bill_data, BILL_SCHEMA):
        return 1
        
    # Test member schema
    member_data = {
        "bioguideID": "S000148",
        "firstName": "Bernie",
        "lastName": "Sanders",
        "state": "VT",
        "party": "Independent",
        "chamber": "Senate",
        "updateDate": "2023-05-01"
    }
    if not validate_against_schema(member_data, MEMBER_SCHEMA):
        return 1
        
    # Test document schema
    document_data = {
        "packageId": "BILLS-117hr1234ih",
        "title": "A Bill 1",
        "congress": 117,
        "lastModified": "2023-01-15T10:30:00Z",
        "dateIssued": "2023-01-10"
    }
    if not validate_against_schema(document_data, DOCUMENT_SCHEMA):
        return 1
        
    # Test API response schema
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
    if not validate_against_schema(api_response_data, API_RESPONSE_SCHEMA):
        return 1
        
    print("All schema validations passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())