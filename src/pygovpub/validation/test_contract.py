"""
API contract validation for PyGovPub.

This module validates API requests and responses against JSON schemas to ensure
they conform to the expected contract. It provides utilities for testing both
outgoing requests to external APIs and incoming responses.
"""

import json
import logging
import os
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import jsonschema
from jsonschema import Draft7Validator, ValidationError

from pygovpub.config import config

logger = logging.getLogger(__name__)


class ApiSource(str, Enum):
    """Enumeration of supported API sources."""
    
    CONGRESS = "congress"
    GOVINFO = "govinfo"
    INTERNAL = "internal"


class ContractValidator:
    """Validator for API request and response contracts."""
    
    def __init__(self, schema_dir: Optional[str] = None):
        """Initialize the contract validator.
        
        Args:
            schema_dir: Directory containing schema files (defaults to package schemas)
        """
        if schema_dir:
            self.schema_dir = Path(schema_dir)
        else:
            # Default to the package schemas directory
            module_dir = Path(__file__).parent.parent
            self.schema_dir = module_dir / "schemas"
            
        # Cache for loaded schemas
        self._schemas: Dict[str, Dict[str, Any]] = {}
        
        # Load available schemas
        self.available_schemas = self._discover_schemas()
        
    def _discover_schemas(self) -> Dict[str, Path]:
        """Discover available schema files.
        
        Returns:
            Dictionary of schema_id -> file_path
        """
        schemas = {}
        
        if self.schema_dir.exists():
            for file_path in self.schema_dir.glob("*.json"):
                try:
                    with open(file_path, "r") as f:
                        schema_data = json.load(f)
                        
                    # Check if this is a valid schema file with api_source and endpoint
                    if "api_source" in schema_data and "endpoint" in schema_data:
                        schema_id = f"{schema_data['api_source']}:{schema_data['endpoint']}"
                        schemas[schema_id] = file_path
                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning(f"Invalid schema file: {file_path}: {e}")
        
        return schemas
    
    def _load_schema(self, api_source: str, endpoint: str) -> Optional[Dict[str, Any]]:
        """Load a schema from file.
        
        Args:
            api_source: API source ("congress", "govinfo", "internal")
            endpoint: API endpoint path
            
        Returns:
            Schema dict or None if not found
        """
        schema_id = f"{api_source}:{endpoint}"
        
        # Return cached schema if available
        if schema_id in self._schemas:
            return self._schemas[schema_id]
        
        # Try to find the schema file
        if schema_id in self.available_schemas:
            file_path = self.available_schemas[schema_id]
            try:
                with open(file_path, "r") as f:
                    schema_data = json.load(f)
                    
                # Store in cache
                self._schemas[schema_id] = schema_data.get("schema", {})
                return self._schemas[schema_id]
            except json.JSONDecodeError as e:
                logger.error(f"Error loading schema {schema_id}: {e}")
                
        return None
    
    def validate_request(
        self, 
        api_source: Union[str, ApiSource], 
        endpoint: str, 
        request_data: Dict[str, Any]
    ) -> Tuple[bool, List[str]]:
        """Validate an API request against its schema.
        
        Args:
            api_source: API source ("congress", "govinfo", "internal")
            endpoint: API endpoint path
            request_data: Request data to validate
            
        Returns:
            Tuple of (is_valid, error_messages)
        """
        # Normalize api_source
        if isinstance(api_source, ApiSource):
            api_source = api_source.value
            
        # Request schemas are typically simple and don't have separate schema files
        # For now, we'll implement basic validation based on the endpoint
        
        if api_source == "congress":
            # Basic validation for Congress API requests
            if "bill" in endpoint:
                # Bill requests require congress, bill_type, bill_number
                if "congress" not in request_data:
                    return False, ["Missing required parameter: congress"]
                if "bill_type" not in request_data:
                    return False, ["Missing required parameter: bill_type"]
                if "bill_number" not in request_data:
                    return False, ["Missing required parameter: bill_number"]
            elif "member" in endpoint:
                # Member requests require bioguide_id
                if "bioguide_id" not in request_data:
                    return False, ["Missing required parameter: bioguide_id"]
            elif "committee" in endpoint:
                # Committee requests require congress, chamber, committee_code
                if "congress" not in request_data:
                    return False, ["Missing required parameter: congress"]
                if "chamber" not in request_data:
                    return False, ["Missing required parameter: chamber"]
                if "committee_code" not in request_data:
                    return False, ["Missing required parameter: committee_code"]
                    
        elif api_source == "govinfo":
            # Basic validation for GovInfo API requests
            if "packages" in endpoint:
                # Package requests require package_id
                if "package_id" not in request_data:
                    return False, ["Missing required parameter: package_id"]
            elif "collections" in endpoint:
                # Collections requests may have optional parameters
                pass
                
        # All checks passed
        return True, []
    
    def validate_response(
        self, 
        api_source: Union[str, ApiSource], 
        endpoint: str, 
        response_data: Dict[str, Any]
    ) -> Tuple[bool, List[str]]:
        """Validate an API response against its schema.
        
        Args:
            api_source: API source ("congress", "govinfo", "internal")
            endpoint: API endpoint path
            response_data: Response data to validate
            
        Returns:
            Tuple of (is_valid, error_messages)
        """
        # Normalize api_source
        if isinstance(api_source, ApiSource):
            api_source = api_source.value
            
        # Load the schema
        schema = self._load_schema(api_source, endpoint)
        if not schema:
            logger.warning(f"No schema found for {api_source}:{endpoint}")
            return True, []  # Can't validate without schema
            
        # Validate against the schema
        try:
            validator = Draft7Validator(schema)
            errors = list(validator.iter_errors(response_data))
            
            if errors:
                error_messages = [f"{e.path}: {e.message}" for e in errors]
                return False, error_messages
                
            return True, []
            
        except Exception as e:
            logger.error(f"Error validating response: {e}")
            # Return False and the error message when an exception occurs
            return False, [str(e)]
    
    def create_schema_from_response(
        self, 
        api_source: Union[str, ApiSource],
        endpoint: str,
        response_data: Dict[str, Any],
        version: str = "v1"
    ) -> str:
        """Create a schema file from a sample response.
        
        Args:
            api_source: API source ("congress", "govinfo", "internal")
            endpoint: API endpoint path
            response_data: Sample response data
            version: API version string
            
        Returns:
            Path to the created schema file
        """
        # Normalize api_source
        if isinstance(api_source, ApiSource):
            api_source = api_source.value
            
        # Generate a schema from the response data
        schema = self._generate_schema(response_data)
        
        # Create the schema file content
        schema_data = {
            "api_source": api_source,
            "endpoint": endpoint,
            "schema": schema,
            "version": {
                "version_string": version,
                "schema_hash": self._hash_schema(schema),
                "first_seen": self._get_iso_timestamp(),
                "last_seen": self._get_iso_timestamp(),
                "is_supported": True
            }
        }
        
        # Create a filename based on the endpoint
        endpoint_parts = endpoint.split("/")
        if len(endpoint_parts) == 1:
            filename = f"{api_source}_{endpoint}.json"
        else:
            resource = endpoint_parts[0]
            filename = f"{api_source}_{resource}.json"
            
        file_path = self.schema_dir / filename
        
        # Make sure the directory exists
        os.makedirs(self.schema_dir, exist_ok=True)
        
        # Write the schema file
        with open(file_path, "w") as f:
            json.dump(schema_data, f, indent=2)
            
        # Add to available schemas
        schema_id = f"{api_source}:{endpoint}"
        self.available_schemas[schema_id] = file_path
        
        return str(file_path)
    
    def _generate_schema(self, data: Any) -> Dict[str, Any]:
        """Generate a JSON schema from sample data.
        
        Args:
            data: Sample data to generate schema from
            
        Returns:
            JSON schema dictionary
        """
        schema = {"$schema": "http://json-schema.org/schema#"}
        
        if isinstance(data, dict):
            schema["type"] = "object"
            schema["properties"] = {}
            schema["required"] = []
            
            for key, value in data.items():
                schema["properties"][key] = self._generate_schema(value)
                schema["required"].append(key)
                
        elif isinstance(data, list):
            schema["type"] = "array"
            if data:
                # Use the first item as a representative item
                schema["items"] = self._generate_schema(data[0])
            else:
                schema["items"] = {}
                
        elif isinstance(data, str):
            schema["type"] = "string"
        elif isinstance(data, bool):
            schema["type"] = "boolean"
        elif isinstance(data, int):
            schema["type"] = "integer"
        elif isinstance(data, float):
            schema["type"] = "number"
        elif data is None:
            schema["type"] = "null"
        else:
            # Default fallback
            schema["type"] = "string"
            
        return schema
        
    def _hash_schema(self, schema: Dict[str, Any]) -> str:
        """Create a hash of the schema for versioning.
        
        Args:
            schema: JSON schema to hash
            
        Returns:
            Hex string hash
        """
        schema_str = json.dumps(schema, sort_keys=True)
        import hashlib
        return hashlib.md5(schema_str.encode()).hexdigest()[:16]
        
    def _get_iso_timestamp(self) -> str:
        """Get current timestamp in ISO format.
        
        Returns:
            ISO timestamp string
        """
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()


