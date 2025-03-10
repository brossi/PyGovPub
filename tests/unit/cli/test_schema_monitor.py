"""
Unit tests for schema_monitor CLI module.
"""
import argparse
import sys
from io import StringIO
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock, call

import pytest

from pygovpub.cli.schema_monitor import (
    format_datetime,
    list_schemas_command,
    list_changes_command,
    list_versions_command,
    create_parser,
    main
)
from pygovpub.auth.models import ApiSource
from pygovpub.core.schema_monitor import SchemaChange, SchemaVersion


class TestSchemaMonitorCLI:
    """Tests for the schema_monitor CLI module."""

    def test_format_datetime(self):
        """Test formatting datetimes."""
        dt = datetime(2023, 1, 1, 12, 30, 45, tzinfo=timezone.utc)
        formatted = format_datetime(dt)
        assert formatted == "2023-01-01 12:30:45 UTC"

    def test_create_parser(self):
        """Test the command parser creation."""
        parser = create_parser()
        
        # Check that the parser has the expected commands
        assert parser.description is not None
        
        # Get all subparsers
        subparsers = next(action for action in parser._actions if isinstance(action, argparse._SubParsersAction))
        subparser_choices = subparsers.choices
        
        # Check for expected subparsers
        assert "list-schemas" in subparser_choices
        assert "list-changes" in subparser_choices
        assert "list-versions" in subparser_choices
        
        # Check that the list-changes parser has a limit argument
        list_changes_parser = subparser_choices["list-changes"]
        limit_action = next((a for a in list_changes_parser._actions if a.dest == "limit"), None)
        assert limit_action is not None
        assert limit_action.default == 20

    def test_list_schemas_command(self):
        """Test listing schemas."""
        # Create a mock for default_monitor
        mock_monitor = MagicMock()
        mock_monitor.schemas = {
            "congress:bill": {"properties": {"id": {}, "title": {}}},
            "govinfo:package": {"properties": {"packageId": {}, "dateIssued": {}}}
        }
        
        # Create mock version info
        version_info_bill = MagicMock()
        version_info_bill.version_string = "v1.0"
        version_info_bill.last_seen = datetime(2023, 1, 1, tzinfo=timezone.utc)
        
        version_info_package = MagicMock()
        version_info_package.version_string = "v2.0"
        version_info_package.last_seen = datetime(2023, 2, 1, tzinfo=timezone.utc)
        
        mock_monitor.versions = {
            "congress:bill": version_info_bill,
            "govinfo:package": version_info_package
        }
        
        # Mock stdout
        with patch("sys.stdout", new=StringIO()) as mock_stdout:
            # Mock default_monitor
            with patch("pygovpub.cli.schema_monitor.default_monitor", mock_monitor):
                # Call command
                args = argparse.Namespace()
                list_schemas_command(args)
                
                # Check output
                output = mock_stdout.getvalue()
                assert "API Schema Registry" in output
                assert "CONGRESS API: 1 endpoints" in output
                assert "GOVINFO API: 1 endpoints" in output
                assert "bill" in output
                assert "package" in output
                assert "v1.0" in output
                assert "v2.0" in output
                assert "2023-01-01" in output
                assert "2023-02-01" in output
                assert "Properties: 2" in output
                assert "Total Endpoints: 2" in output

    def test_list_changes_command(self):
        """Test listing schema changes."""
        # Create mock changes
        change1 = SchemaChange(
            api_source=ApiSource.CONGRESS,
            endpoint="bill",
            field_path="title",
            change_type="added",
            is_breaking=False,
            timestamp=datetime(2023, 1, 1, tzinfo=timezone.utc)
        )
        
        change2 = SchemaChange(
            api_source=ApiSource.GOVINFO,
            endpoint="package",
            field_path="dateIssued",
            change_type="removed",
            is_breaking=True,
            timestamp=datetime(2023, 2, 1, tzinfo=timezone.utc)
        )
        
        # Mock get_recent_changes
        with patch("pygovpub.cli.schema_monitor.get_recent_changes", return_value=[change1, change2]) as mock_get_changes:
            # Mock stdout
            with patch("sys.stdout", new=StringIO()) as mock_stdout:
                # Call command
                args = argparse.Namespace(limit=20)
                list_changes_command(args)
                
                # Check that get_recent_changes was called
                mock_get_changes.assert_called_once_with(limit=20)
                
                # Check output
                output = mock_stdout.getvalue()
                assert "Recent Schema Changes" in output
                assert "CONGRESS API: 1 changes" in output
                assert "GOVINFO API: 1 changes" in output
                assert "Endpoint: bill" in output
                assert "Endpoint: package" in output
                assert "Change: added" in output
                assert "Change: removed (BREAKING)" in output
                assert "Field: title" in output
                assert "Field: dateIssued" in output
                assert "2023-01-01" in output
                assert "2023-02-01" in output
                assert "Total Changes: 2" in output

    def test_list_changes_command_no_changes(self):
        """Test listing schema changes when there are none."""
        # Mock get_recent_changes to return empty list
        with patch("pygovpub.cli.schema_monitor.get_recent_changes", return_value=[]) as mock_get_changes:
            # Mock stdout
            with patch("sys.stdout", new=StringIO()) as mock_stdout:
                # Call command
                args = argparse.Namespace(limit=20)
                list_changes_command(args)
                
                # Check output
                output = mock_stdout.getvalue()
                assert "No schema changes detected" in output

    def test_list_versions_command(self):
        """Test listing API versions."""
        # Create mock versions
        version1 = SchemaVersion(
            api_source=ApiSource.CONGRESS,
            version_string="v1.0",
            schema_hash="hash1",
            first_seen=datetime(2023, 1, 1, tzinfo=timezone.utc),
            last_seen=datetime(2023, 2, 1, tzinfo=timezone.utc)
        )
        
        version2 = SchemaVersion(
            api_source=ApiSource.GOVINFO,
            version_string="v2.0",
            schema_hash="hash2",
            first_seen=datetime(2023, 3, 1, tzinfo=timezone.utc),
            last_seen=datetime(2023, 4, 1, tzinfo=timezone.utc)
        )
        
        # Mock get_supported_versions
        mock_versions = {
            ApiSource.CONGRESS: [version1],
            ApiSource.GOVINFO: [version2]
        }
        
        with patch("pygovpub.cli.schema_monitor.get_supported_versions", return_value=mock_versions) as mock_get_versions:
            # Mock stdout
            with patch("sys.stdout", new=StringIO()) as mock_stdout:
                # Call command
                args = argparse.Namespace()
                list_versions_command(args)
                
                # Check output
                output = mock_stdout.getvalue()
                assert "Supported API Versions" in output
                assert "CONGRESS API: 1 versions" in output
                assert "GOVINFO API: 1 versions" in output
                assert "Version: v1.0" in output
                assert "Version: v2.0" in output
                assert "First seen: 2023-01-01" in output
                assert "Last seen: 2023-02-01" in output
                assert "First seen: 2023-03-01" in output
                assert "Last seen: 2023-04-01" in output
                assert "Total API Sources: 2" in output

    def test_list_versions_command_no_versions(self):
        """Test listing API versions when there are none."""
        # Mock get_supported_versions to return empty dict
        with patch("pygovpub.cli.schema_monitor.get_supported_versions", return_value={}) as mock_get_versions:
            # Mock stdout
            with patch("sys.stdout", new=StringIO()) as mock_stdout:
                # Call command
                args = argparse.Namespace()
                list_versions_command(args)
                
                # Check output
                output = mock_stdout.getvalue()
                assert "No API versions detected" in output

    def test_main_with_command(self):
        """Test main function with valid command."""
        # Create mock args
        mock_args = MagicMock()
        mock_args.func = MagicMock()
        
        # Mock parser
        mock_parser = MagicMock()
        mock_parser.parse_args.return_value = mock_args
        
        # Mock create_parser
        with patch("pygovpub.cli.schema_monitor.create_parser", return_value=mock_parser) as mock_create_parser:
            # Call main
            main()
            
            # Check that parser was created
            mock_create_parser.assert_called_once()
            
            # Check that args were parsed
            mock_parser.parse_args.assert_called_once()
            
            # Check that command function was called
            mock_args.func.assert_called_once_with(mock_args)

    def test_main_without_command(self):
        """Test main function without a command (shows help)."""
        # Create a patch for hasattr to simulate a case where args.func doesn't exist
        def mock_hasattr(obj, name):
            if name == 'func':
                return False
            return True
        
        # Mock parser
        mock_parser = MagicMock()
        mock_args = MagicMock()
        mock_parser.parse_args.return_value = mock_args
        
        # Mock sys.exit to avoid exiting the test
        with patch("sys.exit") as mock_exit:
            # Mock create_parser
            with patch("pygovpub.cli.schema_monitor.create_parser", return_value=mock_parser) as mock_create_parser:
                # Mock hasattr to return False for 'func'
                with patch("pygovpub.cli.schema_monitor.hasattr", side_effect=mock_hasattr):
                    # Call main
                    main()
                    
                    # Check that parser was created
                    mock_create_parser.assert_called_once()
                    
                    # Check that help was printed
                    mock_parser.print_help.assert_called_once()
                    
                    # Check that sys.exit was called with code 1
                    mock_exit.assert_called_once_with(1)