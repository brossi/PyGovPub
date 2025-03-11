"""
Test authorization controls for PyGovPub.

These tests verify the authorization mechanisms beyond basic authentication,
including data protection, authorization checks, and secure communications.
"""

import os
import pytest
import json
from unittest.mock import patch, MagicMock, AsyncMock
import aiohttp
from datetime import datetime
from zoneinfo import ZoneInfo
from cryptography.fernet import Fernet

from pygovpub.auth.auth_manager import AuthManager, ApiKeyStore
from pygovpub.auth.models import ApiSource, AuthType, ApiConfiguration
from pygovpub.exceptions import AuthenticationError, RateLimitExceededError


class TestDataProtection:
    """Test data protection mechanisms."""

    def test_api_key_encryption(self):
        """Test that API keys are properly encrypted."""
        # Generate a test key
        test_key = Fernet.generate_key()
        key_store = ApiKeyStore(encryption_key=test_key.decode())
        
        # Store a sensitive API key
        test_api_key = "test-api-key-12345"
        key_store.store_key(ApiSource.CONGRESS, test_api_key)
        
        # Verify the stored key is encrypted (not plaintext)
        encrypted_key = key_store._keys[ApiSource.CONGRESS]
        assert test_api_key.encode() != encrypted_key
        
        # Verify we can retrieve and decrypt the key
        retrieved_key = key_store.get_key(ApiSource.CONGRESS)
        assert retrieved_key == test_api_key

    def test_key_storage_isolation(self):
        """Test that keys for different sources are isolated."""
        key_store = ApiKeyStore()
        
        # Store keys for different sources
        key_store.store_key(ApiSource.CONGRESS, "congress-key")
        key_store.store_key(ApiSource.GOVINFO, "govinfo-key")
        
        # Verify keys are isolated by source
        assert key_store.get_key(ApiSource.CONGRESS) == "congress-key"
        assert key_store.get_key(ApiSource.GOVINFO) == "govinfo-key"
        
        # Remove one key
        key_store.remove_key(ApiSource.CONGRESS)
        
        # Verify only that key was removed
        assert key_store.get_key(ApiSource.CONGRESS) is None
        assert key_store.get_key(ApiSource.GOVINFO) == "govinfo-key"


class TestSecureCommunications:
    """Test secure communications."""

    def test_enforces_https_urls(self):
        """Test that all API URLs use HTTPS."""
        auth_manager = AuthManager()
        
        # Test Congress.gov URL
        congress_request = auth_manager._get_auth_config(ApiSource.CONGRESS)
        assert congress_request["base_url"].startswith("https://")
        
        # Test GovInfo.gov URL
        govinfo_request = auth_manager._get_auth_config(ApiSource.GOVINFO)
        assert govinfo_request["base_url"].startswith("https://")

    @patch("aiohttp.ClientSession.request")
    async def test_secure_header_transmission(self, mock_request):
        """Test that API keys are transmitted securely in headers."""
        # Mock response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"success": True})
        mock_response.headers = {"Content-Type": "application/json"}
        
        # Setup mock to return our response
        mock_request.return_value.__aenter__.return_value = mock_response
        
        # Setup auth manager with test key
        auth_manager = AuthManager()
        auth_manager.add_key(ApiSource.CONGRESS, "test-congress-key")
        
        # Execute request
        result = await auth_manager.execute_request(
            source=ApiSource.CONGRESS,
            endpoint="/test"
        )
        
        # Verify request was made with correct headers
        call_args = mock_request.call_args[1]
        assert call_args["url"] == "https://api.congress.gov/v3/test"
        assert call_args["headers"]["X-API-Key"] == "test-congress-key"
        
        # Verify successful response
        assert result == {"success": True}


class TestAuthorizationControls:
    """Test authorization controls."""

    def test_version_compatibility_enforcement(self):
        """Test that version compatibility is enforced."""
        auth_manager = AuthManager()
        
        # Test compatible versions
        assert auth_manager.check_version_compatibility(ApiSource.CONGRESS, "3.0")
        assert auth_manager.check_version_compatibility(ApiSource.CONGRESS, "3.1")
        assert auth_manager.check_version_compatibility(ApiSource.GOVINFO, "2.0")
        assert auth_manager.check_version_compatibility(ApiSource.GOVINFO, "2.5")
        
        # Test incompatible versions
        assert not auth_manager.check_version_compatibility(ApiSource.CONGRESS, "2.9")
        assert not auth_manager.check_version_compatibility(ApiSource.CONGRESS, "4.0")
        assert not auth_manager.check_version_compatibility(ApiSource.GOVINFO, "1.9")

    @patch("pygovpub.auth.auth_manager.ApiKeyStore.get_key")
    @patch("aiohttp.ClientSession.request")
    async def test_authentication_error_handling(self, mock_request, mock_get_key):
        """Test proper handling of authentication errors."""
        # Setup mocks
        mock_get_key.return_value = "invalid-key"
        
        # Mock 401 response
        mock_response = AsyncMock()
        mock_response.status = 401
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.raise_for_status = AsyncMock(side_effect=aiohttp.ClientResponseError(
            request_info=MagicMock(), history=(), status=401
        ))
        
        # Setup mock to return our response
        mock_request.return_value.__aenter__.return_value = mock_response
        
        # Setup auth manager
        auth_manager = AuthManager()
        auth_manager.add_key(ApiSource.CONGRESS, "invalid-key")
        
        # Execute request and expect authentication error
        with pytest.raises(AuthenticationError):
            await auth_manager.execute_request(
                source=ApiSource.CONGRESS,
                endpoint="/bills"
            )

    @patch("pygovpub.auth.rate_limiter.RateLimiter.pre_request")
    async def test_rate_limit_enforcement(self, mock_pre_request):
        """Test that rate limits are enforced."""
        # Setup mock to simulate rate limit exceeded
        mock_pre_request.side_effect = RateLimitExceededError("Rate limit exceeded")
        
        # Setup auth manager
        auth_manager = AuthManager()
        auth_manager.add_key(ApiSource.CONGRESS, "test-key")
        
        # Execute request and expect rate limit error
        with pytest.raises(RateLimitExceededError):
            await auth_manager.execute_request(
                source=ApiSource.CONGRESS,
                endpoint="/bills"
            )


# Additional integration tests

@pytest.mark.integration
class TestEndToEndSecurity:
    """End-to-end security tests."""
    
    @pytest.mark.parametrize("source", [ApiSource.CONGRESS, ApiSource.GOVINFO])
    @patch("aiohttp.ClientSession.request")
    async def test_complete_auth_flow(self, mock_request, source):
        """Test complete authentication flow with mock API."""
        # Setup mock response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"data": "test_data"})
        mock_response.headers = {
            "Content-Type": "application/json", 
            "X-RateLimit-Remaining": "100"
        }
        
        # Setup mock to return our response
        mock_request.return_value.__aenter__.return_value = mock_response
        
        # Setup auth manager
        auth_manager = AuthManager()
        auth_manager.add_key(source, f"test-{source}-key")
        
        # Execute request
        result = await auth_manager.execute_request(
            source=source,
            endpoint="/test-endpoint",
            params={"param1": "value1"}
        )
        
        # Verify request was properly authenticated
        call_args = mock_request.call_args[1]
        
        if source == ApiSource.CONGRESS:
            assert "X-API-Key" in call_args["headers"]
            assert call_args["headers"]["X-API-Key"] == f"test-{source}-key"
        else:  # GOVINFO
            assert "api_key" in call_args["params"]
            assert call_args["params"]["api_key"] == f"test-{source}-key"
        
        # Verify successful response
        assert result == {"data": "test_data"}