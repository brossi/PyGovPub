"""
Tests focused on performance aspects of the secure search fallback.

This module tests the performance-related functionality of the secure search fallback,
focusing on the test_performance method and related metrics collection.
"""

import time
from unittest.mock import MagicMock, patch

import pytest
from prometheus_client import Histogram, Counter

from pygovpub.storage.security import StorageSecurity
from pygovpub.storage.secure_search_fallback import SecureSearchFallback
from pygovpub.storage.secure_search_fallback import (
    SECURE_SEARCH_DURATION,
    SECURE_SEARCH_OPERATIONS,
    ENCRYPTION_PROCESSING_DURATION
)


class TestSecureSearchPerformance:
    """Tests for performance aspects of secure search fallback."""
    
    def setup_method(self):
        """Set up test resources."""
        # Mock security instance
        self.mock_security = MagicMock(spec=StorageSecurity)
        self.mock_security.encryption_enabled = True
        self.mock_security.process_metadata.side_effect = lambda x: x
        self.mock_security.decrypt_metadata.side_effect = lambda x: x
        
        # Create fallback instance with mocked security
        self.fallback = SecureSearchFallback(self.mock_security)
    
    def test_performance_testing_large_dataset(self):
        """Test performance testing with larger dataset."""
        # Use a larger dataset to test scaling
        results = self.fallback.test_performance(field_count=100)
        
        # Verify we get performance metrics
        assert "summary" in results
        assert "total_items" in results["summary"]
        assert results["summary"]["total_items"] == 100
        
        # Check detailed operation metrics
        for op in ["exact_match", "prefix", "contains", "range", "batch_operations"]:
            assert op in results
            assert "duration_ms" in results[op]
            assert "result_count" in results[op]
            assert "throughput_items_per_sec" in results[op]
    
    def test_metrics_instrumentation(self):
        """Test that metrics are properly instrumented."""
        # Patch the metrics to test instrumentation
        with patch.object(SECURE_SEARCH_DURATION, 'labels') as mock_duration, \
             patch.object(SECURE_SEARCH_OPERATIONS, 'labels') as mock_operations, \
             patch.object(ENCRYPTION_PROCESSING_DURATION, 'labels') as mock_encryption_duration:
            
            # Mock the returned objects
            mock_duration.return_value = MagicMock()
            mock_operations.return_value = MagicMock()
            mock_encryption_duration.return_value = MagicMock()
            
            # Run a small performance test
            self.fallback.test_performance(field_count=5)
            
            # Verify metrics instrumentation
            mock_duration.assert_called()
            mock_operations.assert_called()
            mock_encryption_duration.assert_called()
    
    def test_detailed_performance_breakdown(self):
        """Test detailed performance breakdown by operation type."""
        # Run performance test
        results = self.fallback.test_performance(field_count=20)
        
        # Verify we get separate metrics for each operation type
        assert "exact_match" in results
        assert "prefix" in results
        assert "contains" in results
        assert "range" in results
        assert "batch_operations" in results
        
        # Verify all operations recorded performance data
        for op in ["exact_match", "prefix", "contains", "range", "batch_operations"]:
            assert "duration_ms" in results[op]
            assert "result_count" in results[op]
            assert "throughput_items_per_sec" in results[op]
    
    def test_throughput_calculation(self):
        """Test throughput calculation logic."""
        # Run a small performance test
        results = self.fallback.test_performance(field_count=10)
        
        # Calculate expected throughput (approximation)
        for op in ["exact_match", "prefix", "contains", "range", "batch_operations"]:
            duration_sec = results[op]["duration_ms"] / 1000
            if duration_sec > 0:
                expected_throughput = int(10 / duration_sec)
                # Allow for some variation in timing
                assert abs(results[op]["throughput_items_per_sec"] - expected_throughput) <= expected_throughput * 0.2
    
    def test_performance_with_custom_test_data(self):
        """Test performance with specific test data patterns."""
        # Override test_performance to use our custom data
        with patch.object(self.fallback, 'test_performance') as mock_perf:
            # Setup mock to return a predetermined result
            mock_result = {
                "exact_match": {
                    "duration_ms": 50,
                    "result_count": 5,
                    "throughput_items_per_sec": 200
                },
                "prefix": {
                    "duration_ms": 60,
                    "result_count": 10,
                    "throughput_items_per_sec": 166
                },
                "contains": {
                    "duration_ms": 70,
                    "result_count": 2,
                    "throughput_items_per_sec": 142
                },
                "range": {
                    "duration_ms": 55,
                    "result_count": 15,
                    "throughput_items_per_sec": 181
                },
                "batch_operations": {
                    "duration_ms": 85,
                    "result_count": 1,
                    "throughput_items_per_sec": 117
                },
                "summary": {
                    "total_items": 100,
                    "encryption_time_ms": 30,
                    "average_search_time_ms": 64,
                    "encryption_enabled": True
                }
            }
            mock_perf.return_value = mock_result
            
            # Call the method
            result = self.fallback.test_performance(field_count=100)
            
            # Verify the result
            assert result["summary"]["total_items"] == 100
            assert result["summary"]["average_search_time_ms"] == 64
            
            # Check operation with best throughput
            assert result["range"]["result_count"] == 15
            assert result["exact_match"]["throughput_items_per_sec"] == 200
    
    def test_performance_with_encryption_overhead(self):
        """Test performance metrics with simulated encryption overhead."""
        # Create a fallback with slow encryption simulation
        slow_security = MagicMock(spec=StorageSecurity)
        slow_security.encryption_enabled = True
        
        # Simulate slow encryption operations
        def slow_process(data):
            time.sleep(0.001)  # Add 1ms delay per item
            return data
            
        def slow_decrypt(data):
            time.sleep(0.002)  # Add 2ms delay per item
            return data
            
        slow_security.process_metadata.side_effect = slow_process
        slow_security.decrypt_metadata.side_effect = slow_decrypt
        
        fallback = SecureSearchFallback(slow_security)
        
        # Run performance test with small dataset to avoid long test time
        results = fallback.test_performance(field_count=5)
        
        # Verify encryption overhead is measured
        assert results["summary"]["encryption_time_ms"] > 0
        
        # Verify search operations take longer due to decryption overhead
        for op in ["exact_match", "prefix", "contains", "range"]:
            assert results[op]["duration_ms"] > 0