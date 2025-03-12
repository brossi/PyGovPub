"""
Accessibility validation module for PyGovPub.

This module provides validation functions for ensuring data, API responses,
and documentation meet accessibility requirements. These functions support
Section 508 compliance and WCAG 2.1 standards.
"""

from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field

def validate_response_accessibility(response_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate that API response includes required accessibility metadata.
    
    Args:
        response_data: API response data to validate
        
    Returns:
        Dictionary with validation results (valid: bool, issues: list)
    """
    issues = []
    
    # Check for basic response structure
    if not isinstance(response_data, dict):
        return {"valid": False, "issues": ["Response must be a dictionary"]}
    
    # Check for basic metadata
    if "data" in response_data and response_data["data"]:
        # Check for descriptive metadata if content is present
        if "metadata" not in response_data:
            issues.append("Response missing 'metadata' field for screen readers")
        elif isinstance(response_data["metadata"], dict):
            # Check essential metadata
            if "description" not in response_data["metadata"]:
                issues.append("'description' missing in metadata")
                
            # Check for content-specific accessibility metadata
            content_type = response_data.get("content_type", "")
            
            # For image content, check alt text
            if "image" in content_type and "alt_text" not in response_data["metadata"]:
                issues.append("Image content missing 'alt_text' in metadata")
                
            # For document content, check for accessible formats
            if "document" in content_type and "accessible_formats" not in response_data["metadata"]:
                issues.append("Document content missing 'accessible_formats' in metadata")
    
    # Check for pagination accessibility
    if "pagination" in response_data:
        pagination = response_data["pagination"]
        required_fields = ["total", "page", "per_page"]
        for field in required_fields:
            if field not in pagination:
                issues.append(f"Pagination missing '{field}' for navigation")
    
    # Check for error message accessibility
    if "error" in response_data:
        if not isinstance(response_data.get("error"), dict):
            issues.append("Error must be a structured object")
        else:
            error = response_data["error"]
            if "message" not in error:
                issues.append("Error missing 'message' field")
            if "details" not in error:
                issues.append("Error missing 'details' field for troubleshooting")
    
    # Return validation result
    return {
        "valid": len(issues) == 0,
        "issues": issues
    }


def validate_data_format_accessibility(data: Any, format_type: str) -> Dict[str, Any]:
    """
    Validate that data format meets accessibility requirements.
    
    Args:
        data: Data to validate
        format_type: Format type (json, xml, csv, etc.)
        
    Returns:
        Dictionary with validation results (valid: bool, issues: list)
    """
    issues = []
    
    # For JSON data
    if format_type == "json":
        if not isinstance(data, (dict, list)):
            issues.append("JSON data must be dictionary or list")
        
        # Validate nested structure (maximum nesting for screen readers)
        if isinstance(data, dict):
            max_depth = get_json_max_depth(data)
            if max_depth > 5:  # Standard accessibility recommendation
                issues.append(f"JSON nesting too deep ({max_depth} levels, max 5 recommended)")
    
    # For tabular data (CSV)
    elif format_type == "csv":
        if not hasattr(data, 'fieldnames') and not (isinstance(data, list) and len(data) > 0):
            issues.append("CSV data must have headers/fieldnames for screen readers")
    
    # For XML data - basic structure check
    elif format_type == "xml" and isinstance(data, str):
        if "<?xml" not in data:
            issues.append("XML missing declaration")
        if "lang=" not in data:
            issues.append("XML missing language attribute")
    
    # Return validation result
    return {
        "valid": len(issues) == 0,
        "issues": issues
    }


def validate_documentation_accessibility(documentation: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate that documentation meets accessibility requirements.
    
    Args:
        documentation: Documentation data (typically OpenAPI schema)
        
    Returns:
        Dictionary with validation results (valid: bool, issues: list)
    """
    issues = []
    
    # Check for basic structure
    if not isinstance(documentation, dict):
        return {"valid": False, "issues": ["Documentation must be a dictionary"]}
    
    # Check for info section
    if "info" not in documentation:
        issues.append("Missing 'info' section")
    else:
        info = documentation["info"]
        if "title" not in info:
            issues.append("Missing 'title' in info")
        if "description" not in info:
            issues.append("Missing 'description' in info")
    
    # Check paths for accessibility
    if "paths" in documentation:
        paths = documentation["paths"]
        for path, path_item in paths.items():
            for method, operation in path_item.items():
                if method in ["get", "post", "put", "delete", "patch"]:
                    # Check for operation description
                    if "description" not in operation:
                        issues.append(f"Operation {method} {path} missing description")
                    
                    # Check parameters for descriptions
                    if "parameters" in operation:
                        for param in operation["parameters"]:
                            if "description" not in param:
                                param_name = param.get("name", "unknown")
                                issues.append(f"Parameter '{param_name}' missing description")
                    
                    # Check response documentation
                    if "responses" not in operation:
                        issues.append(f"Operation {method} {path} missing responses")
    
    # Return validation result
    return {
        "valid": len(issues) == 0,
        "issues": issues
    }


def validate_cli_accessibility(command_help: str) -> Dict[str, Any]:
    """
    Validate CLI help text for accessibility.
    
    Args:
        command_help: Command help text
        
    Returns:
        Dictionary with validation results (valid: bool, issues: list)
    """
    issues = []
    
    # Check basic structure
    if not command_help or not isinstance(command_help, str):
        return {"valid": False, "issues": ["Help text must be a non-empty string"]}
    
    # Check for usage information
    if "Usage:" not in command_help:
        issues.append("Missing 'Usage:' section")
    
    # Check for options documentation
    if "Options:" not in command_help:
        issues.append("Missing 'Options:' section")
    
    # Check for help option
    if "--help" not in command_help:
        issues.append("Missing --help option")
    
    # Check for examples
    if "Examples:" not in command_help and "Example:" not in command_help:
        issues.append("Missing examples section")
    
    # Check for version information
    if "--version" not in command_help:
        issues.append("Missing --version option")
    
    # Return validation result
    return {
        "valid": len(issues) == 0,
        "issues": issues
    }


# Utility functions

def get_json_max_depth(data: Dict[str, Any], current_depth: int = 1) -> int:
    """
    Calculate maximum nesting depth of JSON.
    
    Args:
        data: JSON data
        current_depth: Current depth in recursion
        
    Returns:
        Maximum depth
    """
    if not isinstance(data, (dict, list)):
        return current_depth
    
    max_depth = current_depth
    
    if isinstance(data, dict):
        for value in data.values():
            if isinstance(value, (dict, list)):
                depth = get_json_max_depth(value, current_depth + 1)
                max_depth = max(max_depth, depth)
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, (dict, list)):
                depth = get_json_max_depth(item, current_depth + 1)
                max_depth = max(max_depth, depth)
    
    return max_depth


# Accessibility model mixins for API responses

class AccessibleResponseMixin(BaseModel):
    """Mixin to add accessibility fields to response models."""
    
    description: Optional[str] = Field(
        None, 
        description="Detailed description suitable for screen readers"
    )
    alt_text: Optional[str] = Field(
        None, 
        description="Alternative text for image-based content"
    )
    semantic_context: Optional[str] = Field(
        None,
        description="Contextual information about the data's meaning"
    )
    lang: Optional[str] = Field(
        "en-US",
        description="Language of the content"
    )