# Helper functions
def validate_request(
    api_source: Union[str, ApiSource], 
    endpoint: str, 
    request_data: Dict[str, Any]
) -> Tuple[bool, List[str]]:
    """Validate an API request against its schema.
    
    Args:
        api_source: API source ("congress", "govinfo", "internal")
        endpoint: API endpoint path
        request_data: Request data to validate
        
    Returns:
        Tuple of (is_valid, error_messages)
    """
    validator = ContractValidator()
    return validator.validate_request(api_source, endpoint, request_data)


def validate_response(
    api_source: Union[str, ApiSource], 
    endpoint: str, 
    response_data: Dict[str, Any]
) -> Tuple[bool, List[str]]:
    """Validate an API response against its schema.
    
    Args:
        api_source: API source ("congress", "govinfo", "internal")
        endpoint: API endpoint path
        response_data: Response data to validate
        
    Returns:
        Tuple of (is_valid, error_messages)
    """
    validator = ContractValidator()
    return validator.validate_response(api_source, endpoint, response_data)


def create_schema_from_response(
    api_source: Union[str, ApiSource],
    endpoint: str,
    response_data: Dict[str, Any],
    version: str = "v1"
) -> str:
    """Create a schema file from a sample response.
    
    Args:
        api_source: API source ("congress", "govinfo", "internal")
        endpoint: API endpoint path
        response_data: Sample response data
        version: API version string
        
    Returns:
        Path to the created schema file
    """
    validator = ContractValidator()
    return validator.create_schema_from_response(api_source, endpoint, response_data, version)