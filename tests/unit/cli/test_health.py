"""
Unit tests for the health CLI module.
"""
import json as json_lib
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from typer.testing import CliRunner

from pygovpub.cli.health import (
    app,
    check,
    display_json_report,
    display_markdown_report,
    display_text_report
)


# Create a CLI runner for testing Typer apps
runner = CliRunner()


@pytest.fixture
def mock_health_check():
    """Create a mock health check result."""
    return {
        "timestamp": "2025-03-09T23:45:56.123456Z",
        "status": "healthy",
        "version": "0.1.0",
        "apis": [
            {"name": "congress", "status": "connected", "latency_ms": 120},
            {"name": "govinfo", "status": "connected", "latency_ms": 150}
        ],
        "configuration": {
            "valid": True,
            "environment": "development",
            "api_configs": {
                "congress": {"base_url": "https://api.congress.gov/v3", "has_api_key": True},
                "govinfo": {"base_url": "https://api.govinfo.gov", "has_api_key": True}
            },
            "issues": []
        },
        "system": {
            "python_version": "3.13.2",
            "os": {"system": "Darwin", "release": "23.4.0", "machine": "arm64"},
            "packages": {
                "pygovpub": "0.1.0",
                "requests": "2.32.3",
                "aiohttp": "3.11.13",
                "fastapi": "0.115.11"
            }
        },
        "performance": {
            "memory_usage_mb": 45.2,
            "cpu_percent": 1.5,
            "response_times_ms": {
                "congress": 120,
                "govinfo": 150
            }
        }
    }


