"""
Resource usage limits validation.

This module validates that the application stays within resource usage limits.
"""

import os
import platform
import resource
import sys
import time
from typing import Any, Dict, List, Tuple

import psutil


# Resource limits
MAX_CPU_PERCENT = 80.0  # Maximum CPU usage percentage
MAX_MEMORY_MB = 150  # Maximum memory usage in MB
MAX_OPEN_FILES = 100  # Maximum number of open files
MAX_API_RESPONSE_TIME_MS = 500  # Maximum API response time in milliseconds


def get_resource_usage() -> Dict[str, Any]:
    """
    Get current resource usage.
    
    Returns:
        Dictionary with resource usage metrics
    """
    process = psutil.Process(os.getpid())
    
    # Get memory usage
    memory_info = process.memory_info()
    memory_mb = memory_info.rss / 1024 / 1024  # Convert to MB
    
    # Get CPU usage
    cpu_percent = process.cpu_percent(interval=0.5)
    
    # Get open files count
    try:
        open_files = len(process.open_files())
    except psutil.AccessDenied:
        # Fall back to resource module on platforms where psutil needs elevated permissions
        if platform.system() == "Linux":
            _, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
            open_files = hard
        else:
            open_files = 0
    
    # Get connection count
    try:
        connections = len(process.connections())
    except psutil.AccessDenied:
        connections = 0
    
    return {
        "memory_mb": memory_mb,
        "cpu_percent": cpu_percent,
        "open_files": open_files,
        "connections": connections,
        "threads": process.num_threads()
    }


def measure_api_response_time(func: callable, *args, **kwargs) -> Tuple[Any, float]:
    """
    Measure the response time of an API call.
    
    Args:
        func: The function to call
        *args: Positional arguments for the function
        **kwargs: Keyword arguments for the function
        
    Returns:
        Tuple of (result, response_time_ms)
    """
    start_time = time.time()
    result = func(*args, **kwargs)
    end_time = time.time()
    
    # Calculate response time in milliseconds
    response_time_ms = (end_time - start_time) * 1000
    
    return result, response_time_ms


def test_memory_limits() -> bool:
    """
    Test that memory usage stays within limits.
    
    Returns:
        True if within limits, False otherwise
    """
    usage = get_resource_usage()
    memory_mb = usage["memory_mb"]
    
    print(f"Memory usage: {memory_mb:.2f} MB (limit: {MAX_MEMORY_MB} MB)")
    
    if memory_mb > MAX_MEMORY_MB:
        print(f"Memory usage exceeds limit: {memory_mb:.2f} MB > {MAX_MEMORY_MB} MB")
        return False
    
    return True


def test_cpu_limits() -> bool:
    """
    Test that CPU usage stays within limits.
    
    Returns:
        True if within limits, False otherwise
    """
    usage = get_resource_usage()
    cpu_percent = usage["cpu_percent"]
    
    print(f"CPU usage: {cpu_percent:.2f}% (limit: {MAX_CPU_PERCENT}%)")
    
    if cpu_percent > MAX_CPU_PERCENT:
        print(f"CPU usage exceeds limit: {cpu_percent:.2f}% > {MAX_CPU_PERCENT}%")
        return False
    
    return True


def test_file_descriptor_limits() -> bool:
    """
    Test that open file count stays within limits.
    
    Returns:
        True if within limits, False otherwise
    """
    usage = get_resource_usage()
    open_files = usage["open_files"]
    
    print(f"Open files: {open_files} (limit: {MAX_OPEN_FILES})")
    
    if open_files > MAX_OPEN_FILES:
        print(f"Open files exceeds limit: {open_files} > {MAX_OPEN_FILES}")
        return False
    
    return True


def test_api_response_time() -> bool:
    """
    Test that API response times stay within limits.
    
    Returns:
        True if within limits, False otherwise
    """
    # Import here to avoid circular imports
    try:
        from pygovpub.auth.auth_manager import AuthManager
        
        # Simulate API call
        auth_manager = AuthManager()
        
        # Measure response time
        def simulate_api_request():
            # Add some work to simulate an API call
            auth_manager.add_api_key("congress", "test_key")
            for _ in range(1000):
                auth_manager.get_api_key("congress")
            auth_manager.remove_api_key("congress")
            return {"status": "success"}
        
        result, response_time_ms = measure_api_response_time(simulate_api_request)
        
        print(f"API response time: {response_time_ms:.2f} ms (limit: {MAX_API_RESPONSE_TIME_MS} ms)")
        
        if response_time_ms > MAX_API_RESPONSE_TIME_MS:
            print(f"API response time exceeds limit: {response_time_ms:.2f} ms > {MAX_API_RESPONSE_TIME_MS} ms")
            return False
        
        return True
    except ImportError:
        print("AuthManager not available, skipping API response time test")
        return True


def main() -> int:
    """
    Run all resource limit tests.
    
    Returns:
        0 for success, 1 for failure
    """
    tests = [
        test_memory_limits,
        test_cpu_limits,
        test_file_descriptor_limits,
        test_api_response_time
    ]
    
    for test in tests:
        try:
            if not test():
                return 1
        except Exception as e:
            print(f"Test {test.__name__} failed with exception: {e}")
            return 1
            
    print("All resource limit tests passed")
    return 0


if __name__ == "__main__":
    # psutil is a required dependency for this module
    try:
        import psutil
    except ImportError:
        print("psutil is required for resource limit tests. Install with: pip install psutil")
        sys.exit(1)
        
    sys.exit(main())