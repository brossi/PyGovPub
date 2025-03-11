"""
Tests for validation sanitization.

This module tests the data sanitization utilities.
"""

import pytest
from unittest.mock import patch, MagicMock
import re
import html

from pygovpub.validation.test_sanitization import (
    sanitize_html, sanitize_query_param, sanitize_json_input,
    sanitize_value, test_html_sanitization, test_query_param_sanitization,
    test_json_sanitization, main
)


class TestHtmlSanitization:
    """Tests for HTML sanitization utilities."""
    
    @pytest.mark.skip(reason="Requires html5lib parser which may not be available in test environment")
    def test_sanitize_html_script_tags(self):
        """Test sanitizing HTML with script tags."""
        # Mock html5lib to simulate sanitization
        with patch('html5lib.parse') as mock_parse:
            with patch('html5lib.serialize') as mock_serialize:
                # Configure mocks
                mock_document = MagicMock()
                mock_parse.return_value = mock_document
                mock_document.findall.return_value = []
                mock_serialize.return_value = "<p>Normal text</p><p>More text</p>"
                
                # Call sanitize_html
                unsafe_html = "<p>Normal text</p><script>alert('xss')</script><p>More text</p>"
                result = sanitize_html(unsafe_html)
                
                # Verify result
                assert "<script>" not in result
                assert result == "<p>Normal text</p><p>More text</p>"


class TestQueryParamSanitization:
    """Tests for query parameter sanitization."""
    
    def test_sanitize_query_param_sql_injection(self):
        """Test sanitizing query parameter with SQL injection."""
        # SQL injection attempt
        unsafe_param = "'; DROP TABLE users; --"
        
        # Sanitize the parameter
        result = sanitize_query_param(unsafe_param)
        
        # Verify SQL injection characters are removed
        assert "'" not in result
        assert ";" not in result
        assert "DROP TABLE" in result  # Content is preserved
    
    def test_sanitize_query_param_xss(self):
        """Test sanitizing query parameter with XSS attack."""
        # XSS attack
        unsafe_param = "<script>alert('xss')</script>"
        
        # Sanitize the parameter
        result = sanitize_query_param(unsafe_param)
        
        # Verify HTML is escaped
        assert "<script>" not in result
        assert "&lt;script&gt;" in result  # HTML escaped


class TestJsonSanitization:
    """Tests for JSON sanitization."""
    
    def test_sanitize_json_input_nested(self):
        """Test sanitizing nested JSON with XSS attacks."""
        # JSON with nested XSS attacks
        unsafe_json = {
            "name": "<script>alert('xss')</script>",
            "details": {
                "description": "<img src='x' onerror='alert(\"xss\")'>",
                "tags": ["normal", "<script>alert('nested')</script>"]
            }
        }
        
        # Sanitize the JSON
        result = sanitize_json_input(unsafe_json)
        
        # Verify all nested elements are sanitized
        assert "<script>" not in result["name"]
        assert "&lt;script&gt;" in result["name"]
        
        assert "<img" not in result["details"]["description"]
        assert "&lt;img" in result["details"]["description"]
        
        assert "<script>" not in result["details"]["tags"][1]
        assert "&lt;script&gt;" in result["details"]["tags"][1]
    
    def test_sanitize_json_input_mixed_types(self):
        """Test sanitizing JSON with mixed data types."""
        # JSON with mixed types
        mixed_json = {
            "string": "<b>bold</b>",
            "number": 123,
            "boolean": True,
            "null": None,
            "array": [1, 2, "<script>alert('xss')</script>"]
        }
        
        # Sanitize the JSON
        result = sanitize_json_input(mixed_json)
        
        # Verify only strings are sanitized
        assert "&lt;b&gt;" in result["string"]
        assert result["number"] == 123
        assert result["boolean"] is True
        assert result["null"] is None
        assert result["array"][0] == 1
        assert result["array"][1] == 2
        assert "&lt;script&gt;" in result["array"][2]


class TestValueSanitization:
    """Tests for individual value sanitization."""
    
    def test_sanitize_value_string(self):
        """Test sanitizing a string value."""
        # String with HTML
        value = "<b>text</b>"
        
        # Sanitize the value
        result = sanitize_value(value)
        
        # Verify HTML is escaped
        assert result == "&lt;b&gt;text&lt;/b&gt;"
    
    def test_sanitize_value_nonstring(self):
        """Test sanitizing non-string values."""
        # Non-string values
        values = [123, True, None, 45.67]
        
        # Sanitize each value
        results = [sanitize_value(v) for v in values]
        
        # Verify non-string values are unchanged
        assert results == values


