"""
Test secure communications for PyGovPub.

These tests verify secure communication practices including HTTPS enforcement,
secure header transmission, and proper credential handling during API communications.
"""

import os
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

import aiohttp
from aiohttp import ClientResponseError

from pygovpub.auth.auth_manager import AuthManager
from pygovpub.auth.models import ApiSource, AuthType
from pygovpub.exceptions import AuthenticationError


class TestApiCommunicationSecurity:
    """Test API communication security."""

    def test_https_url_enforcement(self):
        """Test that all API URLs use HTTPS."""
        auth_manager = AuthManager()
        
        # Verify Congress.gov URL
        congress_config = auth_manager._get_auth_config(ApiSource.CONGRESS)
        assert congress_config["base_url"].startswith("https://")
        assert "http://" not in congress_config["base_url"]
        
        # Verify GovInfo.gov URL
        govinfo_config = auth_manager._get_auth_config(ApiSource.GOVINFO)
        assert govinfo_config["base_url"].startswith("https://")
        assert "http://" not in govinfo_config["base_url"]

    def test_authenticate_request_security(self):
        """Test security of authenticate_request method."""
        auth_manager = AuthManager()
        auth_manager.add_key(ApiSource.CONGRESS, "test-congress-key")
        auth_manager.add_key(ApiSource.GOVINFO, "test-govinfo-key")
        
        # Test Congress.gov request (header-based auth)
        congress_req = auth_manager.authenticate_request(
            source=ApiSource.CONGRESS,
            endpoint="/bills",
            params={"limit": 10}
        )
        
        # Verify URL is HTTPS
        assert congress_req["url"].startswith("https://")
        
        # Verify auth in header
        assert "X-API-Key" in congress_req["headers"]
        assert congress_req["headers"]["X-API-Key"] == "test-congress-key"
        
        # Verify params don't contain API key
        assert "X-API-Key" not in congress_req["params"]
        assert "api_key" not in congress_req["params"]
        
        # Test GovInfo.gov request (parameter-based auth)
        govinfo_req = auth_manager.authenticate_request(
            source=ApiSource.GOVINFO,
            endpoint="/packages",
            params={"offset": 0}
        )
        
        # Verify URL is HTTPS
        assert govinfo_req["url"].startswith("https://")
        
        # Verify auth in params
        assert "api_key" in govinfo_req["params"]
        assert govinfo_req["params"]["api_key"] == "test-govinfo-key"
        
        # Verify headers don't contain API key
        assert "X-API-Key" not in govinfo_req["headers"]


class TestApiSecurityHandling:
    """Test API security handling in requests and responses."""

    @patch("aiohttp.ClientSession.request")
    async def test_auth_error_handling(self, mock_request):
        """Test handling of authentication errors."""
        # Setup mock for 401 response
        mock_response = AsyncMock()
        mock_response.status = 401
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.raise_for_status = AsyncMock(side_effect=ClientResponseError(
            request_info=MagicMock(),
            history=(),
            status=401,
            message="Unauthorized"
        ))
        mock_response.text = AsyncMock(return_value='{"error": "Unauthorized"}')
        
        # Setup request mock
        mock_request.return_value.__aenter__.return_value = mock_response
        
        # Setup auth manager
        auth_manager = AuthManager()
        auth_manager.add_key(ApiSource.CONGRESS, "invalid-key")
        
        # Test authentication error is properly raised
        with pytest.raises(AuthenticationError) as exc_info:
            await auth_manager.execute_request(
                source=ApiSource.CONGRESS,
                endpoint="/bills"
            )
        
        # Verify error message
        assert "Authentication failed: 401" in str(exc_info.value)

    @patch("aiohttp.ClientSession.request")
    async def test_header_security(self, mock_request):
        """Test secure header handling."""
        # Setup mock response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"data": "test"})
        mock_response.headers = {"Content-Type": "application/json"}
        
        # Setup request mock
        mock_request.return_value.__aenter__.return_value = mock_response
        
        # Setup auth manager
        auth_manager = AuthManager()
        auth_manager.add_key(ApiSource.CONGRESS, "test-congress-key")
        
        # Add custom security headers
        custom_headers = {
            "User-Agent": "PyGovPub/1.0",
            "X-Security-Header": "SecureValue"
        }
        
        # Execute request with custom headers
        await auth_manager.execute_request(
            source=ApiSource.CONGRESS,
            endpoint="/bills",
            headers=custom_headers
        )
        
        # Verify headers were properly passed
        call_kwargs = mock_request.call_args[1]
        assert call_kwargs["headers"]["User-Agent"] == "PyGovPub/1.0"
        assert call_kwargs["headers"]["X-Security-Header"] == "SecureValue"
        assert call_kwargs["headers"]["X-API-Key"] == "test-congress-key"
        
        # Verify URL is HTTPS
        assert call_kwargs["url"].startswith("https://")


class TestAPIClientAuthentication:
    """Test API client authentication flows."""

    @patch("aiohttp.ClientSession.request")
    async def test_api_key_not_exposed_in_logs(self, mock_request):
        """Test that API keys are not exposed in logs or errors."""
        # Setup mock response that will raise an exception
        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.raise_for_status = AsyncMock(side_effect=ClientResponseError(
            request_info=MagicMock(),
            history=(),
            status=500,
            message="Server Error"
        ))
        
        # Setup request mock
        mock_request.return_value.__aenter__.return_value = mock_response
        
        # Setup auth manager
        auth_manager = AuthManager()
        auth_manager.add_key(ApiSource.CONGRESS, "super-secret-key-12345")
        
        # Execute request that will fail
        with pytest.raises(Exception) as exc_info:
            with patch("logging.Logger.error") as mock_log_error:
                await auth_manager.execute_request(
                    source=ApiSource.CONGRESS,
                    endpoint="/bills"
                )
        
        # Verify API key is not in exception message
        assert "super-secret-key" not in str(exc_info.value)
        
        # Verify API key is not in logs
        for call in mock_log_error.call_args_list:
            assert "super-secret-key" not in str(call)

    @patch("aiohttp.ClientSession.request")
    async def test_credential_storage_security(self, mock_request):
        """Test secure storage of credentials during requests."""
        # Setup mock successful response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"data": "test"})
        mock_response.headers = {"Content-Type": "application/json"}
        
        # Setup request mock
        mock_request.return_value.__aenter__.return_value = mock_response
        
        # Setup auth manager
        auth_manager = AuthManager()
        auth_manager.add_key(ApiSource.CONGRESS, "test-congress-key")
        
        # Execute request
        await auth_manager.execute_request(
            source=ApiSource.CONGRESS,
            endpoint="/bills"
        )
        
        # Verify no plaintext API key in request
        request_args = mock_request.call_args[1]
        
        # API key should not be in URL
        assert "test-congress-key" not in request_args["url"]
        
        # API key should only be in headers, not visible in params or elsewhere
        for param, value in request_args["params"].items():
            assert "test-congress-key" != value