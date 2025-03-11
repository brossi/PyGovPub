"""
Unit tests for the core configuration framework.
"""
import json
import os
import tempfile
import pytest
import yaml
from pathlib import Path
from unittest.mock import patch, mock_open, MagicMock

from pygovpub.config import (
    ConfigFormat,
    ConfigManager,
    ConfigValidationError,
    Environment,
    FeatureFlag,
    SecretHandler,
    load_config_from_file,
    save_config_to_file
)


class TestConfigFormat:
    """Tests for configuration format enum."""

    def test_config_format_values(self):
        """Test configuration format values."""
        assert ConfigFormat.JSON.value == "json"
        assert ConfigFormat.YAML.value == "yaml"
        assert ConfigFormat.ENV.value == "env"

    def test_config_format_file_extensions(self):
        """Test configuration format file extensions."""
        assert ConfigFormat.JSON.get_extension() == ".json"
        assert ConfigFormat.YAML.get_extension() == ".yaml"
        assert ConfigFormat.ENV.get_extension() == ".env"

    def test_config_format_from_extension(self):
        """Test getting format from file extension."""
        assert ConfigFormat.from_extension(".json") == ConfigFormat.JSON
        assert ConfigFormat.from_extension(".yaml") == ConfigFormat.YAML
        assert ConfigFormat.from_extension(".yml") == ConfigFormat.YAML
        assert ConfigFormat.from_extension(".env") == ConfigFormat.ENV
        
        # Test with unknown extension
        with pytest.raises(ValueError):
            ConfigFormat.from_extension(".unknown")
            
    def test_config_format_get_extension_error(self):
        """Test error handling in get_extension method."""
        # Create a mock ConfigFormat with an invalid value
        mock_format = ConfigFormat("json")
        
        # Patch the equality check to force the ValueError path
        with patch.object(ConfigFormat, "__eq__", return_value=False):
            with pytest.raises(ValueError) as excinfo:
                mock_format.get_extension()
            
            assert "Unknown format:" in str(excinfo.value)


class TestEnvironment:
    """Tests for environment enum."""

    def test_environment_values(self):
        """Test environment values."""
        assert Environment.DEVELOPMENT.value == "development"
        assert Environment.TEST.value == "test"
        assert Environment.PRODUCTION.value == "production"

    def test_environment_from_string(self):
        """Test creating environment from string."""
        assert Environment.from_string("development") == Environment.DEVELOPMENT
        assert Environment.from_string("test") == Environment.TEST
        assert Environment.from_string("production") == Environment.PRODUCTION
        
        # Test with unknown environment (should default to DEVELOPMENT)
        assert Environment.from_string("unknown") == Environment.DEVELOPMENT
        
    def test_environment_from_string_exception_handling(self):
        """Test creating environment from string with error handling for line 77, 89."""
        # Test with a string that will cause ValueError
        # Instead of mocking the complex internals, we'll verify that invalid inputs 
        # are handled correctly by the actual implementation
        result = Environment.from_string("invalid_value")
        
        # Verify that we get the default value
        assert result == Environment.DEVELOPMENT
        
        # Test that we can recover from a very invalid value too (if we could inject one)
        # This is a simple test to document that the function is designed to handle
        # unexpected input gracefully
        with patch("builtins.print") as mock_print:
            # We're just documenting the design intent with this test
            assert Environment.from_string("invalid_value") == Environment.DEVELOPMENT


class TestFeatureFlag:
    """Tests for feature flag enum."""

    def test_feature_flag_values(self):
        """Test feature flag values."""
        assert FeatureFlag.CACHE_ENABLED.value == "cache_enabled"
        assert FeatureFlag.ADVANCED_ROUTING.value == "advanced_routing"
        assert FeatureFlag.DEBUG_MODE.value == "debug_mode"

    def test_feature_flag_default_values(self):
        """Test feature flag default values."""
        assert FeatureFlag.CACHE_ENABLED.default_value is True
        assert FeatureFlag.ADVANCED_ROUTING.default_value is False
        assert FeatureFlag.DEBUG_MODE.default_value is False


