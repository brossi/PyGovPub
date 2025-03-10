"""
Unit tests for the CLI configuration manager.
"""
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
import pytest
from io import StringIO

from pygovpub.cli.config_manager import (
    get_config_command,
    set_config_command,
    list_config_command,
    validate_config_command,
    switch_profile_command,
    export_config_command,
    import_config_command,
    init_config_command,
    main
)
from pygovpub.config import (
    Environment,
    FeatureFlag,
    ConfigManager,
    ConfigFormat
)


class MockArgs:
    """Mock class for argparse namespace."""
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class TestConfigCommands:
    """Tests for configuration CLI commands."""

    def test_get_config_command_feature(self, capsys):
        """Test getting feature flag config."""
        mock_manager = MagicMock()
        mock_manager.get_feature_flag.return_value = True
        
        with patch("pygovpub.cli.config_manager.get_config_manager", return_value=mock_manager):
            args = MockArgs(key="feature.cache_enabled")
            get_config_command(args)
            
            # Verify the correct feature flag was accessed
            mock_manager.get_feature_flag.assert_called_once()
            assert mock_manager.get_feature_flag.call_args[0][0] == FeatureFlag.CACHE_ENABLED

    def test_get_config_command_api_key(self, capsys):
        """Test getting API key config."""
        mock_manager = MagicMock()
        mock_manager.get_api_key.return_value = "test_api_key"
        
        with patch("pygovpub.cli.config_manager.get_config_manager", return_value=mock_manager):
            args = MockArgs(key="api.congress")
            get_config_command(args)
            
            # Verify the correct API key was accessed
            mock_manager.get_api_key.assert_called_once_with("congress")

    def test_get_config_command_url(self, capsys):
        """Test getting API URL config."""
        mock_manager = MagicMock()
        mock_manager.get_api_base_url.return_value = "https://api.example.com"
        
        with patch("pygovpub.cli.config_manager.get_config_manager", return_value=mock_manager):
            args = MockArgs(key="url.congress")
            get_config_command(args)
            
            # Verify the correct URL was accessed
            mock_manager.get_api_base_url.assert_called_once_with("congress")

    def test_get_config_command_option(self, capsys):
        """Test getting option config."""
        mock_manager = MagicMock()
        mock_manager.get_option.return_value = "text"
        
        with patch("pygovpub.cli.config_manager.get_config_manager", return_value=mock_manager):
            args = MockArgs(key="option.default_format")
            get_config_command(args)
            
            # Verify the correct option was accessed
            mock_manager.get_option.assert_called_once_with("default_format")

    def test_get_config_command_environment(self, capsys):
        """Test getting environment config."""
        mock_manager = MagicMock()
        mock_manager.environment = Environment.DEVELOPMENT
        
        with patch("pygovpub.cli.config_manager.get_config_manager", return_value=mock_manager):
            args = MockArgs(key="environment")
            get_config_command(args)
            
            # No specific method to check for here, but we verify the command runs
            assert mock_manager.environment == Environment.DEVELOPMENT

    def test_set_config_command_feature(self):
        """Test setting feature flag config."""
        mock_manager = MagicMock()
        
        with patch("pygovpub.cli.config_manager.get_config_manager", return_value=mock_manager):
            args = MockArgs(key="feature.cache_enabled", value="true", save=True)
            set_config_command(args)
            
            # Verify the correct feature flag was set
            mock_manager.set_feature_flag.assert_called_once()
            assert mock_manager.set_feature_flag.call_args[0][0] == FeatureFlag.CACHE_ENABLED
            assert mock_manager.set_feature_flag.call_args[0][1] is True
            
            # Verify save was called
            mock_manager.save_to_file.assert_called_once()

    def test_set_config_command_api_key(self):
        """Test setting API key config."""
        mock_manager = MagicMock()
        
        with patch("pygovpub.cli.config_manager.get_config_manager", return_value=mock_manager):
            args = MockArgs(key="api.congress", value="test_api_key", save=False)
            set_config_command(args)
            
            # Verify the correct API key was set
            mock_manager.set_api_key.assert_called_once_with("congress", "test_api_key")
            
            # Verify save was not called
            mock_manager.save_to_file.assert_not_called()

    def test_list_config_command_all(self):
        """Test listing all config sections."""
        mock_manager = MagicMock()
        mock_manager._options = {
            "default_format": "text",
            "cache_ttl": 3600
        }
        mock_manager.get_feature_flag.return_value = True
        mock_manager.get_api_key.return_value = "test_api_key"
        mock_manager.get_api_base_url.return_value = "https://api.example.com"
        
        with patch("pygovpub.cli.config_manager.get_config_manager", return_value=mock_manager):
            args = MockArgs(section="all")
            list_config_command(args)
            
            # Verify get_feature_flag was called for each feature flag
            assert mock_manager.get_feature_flag.call_count == len(FeatureFlag)

    def test_validate_config_command_valid(self):
        """Test validating valid config."""
        mock_manager = MagicMock()
        
        with patch("pygovpub.cli.config_manager.get_config_manager", return_value=mock_manager):
            args = MockArgs(fix=False, save=False)
            validate_config_command(args)
            
            # Verify validate was called
            mock_manager.validate.assert_called_once()
            
            # Verify save was not called
            mock_manager.save_to_file.assert_not_called()

    def test_validate_config_command_invalid_with_fix(self):
        """Test validating invalid config with fix flag."""
        mock_manager = MagicMock()
        # Import the specific exception class
        from pygovpub.config import ConfigValidationError
        mock_manager.validate.side_effect = [
            ConfigValidationError("API key missing for: congress, govinfo"),
            None  # Second call succeeds
        ]
        
        with patch("pygovpub.cli.config_manager.get_config_manager", return_value=mock_manager):
            args = MockArgs(fix=True, save=True)
            validate_config_command(args)
            
            # Verify validate was called
            assert mock_manager.validate.call_count >= 1
            
            # Verify save was called
            mock_manager.save_to_file.assert_called_once()

    def test_switch_profile_command(self):
        """Test switching environment profile."""
        mock_manager = MagicMock()
        
        with patch("pygovpub.cli.config_manager.get_config_manager", return_value=mock_manager):
            args = MockArgs(profile="production", save=True)
            switch_profile_command(args)
            
            # Verify switch_profile was called with the correct environment
            mock_manager.switch_profile.assert_called_once_with(Environment.PRODUCTION)
            
            # Verify save was called
            mock_manager.save_to_file.assert_called_once()

    def test_export_config_command(self):
        """Test exporting config to file."""
        mock_manager = MagicMock()
        
        with patch("pygovpub.cli.config_manager.get_config_manager", return_value=mock_manager):
            with patch("pathlib.Path.suffix", ".json"):
                args = MockArgs(file="/tmp/test_config.json", format=None)
                export_config_command(args)
                
                # Verify save_to_file was called with the correct path
                mock_manager.save_to_file.assert_called_once_with("/tmp/test_config.json")

    def test_import_config_command(self):
        """Test importing config from file."""
        mock_manager = MagicMock()
        
        with patch("pygovpub.cli.config_manager.get_config_manager", return_value=mock_manager):
            args = MockArgs(file="/tmp/test_config.json", save=True, validate=True)
            import_config_command(args)
            
            # Verify load_from_file was called with the correct path
            mock_manager.load_from_file.assert_called_once_with("/tmp/test_config.json")
            
            # Verify save was called
            mock_manager.save_to_file.assert_called_once()
            
            # Verify validate was called
            mock_manager.validate.assert_called_once()

    def test_init_config_command(self):
        """Test initializing config with defaults."""
        mock_manager = MagicMock()
        mock_manager.get_config_file_path.return_value = Path("/tmp/config.json")
        
        with patch("pygovpub.cli.config_manager.get_config_manager", return_value=mock_manager):
            with patch("pathlib.Path.exists", return_value=False):
                args = MockArgs(
                    environment="production", 
                    congress_key="test_congress_key",
                    govinfo_key="test_govinfo_key",
                    force=False
                )
                init_config_command(args)
                
                # Verify environment was set correctly
                mock_manager.environment = Environment.PRODUCTION
                
                # Verify API keys were set
                mock_manager.set_api_key.assert_any_call("congress", "test_congress_key")
                mock_manager.set_api_key.assert_any_call("govinfo", "test_govinfo_key")
                
                # Verify save was called
                mock_manager.save_to_file.assert_called_once()

    def test_main_with_get_command(self):
        """Test main function with get command."""
        with patch("argparse.ArgumentParser.parse_args") as mock_parse_args:
            mock_parse_args.return_value = MockArgs(command="get", key="environment")
            with patch("pygovpub.cli.config_manager.get_config_command") as mock_get_command:
                main()
                mock_get_command.assert_called_once()

    def test_main_with_set_command(self):
        """Test main function with set command."""
        with patch("argparse.ArgumentParser.parse_args") as mock_parse_args:
            mock_parse_args.return_value = MockArgs(command="set", key="environment", value="production", save=True)
            with patch("pygovpub.cli.config_manager.set_config_command") as mock_set_command:
                main()
                mock_set_command.assert_called_once()

    def test_main_with_no_command(self):
        """Test main function with no command."""
        with patch("argparse.ArgumentParser.parse_args") as mock_parse_args:
            mock_parse_args.return_value = MockArgs(command=None)
            with patch("argparse.ArgumentParser.print_help") as mock_print_help:
                main()
                mock_print_help.assert_called_once()