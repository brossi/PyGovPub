"""
Tests for MySQL support in storage interface.

This module tests MySQL-specific functionality in the storage interface,
including connection string detection, async support, and feature detection.
"""

import pytest
from unittest.mock import patch, MagicMock

from pygovpub.storage.interface import StorageInterface


class TestMySQLSupport:
    """Test suite for MySQL support in the StorageInterface class."""

    @patch("sqlalchemy.create_engine")
    @patch("importlib.util.find_spec")
    def test_mysql_connections(self, mock_find_spec, mock_create_engine):
        """Test MySQL connection string detection with proper driver mocking."""
        # Mock engine
        mock_engine = MagicMock()
        mock_create_engine.return_value = mock_engine
        
        # Mock package availability to avoid driver import errors
        def mock_find_impl(package_name):
            # Return MagicMock for any package to simulate availability
            return MagicMock()
        
        mock_find_spec.side_effect = mock_find_impl
        
        # Mock MySQLdb import by patching the import_dbapi method
        mysql_dbapi_patches = [
            patch("sqlalchemy.dialects.mysql.mysqldb.MySQLDialect_mysqldb.import_dbapi", 
                  return_value=MagicMock()),
            patch("sqlalchemy.dialects.mysql.pymysql.MySQLDialect_pymysql.import_dbapi", 
                  return_value=MagicMock()),
            # Add other dialect patches as needed
        ]
        
        # Create test cases of MySQL connection strings
        test_cases = [
            ("mysql://user:pass@localhost/testdb", "mysql"),
            ("mysql+pymysql://user:pass@localhost/testdb", "mysql"),
            ("mysql+mysqlconnector://user:pass@localhost/testdb", "mysql"),
            ("mysql+mysqldb://user:pass@localhost/testdb", "mysql"),
            ("mysql+aiomysql://user:pass@localhost/testdb", "mysql")
        ]
        
        # Apply all patches
        for patch_obj in mysql_dbapi_patches:
            patch_obj.start()
            
        try:
            # Test each case
            for conn_string, expected_type in test_cases:
                with patch.object(StorageInterface, "_supports_async", return_value=False):
                    # Test only the _determine_db_type method directly, to avoid import issues
                    interface = StorageInterface.__new__(StorageInterface)
                    interface.connection_string = conn_string
                    actual_type = interface._determine_db_type(conn_string)
                    assert actual_type == expected_type, f"Failed to detect {expected_type} from {conn_string}"
        finally:
            # Stop all patches
            for patch_obj in mysql_dbapi_patches:
                patch_obj.stop()
    
    def test_mysql_async_support(self):
        """Test async support detection for MySQL."""
        # Create a minimal interface instance 
        interface = StorageInterface.__new__(StorageInterface)
        interface.db_type = "mysql"
        
        # Test with aiomysql available
        with patch.object(interface, "_is_package_available", side_effect=lambda pkg: pkg == "aiomysql"):
            assert interface._supports_async() is True
            
        # Test with aiomysql not available
        with patch.object(interface, "_is_package_available", return_value=False):
            assert interface._supports_async() is False
    
    def test_get_async_connection_string_mysql(self):
        """Test conversion of MySQL connection strings to async equivalents."""
        # Create a minimal interface instance
        interface = StorageInterface.__new__(StorageInterface)
        
        # Test cases for MySQL
        test_cases = [
            # Input, Expected Output
            ("mysql://user:pass@localhost/testdb", "mysql+aiomysql://user:pass@localhost/testdb"),
            ("mysql+pymysql://user:pass@localhost/testdb", "mysql+aiomysql://user:pass@localhost/testdb"),
            ("mysql+mysqldb://user:pass@localhost/testdb", "mysql+aiomysql://user:pass@localhost/testdb"),
            ("mysql+mysqlconnector://user:pass@localhost/testdb", "mysql+aiomysql://user:pass@localhost/testdb"),
            # Test idempotence - already aiomysql
            ("mysql+aiomysql://user:pass@localhost/testdb", "mysql+aiomysql://user:pass@localhost/testdb")
        ]
        
        # Test each case
        for input_str, expected_output in test_cases:
            result = interface._get_async_connection_string(input_str)
            assert result == expected_output, f"Failed to convert {input_str} to async equivalent"