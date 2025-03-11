"""
Test data protection mechanisms for PyGovPub.

These tests verify the data protection capabilities including encryption,
secure storage, and secure configuration handling.
"""

import os
import base64
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from pygovpub.auth.auth_manager import ApiKeyStore
from pygovpub.auth.models import ApiSource
from pygovpub.config import SecretHandler, ConfigManager, Environment


class TestEncryptionMechanisms:
    """Test encryption mechanisms."""

    def test_api_key_store_encryption(self):
        """Test encryption in ApiKeyStore."""
        # Create key store with known key
        test_key = Fernet.generate_key()
        key_store = ApiKeyStore(encryption_key=test_key.decode())
        
        # Store API key
        sensitive_data = "very-sensitive-api-key-12345"
        key_store.store_key(ApiSource.CONGRESS, sensitive_data)
        
        # Verify data is encrypted in storage
        encrypted_data = key_store._keys[ApiSource.CONGRESS]
        assert encrypted_data != sensitive_data.encode()
        
        # Verify decryption works
        decrypted = key_store.get_key(ApiSource.CONGRESS)
        assert decrypted == sensitive_data
        
        # Verify Fernet instance is using the correct key
        fernet = Fernet(test_key)
        manually_decrypted = fernet.decrypt(encrypted_data).decode()
        assert manually_decrypted == sensitive_data

    def test_environment_var_key_loading(self):
        """Test loading keys from environment variables."""
        # Set env vars
        with patch.dict(os.environ, {
            "CONGRESS_GOV_API_KEY": "env-congress-key",
            "GOVINFO_API_KEY": "env-govinfo-key"
        }):
            # Create auth manager which loads keys from environment
            from pygovpub.auth.auth_manager import AuthManager
            auth_manager = AuthManager()
            
            # Verify keys are loaded
            assert auth_manager.has_key(ApiSource.CONGRESS)
            assert auth_manager.has_key(ApiSource.GOVINFO)


class TestSecretHandler:
    """Test SecretHandler for configuration protection."""

    def test_encryption_decryption(self):
        """Test basic encryption and decryption."""
        # Create handler with known key
        handler = SecretHandler(key="test-key-for-encryption")
        
        # Test data
        test_data = {
            "api_key": "secret-api-key",
            "credentials": {
                "username": "test-user",
                "password": "test-password"
            }
        }
        
        # Encrypt data
        encrypted = handler.encrypt(test_data)
        
        # Verify encrypted data is not plaintext
        assert encrypted != json.dumps(test_data)
        assert "secret-api-key" not in encrypted
        
        # Decrypt data
        decrypted = handler.decrypt(encrypted)
        
        # Verify decryption works
        assert decrypted == test_data
        assert decrypted["api_key"] == "secret-api-key"
        assert decrypted["credentials"]["password"] == "test-password"

    def test_machine_specific_key_derivation(self):
        """Test machine-specific key derivation."""
        # Mock machine-specific information
        with patch.dict(os.environ, {
            "USER": "test-user",
            "HOSTNAME": "test-host"
        }), patch("pathlib.Path.home", return_value=Path("/home/test-user")):
            handler = SecretHandler()
            
            # Verify machine salt is predictable
            expected_salt = b"test-user@test-host:/home/test-user"
            assert handler._get_machine_salt() == expected_salt
            
            # Create a second handler and verify keys match
            handler2 = SecretHandler()
            assert handler.key == handler2.key
            
            # Encrypt with first handler
            test_data = {"secret": "value"}
            encrypted = handler.encrypt(test_data)
            
            # Decrypt with second handler
            decrypted = handler2.decrypt(encrypted)
            assert decrypted == test_data

    def test_secure_config_sections(self):
        """Test securing specific config sections."""
        handler = SecretHandler(key="test-key")
        
        # Test config with sensitive sections
        config = {
            "api_keys": {
                "congress": "congress-key-12345",
                "govinfo": "govinfo-key-67890"
            },
            "base_urls": {
                "congress": "https://api.congress.gov/v3",
                "govinfo": "https://api.govinfo.gov"
            }
        }
        
        # Secure only api_keys section
        secured = handler.secure_config(config, ["api_keys"])
        
        # Verify api_keys is encrypted
        assert isinstance(secured["api_keys"], str)
        assert "congress-key" not in secured["api_keys"]
        
        # Verify base_urls is unchanged
        assert secured["base_urls"] == config["base_urls"]
        
        # Unsecure config
        unsecured = handler.unsecure_config(secured, ["api_keys"])
        
        # Verify unsecured matches original
        assert unsecured["api_keys"] == config["api_keys"]
        assert unsecured == config


class TestConfigManager:
    """Test ConfigManager security features."""

    def test_sensitive_section_handling(self):
        """Test handling of sensitive sections."""
        # Create config manager
        manager = ConfigManager(
            environment=Environment.DEVELOPMENT,
            secret_key="test-config-key"
        )
        
        # Verify sensitive sections are defined
        assert "api_keys" in manager.SENSITIVE_SECTIONS
        
        # Test direct encryption with SecretHandler
        sensitive_data = {
            "congress": "test-congress-key",
            "govinfo": "test-govinfo-key"
        }
        
        # Encrypt the API keys section
        encrypted = manager.secret_handler.encrypt(sensitive_data)
        
        # Verify data is actually encrypted
        assert isinstance(encrypted, str)
        assert "test-congress-key" not in encrypted
        
        # Decrypt and verify integrity
        decrypted = manager.secret_handler.decrypt(encrypted)
        assert decrypted == sensitive_data
        assert decrypted["congress"] == "test-congress-key"
        
        # Test with secure_config helper method
        test_config = {
            "api_keys": sensitive_data,
            "environment": "development",
            "features": {
                "cache_enabled": True
            }
        }
        
        # Secure the configuration
        secured_config = manager.secret_handler.secure_config(test_config, ["api_keys"])
        
        # Verify the API keys section is encrypted
        assert isinstance(secured_config["api_keys"], str)
        assert "test-congress-key" not in str(secured_config["api_keys"])
        
        # Other sections should remain unchanged
        assert secured_config["environment"] == "development"
        assert secured_config["features"]["cache_enabled"] is True

    def test_loading_encrypted_config(self):
        """Test loading and decrypting config."""
        # Setup test data
        handler = SecretHandler(key="test-key")
        sensitive_data = {
            "congress": "secret-congress-key",
            "govinfo": "secret-govinfo-key"
        }
        
        # Encrypt the sensitive data
        encrypted_api_keys = handler.encrypt(sensitive_data)
        
        # Create test config with encrypted section
        encrypted_config = {
            "api_keys": encrypted_api_keys,
            "environment": "development",
            "features": {"cache_enabled": True}
        }
        
        # Test unsecure_config helper method to decrypt
        decrypted_config = handler.unsecure_config(encrypted_config, ["api_keys"])
        
        # Verify the section was decrypted
        assert isinstance(decrypted_config["api_keys"], dict)
        assert decrypted_config["api_keys"]["congress"] == "secret-congress-key"
        assert decrypted_config["api_keys"]["govinfo"] == "secret-govinfo-key"
        
        # Other sections should remain unchanged
        assert decrypted_config["environment"] == "development"
        assert decrypted_config["features"]["cache_enabled"] is True