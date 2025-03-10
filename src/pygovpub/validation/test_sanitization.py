"""
Data sanitization validation.

This module validates that input data is properly sanitized.
"""

import html
import re
import sys
from typing import Any, Dict, List, Union

import html5lib


def sanitize_html(content: str) -> str:
    """
    Sanitize HTML content by removing potentially dangerous tags.
    
    Args:
        content: The HTML content to sanitize
        
    Returns:
        Sanitized HTML content
    """
    # Use html5lib to parse and sanitize
    document = html5lib.parse(content)
    
    # Remove script and style elements
    for script in document.findall(".//script"):
        script.getparent().remove(script)
    for style in document.findall(".//style"):
        style.getparent().remove(style)
        
    # Convert back to string
    sanitized = html5lib.serialize(document)
    return sanitized


def sanitize_query_param(param: str) -> str:
    """
    Sanitize query parameter.
    
    Args:
        param: The query parameter to sanitize
        
    Returns:
        Sanitized query parameter
    """
    # Strip any characters that might cause SQL injection
    param = re.sub(r"[';\"\\]", "", param)
    
    # HTML escape to prevent XSS
    param = html.escape(param)
    
    return param


def sanitize_json_input(data: Union[Dict[str, Any], List[Any]]) -> Union[Dict[str, Any], List[Any]]:
    """
    Sanitize JSON input.
    
    Args:
        data: The JSON data to sanitize
        
    Returns:
        Sanitized JSON data
    """
    if isinstance(data, dict):
        return {k: sanitize_json_input(v) if isinstance(v, (dict, list)) else sanitize_value(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_json_input(v) if isinstance(v, (dict, list)) else sanitize_value(v) for v in data]
    else:
        return data


def sanitize_value(value: Any) -> Any:
    """
    Sanitize a single value.
    
    Args:
        value: The value to sanitize
        
    Returns:
        Sanitized value
    """
    if isinstance(value, str):
        # Sanitize string values
        return html.escape(value)
    else:
        return value


def test_html_sanitization() -> bool:
    """
    Test HTML sanitization.
    
    Returns:
        True if sanitization works, False otherwise
    """
    # Test with script tag
    unsafe_html = "<p>Normal text</p><script>alert('xss')</script><p>More text</p>"
    safe_html = sanitize_html(unsafe_html)
    if "<script>" in safe_html:
        print("HTML sanitization failed: script tag not removed")
        return False
        
    # Test with style tag
    unsafe_html = "<p>Normal text</p><style>body{background:red}</style><p>More text</p>"
    safe_html = sanitize_html(unsafe_html)
    if "<style>" in safe_html:
        print("HTML sanitization failed: style tag not removed")
        return False
        
    return True


def test_query_param_sanitization() -> bool:
    """
    Test query parameter sanitization.
    
    Returns:
        True if sanitization works, False otherwise
    """
    # Test SQL injection attack
    unsafe_param = "'; DROP TABLE users; --"
    safe_param = sanitize_query_param(unsafe_param)
    if "'" in safe_param or ";" in safe_param:
        print("Query parameter sanitization failed: SQL injection characters not removed")
        return False
        
    # Test XSS attack
    unsafe_param = "<script>alert('xss')</script>"
    safe_param = sanitize_query_param(unsafe_param)
    if "<script>" in safe_param:
        print("Query parameter sanitization failed: script tag not escaped")
        return False
        
    return True


def test_json_sanitization() -> bool:
    """
    Test JSON sanitization.
    
    Returns:
        True if sanitization works, False otherwise
    """
    # Test with nested XSS
    unsafe_json = {
        "name": "<script>alert('xss')</script>",
        "details": {
            "description": "<img src='x' onerror='alert(\"xss\")'>",
            "tags": ["normal", "<script>alert('nested')</script>"]
        }
    }
    
    safe_json = sanitize_json_input(unsafe_json)
    
    # Check that all nested elements are sanitized
    if "<script>" in safe_json["name"]:
        print("JSON sanitization failed: script tag not escaped in top level")
        return False
        
    if "<img" in safe_json["details"]["description"] and "onerror=" in safe_json["details"]["description"]:
        print("JSON sanitization failed: img onerror not escaped")
        return False
        
    if "<script>" in safe_json["details"]["tags"][1]:
        print("JSON sanitization failed: script tag not escaped in nested array")
        return False
        
    return True


def main() -> int:
    """
    Run all sanitization tests.
    
    Returns:
        0 for success, 1 for failure
    """
    tests = [
        test_html_sanitization,
        test_query_param_sanitization,
        test_json_sanitization
    ]
    
    for test in tests:
        try:
            if not test():
                return 1
        except Exception as e:
            print(f"Test {test.__name__} failed with exception: {e}")
            return 1
            
    print("All sanitization tests passed")
    return 0


if __name__ == "__main__":
    # HTML5lib is a required dependency for this module
    try:
        import html5lib
    except ImportError:
        print("html5lib is required for sanitization tests. Install with: pip install html5lib")
        sys.exit(1)
        
    sys.exit(main())