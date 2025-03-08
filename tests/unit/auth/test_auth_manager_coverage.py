"""
Tests to complete coverage of the auth_manager module.
These tests focus on edge cases and exceptional paths.
"""

import os
import json
import pytest
from unittest import mock
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests
import aiohttp
from aiohttp import ClientResponse
from cryptography.fernet import Fernet

from pygovpub.auth.auth_manager import (
    ApiKeyStore, AuthManager, VersionCompatibility
)
from pygovpub.auth.models import ApiSource, AuthType
from pygovpub.exceptions import (
    AuthenticationError, ConfigurationError, RateLimitExceededError
)


def test_version_compatibility_validation_error():
    """Test validation error in VersionCompatibility model."""
    # This tests line 54
    with pytest.raises(ValueError, match="Invalid version format"):
        VersionCompatibility(
            major=1, 
            minor=0, 
            min_supported="1.x.0"  # Invalid format
        )


def test_api_key_store_empty_key():
    """Test ApiKeyStore with empty encryption key."""
    # This tests line 67, 71
    # Test with empty key (should generate a new one)
    store = ApiKeyStore(encryption_key="")
    
    # Verify a key was generated
    assert store.encryption_key is not None
    assert len(store.encryption_key) > 0
    
    # Check that we can encrypt/decrypt
    original = "test_secret"
    encrypted = store.encrypt(original)
    decrypted = store.decrypt(encrypted)
    assert decrypted == original


def test_key_not_found_error():
    """Test error when key not found in store."""
    # This tests line 87
    store = ApiKeyStore()
    manager = AuthManager(store)
    
    # Try to get a key that doesn't exist
    with pytest.raises(AuthenticationError, match="No API key configured"):
        manager.get_api_key(ApiSource.CONGRESS, raise_error=True)


def test_validate_key_failure():
    """Test validation failure for API key."""
    # This tests line 105
    store = ApiKeyStore()
    manager = AuthManager(store)
    
    # Test with invalid key formats
    with pytest.raises(ConfigurationError, match="Invalid API key format"):
        manager.validate_api_key("", ApiSource.CONGRESS)
    
    with pytest.raises(ConfigurationError, match="Invalid API key format"):
        manager.validate_api_key("too_short", ApiSource.CONGRESS)


def test_execute_request_network_error():
    """Test execute_request with network error."""
    # This tests line 184
    store = ApiKeyStore()
    manager = AuthManager(store)
    
    # Mock a network error
    with mock.patch("requests.request") as mock_request:
        mock_request.side_effect = requests.exceptions.ConnectionError("Network error")
        
        with pytest.raises(Exception, match="Network error"):
            manager.execute_request("GET", "https://api.example.com", {})


def test_async_request_methods():
    """Test async request methods in AuthManager."""
    # This tests lines 221-237, 253
    
    @pytest.mark.asyncio
    async def test_async():
        store = ApiKeyStore()
        manager = AuthManager(store)
        
        # Mock the ClientSession and response
        mock_session = mock.AsyncMock()
        mock_response = mock.AsyncMock(spec=ClientResponse)
        mock_response.status = 200
        mock_response.headers = {}
        mock_response.json.return_value = {"data": "test"}
        mock_response.text.return_value = '{"data": "test"}'
        mock_session.request.return_value.__aenter__.return_value = mock_response
        
        # Test successful request
        with mock.patch("aiohttp.ClientSession", return_value=mock_session):
            result = await manager.execute_request_async("GET", "https://api.example.com", {})
            assert result.json_data == {"data": "test"}
        
        # Test with rate limit error
        mock_response.status = 429
        mock_response.headers = {"Retry-After": "60"}
        with mock.patch("aiohttp.ClientSession", return_value=mock_session):
            with pytest.raises(RateLimitExceededError):
                await manager.execute_request_async("GET", "https://api.example.com", {})
        
        # Test auth error
        mock_response.status = 401
        with mock.patch("aiohttp.ClientSession", return_value=mock_session):
            with pytest.raises(AuthenticationError):
                await manager.execute_request_async("GET", "https://api.example.com", {})
    
    import asyncio
    asyncio.run(test_async())


def test_resolve_api_url():
    """Test resolve_api_url method."""
    # This tests line 299
    store = ApiKeyStore()
    manager = AuthManager(store)
    
    # Test with custom base_url
    url = manager.resolve_api_url(ApiSource.CONGRESS, "/endpoint", "https://custom.api.com")
    assert url == "https://custom.api.com/endpoint"


def test_key_loading_edge_cases():
    """Test edge cases for key loading."""
    # This tests lines 387-388, 397, 400-404
    
    # Test with environment variables (success case)
    with mock.patch.dict(os.environ, {"PYGOVPUB_CONGRESS_API_KEY": "test_key1"}):
        store = ApiKeyStore()
        manager = AuthManager(store)
        
        # Force reload from environment
        manager.load_keys_from_environment(True)
        assert manager.get_api_key(ApiSource.CONGRESS) == "test_key1"
    
    # Test with database source but no DB connection
    with mock.patch.dict(os.environ, {}):
        store = ApiKeyStore()
        manager = AuthManager(store)
        
        # Mock the database session to raise an exception
        with mock.patch.object(manager, "_get_db_session", side_effect=Exception("DB Error")):
            # Should not raise but log warning
            keys = manager.load_keys_from_database()
            assert keys == {}


def test_manage_different_key_types():
    """Test management of different key types."""
    # This tests lines 411-413
    store = ApiKeyStore()
    manager = AuthManager(store)
    
    # Add keys with different auth types
    manager.add_api_key(ApiSource.CONGRESS, "congress_key", AuthType.HEADER)
    manager.add_api_key(ApiSource.GOVINFO, "govinfo_key", AuthType.PARAMETER)
    
    # Test retrieval
    congress_config = manager.get_api_configuration(ApiSource.CONGRESS)
    govinfo_config = manager.get_api_configuration(ApiSource.GOVINFO)
    
    assert congress_config.auth_type == AuthType.HEADER
    assert govinfo_config.auth_type == AuthType.PARAMETER


def test_bad_version_format():
    """Test version comparison with invalid version format."""
    # This tests lines 439, 443
    store = ApiKeyStore()
    manager = AuthManager(store)
    
    # Test with invalid version format
    with pytest.raises(ValueError):
        manager.check_version_compatibility("not_a_version", "1.0.0")
    
    with pytest.raises(ValueError):
        manager.check_version_compatibility("1.0.0", "not_a_version")


def test_incompatible_version():
    """Test incompatible version detection."""
    # This tests lines 467-468
    store = ApiKeyStore()
    manager = AuthManager(store)
    
    # Test with incompatible version
    assert not manager.check_version_compatibility("2.0.0", "1.0.0")
    assert not manager.check_version_compatibility("1.0.0", "2.0.0")