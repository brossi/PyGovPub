"""
Authentication management for PyGovPub SDK.

This module handles authentication for API requests to
Congress.gov and GovInfo.gov, including:
- API key validation and storage
- Authentication header/parameter generation
- Version compatibility checking
"""

import base64
import os
from datetime import datetime
from enum import Enum
import json
import logging
from typing import Dict, Optional, Union, Any, Callable
from urllib.parse import urljoin

import aiohttp
import requests
from cryptography.fernet import Fernet
from pydantic import BaseModel, Field, validator
from sqlmodel import Session, select

from pygovpub.auth.models import ApiConfiguration, ApiSource, AuthType, ApiUsage
from pygovpub.auth.rate_limiter import RateLimiter, ThrottleStrategy
from pygovpub.exceptions import (
    AuthenticationError,
    ConfigurationError,
    RateLimitExceededError
)


# Configure logging
logger = logging.getLogger("pygovpub.auth")


class VersionCompatibility(BaseModel):
    """API version compatibility information."""
    
    major: int
    minor: int
    patch: Optional[int] = None
    min_supported: str = Field(...)
    max_supported: Optional[str] = None
    
    @validator("min_supported", "max_supported")
    def validate_version_format(cls, v):
        """Validate version string format."""
        if v is not None and not all(part.isdigit() for part in v.split(".")):
            raise ValueError(f"Invalid version format: {v}")
        return v


class ApiKeyStore:
    """Secure storage for API keys."""
    
    def __init__(self, encryption_key: Optional[str] = None):
        """Initialize key store with optional encryption key."""
        self._keys = {}
        
        # Use provided key or generate from environment
        if encryption_key:
            self._encryption_key = encryption_key.encode()
        else:
            env_key = os.getenv("PYGOVPUB_ENCRYPTION_KEY")
            if env_key:
                self._encryption_key = env_key.encode()
            else:
                # Generate random key if none provided
                self._encryption_key = Fernet.generate_key()
                
        self._fernet = Fernet(self._encryption_key)
        
    def store_key(self, source: ApiSource, key: str) -> None:
        """
        Store an API key securely.
        
        Args:
            source: API source identifier
            key: API key to store
        """
        if not key or not source:
            raise ValueError("API source and key are required")
            
        # Encrypt the key
        encrypted = self._fernet.encrypt(key.encode())
        self._keys[source] = encrypted
        
    def get_key(self, source: ApiSource) -> Optional[str]:
        """
        Get a stored API key.
        
        Args:
            source: API source identifier
            
        Returns:
            Decrypted API key or None if not found
        """
        encrypted = self._keys.get(source)
        if not encrypted:
            return None
            
        # Decrypt the key
        decrypted = self._fernet.decrypt(encrypted)
        return decrypted.decode()
        
    def has_key(self, source: ApiSource) -> bool:
        """Check if key exists for source."""
        return source in self._keys
        
    def remove_key(self, source: ApiSource) -> None:
        """Remove a stored key."""
        if source in self._keys:
            del self._keys[source]


