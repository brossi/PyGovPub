"""
Tests specifically for AuthManager session handling improvements.

These tests focus on proper session management and cleanup to prevent resource leaks.
"""

import os
import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock

import aiohttp
from aiohttp import ClientResponse

from pygovpub.auth.auth_manager import AuthManager
from pygovpub.auth.models import ApiSource
from pygovpub.exceptions import AuthenticationError, RateLimitExceededError


@pytest.fixture
def auth_manager():
    """Create an AuthManager instance for testing."""
    # Ensure environment variables are cleared for testing
    for env_var in ["CONGRESS_GOV_API_KEY", "GOVINFO_API_KEY"]:
        if env_var in os.environ:
            del os.environ[env_var]
    
    manager = AuthManager()
    # Add test keys
    manager.add_key(ApiSource.CONGRESS, "test-key-123")
    manager.add_key(ApiSource.GOVINFO, "test-key-456")
    return manager


class ResponseContextManagerMock:
    """Mock for response context manager."""
    
    def __init__(self, response):
        self.response = response
        self.entered = False
        self.exited = False
        
    async def __aenter__(self):
        self.entered = True
        return self.response
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.exited = True
        return False


class CustomSessionMock:
    """Custom mock for aiohttp.ClientSession that tracks session lifecycle."""
    
    def __init__(self, response=None, request_side_effect=None):
        self.closed = False
        self.entered = False
        self.exited = False
        self.response = response
        self.request_side_effect = request_side_effect
        self.request_calls = []
        self.response_context = ResponseContextManagerMock(response)
    
    async def __aenter__(self):
        self.entered = True
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.exited = True
        return False  # Don't suppress exceptions
    
    def request(self, method, url, **kwargs):
        """Not async - returns a context manager directly for the 'async with' pattern."""
        self.request_calls.append((method, url, kwargs))
        if self.request_side_effect:
            raise self.request_side_effect
        return self.response_context
    
    async def close(self):
        self.closed = True


@pytest.mark.asyncio
async def test_execute_request_session_management_success(auth_manager):
    """Test that sessions are properly managed when requests succeed."""
    # Create a successful response
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.headers = {"Content-Type": "application/json"}
    mock_response.json.return_value = {"success": True}
    
    # Create our session with the response
    session = CustomSessionMock(response=mock_response)
    
    # Patch aiohttp.ClientSession to return our mock
    with patch('aiohttp.ClientSession', return_value=session):
        # Execute a successful request
        result = await auth_manager.execute_request(
            source=ApiSource.CONGRESS,
            endpoint="/test",
            method="GET"
        )
        
        # Verify request succeeded
        assert result == {"success": True}
        
        # Verify session lifecycle - with context manager pattern, session.close() isn't called directly
        assert session.entered is True
        assert session.exited is True  # This indicates the context manager exited properly
        
        # Verify response context lifecycle
        assert session.response_context.entered is True
        assert session.response_context.exited is True
        
        # Verify request was made with expected parameters
        assert len(session.request_calls) == 1
        method, url, kwargs = session.request_calls[0]
        assert method == "GET"
        assert url.endswith("/test")
        assert "X-API-Key" in kwargs["headers"]


@pytest.mark.asyncio
async def test_execute_request_session_management_request_error(auth_manager):
    """Test that sessions are properly managed when requests fail with network errors."""
    # Create a session that raises an error on request
    network_error = aiohttp.ClientConnectionError("Network error")
    session = CustomSessionMock(request_side_effect=network_error)
    
    # Patch aiohttp.ClientSession to return our mock
    with patch('aiohttp.ClientSession', return_value=session):
        # Execute request that will fail
        with pytest.raises(Exception):
            await auth_manager.execute_request(
                source=ApiSource.CONGRESS,
                endpoint="/test",
                method="GET"
            )
        
        # Verify session was properly cleaned up despite the error
        assert session.entered is True
        assert session.exited is True  # This indicates the context manager exited properly


@pytest.mark.asyncio
async def test_execute_request_session_management_response_error(auth_manager):
    """Test that sessions are properly managed when responses have error status codes."""
    # Create a response with an error status
    mock_response = AsyncMock()
    mock_response.status = 500
    mock_response.headers = {"Content-Type": "application/json"}
    mock_response.json.return_value = {"error": "Server error"}
    mock_response.raise_for_status.side_effect = aiohttp.ClientResponseError(
        request_info=MagicMock(),
        history=(),
        status=500,
        message="Server error",
        headers={}
    )
    
    # Create our session with the error response
    session = CustomSessionMock(response=mock_response)
    
    # Patch aiohttp.ClientSession to return our mock
    with patch('aiohttp.ClientSession', return_value=session):
        # Execute request that will receive an error response
        with pytest.raises(aiohttp.ClientResponseError):
            await auth_manager.execute_request(
                source=ApiSource.CONGRESS,
                endpoint="/test",
                method="GET"
            )
        
        # Verify session was properly cleaned up despite the error
        assert session.entered is True
        assert session.exited is True  # This indicates the context manager exited properly
        assert session.response_context.entered is True
        assert session.response_context.exited is True


