"""
Unit tests for the health diagnostics module.
"""
import json
import sys
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
import requests

from pygovpub.diagnostics.health import (
    run_health_check,
    check_api_connectivity,
    check_configuration,
    check_system_info,
    check_performance,
    get_status_summary
)
from pygovpub.exceptions import (
    AuthenticationError,
    RateLimitExceededError,
    NetworkError
)


@pytest.fixture
def mock_auth_manager():
    """Create a mock auth_manager for testing."""
    mock = MagicMock()
    mock.execute_request = MagicMock()
    
    # Set up response for a successful request
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"success": True}
    mock.execute_request.return_value = mock_response
    
    # Set up async version too
    mock.execute_request_async = AsyncMock()
    mock.execute_request_async.return_value = mock_response
    
    return mock


class TestHealthCheck:
    """Tests for health check functionality."""

    @patch("pygovpub.diagnostics.health.check_api_connectivity")
    @patch("pygovpub.diagnostics.health.check_configuration")
    @patch("pygovpub.diagnostics.health.check_system_info")
    @patch("pygovpub.diagnostics.health.check_performance")
    @patch("pygovpub.diagnostics.health.get_status_summary")
    def test_run_health_check(
        self, 
        mock_get_status_summary,
        mock_check_performance,
        mock_check_system_info,
        mock_check_configuration, 
        mock_check_api_connectivity
    ):
        """Test run_health_check function."""
        # Mock return values
        mock_check_api_connectivity.return_value = [
            {"name": "congress", "status": "connected", "latency_ms": 120},
            {"name": "govinfo", "status": "connected", "latency_ms": 150}
        ]
        mock_check_configuration.return_value = {"valid": True}
        mock_check_system_info.return_value = {"python": "3.13.2"}
        mock_check_performance.return_value = {
            "memory_usage_mb": 45.2,
            "response_times_ms": {"congress": 120, "govinfo": 150}
        }
        mock_get_status_summary.return_value = "healthy"
        
        # Run the function
        result = run_health_check()
        
        # Verify all check functions were called
        mock_check_api_connectivity.assert_called_once()
        mock_check_configuration.assert_called_once()
        mock_check_system_info.assert_called_once()
        mock_check_performance.assert_called_once()
        
        # Verify the result structure
        assert "timestamp" in result
        assert "status" in result
        assert "version" in result
        assert "apis" in result
        assert "configuration" in result
        assert "system" in result
        assert "performance" in result
        assert result["status"] == "healthy"

    @patch("pygovpub.diagnostics.health.AuthManager")
    @pytest.mark.asyncio
    async def test_check_api_connectivity_success(self, mock_auth_manager_cls, mock_auth_manager):
        """Test check_api_connectivity with successful connections."""
        # Set up mock auth manager
        mock_auth_manager_cls.return_value = mock_auth_manager
        
        # Run the function
        result = await check_api_connectivity()
        
        # Verify execute_request was called for both APIs
        assert mock_auth_manager.execute_request_async.call_count == 2
        
        # Verify the result structure
        assert len(result) == 2
        assert result[0]["name"] in ["congress", "govinfo"]
        assert result[1]["name"] in ["congress", "govinfo"]
        assert result[0]["status"] == "connected"
        assert result[1]["status"] == "connected"
        assert "latency_ms" in result[0]
        assert "latency_ms" in result[1]

    @patch("pygovpub.diagnostics.health.AuthManager")
    @pytest.mark.asyncio
    async def test_check_api_connectivity_auth_error(self, mock_auth_manager_cls, mock_auth_manager):
        """Test check_api_connectivity with authentication error."""
        # Set up mock auth manager
        mock_auth_manager_cls.return_value = mock_auth_manager
        
        # Mock execute_request to raise AuthenticationError for the first API
        mock_auth_manager.execute_request_async.side_effect = [
            AuthenticationError("Invalid API key"),
            MagicMock(status_code=200, json=lambda: {"success": True})
        ]
        
        # Run the function
        result = await check_api_connectivity()
        
        # Verify the result structure
        assert len(result) == 2
        assert result[0]["status"] == "error"
        assert "message" in result[0]
        assert "Invalid API key" in result[0]["message"]
        assert result[1]["status"] == "connected"

    @patch("pygovpub.diagnostics.health.AuthManager")
    @pytest.mark.asyncio
    async def test_check_api_connectivity_rate_limit(self, mock_auth_manager_cls, mock_auth_manager):
        """Test check_api_connectivity with rate limit error."""
        # Set up mock auth manager
        mock_auth_manager_cls.return_value = mock_auth_manager
        
        # Mock execute_request to raise RateLimitExceededError
        mock_auth_manager.execute_request_async.side_effect = [
            RateLimitExceededError("Rate limit exceeded", retry_after=60),
            MagicMock(status_code=200, json=lambda: {"success": True})
        ]
        
        # Run the function
        result = await check_api_connectivity()
        
        # Verify the result structure
        assert len(result) == 2
        assert result[0]["status"] == "rate_limited"
        assert "retry_after" in result[0]
        assert result[0]["retry_after"] == 60
        assert result[1]["status"] == "connected"

    @patch("pygovpub.diagnostics.health.AuthManager")
    @pytest.mark.asyncio
    async def test_check_api_connectivity_network_error(self, mock_auth_manager_cls, mock_auth_manager):
        """Test check_api_connectivity with network error."""
        # Set up mock auth manager
        mock_auth_manager_cls.return_value = mock_auth_manager
        
        # Mock execute_request to raise NetworkError
        mock_auth_manager.execute_request_async.side_effect = [
            NetworkError("Connection refused"),
            MagicMock(status_code=200, json=lambda: {"success": True})
        ]
        
        # Run the function
        result = await check_api_connectivity()
        
        # Verify the result structure
        assert len(result) == 2
        assert result[0]["status"] == "error"
        assert "message" in result[0]
        assert "Connection refused" in result[0]["message"]
        assert result[1]["status"] == "connected"

    @patch("pygovpub.diagnostics.health.config")
    @patch("pygovpub.diagnostics.health.os.environ")
    def test_check_configuration_valid(self, mock_environ, mock_config):
        """Test check_configuration with valid configuration."""
        # Set up mock config
        mock_config.apis = {
            "congress": MagicMock(base_url="https://api.congress.gov/v3", api_key="valid_key"),
            "govinfo": MagicMock(base_url="https://api.govinfo.gov", api_key="valid_key")
        }
        mock_config.environment = "development"
        
        # Mock environment variables
        mock_environ.get.return_value = "development"
        mock_environ.__contains__.return_value = True  # Make 'in' operator work
        
        # Run the function
        result = check_configuration()
        
        # Verify the result structure
        assert result["valid"] is True
        assert "environment" in result
        assert result["environment"] == "development"
        assert "api_configs" in result
        assert len(result["api_configs"]) == 2
        assert "congress" in result["api_configs"]
        assert "govinfo" in result["api_configs"]
        assert result["api_configs"]["congress"]["has_api_key"] is True
        assert result["api_configs"]["govinfo"]["has_api_key"] is True

    @patch("pygovpub.diagnostics.health.config")
    @patch("pygovpub.diagnostics.health.os.environ")
    def test_check_configuration_missing_keys(self, mock_environ, mock_config):
        """Test check_configuration with missing API keys."""
        # Set up mock config with missing keys
        mock_config.apis = {
            "congress": MagicMock(base_url="https://api.congress.gov/v3", api_key=None),
            "govinfo": MagicMock(base_url="https://api.govinfo.gov", api_key="valid_key")
        }
        mock_config.environment = "development"
        
        # Mock environment variables
        mock_environ.get.return_value = "development"
        mock_environ.__contains__.return_value = True  # Make 'in' operator work
        
        # Run the function
        result = check_configuration()
        
        # Verify the result structure
        assert result["valid"] is False
        assert "issues" in result
        assert len(result["issues"]) == 1
        assert "congress" in result["issues"][0]
        assert "api_key" in result["issues"][0]
        assert result["api_configs"]["congress"]["has_api_key"] is False
        assert result["api_configs"]["govinfo"]["has_api_key"] is True

    @patch("platform.python_version")
    @patch("platform.system")
    @patch("platform.release")
    @patch("platform.machine")
    @patch("sys.version")
    def test_check_system_info(
        self, 
        mock_sys_version, 
        mock_machine, 
        mock_release, 
        mock_system, 
        mock_python_version
    ):
        """Test check_system_info."""
        # Set up mocks
        mock_python_version.return_value = "3.13.2"
        mock_system.return_value = "Darwin"
        mock_release.return_value = "23.4.0"
        mock_machine.return_value = "arm64"
        mock_sys_version = "3.13.2 (main, Mar  7 2025, 17:45:01) [Clang 15.0.0 (clang-1500.0.40.1)]"
        
        # Run the function
        result = check_system_info()
        
        # Verify the result structure
        assert "python_version" in result
        assert result["python_version"] == "3.13.2"
        assert "os" in result
        assert result["os"]["system"] == "Darwin"
        assert result["os"]["release"] == "23.4.0"
        assert result["os"]["machine"] == "arm64"
        assert "packages" in result
        assert "pygovpub" in result["packages"]
        
    @patch("pygovpub.diagnostics.health.AuthManager")
    @pytest.mark.asyncio
    async def test_check_performance(self, mock_auth_manager_cls, mock_auth_manager):
        """Test check_performance."""
        # Set up mock auth manager
        mock_auth_manager_cls.return_value = mock_auth_manager
        
        # Run the function
        result = await check_performance()
        
        # Verify the result structure
        assert "memory_usage_mb" in result
        assert "cpu_percent" in result
        assert "response_times_ms" in result
        assert "congress" in result["response_times_ms"]
        assert "govinfo" in result["response_times_ms"]
        
    def test_get_status_summary_all_healthy(self):
        """Test get_status_summary with all checks healthy."""
        # Create test data with all healthy checks
        api_results = [
            {"name": "congress", "status": "connected", "latency_ms": 120},
            {"name": "govinfo", "status": "connected", "latency_ms": 150}
        ]
        config_results = {"valid": True}
        
        # Get status summary
        status = get_status_summary(api_results, config_results)
        
        # Verify the status is healthy
        assert status == "healthy"
        
    def test_get_status_summary_api_error(self):
        """Test get_status_summary with API error."""
        # Create test data with API error
        api_results = [
            {"name": "congress", "status": "error", "message": "Connection refused"},
            {"name": "govinfo", "status": "connected", "latency_ms": 150}
        ]
        config_results = {"valid": True}
        
        # Get status summary
        status = get_status_summary(api_results, config_results)
        
        # Verify the status is unhealthy
        assert status == "unhealthy"
        
    def test_get_status_summary_config_error(self):
        """Test get_status_summary with configuration error."""
        # Create test data with configuration error
        api_results = [
            {"name": "congress", "status": "connected", "latency_ms": 120},
            {"name": "govinfo", "status": "connected", "latency_ms": 150}
        ]
        config_results = {"valid": False, "issues": ["Missing API key for congress"]}
        
        # Get status summary
        status = get_status_summary(api_results, config_results)
        
        # Verify the status is unhealthy
        assert status == "unhealthy"
        
    def test_get_status_summary_rate_limit(self):
        """Test get_status_summary with rate limit."""
        # Create test data with rate limit
        api_results = [
            {"name": "congress", "status": "rate_limited", "retry_after": 60},
            {"name": "govinfo", "status": "connected", "latency_ms": 150}
        ]
        config_results = {"valid": True}
        
        # Get status summary
        status = get_status_summary(api_results, config_results)
        
        # Verify the status is degraded
        assert status == "degraded"
        
    def test_get_status_summary_both_apis_unavailable(self):
        """Test get_status_summary with both APIs unavailable."""
        # Create test data with both APIs unavailable
        api_results = [
            {"name": "congress", "status": "error", "message": "Connection refused"},
            {"name": "govinfo", "status": "error", "message": "Timeout"}
        ]
        config_results = {"valid": True}
        
        # Get status summary
        status = get_status_summary(api_results, config_results)
        
        # Verify the status is critical
        assert status == "critical"