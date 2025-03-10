"""
Memory usage testing for PyGovPub.

This module contains tests to monitor memory usage of core operations.
"""

import os
import psutil
import pytest
from fastapi.testclient import TestClient

# Maximum allowed memory usage in MB
MAX_MEMORY_THRESHOLD = 50  # MB


def get_memory_usage():
    """Get current memory usage in MB."""
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / 1024 / 1024  # Convert to MB


# Comment out the @profile decorator when not running with memory_profiler
# @profile
def test_memory_usage_api_client():
    """Test memory usage for core API client operations."""
    from pygovpub.auth.auth_manager import AuthManager
    
    # Create an auth manager
    auth_manager = AuthManager()
    
    # Measure memory usage
    initial_memory = get_memory_usage()
    
    # Perform some operations
    auth_manager.add_api_key("congress", "test_key")
    auth_manager.add_api_key("govinfo", "test_key")
    
    # Generate some data
    for i in range(1000):
        auth_manager.get_api_key("congress")
        auth_manager.get_api_key("govinfo")
    
    # Measure memory usage again
    final_memory = get_memory_usage()
    memory_increase = final_memory - initial_memory
    
    print(f"Memory usage increased by {memory_increase:.2f} MB")
    assert memory_increase < MAX_MEMORY_THRESHOLD


# Comment out the @profile decorator when not running with memory_profiler
# @profile
def test_memory_usage_response_model():
    """Test memory usage for response models."""
    from pygovpub.models.response import ApiResponse
    from pygovpub.auth.models import ApiSource
    
    # Measure memory usage
    initial_memory = get_memory_usage()
    
    # Generate a large number of response objects
    responses = []
    for i in range(1000):
        response = ApiResponse.from_data(
            data=[{"id": j, "name": f"Item {j}"} for j in range(100)],
            source=ApiSource.INTERNAL,
            total_count=100,
            count=100,
            offset=0
        )
        responses.append(response)
    
    # Measure memory usage again
    final_memory = get_memory_usage()
    memory_increase = final_memory - initial_memory
    
    print(f"Memory usage increased by {memory_increase:.2f} MB")
    assert memory_increase < MAX_MEMORY_THRESHOLD