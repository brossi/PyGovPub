"""
Unit tests for the CLI output formatting and shell integration.
"""
import json
import os
import sys
import tempfile
from io import StringIO
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open

import pytest
from lxml import etree
from rich.console import Console

from pygovpub.cli.output import (
    output_json,
    output_xml,
    output_text,
    output_to_file,
    get_output_format,
    OutputFormat
)

# Helper function for mocking import errors
def raise_import_error(name, *args, **kwargs):
    if name == 'lxml':
        raise ImportError(f"No module named '{name}'")
    return __import__(name, *args, **kwargs)


class TestOutputFormatting:
    """Tests for output formatting functions."""

    def test_output_json(self):
        """Test JSON output formatting."""
        # Test data
        data = {"name": "test", "value": 42}
        
        # Mock console
        mock_console = MagicMock()
        
        # Call function
        with patch("pygovpub.cli.output.console", mock_console):
            output_json(data)
        
        # Verify console.print_json was called
        mock_console.print_json.assert_called_once()
        json_str = mock_console.print_json.call_args[0][0]
        
        # Verify JSON is valid and contains expected data
        parsed = json.loads(json_str)
        assert parsed["name"] == "test"
        assert parsed["value"] == 42
        
    def test_output_xml_with_lxml_import_error(self):
        """Test XML output formatting when lxml is not available."""
        # Test data
        data = {"name": "test", "value": 42}
        
        # Mock console
        mock_console = MagicMock()
        
        # Mock dicttoxml to return a predictable value
        mock_xml = b'<root><name>test</name><value>42</value></root>'
        
        # Test the import error case
        with patch("pygovpub.cli.output.console", mock_console):
            with patch("pygovpub.cli.output.dicttoxml.dicttoxml", return_value=mock_xml):
                # Mock the import behavior to raise ImportError when lxml is imported
                with patch("builtins.__import__", side_effect=lambda name, *args, **kwargs: 
                    raise_import_error(name, *args, **kwargs) if name == 'lxml' else 
                    __import__(name, *args, **kwargs)):
                    output_xml(data)
            
        # Verify console.print was called with raw XML
        mock_console.print.assert_called_once()
        xml_str = mock_console.print.call_args[0][0]
        assert xml_str == mock_xml.decode("utf-8")
        
    def test_output_text_simple_dict(self):
        """Test text output formatting with a simple dictionary."""
        # Test data - simple dict with no nested structures
        simple_data = {"name": "test", "value": 42, "active": True}
        
        # Mock console
        mock_console = MagicMock()
        
        # Mock Table for verification
        mock_table = MagicMock()
        
        with patch("pygovpub.cli.output.console", mock_console):
            with patch("pygovpub.cli.output.Table", return_value=mock_table) as mock_table_class:
                output_text(simple_data)
                
                # Verify Table was created correctly
                mock_table_class.assert_called_once_with(show_header=False, box=None)
                
                # Verify columns were added
                assert mock_table.add_column.call_count == 2
                
                # Verify rows were added for each item
                assert mock_table.add_row.call_count == 3
                
                # Verify console.print was called with the table
                mock_console.print.assert_called_once_with(mock_table)
    
    def test_output_text_with_list(self):
        """Test text output with a list."""
        # Test data with a list
        data_with_list = {"items": [1, 2, 3], "meta": {"count": 3}}
        
        # Mock console and Tree
        mock_console = MagicMock()
        mock_tree = MagicMock()
        mock_branch = MagicMock()
        
        # Make the tree return a branch when add is called
        mock_tree.add.return_value = mock_branch
        
        with patch("pygovpub.cli.output.console", mock_console):
            with patch("pygovpub.cli.output.Tree", return_value=mock_tree):
                output_text(data_with_list)
                
                # Verify console.print was called with the tree
                mock_console.print.assert_called_once_with(mock_tree)
                
                # Verify the tree was built with appropriate add calls
                assert mock_tree.add.call_count >= 1
    
    def test_output_to_file_xml_format(self):
        """Test writing XML output to a file."""
        # Create temp file path
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            file_path = tmp.name
        
        # Test data
        data = {"name": "test", "value": 42}
        
        try:
            # Mock console to avoid output during tests
            mock_console = MagicMock()
            
            # Test with lxml available
            with patch("pygovpub.cli.output.console", mock_console):
                with patch("builtins.open", mock_open()) as mock_file:
                    with patch("pygovpub.cli.output.dicttoxml.dicttoxml", return_value=b'<root><name>test</name></root>'):
                        # Mock from lxml import etree by patching xml module
                        mock_etree = MagicMock()
                        mock_etree.fromstring.return_value = MagicMock()
                        mock_etree.tostring.return_value = b'<root>\n  <name>test</name>\n</root>'
                        
                        # Use patch.object to specifically patch the modules and import behavior
                        with patch.object(sys.modules['pygovpub.cli.output'], 'etree', mock_etree, create=True):
                            output_to_file(data, file_path, OutputFormat.XML)
                        
                        # Verify formatted XML was written - the actual output has a trailing newline
                        handle = mock_file()
                        handle.write.assert_called_once_with('<root>\n  <name>test</name>\n</root>\n')
                
                # Reset the mock for the next test
                mock_file.reset_mock()
                
                # Test with lxml not available
                with patch("builtins.open", mock_open()) as mock_file:
                    with patch("pygovpub.cli.output.dicttoxml.dicttoxml", return_value=b'<root><name>test</name></root>'):
                        # Set up the try/except block to go to the except path
                        def mock_lxml_import(*args, **kwargs):
                            if args[0] == 'lxml':
                                raise ImportError("No module named 'lxml'")
                        
                        with patch('builtins.__import__', side_effect=mock_lxml_import):
                            output_to_file(data, file_path, OutputFormat.XML)
                        
                        # Verify raw XML was written - check for trailing newline
                        handle = mock_file()
                        handle.write.assert_called_once_with('<root><name>test</name></root>')
        finally:
            # Clean up
            if os.path.exists(file_path):
                os.unlink(file_path)
    
    def test_output_to_file_text_format(self):
        """Test writing text output to a file."""
        # Create temp file path
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            file_path = tmp.name
        
        try:
            # Mock console to avoid output during tests
            mock_console = MagicMock()
            
            # Test with complex nested data
            complex_data = {
                "name": "Test Data",
                "items": [
                    {"id": 1, "value": "first"},
                    {"id": 2, "value": "second"}
                ],
                "metadata": {
                    "count": 2,
                    "tags": ["test", "sample"]
                }
            }
            
            with patch("pygovpub.cli.output.console", mock_console):
                with patch("builtins.open", mock_open()) as mock_file:
                    output_to_file(complex_data, file_path, OutputFormat.TEXT)
                    
                    # Verify write was called multiple times
                    handle = mock_file()
                    assert handle.write.call_count > 5
                    
                    # Check some specific writes for dictionary
                    handle.write.assert_any_call("name: Test Data\n")
                    
                    # Check for nested dictionary writes
                    nested_calls = [call_args[0][0] for call_args in handle.write.call_args_list]
                    assert any("metadata:\n" in call for call in nested_calls)
                    
                    # Check for list handling
                    assert any("items:\n" in call for call in nested_calls)
                    assert any("  [0]:\n" in call for call in nested_calls)
        finally:
            # Clean up
            if os.path.exists(file_path):
                os.unlink(file_path)
    
    def test_output_xml(self):
        """Test XML output formatting."""
        # Test data
        data = {"name": "test", "value": 42}
        
        # Mock console
        mock_console = MagicMock()
        
        # Call function
        with patch("pygovpub.cli.output.console", mock_console):
            output_xml(data)
        
        # Verify console.print was called
        mock_console.print.assert_called_once()
        xml_str = mock_console.print.call_args[0][0]
        
        # Verify XML is valid
        try:
            # Parse XML and check structure
            root = etree.fromstring(xml_str)
            assert root.tag == "root"  # Root element should be "root"
            assert len(root) > 0  # Should have child elements
        except Exception as e:
            pytest.fail(f"Invalid XML: {e}")
    
    def test_output_text(self):
        """Test text output formatting."""
        # Test data
        data = {
            "name": "test", 
            "value": 42, 
            "nested": {"key1": "value1", "key2": "value2"}
        }
        
        # Mock console
        mock_console = MagicMock()
        
        # Mock Tree implementation because it gets built and then printed once
        mock_tree = MagicMock()
        
        # Call function
        with patch("pygovpub.cli.output.console", mock_console):
            with patch("pygovpub.cli.output.Tree", return_value=mock_tree):
                output_text(data)
        
        # Verify console.print was called with tree
        mock_console.print.assert_called_once_with(mock_tree)
        
        # Verify add was called multiple times on tree (recursively building tree)
        assert mock_tree.add.call_count > 0
    
    def test_output_to_file(self):
        """Test output to file."""
        # Test data
        data = {"name": "test", "value": 42}
        
        # Create temp file path
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            file_path = tmp.name
        
        try:
            # Mock json.dump to capture its arguments
            with patch("json.dump") as mock_json_dump:
                with patch("builtins.open", mock_open()) as mock_file:
                    output_to_file(data, file_path, OutputFormat.JSON)
                
                # Verify json.dump was called with the data and a file handle
                mock_json_dump.assert_called_once()
                assert mock_json_dump.call_args[0][0] == data  # First arg is data
            
            # Verify file was opened for writing
            mock_file.assert_called_once_with(file_path, "w", encoding="utf-8")
        finally:
            # Clean up temp file
            if os.path.exists(file_path):
                os.unlink(file_path)
    
    def test_get_output_format(self):
        """Test output format detection."""
        # Test with explicit format
        assert get_output_format("json") == OutputFormat.JSON
        assert get_output_format("xml") == OutputFormat.XML
        assert get_output_format("text") == OutputFormat.TEXT
        
        # Test with invalid format
        with pytest.raises(ValueError):
            get_output_format("invalid")
        
        # Test with None (should return default)
        assert get_output_format(None) == OutputFormat.TEXT
        
        # Test with file extension
        with patch("pygovpub.cli.output.Path") as mock_path:
            # Mock Path object to return .json suffix
            mock_path_instance = MagicMock()
            mock_path_instance.suffix = ".json"
            mock_path.return_value = mock_path_instance
            
            assert get_output_format(None, output_file="test.json") == OutputFormat.JSON
            
            # Mock Path object to return .xml suffix
            mock_path_instance.suffix = ".xml"
            mock_path.return_value = mock_path_instance
            
            assert get_output_format(None, output_file="test.xml") == OutputFormat.XML