class TestSanitizationTests:
    """Tests for the test functions themselves."""
    
    def test_html_sanitization_test(self):
        """Test the HTML sanitization test function."""
        # Mock sanitize_html to simulate success
        with patch('pygovpub.validation.test_sanitization.sanitize_html') as mock_sanitize:
            mock_sanitize.return_value = "<p>Normal text</p><p>More text</p>"
            
            # Call the test function
            result = test_html_sanitization()
            
            # Verify the test passes
            assert result is True
    
    def test_query_param_sanitization_test(self):
        """Test the query parameter sanitization test function."""
        # Mock sanitize_query_param to return safe output
        with patch('pygovpub.validation.test_sanitization.sanitize_query_param') as mock_sanitize:
            mock_sanitize.return_value = "DROP TABLE users  "  # Safe version, no SQL chars
            
            # Call the test function
            result = test_query_param_sanitization()
            
            # Verify the test passes
            assert result is True
    
    def test_json_sanitization_test(self):
        """Test the JSON sanitization test function."""
        # Mock sanitize_json_input to return sanitized JSON
        with patch('pygovpub.validation.test_sanitization.sanitize_json_input') as mock_sanitize:
            mock_sanitize.return_value = {
                "name": "&lt;script&gt;alert('xss')&lt;/script&gt;",
                "details": {
                    "description": "&lt;img src='x' onerror='alert(\"xss\")'&gt;",
                    "tags": ["normal", "&lt;script&gt;alert('nested')&lt;/script&gt;"]
                }
            }
            
            # Call the test function
            result = test_json_sanitization()
            
            # Verify the test passes
            assert result is True


class TestMainFunction:
    """Tests for the main sanitization function."""
    
    def test_main_success(self):
        """Test main function with successful tests."""
        # Mock all test functions to return True
        with patch('pygovpub.validation.test_sanitization.test_html_sanitization', return_value=True):
            with patch('pygovpub.validation.test_sanitization.test_query_param_sanitization', return_value=True):
                with patch('pygovpub.validation.test_sanitization.test_json_sanitization', return_value=True):
                    with patch('builtins.print') as mock_print:
                        # Call main function
                        result = main()
                        
                        # Verify success
                        assert result == 0
                        mock_print.assert_called_with("All sanitization tests passed")
    
    def test_main_html_test_failure(self):
        """Test main function with HTML test failure."""
        # Mock test_html_sanitization to fail
        with patch('pygovpub.validation.test_sanitization.test_html_sanitization', return_value=False):
            # Call main function
            result = main()
            
            # Verify failure
            assert result == 1
    
    def test_main_query_param_test_failure(self):
        """Test main function with query parameter test failure."""
        # Mock test_html_sanitization to succeed but test_query_param_sanitization to fail
        with patch('pygovpub.validation.test_sanitization.test_html_sanitization', return_value=True):
            with patch('pygovpub.validation.test_sanitization.test_query_param_sanitization', return_value=False):
                # Call main function
                result = main()
                
                # Verify failure
                assert result == 1
    
    def test_main_json_test_failure(self):
        """Test main function with JSON test failure."""
        # Mock first two tests to succeed but test_json_sanitization to fail
        with patch('pygovpub.validation.test_sanitization.test_html_sanitization', return_value=True):
            with patch('pygovpub.validation.test_sanitization.test_query_param_sanitization', return_value=True):
                with patch('pygovpub.validation.test_sanitization.test_json_sanitization', return_value=False):
                    # Call main function
                    result = main()
                    
                    # Verify failure
                    assert result == 1
    
    def test_main_exception_handling(self):
        """Test main function with exception in test."""
        # Mock test_html_sanitization to raise exception
        with patch('pygovpub.validation.test_sanitization.test_html_sanitization') as mock_test:
            mock_test.side_effect = Exception("Test failure")
            with patch('builtins.print') as mock_print:
                # Call main function
                result = main()
                
                # Verify failure
                assert result == 1
                # Check that error message was printed
                mock_print.assert_called_with("Test test_html_sanitization failed with exception: Test failure")