"""
Integration tests for auth module.

These tests cover end-to-end functionality and interactions between
components in the auth module.
"""

import pytest
import os
import json
import asyncio
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from unittest import mock
from aioresponses import aioresponses

from pygovpub.auth.auth_manager import AuthManager
from pygovpub.auth.models import ApiSource, AuthType, ApiConfiguration
from pygovpub.exceptions import (
    AuthenticationError, RateLimitExceededError
)


@pytest.mark.asyncio
async def test_auth_manager_with_rate_limiter():
    """Test integration between AuthManager and RateLimiter."""
    # This tests lines 348-351

    # Testing the integration between AuthManager and RateLimiter
    # Create AuthManager with API key
    manager = AuthManager()
    manager.add_key(ApiSource.CONGRESS, "test_key_123")

    # Set up a rate limit exceeded situation
    with mock.patch.object(manager.rate_limiter, 'pre_request') as mock_pre_request:
        # Configure mock to raise Exception that should be caught and converted to RateLimitExceededError
        mock_pre_request.side_effect = Exception("Rate limit exceeded")

        # Attempt to execute a request
        with pytest.raises(RateLimitExceededError):
            await manager.execute_request(
                source=ApiSource.CONGRESS,
                endpoint="/test",
                method="GET"
            )

    # Verify rate limiter was used by AuthManager
    assert hasattr(manager, 'rate_limiter')


@pytest.mark.asyncio
async def test_end_to_end_auth_flow():
    """Test the complete authentication flow."""
    # This tests lines 392-404

    # Set up test environment with API key
    os.environ["CONGRESS_GOV_API_KEY"] = "test_env_key"

    try:
        # Create manager which should load the key from environment
        manager = AuthManager()

        with aioresponses() as mocked:
            # Mock the response
            mocked.get(
                'https://api.congress.gov/v3/test',
                status=200,
                payload={"data": "success"},
                headers={"Content-Type": "application/json"}
            )

            # Execute request (should use key from environment)
            result = await manager.execute_request(
                source=ApiSource.CONGRESS,
                endpoint="/test"
            )

            # Verify result
            assert result == {"data": "success"}

    finally:
        # Clean up environment
        os.environ.pop("CONGRESS_GOV_API_KEY", None)