class TestShellIntegration:
    """Tests for shell integration."""

    def test_environment_variable_handling(self):
        """Test environment variable handling."""
        # Import module so it can be tested and imported in other tests
        import pygovpub.cli.config
        
        # Test getting an environment variable
        with patch.dict(os.environ, {"PYGOVPUB_TEST": "test_value"}):
            assert pygovpub.cli.config.get_environment_value("PYGOVPUB_TEST") == "test_value"
            assert pygovpub.cli.config.get_environment_value("PYGOVPUB_NONEXISTENT") is None
        
        # Test setting an environment variable
        with patch.dict(os.environ, {}, clear=True):
            pygovpub.cli.config.set_environment_value("PYGOVPUB_TEST", "new_value")
            assert os.environ.get("PYGOVPUB_TEST") == "new_value"
    
    def test_config_file_handling(self):
        """Test config file handling."""
        # Import module for testing
        import pygovpub.cli.config
        
        # Mock config file content
        mock_config = {
            "api_keys": {
                "congress": "test_congress_key",
                "govinfo": "test_govinfo_key"
            },
            "options": {
                "default_format": "json",
                "cache_enabled": True
            }
        }
        
        # Test getting config file path
        with patch("pygovpub.cli.config.Path.home") as mock_home:
            mock_home.return_value = Path("/mock/home")
            assert pygovpub.cli.config.get_config_file_path() == Path("/mock/home/.pygovpub/config.json")
        
        # Test reading config file
        with patch("pygovpub.cli.config.get_config_file_path") as mock_path:
            mock_path.return_value = Path("/mock/config.json")
            # Mock the Path.exists method
            with patch("pathlib.Path.exists", return_value=True):
                with patch("builtins.open", mock_open(read_data=json.dumps(mock_config))):
                    config = pygovpub.cli.config.read_config_file()
                    assert config["api_keys"]["congress"] == "test_congress_key"
                    assert config["options"]["default_format"] == "json"
        
        # Test writing config file
        with patch("pygovpub.cli.config.get_config_file_path") as mock_path:
            mock_path.return_value = Path("/mock/config.json")
            # Mock json.dump to capture its arguments directly
            with patch("json.dump") as mock_json_dump:
                with patch("builtins.open", mock_open()) as mock_file:
                    # Mock makedirs to avoid attempting to create directories
                    with patch("os.makedirs"):
                        pygovpub.cli.config.write_config_file(mock_config)
                    
                    # Verify file was opened for writing
                    mock_file.assert_called_once_with(Path("/mock/config.json"), "w", encoding="utf-8")
                
                # Verify json.dump was called with the data
                mock_json_dump.assert_called_once()
                # First argument should be the config data
                assert mock_json_dump.call_args[0][0] == mock_config