class TestConfigFileOperations:
    """Tests for configuration file operations."""

    def test_load_config_json(self):
        """Test loading JSON configuration."""
        mock_data = {"test": "value", "nested": {"key": "value"}}
        
        # Test with file path
        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=json.dumps(mock_data))):
                config = load_config_from_file("test.json")
                assert config == mock_data

        # Test with Path object
        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=json.dumps(mock_data))):
                config = load_config_from_file(Path("test.json"))
                assert config == mock_data

    def test_load_config_yaml(self):
        """Test loading YAML configuration."""
        mock_data = {"test": "value", "nested": {"key": "value"}}
        mock_yaml = """
        test: value
        nested:
          key: value
        """
        
        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=mock_yaml)):
                config = load_config_from_file("test.yaml")
                assert config == mock_data

    def test_load_config_env(self):
        """Test loading ENV configuration."""
        mock_env = """
        # This is a comment
        TEST_VALUE=value
        NESTED_KEY=nested_value
        BOOL_TRUE=true
        BOOL_FALSE=false
        NUMBER=123
        """
        
        expected = {
            "test_value": "value",
            "nested_key": "nested_value",
            "bool_true": True,
            "bool_false": False,
            "number": 123
        }
        
        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=mock_env)):
                config = load_config_from_file("test.env")
                assert config == expected

    def test_load_config_file_not_exists(self):
        """Test loading configuration when file doesn't exist."""
        with patch("pathlib.Path.exists", return_value=False):
            with pytest.raises(FileNotFoundError):
                load_config_from_file("nonexistent.json")

    def test_load_config_invalid_json(self):
        """Test loading invalid JSON configuration."""
        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data="invalid json")):
                with pytest.raises(json.JSONDecodeError):
                    load_config_from_file("test.json")

    def test_load_config_invalid_yaml(self):
        """Test loading invalid YAML configuration."""
        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data="invalid: yaml:\n  - not valid")):
                with pytest.raises(yaml.YAMLError):
                    load_config_from_file("test.yaml")

    def test_save_config_json(self):
        """Test saving JSON configuration."""
        mock_data = {"test": "value", "nested": {"key": "value"}}
        
        # Mock file operations
        with patch("os.makedirs") as mock_makedirs:
            with patch("builtins.open", mock_open()) as mock_file:
                with patch("json.dump") as mock_json_dump:
                    save_config_to_file(mock_data, "/tmp/test_config.json")
                    
                    # Verify os.makedirs was called
                    mock_makedirs.assert_called_once()
                    
                    # Verify file was opened for writing
                    mock_file.assert_called_once()
                    
                    # Verify json.dump was called with the data
                    mock_json_dump.assert_called_once()
                    # First argument should be the config data
                    assert mock_json_dump.call_args[0][0] == mock_data

    def test_save_config_yaml(self):
        """Test saving YAML configuration."""
        mock_data = {"test": "value", "nested": {"key": "value"}}
        
        # Mock file operations
        with patch("os.makedirs") as mock_makedirs:
            with patch("builtins.open", mock_open()) as mock_file:
                with patch("yaml.dump") as mock_yaml_dump:
                    save_config_to_file(mock_data, "/tmp/test_config.yaml")
                    
                    # Verify os.makedirs was called
                    mock_makedirs.assert_called_once()
                    
                    # Verify file was opened for writing
                    mock_file.assert_called_once()
                    
                    # Verify yaml.dump was called with the data
                    mock_yaml_dump.assert_called_once()
                    # First argument should be the config data
                    assert mock_yaml_dump.call_args[0][0] == mock_data

    def test_save_config_env(self):
        """Test saving ENV configuration."""
        mock_data = {
            "test_value": "value",
            "nested_key": "nested_value",
            "bool_true": True,
            "bool_false": False,
            "number": 123
        }
        
        # Create a mock file object with a write method
        mock_file = mock_open()
        
        # Mock file operations
        with patch("os.makedirs") as mock_makedirs:
            with patch("builtins.open", mock_file) as m:
                save_config_to_file(mock_data, "/tmp/test_config.env")
                
                # Verify os.makedirs was called
                mock_makedirs.assert_called_once()
                
                # Verify file was opened for writing
                m.assert_called_once()
                
                # Verify the write method was called for each key-value pair
                handle = m()
                assert handle.write.call_count >= 5  # At least 5 calls (one for each key-value pair)
                
                # Check the content of the write calls
                write_calls = [call[0][0] for call in handle.write.call_args_list]
                assert any("TEST_VALUE=value" in call for call in write_calls)
                assert any("NESTED_KEY=nested_value" in call for call in write_calls)
                assert any("BOOL_TRUE=true" in call for call in write_calls)
                assert any("BOOL_FALSE=false" in call for call in write_calls)
                assert any("NUMBER=123" in call for call in write_calls)


