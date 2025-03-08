"""
Tests for authentication manager.

This module tests the AuthManager class that handles API
authentication, key management, and request execution.
"""

import os
import pytest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
import aiohttp
from aiohttp import ClientResponse, RequestInfo

# Direct imports using conftest.py path configuration
from pygovpub.auth.auth_manager import AuthManager, ApiKeyStore
from pygovpub.auth.models import ApiSource, AuthType
from pygovpub.auth.rate_limiter import ThrottleStrategy
from pygovpub.exceptions import AuthenticationError, RateLimitExceededError


@pytest.fixture
def auth_manager():
    """Create an AuthManager instance for testing."""
    # Ensure environment variables are cleared for testing
    for env_var in ["CONGRESS_GOV_API_KEY", "GOVINFO_API_KEY"]:
        if env_var in os.environ:
            del os.environ[env_var]
    
    return AuthManager()


class MockResponse:
    """Mock aiohttp response for testing."""
    
    def __init__(self, status, data, headers=None):
        self.status = status
        self._data = data
        self.headers = headers or {}
        
    async def json(self):
        return self._data
        
    async def text(self):
        return str(self._data)
        
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass
        
    def raise_for_status(self):
        if self.status >= 400:
            raise aiohttp.ClientResponseError(
                request_info=RequestInfo(url="", method="GET", headers={}, real_url=""),
                history=(),
                status=self.status,
                message=f"Error {self.status}"
            )


def test_key_store_encryption():
    """Test API key store encryption and decryption."""
    # Create key store
    key_store = ApiKeyStore()
    
    # Store a key
    key_store.store_key(ApiSource.CONGRESS, "test-api-key-123")
    
    # Get the key back
    retrieved = key_store.get_key(ApiSource.CONGRESS)
    
    # Verify
    assert retrieved == "test-api-key-123"
    
    # Check internal state - key should be encrypted
    assert ApiSource.CONGRESS in key_store._keys
    encrypted = key_store._keys[ApiSource.CONGRESS]
    assert isinstance(encrypted, bytes)
    assert encrypted != b"test-api-key-123"
    
    # Verify has_key and remove_key
    assert key_store.has_key(ApiSource.CONGRESS) is True
    key_store.remove_key(ApiSource.CONGRESS)
    assert key_store.has_key(ApiSource.CONGRESS) is False


def test_auth_manager_env_keys():
    """Test loading API keys from environment variables."""
    # Set environment variables
    os.environ["CONGRESS_GOV_API_KEY"] = "congress-test-key"
    os.environ["GOVINFO_API_KEY"] = "govinfo-test-key"
    
    # Create manager
    manager = AuthManager()
    
    # Verify keys loaded
    assert manager.has_key(ApiSource.CONGRESS) is True
    assert manager.has_key(ApiSource.GOVINFO) is True
    
    # Clean up
    del os.environ["CONGRESS_GOV_API_KEY"]
    del os.environ["GOVINFO_API_KEY"]


def test_add_remove_key(auth_manager):
    """Test adding and removing API keys."""
    # Add keys
    auth_manager.add_key(ApiSource.CONGRESS, "congress-key-test")
    auth_manager.add_key(ApiSource.GOVINFO, "govinfo-key-test")
    
    # Verify keys
    assert auth_manager.has_key(ApiSource.CONGRESS) is True
    assert auth_manager.has_key(ApiSource.GOVINFO) is True
    
    # Remove key
    auth_manager.remove_key(ApiSource.CONGRESS)
    
    # Verify removed
    assert auth_manager.has_key(ApiSource.CONGRESS) is False
    assert auth_manager.has_key(ApiSource.GOVINFO) is True


def test_authenticate_request_congress(auth_manager):
    """Test preparing authenticated request for Congress.gov."""
    # Add key
    auth_manager.add_key(ApiSource.CONGRESS, "congress-key-test")
    
    # Authenticate request
    auth_request = auth_manager.authenticate_request(
        source=ApiSource.CONGRESS,
        endpoint="/bills",
        method="GET",
        params={"limit": 10},
        headers={"Accept": "application/json"}
    )
    
    # Verify request
    assert auth_request["url"] == "https://api.congress.gov/v3/bills"
    assert auth_request["method"] == "GET"
    assert auth_request["params"] == {"limit": 10}
    assert auth_request["headers"] == {
        "Accept": "application/json",
        "X-API-Key": "congress-key-test"
    }


