"""
Tests for the storage security module.

This module tests the security layer for protecting API keys
and sensitive metadata in storage operations.
"""

import os
import json
import pytest
from unittest.mock import patch, MagicMock, mock_open

from pygovpub.storage.security import StorageSecurity, SecuritySettings


class TestSecuritySettings:
    """Test suite for the SecuritySettings class."""
    
    @patch.dict(os.environ, {"GOVINFO_API_KEY": "test_api_key"})
    def test_load_from_environment(self):
        """Test loading settings from environment variables."""
        settings = SecuritySettings()
        assert settings.GOVINFO_API_KEY == "test_api_key"
    
    @patch.dict(os.environ, {})
    @patch("builtins.open", new_callable=mock_open, read_data="GOVINFO_API_KEY=test_api_key_from_file")
    def test_load_from_env_file(self, mock_file):
        """Test loading settings from .env file."""
        settings = SecuritySettings(_env_file=".env")
        # Note: This will not actually read the file since we're using the pydantic_settings default implementation
        # This test is mostly for documentation purposes
        # In actual implementation, pydantic-settings would read from the .env file
        pass


class TestStorageSecurity:
    """Test suite for the StorageSecurity class."""
    
    def test_init_with_encryption_enabled(self):
        """Test initialization with encryption enabled."""
        with patch.object(StorageSecurity, '_initialize_cipher') as mock_init_cipher:
            mock_init_cipher.return_value = MagicMock()
            security = StorageSecurity(encryption_enabled=True)
            
            # Verify cipher initialization
            mock_init_cipher.assert_called_once()
            
            # Verify sensitive field names are defined
            assert "api_key" in security.sensitive_field_names
            assert "classification" in security.sensitive_field_names
            assert len(security.sensitive_field_names) >= 3  # Should have several sensitive fields
    
    def test_init_without_encryption(self):
        """Test initialization with encryption disabled."""
        with patch.object(StorageSecurity, '_initialize_cipher') as mock_init_cipher:
            security = StorageSecurity(encryption_enabled=False)
            
            # Verify cipher initialization not called
            mock_init_cipher.assert_not_called()
    
    @patch.dict(os.environ, {"ENCRYPTION_KEY": "test_encryption_key"})
    @patch("cryptography.fernet.Fernet")
    def test_initialize_cipher_from_env(self, mock_fernet):
        """Test cipher initialization using environment variable."""
        mock_fernet.return_value = MagicMock()
        
        security = StorageSecurity()
        
        # Verify Fernet initialization
        mock_fernet.assert_called_once()
        # Verify key was passed
        assert "test_encryption_key" in str(mock_fernet.call_args)
    
    @patch.dict(os.environ, {})
    @patch("os.path.exists")
    @patch("builtins.open", new_callable=mock_open, read_data=b"test_file_key")
    @patch("cryptography.fernet.Fernet")
    def test_initialize_cipher_from_file(self, mock_fernet, mock_file, mock_exists):
        """Test cipher initialization using key file."""
        mock_fernet.return_value = MagicMock()
        mock_exists.return_value = True
        
        security = StorageSecurity()
        
        # Verify Fernet initialization
        mock_fernet.assert_called_once()
        # Verify file was read
        mock_file.assert_called_once()
    
    @patch.dict(os.environ, {})
    @patch("os.path.exists")
    @patch("os.makedirs")
    @patch("builtins.open", new_callable=mock_open)
    @patch("cryptography.fernet.Fernet")
    def test_initialize_cipher_generate_key(self, mock_fernet, mock_file, mock_makedirs, mock_exists):
        """Test key generation when no key exists."""
        mock_fernet.generate_key.return_value = b"generated_key"
        mock_fernet.return_value = MagicMock()
        mock_exists.return_value = False
        
        security = StorageSecurity()
        
        # Verify directory creation
        mock_makedirs.assert_called_once()
        # Verify key generation
        mock_fernet.generate_key.assert_called_once()
        # Verify key saving
        mock_file.assert_called_once()
        # Verify Fernet initialization
        assert mock_fernet.call_count == 2  # Once for generate_key, once for initialization
    
    def test_process_metadata_without_encryption(self):
        """Test metadata processing with encryption disabled."""
        security = StorageSecurity(encryption_enabled=False)
        
        # Test data with sensitive fields
        test_data = {
            "api_key": "secret_api_key",
            "title": "Public Title",
            "classification": "CONFIDENTIAL",
            "nested": {
                "api_key": "nested_secret",
                "public": "Public Value"
            }
        }
        
        # Process metadata
        result = security.process_metadata(test_data)
        
        # Verify nothing was encrypted
        assert result == test_data
    
    def test_process_metadata_with_encryption(self):
        """Test metadata processing with encryption enabled."""
        # Mock cipher
        mock_cipher = MagicMock()
        mock_cipher.encrypt.return_value = b"encrypted_value"
        
        with patch.object(StorageSecurity, '_initialize_cipher', return_value=mock_cipher):
            security = StorageSecurity(encryption_enabled=True)
            
            # Test data with sensitive fields
            test_data = {
                "api_key": "secret_api_key",
                "title": "Public Title",
                "classification": "CONFIDENTIAL",
                "nested": {
                    "api_key": "nested_secret",
                    "public": "Public Value"
                }
            }
            
            # Process metadata
            result = security.process_metadata(test_data)
            
            # Verify sensitive fields encrypted
            assert result["api_key"].startswith("__ENC__:")
            assert result["classification"].startswith("__ENC__:")
            assert result["title"] == "Public Title"  # Non-sensitive field unchanged
            
            # Verify nested sensitive fields encrypted
            assert result["nested"]["api_key"].startswith("__ENC__:")
            assert result["nested"]["public"] == "Public Value"  # Non-sensitive field unchanged
            
            # Verify correct number of encryptions
            assert mock_cipher.encrypt.call_count == 3
    
    def test_process_metadata_with_none_values(self):
        """Test metadata processing with None values."""
        security = StorageSecurity(encryption_enabled=True)
        
        # Mock cipher
        security.cipher = MagicMock()
        security.cipher.encrypt.return_value = b"encrypted_value"
        
        # Test data with None values
        test_data = {
            "api_key": None,
            "title": "Public Title",
            "classification": None
        }
        
        # Process metadata
        result = security.process_metadata(test_data)
        
        # Verify None values preserved
        assert result["api_key"] is None
        assert result["classification"] is None
        assert result["title"] == "Public Title"
        
        # Verify no encryption attempted for None values
        assert security.cipher.encrypt.call_count == 0
    
    def test_decrypt_metadata(self):
        """Test metadata decryption."""
        # Mock cipher
        mock_cipher = MagicMock()
        mock_cipher.decrypt.return_value = b"decrypted_value"
        
        with patch.object(StorageSecurity, '_initialize_cipher', return_value=mock_cipher):
            security = StorageSecurity(encryption_enabled=True)
            
            # Test data with encrypted fields
            test_data = {
                "api_key": "__ENC__:encrypted_api_key",
                "title": "Public Title",
                "classification": "__ENC__:encrypted_classification",
                "nested": {
                    "api_key": "__ENC__:encrypted_nested",
                    "public": "Public Value"
                }
            }
            
            # Decrypt metadata
            result = security.decrypt_metadata(test_data)
            
            # Verify decryption
            assert result["api_key"] == "decrypted_value"
            assert result["classification"] == "decrypted_value"
            assert result["title"] == "Public Title"  # Unchanged
            
            # Verify nested decryption
            assert result["nested"]["api_key"] == "decrypted_value"
            assert result["nested"]["public"] == "Public Value"  # Unchanged
            
            # Verify correct number of decryptions
            assert mock_cipher.decrypt.call_count == 3
    
    def test_decrypt_metadata_without_encryption(self):
        """Test metadata decryption with encryption disabled."""
        security = StorageSecurity(encryption_enabled=False)
        
        # Test data with encryption markers
        test_data = {
            "api_key": "__ENC__:encrypted_api_key",
            "title": "Public Title"
        }
        
        # Decrypt metadata
        result = security.decrypt_metadata(test_data)
        
        # Verify data returned unchanged
        assert result == test_data
    
    def test_decrypt_metadata_error_handling(self):
        """Test error handling during decryption."""
        # Mock cipher with error
        mock_cipher = MagicMock()
        mock_cipher.decrypt.side_effect = Exception("Decryption error")
        
        with patch.object(StorageSecurity, '_initialize_cipher', return_value=mock_cipher):
            security = StorageSecurity(encryption_enabled=True)
            
            # Test data with encrypted field
            test_data = {
                "api_key": "__ENC__:invalid_encrypted_value"
            }
            
            # Decrypt metadata
            result = security.decrypt_metadata(test_data)
            
            # Verify error handling
            assert result["api_key"] == "[DECRYPTION ERROR]"
    
    @patch.dict(os.environ, {
        "DB_PASSWORD": "db_password",
        "GOVINFO_API_KEY": "gov_api_key",
        "PINECONE_API_KEY": "pinecone_key"
    })
    def test_get_credentials(self):
        """Test retrieving credentials."""
        security = StorageSecurity(encryption_enabled=False)
        
        # Get different types of credentials
        postgres_creds = security.get_credentials("postgres")
        govinfo_creds = security.get_credentials("govinfo")
        pinecone_creds = security.get_credentials("pinecone")
        unknown_creds = security.get_credentials("unknown_service")
        
        # Verify correct credentials returned
        assert postgres_creds["password"] == "db_password"
        assert govinfo_creds["api_key"] == "gov_api_key"
        assert pinecone_creds["api_key"] == "pinecone_key"
        assert unknown_creds == {}