"""
Base API client for PyGovPub SDK.

This module provides a base class for API clients with
common functionality for authentication and request handling.
"""

from typing import Dict, List, Optional, Union, Any
import asyncio
from datetime import datetime
import logging

from pygovpub.auth.auth_manager import AuthManager
from pygovpub.auth.models import ApiSource
from pygovpub.exceptions import ApiError, CongressApiError, GovInfoApiError, AuthenticationError, RateLimitExceededError

# Configure logging
logger = logging.getLogger("pygovpub.api")

class BaseApiClient:
    """Base class for API clients."""
    
    def __init__(self, auth_manager: Optional[AuthManager] = None, api_source: ApiSource = None):
        """Initialize API client.
        
        Args:
            auth_manager: Authentication manager instance
            api_source: API source identifier
        """
        self.auth_manager = auth_manager or AuthManager()
        self.api_source = api_source
        
        # If no API source is provided, raise error
        if not self.api_source:
            raise ValueError("API source must be provided")
        
    async def execute_request(
        self,
        endpoint: str,
        method: str = "GET",
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        timeout: int = 30
    ) -> Dict[str, Any]:
        """Execute API request.
        
        Args:
            endpoint: API endpoint (without base URL)
            method: HTTP method
            params: Query parameters
            headers: HTTP headers
            json_data: JSON request body
            timeout: Request timeout in seconds
            
        Returns:
            JSON response data
            
        Raises:
            ApiError: If request fails
            AuthenticationError: If authentication fails
            RateLimitExceededError: If rate limit exceeded
        """
        try:
            response = await self.auth_manager.execute_request(
                source=self.api_source,
                endpoint=endpoint,
                method=method,
                params=params,
                headers=headers,
                json_data=json_data,
                timeout=timeout
            )
            
            return response
        except AuthenticationError as e:
            logger.error(f"Authentication error: {e}")
            raise
        except RateLimitExceededError as e:
            logger.error(f"Rate limit exceeded: {e}")
            raise
        except Exception as e:
            logger.error(f"API error: {e}")
            if self.api_source == ApiSource.CONGRESS:
                raise CongressApiError(f"Error executing request: {e}", status_code=500, endpoint=endpoint)
            elif self.api_source == ApiSource.GOVINFO:
                raise GovInfoApiError(f"Error executing request: {e}", status_code=500, endpoint=endpoint)
            else:
                raise ApiError(f"Error executing request: {e}", status_code=500, api_name="unknown", endpoint=endpoint)
            
    def validate_response(self, response: Dict[str, Any], expected_keys: List[str]) -> bool:
        """Validate API response contains expected keys.
        
        Args:
            response: API response dictionary
            expected_keys: List of expected top-level keys
            
        Returns:
            True if response is valid, False otherwise
        """
        if not isinstance(response, dict):
            return False
            
        return all(key in response for key in expected_keys)