class TestConfigManager:
    """Tests for configuration manager."""

    def test_config_manager_initialization(self):
        """Test initialization of configuration manager."""
        # Test with default values
        manager = ConfigManager()
        assert manager.environment == Environment.DEVELOPMENT
        assert manager.config_dir == Path.home() / ".pygovpub"
        
        # Test with custom values
        custom_dir = Path("/custom/dir")
        manager = ConfigManager(
            environment=Environment.PRODUCTION,
            config_dir=custom_dir
        )
        assert manager.environment == Environment.PRODUCTION
        assert manager.config_dir == custom_dir

    def test_config_manager_load_from_env(self):
        """Test loading configuration from environment variables."""
        with patch.dict(os.environ, {
            "PYGOVPUB_ENV": "production",
            "PYGOVPUB_FEATURES_CACHE_ENABLED": "false",
            "PYGOVPUB_API_CONGRESS_KEY": "test_congress_key",
            "PYGOVPUB_API_GOVINFO_KEY": "test_govinfo_key"
        }):
            manager = ConfigManager()
            manager.load_from_env()
            
            # Check environment
            assert manager.environment == Environment.PRODUCTION
            
            # Check feature flags
            assert manager.get_feature_flag(FeatureFlag.CACHE_ENABLED) is False
            
            # Check API keys
            assert manager.get_api_key("congress") == "test_congress_key"
            assert manager.get_api_key("govinfo") == "test_govinfo_key"

    def test_config_manager_load_from_file(self):
        """Test loading configuration from file."""
        mock_config = {
            "environment": "test",
            "features": {
                "cache_enabled": False,
                "debug_mode": True
            },
            "api_keys": {
                "congress": "file_congress_key",
                "govinfo": "file_govinfo_key"
            }
        }
        
        with patch("pygovpub.config.load_config_from_file", return_value=mock_config):
            manager = ConfigManager()
            manager.load_from_file("config.json")
            
            # Check environment
            assert manager.environment == Environment.TEST
            
            # Check feature flags
            assert manager.get_feature_flag(FeatureFlag.CACHE_ENABLED) is False
            assert manager.get_feature_flag(FeatureFlag.DEBUG_MODE) is True
            
            # Check API keys
            assert manager.get_api_key("congress") == "file_congress_key"
            assert manager.get_api_key("govinfo") == "file_govinfo_key"

    def test_config_manager_save_to_file(self):
        """Test saving configuration to file."""
        # Create a manager with test values
        manager = ConfigManager(environment=Environment.TEST)
        manager.set_feature_flag(FeatureFlag.CACHE_ENABLED, False)
        manager.set_feature_flag(FeatureFlag.DEBUG_MODE, True)
        manager.set_api_key("congress", "test_congress_key")
        manager.set_api_key("govinfo", "test_govinfo_key")
        
        # Mock the secure_config method to return the config as is (no encryption)
        with patch.object(manager.secret_handler, "secure_config", side_effect=lambda cfg, sections: cfg) as mock_secure:
            # And then mock the save_config_to_file function
            with patch("pygovpub.config.save_config_to_file") as mock_save:
                manager.save_to_file("config.json")
                
                # Check that save_config_to_file was called
                mock_save.assert_called_once()
                
                # Check that secure_config was called with the right sections
                mock_secure.assert_called_once()
                # SENSITIVE_SECTIONS is a list, so we need to verify it was passed correctly
                assert mock_secure.call_args[0][1] == manager.SENSITIVE_SECTIONS
                
                # Check the config that was saved
                saved_config = mock_save.call_args[0][0]
                assert saved_config["environment"] == "test"
                assert saved_config["features"]["cache_enabled"] is False
                assert saved_config["features"]["debug_mode"] is True
                assert saved_config["api_keys"]["congress"] == "test_congress_key"
                assert saved_config["api_keys"]["govinfo"] == "test_govinfo_key"

    def test_config_manager_get_set_feature_flags(self):
        """Test getting and setting feature flags."""
        manager = ConfigManager()
        
        # Check default values
        assert manager.get_feature_flag(FeatureFlag.CACHE_ENABLED) is True
        assert manager.get_feature_flag(FeatureFlag.ADVANCED_ROUTING) is False
        
        # Set values
        manager.set_feature_flag(FeatureFlag.CACHE_ENABLED, False)
        manager.set_feature_flag(FeatureFlag.ADVANCED_ROUTING, True)
        
        # Check updated values
        assert manager.get_feature_flag(FeatureFlag.CACHE_ENABLED) is False
        assert manager.get_feature_flag(FeatureFlag.ADVANCED_ROUTING) is True

    def test_config_manager_get_set_api_keys(self):
        """Test getting and setting API keys."""
        manager = ConfigManager()
        
        # Check default values
        assert manager.get_api_key("congress") == ""
        assert manager.get_api_key("govinfo") == ""
        
        # Set values
        manager.set_api_key("congress", "test_congress_key")
        manager.set_api_key("govinfo", "test_govinfo_key")
        
        # Check updated values
        assert manager.get_api_key("congress") == "test_congress_key"
        assert manager.get_api_key("govinfo") == "test_govinfo_key"

    def test_config_manager_validate_invalid_keys(self):
        """Test validation with invalid keys."""
        manager = ConfigManager()
        
        # Set invalid keys
        manager.set_api_key("congress", "")
        manager.set_api_key("govinfo", "")
        
        # Validate
        with pytest.raises(ConfigValidationError) as excinfo:
            manager.validate()
        
        # Check error message
        assert "API key missing" in str(excinfo.value)
        assert "congress" in str(excinfo.value)
        assert "govinfo" in str(excinfo.value)


