"""
Unit tests for the CLI configuration module.
"""
import json
import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open, call

from pygovpub.cli.config import (
    DEFAULT_CONFIG,
    ENV_PREFIX,
    get_environment_value,
    set_environment_value,
    get_config_file_path,
    read_config_file,
    write_config_file,
    get_config_value,
    set_config_value,
    list_config,
    check_required_config
)


class TestConfigFunctions:
    """Tests for configuration functions."""

    def test_default_config(self):
        """Test default configuration values."""
        assert "api_keys" in DEFAULT_CONFIG
        assert "congress" in DEFAULT_CONFIG["api_keys"]
        assert "govinfo" in DEFAULT_CONFIG["api_keys"]
        
        assert "options" in DEFAULT_CONFIG
        assert "default_format" in DEFAULT_CONFIG["options"]
        assert "cache_enabled" in DEFAULT_CONFIG["options"]
        assert "cache_ttl" in DEFAULT_CONFIG["options"]

    def test_environment_variables(self):
        """Test environment variable handling."""
        # Test getting an environment variable
        with patch.dict(os.environ, {"PYGOVPUB_TEST": "test_value"}):
            assert get_environment_value("PYGOVPUB_TEST") == "test_value"
            assert get_environment_value("PYGOVPUB_NONEXISTENT") is None
        
        # Test setting an environment variable
        with patch.dict(os.environ, {}, clear=True):
            set_environment_value("PYGOVPUB_TEST", "new_value")
            assert os.environ.get("PYGOVPUB_TEST") == "new_value"

    def test_config_file_path_with_xdg(self):
        """Test getting config file path with XDG_CONFIG_HOME."""
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": "/mock/xdg/config"}):
            assert get_config_file_path() == Path("/mock/xdg/config/pygovpub/config.json")

    def test_config_file_path_without_xdg(self):
        """Test getting config file path without XDG_CONFIG_HOME."""
        # Mock os.environ.get to return None for XDG_CONFIG_HOME
        with patch.dict(os.environ, {}, clear=True):
            with patch("pathlib.Path.home") as mock_home:
                mock_home.return_value = Path("/mock/home")
                assert get_config_file_path() == Path("/mock/home/.pygovpub/config.json")

    def test_read_config_file_exists(self):
        """Test reading config file when it exists."""
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
        
        with patch("pygovpub.cli.config.get_config_file_path") as mock_path:
            mock_path.return_value = Path("/mock/config.json")
            # Mock the Path.exists method
            with patch("pathlib.Path.exists", return_value=True):
                with patch("builtins.open", mock_open(read_data=json.dumps(mock_config))):
                    config = read_config_file()
                    assert config["api_keys"]["congress"] == "test_congress_key"
                    assert config["options"]["default_format"] == "json"
                    # Verify default key is added if missing
                    assert "cache_ttl" in config["options"]
                    assert config["options"]["cache_ttl"] == DEFAULT_CONFIG["options"]["cache_ttl"]

    def test_read_config_file_not_exists(self):
        """Test reading config file when it doesn't exist."""
        with patch("pygovpub.cli.config.get_config_file_path") as mock_path:
            mock_path.return_value = Path("/mock/config.json")
            # Mock the Path.exists method
            with patch("pathlib.Path.exists", return_value=False):
                config = read_config_file()
                # Should return a copy of DEFAULT_CONFIG
                assert config == DEFAULT_CONFIG
                assert config is not DEFAULT_CONFIG  # Should be a copy

    def test_read_config_file_exception(self):
        """Test reading config file when there's an exception."""
        with patch("pygovpub.cli.config.get_config_file_path") as mock_path:
            mock_path.return_value = Path("/mock/config.json")
            # Mock the Path.exists method
            with patch("pathlib.Path.exists", return_value=True):
                # Mock open to raise an exception
                with patch("builtins.open", side_effect=Exception("Test error")):
                    with patch("pygovpub.cli.config.console.print") as mock_print:
                        config = read_config_file()
                        # Should print an error message
                        mock_print.assert_called_once()
                        assert "Error reading" in mock_print.call_args[0][0]
                        # Should return a copy of DEFAULT_CONFIG
                        assert config == DEFAULT_CONFIG
                        assert config is not DEFAULT_CONFIG  # Should be a copy

    def test_write_config_file_success(self):
        """Test writing config file (successful)."""
        mock_config = {
            "api_keys": {
                "congress": "test_congress_key"
            }
        }
        
        with patch("pygovpub.cli.config.get_config_file_path") as mock_path:
            mock_path.return_value = Path("/mock/config.json")
            # Mock os.makedirs to avoid attempting to create directories
            with patch("os.makedirs") as mock_makedirs:
                # Mock json.dump to capture its arguments directly
                with patch("json.dump") as mock_json_dump:
                    with patch("builtins.open", mock_open()) as mock_file:
                        write_config_file(mock_config)
                        
                        # Verify os.makedirs was called with the parent directory
                        mock_makedirs.assert_called_once_with(Path("/mock/config.json").parent, exist_ok=True)
                        
                        # Verify file was opened for writing
                        mock_file.assert_called_once_with(Path("/mock/config.json"), "w", encoding="utf-8")
                        
                        # Verify json.dump was called with the data
                        mock_json_dump.assert_called_once()
                        # First argument should be the config data
                        assert mock_json_dump.call_args[0][0] == mock_config

    def test_write_config_file_exception(self):
        """Test writing config file when there's an exception."""
        mock_config = {"test": "value"}
        
        with patch("pygovpub.cli.config.get_config_file_path") as mock_path:
            mock_path.return_value = Path("/mock/config.json")
            # Mock os.makedirs to avoid attempting to create directories
            with patch("os.makedirs"):
                # Mock open to raise an exception
                with patch("builtins.open", side_effect=Exception("Test error")):
                    with patch("pygovpub.cli.config.console.print") as mock_print:
                        write_config_file(mock_config)
                        # Should print an error message
                        mock_print.assert_called_once()
                        assert "Error writing" in mock_print.call_args[0][0]

    def test_get_config_value_from_env(self):
        """Test getting config value from environment."""
        # Test with environment variable
        with patch.dict(os.environ, {"PYGOVPUB_API_KEYS_CONGRESS": "env_congress_key"}):
            assert get_config_value("api_keys.congress") == "env_congress_key"

    def test_get_config_value_from_file(self):
        """Test getting config value from file."""
        # Mock config file
        mock_config = {
            "api_keys": {
                "congress": "file_congress_key"
            }
        }
        
        # No environment variable, should read from file
        with patch.dict(os.environ, {}, clear=True):
            with patch("pygovpub.cli.config.read_config_file", return_value=mock_config):
                assert get_config_value("api_keys.congress") == "file_congress_key"

    def test_get_config_value_invalid_key(self):
        """Test getting config value with invalid key."""
        with pytest.raises(ValueError) as excinfo:
            get_config_value("invalid_key")
        assert "Invalid config key" in str(excinfo.value)

    def test_get_config_value_missing_section(self):
        """Test getting config value with missing section."""
        mock_config = {"api_keys": {}}
        
        with patch.dict(os.environ, {}, clear=True):
            with patch("pygovpub.cli.config.read_config_file", return_value=mock_config):
                assert get_config_value("nonexistent.key") is None

    def test_get_config_value_missing_key(self):
        """Test getting config value with missing key."""
        mock_config = {"api_keys": {}}
        
        with patch.dict(os.environ, {}, clear=True):
            with patch("pygovpub.cli.config.read_config_file", return_value=mock_config):
                assert get_config_value("api_keys.nonexistent") is None

    def test_set_config_value_success(self):
        """Test setting config value (successful)."""
        mock_config = {
            "api_keys": {
                "congress": "old_value"
            }
        }
        
        with patch("pygovpub.cli.config.read_config_file", return_value=mock_config):
            with patch("pygovpub.cli.config.write_config_file") as mock_write:
                set_config_value("api_keys.congress", "new_value")
                
                # Should call write_config_file with updated config
                mock_write.assert_called_once()
                updated_config = mock_write.call_args[0][0]
                assert updated_config["api_keys"]["congress"] == "new_value"

    def test_set_config_value_new_section(self):
        """Test setting config value with new section."""
        mock_config = {"api_keys": {}}
        
        with patch("pygovpub.cli.config.read_config_file", return_value=mock_config):
            with patch("pygovpub.cli.config.write_config_file") as mock_write:
                set_config_value("new_section.key", "value")
                
                # Should call write_config_file with updated config
                mock_write.assert_called_once()
                updated_config = mock_write.call_args[0][0]
                assert "new_section" in updated_config
                assert updated_config["new_section"]["key"] == "value"

    def test_set_config_value_invalid_key(self):
        """Test setting config value with invalid key."""
        with pytest.raises(ValueError) as excinfo:
            set_config_value("invalid_key", "value")
        assert "Invalid config key" in str(excinfo.value)

    def test_list_config(self):
        """Test listing config values."""
        mock_config = {
            "api_keys": {
                "congress": "congress_key",
                "govinfo": "govinfo_key"
            },
            "options": {
                "default_format": "json"
            }
        }
        
        with patch("pygovpub.cli.config.read_config_file", return_value=mock_config):
            # Mock environment override for one value
            with patch.dict(os.environ, {"PYGOVPUB_API_KEYS_CONGRESS": "env_congress_key"}):
                with patch("pygovpub.cli.config.console.print") as mock_print:
                    list_config()
                    
                    # Should call console.print
                    mock_print.assert_called_once()
                    
                    # Verify table was created and passed to print
                    table = mock_print.call_args[0][0]
                    assert hasattr(table, "add_row")  # Should be a table object

    def test_check_required_config_all_present(self):
        """Test checking required config when all values are present."""
        # Mock get_config_value to return non-empty values
        with patch("pygovpub.cli.config.get_config_value", return_value="value"):
            missing = check_required_config()
            assert len(missing) == 0

    def test_check_required_config_missing(self):
        """Test checking required config when values are missing."""
        # Mock get_config_value to handle different keys
        def mock_get_value(key):
            if key == "api_keys.congress":
                return "value"
            else:
                return ""
        
        with patch("pygovpub.cli.config.get_config_value", side_effect=mock_get_value):
            missing = check_required_config()
            assert len(missing) == 1
            assert missing[0] == "api_keys.govinfo"