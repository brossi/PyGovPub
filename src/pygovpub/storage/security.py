"""
Security layer for storage operations.

This module provides security features for storage operations:
- Field-level encryption for sensitive metadata
- Secure credential management
- API key handling
- Key versioning and rotation

It focuses on protecting API keys and sensitive metadata while maintaining
compatibility with the database-agnostic storage interface.
"""

import os
import json
import time
import hmac
import hashlib
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import structlog
from cryptography.fernet import Fernet as CryptoFernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
from pydantic_settings import BaseSettings

# Alias for better clarity and to avoid import issues in methods
Fernet = CryptoFernet

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
    ENCRYPTION_KEY_V1: Optional[str] = None
    ENCRYPTION_KEY_V2: Optional[str] = None
    ENCRYPTION_KEY_V3: Optional[str] = None
    ENCRYPTION_HMAC_KEY: Optional[str] = None

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "allow"  # Allow extra fields from environment
    }


class EncryptionKeys:
    """Manages versioned encryption keys for secure data storage"""
    
    DEFAULT_VERSION = 1
    CURRENT_VERSION = 1
    
    def __init__(self):
        """Initialize encryption keys manager"""
        self.keys = {}
        self.hmac_key = None
    
    def add_key(self, version: int, key: str) -> None:
        """
        Add a versioned encryption key.
        
        Args:
            version: Key version number
            key: Encryption key (Fernet key)
        """
        if key:
            # Ensure key is in bytes format for Fernet
            key_bytes = key.encode('utf-8') if isinstance(key, str) else key
            self.keys[version] = Fernet(key_bytes)
            # Update current version if adding a higher version
            if version > self.CURRENT_VERSION:
                self.CURRENT_VERSION = version
    
    def set_hmac_key(self, key: str) -> None:
        """
        Set HMAC key for tamper detection.
        
        Args:
            key: HMAC key
        """
        if key:
            self.hmac_key = key.encode('utf-8') if isinstance(key, str) else key
        else:
            # Generate a HMAC key if not provided
            self.hmac_key = base64.b64encode(os.urandom(32))
    
    def get_current_key(self) -> Tuple[int, Fernet]:
        """
        Get the current (highest version) encryption key.
        
        Returns:
            Tuple of (version, Fernet instance)
        """
        if not self.keys:
            raise ValueError("No encryption keys configured")
        
        version = max(self.keys.keys())
        return version, self.keys[version]
    
    def create_hmac(self, data: str) -> str:
        """
        Create HMAC for data integrity verification.
        
        Args:
            data: Data to create HMAC for
            
        Returns:
            HMAC digest as hex string
        """
        if not self.hmac_key:
            raise ValueError("HMAC key not configured")
        
        h = hmac.new(self.hmac_key, data.encode('utf-8'), hashlib.sha256)
        return h.hexdigest()
    
    def verify_hmac(self, data: str, digest: str) -> bool:
        """
        Verify HMAC for data integrity.
        
        Args:
            data: Original data
            digest: Expected HMAC digest
            
        Returns:
            True if HMAC verification succeeds
        """
        if not self.hmac_key:
            raise ValueError("HMAC key not configured")
        
        calculated = self.create_hmac(data)
        return hmac.compare_digest(calculated, digest)


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
        # Track requests for audit logging
        self._audit_trail = []
        self._last_audit_flush = time.time()

        # Initialize encryption only if enabled
        if encryption_enabled:
            self.keys = self._initialize_keys()

            # Define specific fields that should be encrypted
            # Note: These are only metadata fields, not the legislative content itself
            self.sensitive_field_names: Set[str] = {
                "api_key",           # External service credentials
                "classification",    # Document classification markings
                "restricted_note",   # Sensitive annotations
                "personal_data"      # Any fields containing personal identifiers
            }

            logger.info("Storage security initialized with encryption", 
                        key_versions=list(self.keys.keys.keys()),
                        current_version=self.keys.CURRENT_VERSION)
        else:
            logger.info("Storage security initialized without encryption")

    def _initialize_keys(self) -> EncryptionKeys:
        """
        Initialize encryption keys.
        
        Returns:
            EncryptionKeys instance
        """
        keys = EncryptionKeys()
        
        # Check for versioned keys in environment
        if self.settings.ENCRYPTION_KEY_V1:
            keys.add_key(1, self.settings.ENCRYPTION_KEY_V1)
        if self.settings.ENCRYPTION_KEY_V2:
            keys.add_key(2, self.settings.ENCRYPTION_KEY_V2)
        if self.settings.ENCRYPTION_KEY_V3:
            keys.add_key(3, self.settings.ENCRYPTION_KEY_V3)
            
        # Backward compatibility: use ENCRYPTION_KEY as version 1 if not set
        if not keys.keys and self.settings.ENCRYPTION_KEY:
            keys.add_key(1, self.settings.ENCRYPTION_KEY)
        
        # Set HMAC key for tamper detection
        keys.set_hmac_key(self.settings.ENCRYPTION_HMAC_KEY)
        
        # If no keys set, load or generate
        if not keys.keys:
            self._load_or_generate_keys(keys)
        
        return keys
    
    def _load_or_generate_keys(self, keys: EncryptionKeys) -> None:
        """
        Load keys from file or generate new ones.
        
        Args:
            keys: EncryptionKeys instance to populate
        """
        # Keys directory
        keys_dir = os.path.expanduser("~/.pygovpub/keys")
        os.makedirs(keys_dir, exist_ok=True)
        
        # Check for key files
        key_files = {}
        for i in range(1, 4):  # Support up to 3 key versions
            key_path = os.path.join(keys_dir, f"v{i}.key")
            if os.path.exists(key_path):
                with open(key_path, "rb") as key_file:
                    key_data = key_file.read()
                    # Handle both string and bytes
                    key_files[i] = key_data.decode('utf-8') if isinstance(key_data, bytes) else key_data
        
        # Load existing keys
        for version, key in key_files.items():
            keys.add_key(version, key)
        
        # Generate version 1 if no keys exist
        if not keys.keys:
            version = 1
            key = Fernet.generate_key().decode('utf-8')
            key_path = os.path.join(keys_dir, f"v{version}.key")
            with open(key_path, "wb") as key_file:
                key_file.write(key.encode('utf-8'))
            keys.add_key(version, key)
            logger.info(f"Generated new encryption key v{version}")
        
        # Check for HMAC key
        hmac_path = os.path.join(keys_dir, "hmac.key")
        if os.path.exists(hmac_path):
            with open(hmac_path, "rb") as key_file:
                hmac_key = key_file.read()
                keys.set_hmac_key(hmac_key)
        else:
            # Generate new HMAC key
            hmac_key = base64.b64encode(os.urandom(32))
            with open(hmac_path, "wb") as key_file:
                key_file.write(hmac_key)
            keys.set_hmac_key(hmac_key)
            logger.info("Generated new HMAC key")

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
                # Get current key version and cipher
                version, cipher = self.keys.get_current_key()
                
                # Add encryption marker and encrypt
                encrypted_value = cipher.encrypt(value.encode()).decode('utf-8')
                
                # Generate HMAC for tamper detection
                hmac_digest = self.keys.create_hmac(encrypted_value)
                
                # Store with version and HMAC
                processed[key] = f"__ENC_V{version}__:{encrypted_value}:{hmac_digest}"
                logger.debug(f"Encrypted metadata field {key} with key version {version}")
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

            # Check for encryption marker (new versioned format)
            if isinstance(value, str) and value.startswith("__ENC_V"):
                # Parse versioned format: __ENC_V{version}__:{encrypted_value}:{hmac}
                try:
                    version_end = value.index("__:")
                    version_str = value[6:version_end]
                    version = int(version_str)
                    
                    # Split remaining parts
                    remaining = value[version_end+2:]
                    parts = remaining.split(":", 1)
                    
                    if len(parts) < 2:
                        # No HMAC provided (backward compatibility)
                        encrypted_value = parts[0]
                        hmac_digest = None
                    else:
                        encrypted_value = parts[0]
                        hmac_digest = parts[1]
                    
                    # Verify HMAC if available
                    if hmac_digest and not self.keys.verify_hmac(encrypted_value, hmac_digest):
                        raise ValueError("HMAC verification failed, data may be tampered")
                    
                    # Get cipher for version
                    if version not in self.keys.keys:
                        raise ValueError(f"Encryption key version {version} not found")
                    
                    cipher = self.keys.keys[version]
                    decrypted = cipher.decrypt(encrypted_value.encode()).decode('utf-8')
                    processed[key] = decrypted
                    
                except (ValueError, InvalidToken) as e:
                    logger.error(f"Failed to decrypt field {key}", error=str(e), version=version_str if 'version_str' in locals() else "unknown")
                    processed[key] = "[DECRYPTION ERROR]"
            
            # Check for old encryption marker for backward compatibility
            elif isinstance(value, str) and value.startswith("__ENC__:"):
                # Handle legacy format without versioning
                encrypted_value = value[8:]  # Remove marker
                try:
                    # Try with default key (v1)
                    cipher = self.keys.keys.get(1)
                    if not cipher:
                        raise ValueError("No default encryption key available")
                        
                    decrypted = cipher.decrypt(encrypted_value.encode()).decode('utf-8')
                    processed[key] = decrypted
                    
                    # Log that we're using legacy format
                    logger.info(f"Decrypted field {key} using legacy format")
                    
                except Exception as e:
                    logger.error(f"Failed to decrypt legacy field {key}", error=str(e))
                    processed[key] = "[DECRYPTION ERROR]"
            
            elif isinstance(value, dict):
                # Recursively process nested dictionaries
                processed[key] = self.decrypt_metadata(value)
            else:
                # Pass through other values
                processed[key] = value

        return processed

    def rotate_keys(self) -> bool:
        """
        Generate a new encryption key and make it the current version.
        
        This doesn't re-encrypt existing data, but ensures new data uses
        the latest key. Existing encrypted data can still be decrypted
        with the old keys.
        
        Returns:
            True if key rotation succeeded
        """
        if not self.encryption_enabled:
            return False
            
        try:
            # Generate new key with incremented version
            new_version = self.keys.CURRENT_VERSION + 1
            key = Fernet.generate_key().decode('utf-8')
            
            # Save to file
            key_path = os.path.expanduser(f"~/.pygovpub/keys/v{new_version}.key")
            os.makedirs(os.path.dirname(key_path), exist_ok=True)
            
            with open(key_path, "wb") as key_file:
                key_file.write(key.encode('utf-8'))
                
            # Add to encryption keys
            self.keys.add_key(new_version, key)
            
            logger.info(f"Generated new encryption key v{new_version}")
            
            # Add key rotation to audit log
            self._add_audit_entry("key_rotation", 
                                  {"new_version": new_version, 
                                   "previous_version": new_version - 1})
            
            return True
        except Exception as e:
            logger.error("Failed to rotate encryption keys", error=str(e))
            return False

    def rekey_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Re-encrypt data with the latest key version.
        
        This can be used during key rotation to update existing encrypted data
        to use the latest key.
        
        Args:
            data: Data containing encrypted fields
            
        Returns:
            Data with fields re-encrypted using latest key
        """
        if not self.encryption_enabled:
            return data
            
        # First decrypt all fields
        decrypted = self.decrypt_metadata(data)
        
        # Then re-encrypt using latest key
        return self.process_metadata(decrypted)

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
        credentials = {}
        
        if service_name == "postgres":
            credentials = {"password": self.settings.DB_PASSWORD} if self.settings.DB_PASSWORD else {}
        elif service_name == "govinfo":
            credentials = {"api_key": self.settings.GOVINFO_API_KEY} if self.settings.GOVINFO_API_KEY else {}
        elif service_name == "pinecone":
            credentials = {"api_key": self.settings.PINECONE_API_KEY} if self.settings.PINECONE_API_KEY else {}
        elif service_name == "supabase":
            credentials = {"key": self.settings.SUPABASE_KEY} if self.settings.SUPABASE_KEY else {}
        else:
            logger.warning(f"No credentials configured for service: {service_name}")
            
        # Record credential access for audit
        self._add_audit_entry("credential_access", 
                            {"service": service_name, 
                             "credential_type": list(credentials.keys()),
                             "has_credentials": bool(credentials)})
            
        return credentials
    
    def reload_credentials(self) -> bool:
        """
        Reload credentials from environment or config.
        
        This can be used to update credentials without restarting the application.
        
        Returns:
            True if reload succeeded
        """
        try:
            # Create a new settings instance to reload from environment
            new_settings = SecuritySettings()
            
            # Update current settings
            self.settings = new_settings
            
            # Log the reload
            self._add_audit_entry("credential_reload", {"success": True})
            
            return True
        except Exception as e:
            logger.error("Failed to reload credentials", error=str(e))
            
            # Log the failure
            self._add_audit_entry("credential_reload", {"success": False, "error": str(e)})
            
            return False
    
    def _add_audit_entry(self, action: str, details: Dict[str, Any]) -> None:
        """
        Add entry to audit trail.
        
        Args:
            action: Security action name
            details: Details about the action
        """
        if not self.encryption_enabled:
            return
            
        self._audit_trail.append({
            "timestamp": datetime.utcnow().isoformat(),
            "action": action,
            "details": details
        })
        
        # Flush audit trail periodically
        if len(self._audit_trail) >= 100 or (time.time() - self._last_audit_flush) > 3600:
            self._flush_audit_trail()
    
    def _flush_audit_trail(self) -> None:
        """Flush audit trail to log"""
        if not self._audit_trail:
            return
            
        try:
            # Save audit trail to file
            audit_dir = os.path.expanduser("~/.pygovpub/audit")
            os.makedirs(audit_dir, exist_ok=True)
            
            # Create timestamped filename
            timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
            filename = f"security-audit-{timestamp}.jsonl"
            filepath = os.path.join(audit_dir, filename)
            
            with open(filepath, "w") as f:
                for entry in self._audit_trail:
                    f.write(json.dumps(entry) + "\n")
            
            # Clear trail after flush
            self._audit_trail = []
            self._last_audit_flush = time.time()
            
            logger.debug(f"Flushed security audit trail to {filepath}")
        except Exception as e:
            logger.error("Failed to flush audit trail", error=str(e))
            
    def map_storage_error(self, exception: Exception) -> Dict[str, Any]:
        """
        Map storage errors to API-friendly format.
        
        This provides a consistent error format for API responses
        while hiding implementation details from the client.
        
        Args:
            exception: Storage exception
            
        Returns:
            Dictionary with error details in API-friendly format
        """
        from pygovpub.exceptions import (
            PyGovPubException, 
            AuthenticationError,
            ResourceNotFoundError,
            DataValidationError,
            RateLimitExceededError,
            NetworkError,
            TimeoutError
        )
        
        error_info = {
            "error": True,
            "error_type": "storage_error",
            "message": "Storage operation failed",
            "reference_id": hashlib.md5(str(datetime.utcnow().timestamp()).encode()).hexdigest()[:10],
            "status_code": 500
        }
        
        # Record the error for audit
        self._add_audit_entry("storage_error", {
            "reference_id": error_info["reference_id"],
            "exception_type": type(exception).__name__
        })
        
        # Map specific exceptions to appropriate error formats
        if isinstance(exception, PyGovPubException):
            # Already a PyGovPub exception, use its error_code
            error_info["error_type"] = exception.__class__.__name__
            error_info["message"] = str(exception)
            
            # Map standard exceptions to appropriate status codes
            if isinstance(exception, AuthenticationError):
                error_info["status_code"] = 401
            elif isinstance(exception, ResourceNotFoundError):
                error_info["status_code"] = 404
            elif isinstance(exception, DataValidationError):
                error_info["status_code"] = 400
            elif isinstance(exception, RateLimitExceededError):
                error_info["status_code"] = 429
            elif isinstance(exception, (NetworkError, TimeoutError)):
                error_info["status_code"] = 503
                
        elif "permission" in str(exception).lower() or "access" in str(exception).lower():
            # Permission-related errors
            error_info["error_type"] = "PermissionError"
            error_info["message"] = "Insufficient permissions for this operation"
            error_info["status_code"] = 403
            
        elif "not found" in str(exception).lower() or "does not exist" in str(exception).lower():
            # Not found errors
            error_info["error_type"] = "ResourceNotFoundError"
            error_info["message"] = "Requested resource not found"
            error_info["status_code"] = 404
            
        elif "timeout" in str(exception).lower():
            # Timeout errors
            error_info["error_type"] = "TimeoutError"
            error_info["message"] = "Operation timed out"
            error_info["status_code"] = 504
            
        elif "invalid" in str(exception).lower() or "validation" in str(exception).lower():
            # Validation errors
            error_info["error_type"] = "ValidationError"
            error_info["message"] = "Invalid data provided"
            error_info["status_code"] = 400
            
        elif "duplicate" in str(exception).lower() or "already exists" in str(exception).lower():
            # Duplicate data errors
            error_info["error_type"] = "DuplicateError"
            error_info["message"] = "Resource already exists"
            error_info["status_code"] = 409
            
        else:
            # Generic server error for unknown exceptions
            error_info["error_type"] = "ServerError"
            error_info["message"] = "An unexpected error occurred"
            error_info["status_code"] = 500
        
        # Add reference for support inquiries
        error_info["detail"] = f"Reference ID: {error_info['reference_id']}"
        
        # Log the error mapping
        logger.error("Storage error mapped", 
                     error_type=error_info["error_type"],
                     reference_id=error_info["reference_id"],
                     status_code=error_info["status_code"],
                     original_exception=type(exception).__name__)
        
        return error_info