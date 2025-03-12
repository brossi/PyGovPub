"""
Test the integration of circuit breakers with the health check system.
"""

import unittest
from unittest.mock import patch, MagicMock

from pygovpub.diagnostics.health import check_circuit_breakers, get_status_summary
from pygovpub.recovery import CircuitState


class TestCircuitBreakerHealth(unittest.TestCase):
    """Test the integration of circuit breakers with the health check system."""

    @patch('pygovpub.diagnostics.health.CircuitBreakerRegistry')
    def test_check_circuit_breakers(self, mock_registry_class):
        """Test that the circuit breaker check function returns correct information."""
        # Setup mock registry
        mock_registry = MagicMock()
        mock_registry_class.return_value = mock_registry
        
        # Mock circuit breakers (1 closed, 1 open, 1 half-open)
        mock_registry.get_all_statuses.return_value = {
            "api_client": {
                "name": "api_client",
                "state": CircuitState.CLOSED,
                "failure_count": 0,
                "last_failure": None,
                "last_attempt": "2025-03-12T12:00:00",
                "reset_time": 0
            },
            "database": {
                "name": "database",
                "state": CircuitState.OPEN,
                "failure_count": 5,
                "last_failure": "2025-03-12T11:55:00",
                "last_attempt": "2025-03-12T12:00:00",
                "reset_time": 25
            },
            "cache": {
                "name": "cache",
                "state": CircuitState.HALF_OPEN,
                "failure_count": 3,
                "last_failure": "2025-03-12T11:30:00",
                "last_attempt": "2025-03-12T12:00:00",
                "reset_time": 0
            }
        }
        
        # Call the function
        result = check_circuit_breakers()
        
        # Verify the results
        self.assertEqual(result["total_circuits"], 3)
        self.assertEqual(result["state_counts"]["closed"], 1)
        self.assertEqual(result["state_counts"]["open"], 1)
        self.assertEqual(result["state_counts"]["half_open"], 1)
        
        # Check critical circuits
        self.assertEqual(len(result["critical_circuits"]), 2)
        circuit_names = {circuit["name"] for circuit in result["critical_circuits"]}
        self.assertEqual(circuit_names, {"database", "cache"})

    def test_get_status_summary_with_circuit_breakers(self):
        """Test that the status summary function correctly considers circuit breaker status."""
        # Mock API results - all healthy
        api_results = [
            {"name": "congress", "status": "connected", "latency_ms": 150},
            {"name": "govinfo", "status": "connected", "latency_ms": 200}
        ]
        
        # Mock config results - valid
        config_results = {"valid": True}
        
        # Different circuit breaker scenarios
        
        # 1. No circuit breakers - should be healthy
        status = get_status_summary(api_results, config_results)
        self.assertEqual(status, "healthy")
        
        # 2. All circuit breakers closed - should be healthy
        circuit_breaker_results = {
            "total_circuits": 3,
            "state_counts": {"closed": 3, "open": 0, "half_open": 0},
            "critical_circuits": []
        }
        status = get_status_summary(api_results, config_results, circuit_breaker_results)
        self.assertEqual(status, "healthy")
        
        # 3. One circuit breaker half-open - should be degraded
        circuit_breaker_results = {
            "total_circuits": 3,
            "state_counts": {"closed": 2, "open": 0, "half_open": 1},
            "critical_circuits": [{"name": "cache", "state": "half_open"}]
        }
        status = get_status_summary(api_results, config_results, circuit_breaker_results)
        self.assertEqual(status, "degraded")
        
        # 4. One circuit breaker open (< 50%) - should be degraded
        circuit_breaker_results = {
            "total_circuits": 3,
            "state_counts": {"closed": 2, "open": 1, "half_open": 0},
            "critical_circuits": [{"name": "database", "state": "open"}]
        }
        status = get_status_summary(api_results, config_results, circuit_breaker_results)
        self.assertEqual(status, "degraded")
        
        # 5. More than 50% of circuit breakers open - should be unhealthy
        circuit_breaker_results = {
            "total_circuits": 3,
            "state_counts": {"closed": 1, "open": 2, "half_open": 0},
            "critical_circuits": [
                {"name": "database", "state": "open"},
                {"name": "api_client", "state": "open"}
            ]
        }
        status = get_status_summary(api_results, config_results, circuit_breaker_results)
        self.assertEqual(status, "unhealthy")
        
        # 6. API issues should take precedence over circuit breakers
        api_results_with_error = [
            {"name": "congress", "status": "error", "message": "Network error"},
            {"name": "govinfo", "status": "connected", "latency_ms": 200}
        ]
        circuit_breaker_results = {
            "total_circuits": 3,
            "state_counts": {"closed": 2, "open": 1, "half_open": 0},
            "critical_circuits": [{"name": "database", "state": "open"}]
        }
        status = get_status_summary(api_results_with_error, config_results, circuit_breaker_results)
        self.assertEqual(status, "unhealthy")


if __name__ == '__main__':
    unittest.main()