@pytest.mark.asyncio
async def test_execute_request_session_management_auth_error(auth_manager):
    """Test that sessions are properly managed when responses have auth errors."""
    # Create a response with an auth error status
    mock_response = AsyncMock()
    mock_response.status = 401
    mock_response.headers = {"Content-Type": "application/json"}
    mock_response.json.return_value = {"error": "Unauthorized"}
    
    # Create our session with the auth error response
    session = CustomSessionMock(response=mock_response)
    
    # Patch aiohttp.ClientSession to return our mock
    with patch('aiohttp.ClientSession', return_value=session):
        # Execute request that will receive an auth error
        with pytest.raises(AuthenticationError):
            await auth_manager.execute_request(
                source=ApiSource.CONGRESS,
                endpoint="/test",
                method="GET"
            )
        
        # Verify session was properly cleaned up despite the error
        assert session.entered is True
        assert session.exited is True  # This indicates the context manager exited properly
        assert session.response_context.entered is True
        assert session.response_context.exited is True


@pytest.mark.asyncio
async def test_execute_request_json_parsing_error(auth_manager):
    """Test handling of JSON parsing errors while ensuring proper session cleanup."""
    # Create a response that will fail when json() is called
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.headers = {"Content-Type": "application/json"}
    mock_response.json.side_effect = ValueError("Invalid JSON")
    mock_response.text.return_value = "Not JSON data"
    
    # Create our session with the problematic response
    session = CustomSessionMock(response=mock_response)
    
    # Patch aiohttp.ClientSession to return our mock
    with patch('aiohttp.ClientSession', return_value=session):
        # Execute request that will have JSON parsing issues
        result = await auth_manager.execute_request(
            source=ApiSource.CONGRESS,
            endpoint="/test",
            method="GET"
        )
        
        # Verify fallback to text response
        assert result == {"text": "Not JSON data"}
        
        # Verify session was properly cleaned up
        assert session.entered is True
        assert session.exited is True  # This indicates the context manager exited properly
        assert session.response_context.entered is True
        assert session.response_context.exited is True


@pytest.mark.asyncio
async def test_execute_request_json_and_text_parsing_error(auth_manager):
    """Test handling of both JSON and text parsing errors while ensuring proper session cleanup."""
    # Create a response that will fail for both json() and text()
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.headers = {"Content-Type": "application/json"}
    mock_response.json.side_effect = ValueError("Invalid JSON")
    mock_response.text.side_effect = UnicodeDecodeError("utf-8", b"\x80", 0, 1, "Invalid UTF-8")
    
    # Create our session with the problematic response
    session = CustomSessionMock(response=mock_response)
    
    # Patch aiohttp.ClientSession to return our mock
    with patch('aiohttp.ClientSession', return_value=session):
        # Execute request that will have both JSON and text parsing issues
        result = await auth_manager.execute_request(
            source=ApiSource.CONGRESS,
            endpoint="/test",
            method="GET"
        )
        
        # Verify we get an empty result but don't crash
        assert "error" in result
        
        # Verify session was properly cleaned up
        assert session.entered is True
        assert session.exited is True  # This indicates the context manager exited properly
        assert session.response_context.entered is True
        assert session.response_context.exited is True


@pytest.mark.asyncio
async def test_execute_request_content_type_handling(auth_manager):
    """Test proper handling of different content types."""
    # Create responses with different content types
    content_types = [
        "application/json", 
        "text/plain",
        "application/xml",
        "application/octet-stream",
        ""  # Empty content type
    ]
    
    # Optimize by patching rate limiter to avoid unnecessary waits
    with patch.object(auth_manager.rate_limiter, 'pre_request', return_value=None), \
         patch.object(auth_manager.rate_limiter, 'track_request', return_value=None):
        
        for content_type in content_types:
            # Create a response with the current content type
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.headers = {"Content-Type": content_type}
            
            if content_type == "application/json":
                mock_response.json.return_value = {"data": "json data"}
                mock_response.text.return_value = '{"data": "json data"}'
            else:
                mock_response.json.side_effect = ValueError("Not JSON")
                mock_response.text.return_value = "Text data"
            
            # Create session with this response
            session = CustomSessionMock(response=mock_response)
            
            # Patch aiohttp.ClientSession to return our mock
            with patch('aiohttp.ClientSession', return_value=session):
                # Execute request with this content type
                result = await auth_manager.execute_request(
                    source=ApiSource.CONGRESS,
                    endpoint="/test",
                    method="GET"
                )
                
                # Verify we got appropriate results based on content type
                if content_type == "application/json":
                    assert result == {"data": "json data"}
                else:
                    assert result == {"text": "Text data"}
                
                # Verify session was properly cleaned up
                assert session.entered is True
                assert session.exited is True  # This indicates the context manager exited properly
                assert session.response_context.entered is True
                assert session.response_context.exited is True