"""
Unit tests for the base API client.
"""

import asyncio
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from pygovpub.api.base import BaseApiClient
from pygovpub.auth.auth_manager import AuthManager
from pygovpub.auth.models import ApiSource
from pygovpub.exceptions import ApiError, CongressApiError, GovInfoApiError, AuthenticationError, RateLimitExceededError


class TestBaseApiClient:
    """Tests for the base API client."""
    
    @pytest.fixture
    def mock_auth_manager(self):
        """Create a mock auth manager."""
        auth_manager = MagicMock(spec=AuthManager)
        auth_manager.execute_request = AsyncMock()
        return auth_manager
    
    @pytest.fixture
    def client(self, mock_auth_manager):
        """Create a client with mock auth manager."""
        return BaseApiClient(auth_manager=mock_auth_manager, api_source=ApiSource.CONGRESS)
    
    def test_init_requires_api_source(self, mock_auth_manager):
        """Test that initialization requires an API source."""
        with pytest.raises(ValueError):
            BaseApiClient(auth_manager=mock_auth_manager)
    
    async def test_execute_request(self, client, mock_auth_manager):
        """Test executing a request."""
        # Set up the mock to return a response
        expected_response = {"key": "value"}
        mock_auth_manager.execute_request.return_value = expected_response
        
        # Call the method under test
        response = await client.execute_request(endpoint="/test")
        
        # Verify the auth manager was called correctly
        mock_auth_manager.execute_request.assert_called_once_with(
            source=ApiSource.CONGRESS,
            endpoint="/test",
            method="GET",
            params=None,
            headers=None,
            json_data=None,
            timeout=30
        )
        
        # Verify the response
        assert response == expected_response
    
    async def test_execute_request_with_params(self, client, mock_auth_manager):
        """Test executing a request with parameters."""
        # Set up the mock to return a response
        expected_response = {"key": "value"}
        mock_auth_manager.execute_request.return_value = expected_response
        
        # Call the method under test with parameters
        response = await client.execute_request(
            endpoint="/test",
            method="POST",
            params={"param": "value"},
            headers={"header": "value"},
            json_data={"data": "value"},
            timeout=60
        )
        
        # Verify the auth manager was called correctly with all parameters
        mock_auth_manager.execute_request.assert_called_once_with(
            source=ApiSource.CONGRESS,
            endpoint="/test",
            method="POST",
            params={"param": "value"},
            headers={"header": "value"},
            json_data={"data": "value"},
            timeout=60
        )
        
        # Verify the response
        assert response == expected_response
    
    async def test_authentication_error(self, client, mock_auth_manager):
        """Test handling authentication error."""
        # Set up the mock to raise an authentication error
        mock_auth_manager.execute_request.side_effect = AuthenticationError("Auth failed")
        
        # Verify that the error is propagated
        with pytest.raises(AuthenticationError):
            await client.execute_request(endpoint="/test")
    
    async def test_rate_limit_error(self, client, mock_auth_manager):
        """Test handling rate limit error."""
        # Set up the mock to raise a rate limit error
        mock_auth_manager.execute_request.side_effect = RateLimitExceededError("Rate limit exceeded")
        
        # Verify that the error is propagated
        with pytest.raises(RateLimitExceededError):
            await client.execute_request(endpoint="/test")
    
    async def test_general_error(self, client, mock_auth_manager):
        """Test handling general error."""
        # Set up the mock to raise a general error
        mock_auth_manager.execute_request.side_effect = Exception("General error")
        
        # Verify that the error is converted to a CongressApiError (since we're using ApiSource.CONGRESS)
        with pytest.raises(CongressApiError):
            await client.execute_request(endpoint="/test")
    
    def test_validate_response(self, client):
        """Test response validation."""
        # Test valid response
        assert client.validate_response({"key1": "value1", "key2": "value2"}, ["key1", "key2"])
        
        # Test missing key
        assert not client.validate_response({"key1": "value1"}, ["key1", "key2"])
        
        # Test non-dict response
        assert not client.validate_response("not a dict", ["key1"])
        
        # Test empty expected keys
        assert client.validate_response({"key1": "value1"}, [])