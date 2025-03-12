"""
Security layer for storage operations.

This module provides security features for storage operations:
- Field-level encryption for sensitive metadata
- Secure credential management
- API key handling

It focuses on protecting API keys and sensitive metadata while maintaining
compatibility with the database-agnostic storage interface.
"""

import os
from typing import Any, Dict, Optional, Set, Union

import structlog
from cryptography.fernet import Fernet
from pydantic_settings import BaseSettings

logger = structlog.get_logger()

class SecuritySettings(BaseSettings):
    """Validate and access security-related environment variables"""
    # Database credentials
    DB_PASSWORD: Optional[str] = None

    # External API keys
    GOVINFO_API_KEY: Optional[str] = None
    PINECONE_API_KEY: Optional[str] = None
    SUPABASE_KEY: Optional[str] = None

    # Encryption settings
    ENCRYPTION_KEY: Optional[str] = None

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

class StorageSecurity:
    """Handles targeted encryption for sensitive metadata fields"""

    def __init__(self, encryption_enabled: bool = True):
        """
        Initialize storage security.
        
        Args:
            encryption_enabled: Whether to enable encryption
        """
        self.settings = SecuritySettings()
        self.encryption_enabled = encryption_enabled

        # Initialize encryption only if enabled
        if encryption_enabled:
            self.cipher = self._initialize_cipher()

            # Define specific fields that should be encrypted
            # Note: These are only metadata fields, not the legislative content itself
            self.sensitive_field_names: Set[str] = {
                "api_key",           # External service credentials
                "classification",    # Document classification markings
                "restricted_note",   # Sensitive annotations
                "personal_data"      # Any fields containing personal identifiers
            }

            logger.info("Storage security initialized with encryption")
        else:
            logger.info("Storage security initialized without encryption")

    def _initialize_cipher(self) -> Fernet:
        """
        Initialize the encryption cipher.
        
        Returns:
            Fernet cipher instance
        """
        # Use environment variable if available
        key = self.settings.ENCRYPTION_KEY

        if not key:
            # Generate a key only if one doesn't exist
            key_path = os.path.expanduser("~/.pygovpub/crypto.key")
            os.makedirs(os.path.dirname(key_path), exist_ok=True)

            if os.path.exists(key_path):
                with open(key_path, "rb") as key_file:
                    key = key_file.read().decode('utf-8')
            else:
                # Generate new key
                key = Fernet.generate_key().decode('utf-8')
                with open(key_path, "wb") as key_file:
                    key_file.write(key.encode('utf-8'))
                logger.info("Generated new encryption key")

        return Fernet(key.encode('utf-8') if isinstance(key, str) else key)

    def process_metadata(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process metadata for storage, encrypting only specific sensitive fields.
        
        This targets only metadata annotations and classifications - not document content.
        
        Args:
            data: Metadata dictionary
            
        Returns:
            Processed metadata with sensitive fields encrypted
        """
        if not self.encryption_enabled:
            return data

        processed = {}

        for key, value in data.items():
            # Skip None values
            if value is None:
                processed[key] = None
                continue

            # Only encrypt specific sensitive metadata fields
            if key in self.sensitive_field_names and isinstance(value, str):
                # Add encryption marker and encrypt
                encrypted_value = self.cipher.encrypt(value.encode()).decode('utf-8')
                processed[key] = f"__ENC__:{encrypted_value}"
                logger.debug(f"Encrypted metadata field {key}")
            elif isinstance(value, dict):
                # Recursively process nested dictionaries
                processed[key] = self.process_metadata(value)
            else:
                # Pass through other values
                processed[key] = value

        return processed

    def decrypt_metadata(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Decrypt only the encrypted metadata fields.
        
        Args:
            data: Metadata dictionary with potentially encrypted fields
            
        Returns:
            Metadata with sensitive fields decrypted
        """
        if not self.encryption_enabled:
            return data

        processed = {}

        for key, value in data.items():
            # Skip None values
            if value is None:
                processed[key] = None
                continue

            # Check for encryption marker
            if isinstance(value, str) and value.startswith("__ENC__:"):
                encrypted_value = value[8:]  # Remove marker
                try:
                    decrypted = self.cipher.decrypt(encrypted_value.encode()).decode('utf-8')
                    processed[key] = decrypted
                except Exception as e:
                    logger.error(f"Failed to decrypt field {key}", error=str(e))
                    processed[key] = "[DECRYPTION ERROR]"
            elif isinstance(value, dict):
                # Recursively process nested dictionaries
                processed[key] = self.decrypt_metadata(value)
            else:
                # Pass through other values
                processed[key] = value

        return processed

    def get_credentials(self, service_name: str) -> Dict[str, str]:
        """
        Get credentials for external services from environment variables.
        
        This centralizes credential access and facilitates future enhancements
        like credential rotation or secrets management integration.
        
        Args:
            service_name: Service name (postgres, govinfo, pinecone, etc.)
            
        Returns:
            Dictionary of credentials
        """
        if service_name == "postgres":
            return {"password": self.settings.DB_PASSWORD} if self.settings.DB_PASSWORD else {}
        elif service_name == "govinfo":
            return {"api_key": self.settings.GOVINFO_API_KEY} if self.settings.GOVINFO_API_KEY else {}
        elif service_name == "pinecone":
            return {"api_key": self.settings.PINECONE_API_KEY} if self.settings.PINECONE_API_KEY else {}
        elif service_name == "supabase":
            return {"key": self.settings.SUPABASE_KEY} if self.settings.SUPABASE_KEY else {}
        else:
            logger.warning(f"No credentials configured for service: {service_name}")
            return {}