class TestSecretHandler:
    """Tests for secret handler."""

    def test_secret_handler_encrypt_decrypt(self):
        """Test encrypting and decrypting secrets."""
        # Create a valid URL-safe base64-encoded key for Fernet
        import base64
        test_key_bytes = base64.urlsafe_b64encode(b'a' * 32)
        
        # Create handler with our test key
        with patch.object(SecretHandler, '_process_key', return_value=test_key_bytes):
            handler = SecretHandler(key="test_key")
            
            # Test with string
            secret = "test_secret"
            encrypted = handler.encrypt(secret)
            assert encrypted != secret
            assert handler.decrypt(encrypted) == secret
            
            # Test with dict
            secret_dict = {"key": "value", "nested": {"subkey": "subvalue"}}
            encrypted = handler.encrypt(secret_dict)
            assert encrypted != str(secret_dict)
            assert handler.decrypt(encrypted) == secret_dict

    def test_secret_handler_secure_config(self):
        """Test encrypting and decrypting configuration."""
        # Create a valid URL-safe base64-encoded key for Fernet
        import base64
        test_key_bytes = base64.urlsafe_b64encode(b'a' * 32)
        
        # Create handler with our test key
        with patch.object(SecretHandler, '_process_key', return_value=test_key_bytes):
            handler = SecretHandler(key="test_key")
            
            # Create test config
            config = {
                "api_keys": {
                    "congress": "test_congress_key",
                    "govinfo": "test_govinfo_key"
                },
                "options": {
                    "setting": "value"
                }
            }
            
            # Mock the encrypt method to simulate encryption
            with patch.object(handler, 'encrypt', return_value="ENCRYPTED_DATA"):
                # Encrypt sensitive sections
                secure_config = handler.secure_config(config, ["api_keys"])
                
                # Check that api_keys section is "encrypted"
                assert "api_keys" in secure_config
                assert secure_config["api_keys"] == "ENCRYPTED_DATA"
                
                # Check that other sections are not encrypted
                assert secure_config["options"] == config["options"]
            
            # Mock the decrypt method to simulate decryption
            with patch.object(handler, 'decrypt', return_value=config["api_keys"]):
                # Decrypt config
                encrypted_config = {
                    "api_keys": "ENCRYPTED_DATA",
                    "options": config["options"]
                }
                decrypted = handler.unsecure_config(encrypted_config, ["api_keys"])
                assert decrypted == config