class AuthManager:
    """
    Authentication manager for API requests.
    
    Handles API key management, authentication, and rate limiting
    for requests to Congress.gov and GovInfo.gov APIs.
    """
    
    def __init__(
        self, 
        session_factory: Optional[Callable[[], Session]] = None,
        rate_limit_strategy: ThrottleStrategy = ThrottleStrategy.WAIT,
        encryption_key: Optional[str] = None
    ):
        """
        Initialize authentication manager.
        
        Args:
            session_factory: Function to get database session
            rate_limit_strategy: Strategy for handling rate limits
            encryption_key: Key for API key encryption
        """
        self.key_store = ApiKeyStore(encryption_key)
        self.rate_limiter = RateLimiter(session_factory, rate_limit_strategy)
        self._session_factory = session_factory
        
        # API version compatibility info
        self._version_info = {
            ApiSource.CONGRESS: VersionCompatibility(
                major=3,
                minor=0,
                min_supported="3.0",
                max_supported="3.999"
            ),
            ApiSource.GOVINFO: VersionCompatibility(
                major=2,
                minor=0,
                min_supported="2.0"
            )
        }
        
        # Check for environment keys
        self._load_env_keys()
        
    def _load_env_keys(self) -> None:
        """Load API keys from environment variables."""
        congress_key = os.getenv("CONGRESS_GOV_API_KEY")
        if congress_key:
            self.key_store.store_key(ApiSource.CONGRESS, congress_key)
            
        govinfo_key = os.getenv("GOVINFO_API_KEY")
        if govinfo_key:
            self.key_store.store_key(ApiSource.GOVINFO, govinfo_key)
            
    def add_key(self, source: ApiSource, key: str) -> None:
        """
        Add an API key.
        
        Args:
            source: API source
            key: API key to add
        """
        if not key:
            raise ValueError("API key cannot be empty")
            
        self.key_store.store_key(source, key)
        
    def remove_key(self, source: ApiSource) -> None:
        """
        Remove an API key.
        
        Args:
            source: API source
        """
        self.key_store.remove_key(source)
        
    def has_key(self, source: ApiSource) -> bool:
        """
        Check if API key exists for source.
        
        Args:
            source: API source
            
        Returns:
            True if key exists, False otherwise
        """
        return self.key_store.has_key(source)
        
    def _get_auth_config(self, source: ApiSource) -> Dict[str, Any]:
        """
        Get authentication configuration for API source.
        
        Args:
            source: API source
            
        Returns:
            Dictionary with auth configuration
        """
        # Check if we have DB config
        if self._session_factory:
            try:
                with self._session_factory() as session:
                    stmt = (
                        select(ApiConfiguration)
                        .where(ApiConfiguration.source == source)
                        .where(ApiConfiguration.active == True)
                    )
                    config = session.exec(stmt).first()
                    
                    if config:
                        return {
                            "auth_type": config.auth_type,
                            "auth_key_name": config.auth_key_name,
                            "base_url": config.base_url
                        }
            except Exception as e:
                logger.warning(f"Failed to get DB auth config: {e}")
                
        # Fall back to default configuration
        if source == ApiSource.CONGRESS:
            return {
                "auth_type": AuthType.HEADER,
                "auth_key_name": "X-API-Key",
                "base_url": "https://api.congress.gov/v3"
            }
        elif source == ApiSource.GOVINFO:
            return {
                "auth_type": AuthType.PARAMETER,
                "auth_key_name": "api_key",
                "base_url": "https://api.govinfo.gov"
            }
            
        raise ValueError(f"Unsupported API source: {source}")
        
    def authenticate_request(
        self, 
        source: ApiSource,
        endpoint: str,
        method: str = "GET",
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Prepare request with authentication.
        
        Args:
            source: API source
            endpoint: API endpoint
            method: HTTP method
            params: Query parameters
            headers: HTTP headers
            
        Returns:
            Dictionary with authenticated request details
            
        Raises:
            AuthenticationError: If authentication fails
        """
        if not self.has_key(source):
            raise AuthenticationError(f"No API key available for {source}")
            
        auth_config = self._get_auth_config(source)
        api_key = self.key_store.get_key(source)
        
        # Prepare request components
        request_params = params.copy() if params else {}
        request_headers = headers.copy() if headers else {}
        
        # Add authentication
        if auth_config["auth_type"] == AuthType.HEADER:
            request_headers[auth_config["auth_key_name"]] = api_key
        elif auth_config["auth_type"] == AuthType.PARAMETER:
            request_params[auth_config["auth_key_name"]] = api_key
            
        # Construct URL
        base_url = auth_config["base_url"]
        url = urljoin(base_url, endpoint)
        
        return {
            "url": url,
            "method": method,
            "params": request_params,
            "headers": request_headers
        }
        
    async def execute_request(
        self,
        source: ApiSource,
        endpoint: str,
        method: str = "GET",
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        timeout: int = 30
    ) -> Dict[str, Any]:
        """
        Execute authenticated API request with rate limiting.
        
        Args:
            source: API source
            endpoint: API endpoint
            method: HTTP method
            params: Query parameters
            headers: HTTP headers
            json_data: JSON request body
            timeout: Request timeout in seconds
            
        Returns:
            JSON response data
            
        Raises:
            AuthenticationError: If authentication fails
            RateLimitExceededError: If rate limit exceeded
        """
        # Get authenticated request details
        auth_request = self.authenticate_request(
            source=source,
            endpoint=endpoint,
            method=method,
            params=params,
            headers=headers
        )
        
        # Check rate limits
        try:
            await self.rate_limiter.pre_request(source)
        except Exception as e:
            raise RateLimitExceededError(f"Rate limit exceeded: {e}")
            
        # Execute request
        start_time = datetime.utcnow()
        success = False
        status_code = None
        error_message = None
        response_time_ms = None
        rate_limit_headers = None
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.request(
                    method=auth_request["method"],
                    url=auth_request["url"],
                    params=auth_request["params"],
                    headers=auth_request["headers"],
                    json=json_data,
                    timeout=timeout
                ) as response:
                    status_code = response.status
                    response_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
                    rate_limit_headers = {k.lower(): v for k, v in response.headers.items()}
                    
                    # Check for auth errors
                    if status_code == 401 or status_code == 403:
                        error_message = f"Authentication failed: {status_code}"
                        raise AuthenticationError(error_message)
                        
                    # Check other error status
                    if status_code >= 400:
                        error_message = f"Request failed with status {status_code}"
                        response.raise_for_status()
                        
                    # Parse response body
                    success = True
                    if "application/json" in response.headers.get("Content-Type", ""):
                        return await response.json()
                    else:
                        return {"text": await response.text()}
        except AuthenticationError:
            # Re-raise authentication errors
            raise
        except Exception as e:
            error_message = str(e)
            raise
        finally:
            # Track request for rate limiting
            await self.rate_limiter.track_request(
                source=source,
                endpoint=endpoint,
                status_code=status_code,
                rate_limit_headers=rate_limit_headers,
                response_time_ms=response_time_ms,
                success=success,
                error_message=error_message
            )
            
    def check_version_compatibility(self, source: ApiSource, version: str) -> bool:
        """
        Check if API version is compatible.
        
        Args:
            source: API source
            version: API version string
            
        Returns:
            True if compatible, False otherwise
        """
        compat = self._version_info.get(source)
        if not compat:
            return True  # No compatibility info, assume compatible
            
        version_parts = version.split(".")
        if len(version_parts) < 2:
            return False
            
        try:
            major = int(version_parts[0])
            minor = int(version_parts[1])
            
            min_parts = compat.min_supported.split(".")
            min_major = int(min_parts[0])
            min_minor = int(min_parts[1])
            
            # Check minimum compatibility
            if major < min_major or (major == min_major and minor < min_minor):
                return False
                
            # Check maximum compatibility if specified
            if compat.max_supported:
                max_parts = compat.max_supported.split(".")
                max_major = int(max_parts[0])
                max_minor = int(max_parts[1])
                
                if major > max_major or (major == max_major and minor > max_minor):
                    return False
                    
            return True
        except (ValueError, IndexError):
            return False