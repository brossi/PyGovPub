"""
Unit tests for resource limit validation.

Tests the functionality for validating resource usage limits.
"""

import pytest
from unittest.mock import patch, MagicMock

from pygovpub.validation.test_resource_limits import (
    get_resource_usage,
    measure_api_response_time,
    test_memory_limits,
    test_cpu_limits,
    test_file_descriptor_limits,
    test_api_response_time,
    main,
    MAX_MEMORY_MB,
    MAX_CPU_PERCENT,
    MAX_OPEN_FILES,
    MAX_API_RESPONSE_TIME_MS
)


class TestResourceLimits:
    """Tests for resource limit validation."""
    
    def test_get_resource_usage(self):
        """Test getting resource usage."""
        # Mock psutil.Process
        mock_process = MagicMock()
        mock_process.memory_info.return_value.rss = 100 * 1024 * 1024  # 100 MB
        mock_process.cpu_percent.return_value = 50.0
        mock_process.open_files.return_value = ["file1", "file2"]
        mock_process.connections.return_value = ["conn1", "conn2"]
        mock_process.num_threads.return_value = 5
        
        with patch("psutil.Process", return_value=mock_process):
            # Get resource usage
            usage = get_resource_usage()
            
            # Verify values
            assert usage["memory_mb"] == 100.0
            assert usage["cpu_percent"] == 50.0
            assert usage["open_files"] == 2
            assert usage["connections"] == 2
            assert usage["threads"] == 5
    
    def test_get_resource_usage_with_access_denied(self):
        """Test getting resource usage when psutil.AccessDenied is raised."""
        # Mock psutil.Process
        mock_process = MagicMock()
        mock_process.memory_info.return_value.rss = 100 * 1024 * 1024  # 100 MB
        mock_process.cpu_percent.return_value = 50.0
        mock_process.open_files.side_effect = pytest.importorskip("psutil").AccessDenied()
        mock_process.connections.side_effect = pytest.importorskip("psutil").AccessDenied()
        mock_process.num_threads.return_value = 5
        
        # Mock platform.system to return "Linux"
        with patch("psutil.Process", return_value=mock_process):
            with patch("platform.system", return_value="Linux"):
                with patch("resource.getrlimit", return_value=(0, 1024)):
                    # Get resource usage
                    usage = get_resource_usage()
                    
                    # Verify values
                    assert usage["memory_mb"] == 100.0
                    assert usage["cpu_percent"] == 50.0
                    assert usage["open_files"] == 1024  # Hard limit from resource.getrlimit
                    assert usage["connections"] == 0  # Default when AccessDenied
                    assert usage["threads"] == 5
    
    def test_get_resource_usage_non_linux(self):
        """Test getting resource usage on non-Linux platform with AccessDenied."""
        # Mock psutil.Process
        mock_process = MagicMock()
        mock_process.memory_info.return_value.rss = 100 * 1024 * 1024  # 100 MB
        mock_process.cpu_percent.return_value = 50.0
        mock_process.open_files.side_effect = pytest.importorskip("psutil").AccessDenied()
        mock_process.connections.side_effect = pytest.importorskip("psutil").AccessDenied()
        mock_process.num_threads.return_value = 5
        
        # Mock platform.system to return "Windows"
        with patch("psutil.Process", return_value=mock_process):
            with patch("platform.system", return_value="Windows"):
                # Get resource usage
                usage = get_resource_usage()
                
                # Verify values
                assert usage["memory_mb"] == 100.0
                assert usage["cpu_percent"] == 50.0
                assert usage["open_files"] == 0  # Default for non-Linux with AccessDenied
                assert usage["connections"] == 0  # Default when AccessDenied
                assert usage["threads"] == 5
    
    def test_measure_api_response_time(self):
        """Test measuring API response time."""
        # Create a test function
        def test_func(arg1, arg2=None):
            return arg1 + arg2 if arg2 else arg1
        
        # Mock time.time to return fixed values
        with patch("time.time", side_effect=[0.0, 0.1]):  # 100ms difference
            # Measure response time
            result, response_time = measure_api_response_time(test_func, 1, arg2=2)
            
            # Verify
            assert result == 3  # 1 + 2
            assert response_time == 100.0  # 100ms
    
    def test_memory_limits_within_limits(self):
        """Test memory limits when within limits."""
        # Mock get_resource_usage to return a value within limits
        with patch("pygovpub.validation.test_resource_limits.get_resource_usage",
                  return_value={"memory_mb": MAX_MEMORY_MB - 10}):
            with patch("builtins.print") as mock_print:
                # Test memory limits
                result = test_memory_limits()
                
                # Verify
                assert result is True
                assert mock_print.called
    
    def test_memory_limits_exceeds_limits(self):
        """Test memory limits when exceeding limits."""
        # Mock get_resource_usage to return a value exceeding limits
        with patch("pygovpub.validation.test_resource_limits.get_resource_usage",
                  return_value={"memory_mb": MAX_MEMORY_MB + 10}):
            with patch("builtins.print") as mock_print:
                # Test memory limits
                result = test_memory_limits()
                
                # Verify
                assert result is False
                assert mock_print.called
    
    def test_cpu_limits_within_limits(self):
        """Test CPU limits when within limits."""
        # Mock get_resource_usage to return a value within limits
        with patch("pygovpub.validation.test_resource_limits.get_resource_usage",
                  return_value={"cpu_percent": MAX_CPU_PERCENT - 10}):
            with patch("builtins.print") as mock_print:
                # Test CPU limits
                result = test_cpu_limits()
                
                # Verify
                assert result is True
                assert mock_print.called
    
    def test_cpu_limits_exceeds_limits(self):
        """Test CPU limits when exceeding limits."""
        # Mock get_resource_usage to return a value exceeding limits
        with patch("pygovpub.validation.test_resource_limits.get_resource_usage",
                  return_value={"cpu_percent": MAX_CPU_PERCENT + 10}):
            with patch("builtins.print") as mock_print:
                # Test CPU limits
                result = test_cpu_limits()
                
                # Verify
                assert result is False
                assert mock_print.called
    
    def test_file_descriptor_limits_within_limits(self):
        """Test file descriptor limits when within limits."""
        # Mock get_resource_usage to return a value within limits
        with patch("pygovpub.validation.test_resource_limits.get_resource_usage",
                  return_value={"open_files": MAX_OPEN_FILES - 10}):
            with patch("builtins.print") as mock_print:
                # Test file descriptor limits
                result = test_file_descriptor_limits()
                
                # Verify
                assert result is True
                assert mock_print.called
    
    def test_file_descriptor_limits_exceeds_limits(self):
        """Test file descriptor limits when exceeding limits."""
        # Mock get_resource_usage to return a value exceeding limits
        with patch("pygovpub.validation.test_resource_limits.get_resource_usage",
                  return_value={"open_files": MAX_OPEN_FILES + 10}):
            with patch("builtins.print") as mock_print:
                # Test file descriptor limits
                result = test_file_descriptor_limits()
                
                # Verify
                assert result is False
                assert mock_print.called
    
    def test_api_response_time_within_limits(self):
        """Test API response time when within limits."""
        # Mock measure_api_response_time to return a value within limits
        with patch("pygovpub.validation.test_resource_limits.measure_api_response_time",
                  return_value=({"status": "success"}, MAX_API_RESPONSE_TIME_MS - 100)):
            with patch("builtins.print") as mock_print:
                # Mock AuthManager with the required methods
                mock_auth_manager = MagicMock()
                mock_auth_manager.add_api_key = MagicMock()
                mock_auth_manager.get_api_key = MagicMock()
                mock_auth_manager.remove_api_key = MagicMock()
                
                # Mock AuthManager class to return our mock instance
                with patch("pygovpub.validation.test_resource_limits.AuthManager", 
                          return_value=mock_auth_manager):
                    # Test API response time
                    result = test_api_response_time()
                    
                    # Verify
                    assert result is True
                    assert mock_print.called
    
    def test_api_response_time_exceeds_limits(self):
        """Test API response time when exceeding limits."""
        # Mock measure_api_response_time to return a value exceeding limits
        with patch("pygovpub.validation.test_resource_limits.measure_api_response_time",
                  return_value=({"status": "success"}, MAX_API_RESPONSE_TIME_MS + 100)):
            with patch("builtins.print") as mock_print:
                # Mock AuthManager with the required methods
                mock_auth_manager = MagicMock()
                mock_auth_manager.add_api_key = MagicMock()
                mock_auth_manager.get_api_key = MagicMock()
                mock_auth_manager.remove_api_key = MagicMock()
                
                # Mock AuthManager class to return our mock instance
                with patch("pygovpub.validation.test_resource_limits.AuthManager", 
                          return_value=mock_auth_manager):
                    # Test API response time
                    result = test_api_response_time()
                    
                    # Verify
                    assert result is False
                    assert mock_print.called
    
    def test_api_response_time_import_error(self):
        """Test API response time when ImportError is raised."""
        # Mock the import to raise ImportError
        with patch("pygovpub.validation.test_resource_limits.AuthManager",
                  side_effect=ImportError):
            with patch("builtins.print") as mock_print:
                # Test API response time
                result = test_api_response_time()
                
                # Verify
                assert result is True  # Should still pass if AuthManager is not available
                assert mock_print.called
    
    def test_main_all_tests_pass(self):
        """Test main function when all tests pass."""
        # Mock all test functions to return True
        with patch("pygovpub.validation.test_resource_limits.test_memory_limits", return_value=True):
            with patch("pygovpub.validation.test_resource_limits.test_cpu_limits", return_value=True):
                with patch("pygovpub.validation.test_resource_limits.test_file_descriptor_limits", return_value=True):
                    with patch("pygovpub.validation.test_resource_limits.test_api_response_time", return_value=True):
                        with patch("builtins.print") as mock_print:
                            # Run main
                            result = main()
                            
                            # Verify
                            assert result == 0  # Success
                            assert mock_print.called
    
    def test_main_one_test_fails(self):
        """Test main function when one test fails."""
        # Mock one test function to return False
        with patch("pygovpub.validation.test_resource_limits.test_memory_limits", return_value=True):
            with patch("pygovpub.validation.test_resource_limits.test_cpu_limits", return_value=False):
                with patch("pygovpub.validation.test_resource_limits.test_file_descriptor_limits", return_value=True):
                    with patch("pygovpub.validation.test_resource_limits.test_api_response_time", return_value=True):
                        with patch("builtins.print") as mock_print:
                            # Run main
                            result = main()
                            
                            # Verify
                            assert result == 1  # Failure
                            assert mock_print.called
    
    def test_main_test_raises_exception(self):
        """Test main function when a test raises an exception."""
        # Mock one test function to raise an exception
        with patch("pygovpub.validation.test_resource_limits.test_memory_limits", return_value=True):
            with patch("pygovpub.validation.test_resource_limits.test_cpu_limits", 
                      side_effect=Exception("Test error")):
                with patch("pygovpub.validation.test_resource_limits.test_file_descriptor_limits", return_value=True):
                    with patch("pygovpub.validation.test_resource_limits.test_api_response_time", return_value=True):
                        with patch("builtins.print") as mock_print:
                            # Run main
                            result = main()
                            
                            # Verify
                            assert result == 1  # Failure
                            assert mock_print.called