class TestHealthCLI:
    """Tests for the health CLI module."""

    @patch("pygovpub.cli.health.run_health_check")
    @patch("pygovpub.cli.health.console")
    def test_check_default_format(self, mock_console, mock_run_health_check, mock_health_check):
        """Test check command with default text format."""
        # Mock health check result
        mock_run_health_check.return_value = mock_health_check
        
        # Mock console status context manager
        mock_status = MagicMock()
        mock_console.status.return_value.__enter__.return_value = mock_status
        
        # Run the CLI command - using directly call method because we've mocked console
        check(format="text", output=None, verbose=False, quiet=False, json=False)
        
        # Verify display_text_report was called
        assert mock_console.print.call_count > 0

    @patch("pygovpub.cli.health.run_health_check")
    @patch("pygovpub.cli.health.console")
    def test_check_json_format(self, mock_console, mock_run_health_check, mock_health_check):
        """Test check command with JSON format."""
        # Mock health check result
        mock_run_health_check.return_value = mock_health_check
        
        # Mock console status context manager
        mock_status = MagicMock()
        mock_console.status.return_value.__enter__.return_value = mock_status
        
        # Mock print_json method
        mock_console.print_json = MagicMock()
        
        # Run the CLI command
        check(format="json", output=None, verbose=False, quiet=False, json=False)
        
        # Verify display_json_report was called
        mock_console.print_json.assert_called_once()
        
        # Verify data in call
        json_str = mock_console.print_json.call_args[0][0]
        assert "healthy" in json_str
        assert "0.1.0" in json_str

    @patch("pygovpub.cli.health.run_health_check")
    @patch("pygovpub.cli.health.console")
    def test_check_markdown_format(self, mock_console, mock_run_health_check, mock_health_check):
        """Test check command with Markdown format."""
        # Mock health check result
        mock_run_health_check.return_value = mock_health_check
        
        # Mock console status context manager
        mock_status = MagicMock()
        mock_console.status.return_value.__enter__.return_value = mock_status
        
        # Mock print method
        mock_console.print = MagicMock()
        
        # Run the CLI command
        check(format="markdown", output=None, verbose=False, quiet=False, json=False)
        
        # Verify print was called
        mock_console.print.assert_called_once()
        
        # Verify argument is Markdown
        arg = mock_console.print.call_args[0][0]
        assert "Markdown" in str(type(arg))

    @patch("pygovpub.cli.health.run_health_check")
    @patch("pygovpub.cli.health.console")
    def test_check_json_shorthand(self, mock_console, mock_run_health_check, mock_health_check):
        """Test check command with --json shorthand."""
        # Mock health check result
        mock_run_health_check.return_value = mock_health_check
        
        # Mock console status context manager
        mock_status = MagicMock()
        mock_console.status.return_value.__enter__.return_value = mock_status
        
        # Mock print_json method
        mock_console.print_json = MagicMock()
        
        # Run the CLI command
        check(format="text", output=None, verbose=False, quiet=False, json=True)
        
        # Verify display_json_report was called
        mock_console.print_json.assert_called_once()

    @patch("pygovpub.cli.health.run_health_check")
    @patch("pygovpub.cli.health.console")
    @patch("pygovpub.cli.health.display_text_report")
    def test_check_verbose(self, mock_display_text, mock_console, mock_run_health_check, mock_health_check):
        """Test check command with verbose flag."""
        # Mock health check result
        mock_run_health_check.return_value = mock_health_check
        
        # Mock console status context manager
        mock_status = MagicMock()
        mock_console.status.return_value.__enter__.return_value = mock_status
        
        # Run the CLI command
        check(format="text", output=None, verbose=True, quiet=False, json=False)
        
        # Verify display_text_report was called with verbose=True
        mock_display_text.assert_called_once_with(mock_health_check, True)

    @patch("pygovpub.cli.health.run_health_check")
    @patch("pygovpub.cli.health.console")
    def test_check_file_output(self, mock_console, mock_run_health_check, mock_health_check, tmp_path):
        """Test check command with file output."""
        # Mock health check result
        mock_run_health_check.return_value = mock_health_check
        
        # Create temporary file path
        output_file = tmp_path / "health.json"
        
        # Mock console status
        mock_status = MagicMock()
        mock_console.status.return_value.__enter__.return_value = mock_status
        
        # Mock file output
        with patch("pygovpub.cli.health.Console", MagicMock()) as mock_console_cls:
            mock_file_console = MagicMock()
            mock_console_cls.return_value = mock_file_console
            mock_file = MagicMock()
            mock_file_console.file = mock_file
            
            # Run command
            check(format="json", output=output_file, verbose=False, quiet=False, json=False)
            
            # Verify file Console was created
            mock_console_cls.assert_called_once()
            
            # Verify message about saving file
            assert mock_console.print.call_count > 0

    @patch("pygovpub.cli.health.run_health_check")
    @patch("pygovpub.cli.health.console")
    @patch("sys.exit")
    def test_check_unhealthy_status(self, mock_exit, mock_console, mock_run_health_check):
        """Test check command with unhealthy status."""
        # Mock health check result with unhealthy status
        mock_result = {
            "timestamp": "2025-03-09T23:45:56.123456Z",
            "status": "unhealthy",
            "version": "0.1.0",
            "apis": [
                {"name": "congress", "status": "error", "message": "Connection refused"},
                {"name": "govinfo", "status": "connected", "latency_ms": 150}
            ],
            "configuration": {"valid": True, "environment": "development", "api_configs": {}, "issues": []},
            "system": {"python_version": "3.13.2", "os": {"system": "Darwin", "release": "23.4.0", "machine": "arm64"}, "packages": {}},
            "performance": {"memory_usage_mb": 45.2, "cpu_percent": 1.5, "response_times_ms": {"govinfo": 150}}
        }
        mock_run_health_check.return_value = mock_result
        
        # Mock console status
        mock_status = MagicMock()
        mock_console.status.return_value.__enter__.return_value = mock_status
        
        # Run the CLI command
        check(format="text", output=None, verbose=False, quiet=False, json=False)
        
        # Verify exit code 1 for unhealthy status
        mock_exit.assert_called_once_with(1)

    @patch("pygovpub.cli.health.run_health_check", side_effect=Exception("Test error"))
    @patch("pygovpub.cli.health.console")
    @patch("sys.exit")
    def test_check_exception(self, mock_exit, mock_console, mock_run_health_check):
        """Test check command with exception."""
        # Mock console status
        mock_status = MagicMock()
        mock_console.status.return_value.__enter__.return_value = mock_status
        
        # Run the CLI command with mocked exception
        check(format="text", output=None, verbose=False, quiet=False, json=False)
        
        # Verify error message was printed
        mock_console.print.assert_called_once()
        args = mock_console.print.call_args[0][0]
        assert "Error running health check" in args
        assert "Test error" in args
        
        # Verify exit code 2 for error
        mock_exit.assert_called_once_with(2)

    @patch("pygovpub.cli.health.console")
    def test_display_json_report(self, mock_console, mock_health_check):
        """Test display_json_report function."""
        display_json_report(mock_health_check)
        
        # Verify console.print_json was called
        mock_console.print_json.assert_called_once()
        # Convert the call argument to dict and verify
        json_str = mock_console.print_json.call_args[0][0]
        parsed = json_lib.loads(json_str)
        assert parsed["status"] == "healthy"

    @patch("pygovpub.cli.health.console")
    def test_display_markdown_report(self, mock_console, mock_health_check):
        """Test display_markdown_report function."""
        display_markdown_report(mock_health_check)
        
        # Verify console.print was called
        mock_console.print.assert_called_once()
        # Check that argument is Markdown
        markdown_obj = mock_console.print.call_args[0][0]
        assert "Markdown" in str(type(markdown_obj))

    @patch("pygovpub.cli.health.console")
    def test_display_text_report(self, mock_console, mock_health_check):
        """Test display_text_report function."""
        # Test with non-verbose mode
        display_text_report(mock_health_check, verbose=False)
        
        # Verify console.print was called multiple times (panels, tables)
        assert mock_console.print.call_count >= 3
        
        # Reset mock
        mock_console.reset_mock()
        
        # Test with verbose mode
        display_text_report(mock_health_check, verbose=True)
        
        # Verify console.print was called even more times (including performance panel)
        assert mock_console.print.call_count >= 4