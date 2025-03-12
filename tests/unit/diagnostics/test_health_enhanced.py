"""
Enhanced tests for the health check module.

This module provides additional tests to improve coverage for the health check
functionality, particularly focusing on the circuit breaker integration.
"""

import unittest
import asyncio
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock, AsyncMock

from pygovpub.diagnostics.health import (
    check_api_connectivity,
    check_configuration,
    check_system_info,
    check_performance,
    check_circuit_breakers,
    get_status_summary,
    run_health_check
)
from pygovpub.recovery import CircuitState


class TestHealthEnhanced(unittest.TestCase):
    """Enhanced tests for the health check module."""

    def test_check_circuit_breakers_empty(self):
        """Test circuit breaker check with empty registry."""
        with patch('pygovpub.diagnostics.health.CircuitBreakerRegistry') as mock_registry_class:
            # Mock an empty registry (no circuit breakers)
            mock_registry = MagicMock()
            mock_registry_class.return_value = mock_registry
            mock_registry.get_all_statuses.return_value = {}
            
            # Call the function
            result = check_circuit_breakers()
            
            # Verify the result structure with empty data
            assert result["total_circuits"] == 0
            assert result["state_counts"]["closed"] == 0
            assert result["state_counts"]["open"] == 0
            assert result["state_counts"]["half_open"] == 0
            assert result["critical_circuits"] == []
    
    def test_get_status_summary_rate_limit_and_circuit_breakers(self):
        """Test status summary with both rate limits and circuit breakers."""
        # API results with rate limiting
        api_results = [
            {"name": "congress", "status": "rate_limited", "message": "Too many requests", "retry_after": 30},
            {"name": "govinfo", "status": "connected", "latency_ms": 200}
        ]
        
        # Configuration valid
        config_results = {"valid": True}
        
        # Circuit breakers with an open circuit
        circuit_breaker_results = {
            "total_circuits": 3,
            "state_counts": {"closed": 2, "open": 1, "half_open": 0},
            "critical_circuits": [{"name": "database", "state": "open"}]
        }
        
        # Get status summary
        status = get_status_summary(api_results, config_results, circuit_breaker_results)
        
        # Should be degraded due to both rate limit and open circuit
        assert status == "degraded"
    
    def test_get_status_summary_multiple_circuit_states(self):
        """Test status summary with multiple circuit breaker states."""
        # API results all good
        api_results = [
            {"name": "congress", "status": "connected", "latency_ms": 150},
            {"name": "govinfo", "status": "connected", "latency_ms": 200}
        ]
        
        # Configuration valid
        config_results = {"valid": True}
        
        # Circuit breakers with various states (60% open)
        circuit_breaker_results = {
            "total_circuits": 5,
            "state_counts": {"closed": 2, "open": 3, "half_open": 0},
            "critical_circuits": [
                {"name": "database", "state": "open"},
                {"name": "cache", "state": "open"},
                {"name": "api_client", "state": "open"}
            ]
        }
        
        # Get status summary
        status = get_status_summary(api_results, config_results, circuit_breaker_results)
        
        # Should be unhealthy due to >50% open circuits
        assert status == "unhealthy"
    
    @patch('pygovpub.diagnostics.health.asyncio.new_event_loop')
    @patch('pygovpub.diagnostics.health.check_api_connectivity')
    @patch('pygovpub.diagnostics.health.check_configuration')
    @patch('pygovpub.diagnostics.health.check_system_info')
    @patch('pygovpub.diagnostics.health.check_performance')
    @patch('pygovpub.diagnostics.health.check_circuit_breakers')
    @patch('pygovpub.diagnostics.health.get_status_summary')
    @patch('pygovpub.diagnostics.health.__version__', '1.0.0')
    @patch('pygovpub.diagnostics.health.datetime')
    def test_run_health_check_with_circuit_breakers(
        self, mock_datetime, mock_get_status_summary, mock_check_circuit_breakers,
        mock_check_performance, mock_check_system_info, mock_check_configuration,
        mock_check_api_connectivity, mock_new_event_loop
    ):
        """Test the run_health_check function with circuit breakers."""
        # Setup mocks
        mock_loop = MagicMock()
        mock_new_event_loop.return_value = mock_loop
        
        # Mock return values
        mock_datetime.now.return_value = datetime(2025, 3, 12, 12, 0, 0, tzinfo=timezone.utc)
        mock_check_api_connectivity_result = [{"name": "test_api", "status": "connected"}]
        mock_check_configuration_result = {"valid": True}
        mock_check_system_info_result = {"python_version": "3.11.0"}
        mock_check_performance_result = {"memory_usage_mb": 100}
        mock_check_circuit_breakers_result = {
            "total_circuits": 3,
            "state_counts": {"closed": 3, "open": 0, "half_open": 0},
            "critical_circuits": []
        }
        mock_get_status_summary.return_value = "healthy"
        
        # Configure the mocks
        mock_loop.run_until_complete.side_effect = [
            mock_check_api_connectivity_result,
            mock_check_performance_result
        ]
        mock_check_configuration.return_value = mock_check_configuration_result
        mock_check_system_info.return_value = mock_check_system_info_result
        mock_check_circuit_breakers.return_value = mock_check_circuit_breakers_result
        
        # Run the health check
        result = run_health_check()
        
        # Verify all expected components were called
        mock_check_api_connectivity.assert_called_once()
        mock_check_configuration.assert_called_once()
        mock_check_system_info.assert_called_once()
        mock_check_performance.assert_called_once()
        mock_check_circuit_breakers.assert_called_once()
        
        # Verify the result structure
        assert result["timestamp"] == "2025-03-12T12:00:00+00:00"
        assert result["status"] == "healthy"
        assert result["version"] == "1.0.0"
        assert result["apis"] == mock_check_api_connectivity_result
        assert result["configuration"] == mock_check_configuration_result
        assert result["system"] == mock_check_system_info_result
        assert result["performance"] == mock_check_performance_result
        assert result["circuit_breakers"] == mock_check_circuit_breakers_result
        
        # Verify get_status_summary was called with circuit breakers
        mock_get_status_summary.assert_called_once_with(
            mock_check_api_connectivity_result, 
            mock_check_configuration_result,
            mock_check_circuit_breakers_result
        )
        
        # Verify loop was closed
        mock_loop.close.assert_called_once()


if __name__ == '__main__':
    unittest.main()