def test_authenticate_request_govinfo(auth_manager):
    """Test preparing authenticated request for GovInfo.gov."""
    # Add key
    auth_manager.add_key(ApiSource.GOVINFO, "govinfo-key-test")
    
    # Authenticate request
    auth_request = auth_manager.authenticate_request(
        source=ApiSource.GOVINFO,
        endpoint="/collections",
        method="GET"
    )
    
    # Verify request
    assert auth_request["url"] == "https://api.govinfo.gov/collections"
    assert auth_request["method"] == "GET"
    assert auth_request["params"] == {"api_key": "govinfo-key-test"}
    assert auth_request["headers"] == {}


def test_authenticate_request_no_key(auth_manager):
    """Test authentication fails when no key is available."""
    # Attempt to authenticate without adding key
    with pytest.raises(AuthenticationError) as exc_info:
        auth_manager.authenticate_request(
            source=ApiSource.CONGRESS,
            endpoint="/bills"
        )
    
    # Verify exception
    assert "No API key available" in str(exc_info.value)


@pytest.mark.asyncio
async def test_execute_request_success(auth_manager):
    """Test successful API request execution."""
    # Add key
    auth_manager.add_key(ApiSource.CONGRESS, "congress-key-test")
    
    # Mock session.request to return test data
    mock_response = MockResponse(
        status=200,
        data={"items": [{"id": "test-1"}]},
        headers={"Content-Type": "application/json", "x-ratelimit-remaining": "4999"}
    )
    
    with patch('aiohttp.ClientSession.request', new_callable=AsyncMock) as mock_request:
        mock_request.return_value = mock_response
        
        # Execute request
        result = await auth_manager.execute_request(
            source=ApiSource.CONGRESS,
            endpoint="/bills",
            params={"limit": 10}
        )
        
        # Verify result
        assert result == {"items": [{"id": "test-1"}]}
        
        # Verify request made with correct parameters
        mock_request.assert_called_once()
        call_args = mock_request.call_args[1]
        assert call_args["method"] == "GET"
        assert call_args["url"] == "https://api.congress.gov/v3/bills"
        assert call_args["params"]["limit"] == 10
        assert "X-API-Key" in call_args["headers"]


@pytest.mark.asyncio
async def test_execute_request_auth_error(auth_manager):
    """Test handling of authentication errors."""
    # Add key
    auth_manager.add_key(ApiSource.CONGRESS, "congress-key-test")
    
    # Mock session.request to return authentication error
    mock_response = MockResponse(
        status=401,
        data={"error": "Invalid API key"},
        headers={"Content-Type": "application/json"}
    )
    
    with patch('aiohttp.ClientSession.request', new_callable=AsyncMock) as mock_request:
        mock_request.return_value = mock_response
        
        # Execute request - should raise AuthenticationError
        with pytest.raises(AuthenticationError) as exc_info:
            await auth_manager.execute_request(
                source=ApiSource.CONGRESS,
                endpoint="/bills"
            )
        
        # Verify exception
        assert "Authentication failed: 401" in str(exc_info.value)


@pytest.mark.asyncio
async def test_execute_request_rate_limit(auth_manager):
    """Test handling of rate limit errors."""
    # Add key
    auth_manager.add_key(ApiSource.CONGRESS, "congress-key-test")
    
    # Mock rate limiter to raise exception
    with patch.object(auth_manager.rate_limiter, 'pre_request') as mock_check:
        mock_check.side_effect = Exception("Rate limit exceeded")
        
        # Execute request - should raise RateLimitExceededError
        with pytest.raises(RateLimitExceededError) as exc_info:
            await auth_manager.execute_request(
                source=ApiSource.CONGRESS,
                endpoint="/bills"
            )
        
        # Verify exception
        assert "Rate limit exceeded" in str(exc_info.value)


def test_check_version_compatibility(auth_manager):
    """Test API version compatibility checking."""
    # Test Congress.gov version compatibility
    source = ApiSource.CONGRESS
    
    # Compatible versions
    assert auth_manager.check_version_compatibility(source, "3.0") is True
    assert auth_manager.check_version_compatibility(source, "3.1") is True
    assert auth_manager.check_version_compatibility(source, "3.999") is True
    
    # Incompatible versions
    assert auth_manager.check_version_compatibility(source, "2.9") is False
    assert auth_manager.check_version_compatibility(source, "4.0") is False
    
    # Test GovInfo.gov version compatibility
    source = ApiSource.GOVINFO
    
    # Compatible versions
    assert auth_manager.check_version_compatibility(source, "2.0") is True
    assert auth_manager.check_version_compatibility(source, "2.1") is True
    assert auth_manager.check_version_compatibility(source, "3.0") is True
    
    # Incompatible versions
    assert auth_manager.check_version_compatibility(source, "1.9") is False