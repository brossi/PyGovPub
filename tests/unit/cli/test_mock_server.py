"""
Unit tests for the mock_server CLI module.
"""
import argparse
import asyncio
import os
import pytest
import signal
import types
from unittest.mock import patch, MagicMock, AsyncMock

from pygovpub.cli.mock_server import (
    parse_args,
    run_server,
    shutdown,
    start_mock_server_cli
)

# Helper function to create a fake coroutine function that won't complain about not being awaited
def mock_coro(return_value=None):
    """Create a mocked coroutine function that returns a regular function instead of a coroutine."""
    def mock_coroutine(*args, **kwargs):
        return return_value
    return mock_coroutine


class TestMockServerCLI:
    """Tests for the mock_server CLI module."""

    def test_parse_args_defaults(self):
        """Test parse_args with default values."""
        args = parse_args([])
        
        assert args.host == "127.0.0.1"
        assert args.port == 8000
        assert args.log_level == "info"
        assert args.latency is None
        assert not args.rate_limits
        assert not args.record
        assert args.fixtures is None

    def test_parse_args_custom(self):
        """Test parse_args with custom values."""
        args = parse_args([
            "--host", "0.0.0.0",
            "--port", "9000",
            "--log-level", "debug",
            "--latency", "200",
            "--rate-limits",
            "--record",
            "--fixtures", "/custom/path"
        ])
        
        assert args.host == "0.0.0.0"
        assert args.port == 9000
        assert args.log_level == "debug"
        assert args.latency == 200
        assert args.rate_limits
        assert args.record
        assert args.fixtures == "/custom/path"

    @pytest.mark.asyncio
    @patch("pygovpub.cli.mock_server.start_mock_server")
    @patch("pygovpub.cli.mock_server.config")
    @patch("pygovpub.cli.mock_server.logging")
    async def test_run_server(self, mock_logging, mock_config, mock_start_server):
        """Test run_server function."""
        # Create mock args
        args = argparse.Namespace(
            host="127.0.0.1",
            port=8000,
            log_level="info",
            latency=100,
            rate_limits=True,
            record=True,
            fixtures="/test/fixtures"
        )
        
        # Mock logger
        mock_logger = MagicMock()
        mock_logging.getLogger.return_value = mock_logger
        
        # Mock config properties
        mock_config.mock.latency_ms = 100
        mock_config.mock.simulate_rate_limits = True
        mock_config.mock.record_mode = True
        mock_config.mock.fixtures_path = "/test/fixtures"
        
        # Mock asyncio functions
        mock_loop = MagicMock()
        
        # Make start_mock_server return a proper awaitable
        mock_start_server.return_value = None
        
        with patch("asyncio.get_event_loop", return_value=mock_loop):
            # Mock asyncio.sleep to avoid infinite loop
            with patch("asyncio.sleep", side_effect=[None, asyncio.CancelledError]):
                # Run the function
                with pytest.raises(asyncio.CancelledError):
                    await run_server(args)
        
        # Verify environment variables were set
        assert os.environ["PYGOVPUB_MOCK_LATENCY_MS"] == "100"
        assert os.environ["PYGOVPUB_MOCK_SIMULATE_RATE_LIMITS"] == "true"
        assert os.environ["PYGOVPUB_MOCK_RECORD_MODE"] == "true"
        assert os.environ["PYGOVPUB_MOCK_FIXTURES_PATH"] == "/test/fixtures"
        assert os.environ["PYGOVPUB_MOCK_ENABLED"] == "true"
        
        # Verify start_mock_server was called
        mock_start_server.assert_called_once_with(
            host="127.0.0.1",
            port=8000,
            log_level="info"
        )
        
        # Verify signal handlers were set
        assert mock_loop.add_signal_handler.call_count == 2

    @pytest.mark.asyncio
    @patch("pygovpub.cli.mock_server.stop_mock_server")
    @patch("pygovpub.cli.mock_server.logging")
    async def test_shutdown(self, mock_logging, mock_stop_server):
        """Test shutdown function."""
        # Mock logger
        mock_logger = MagicMock()
        mock_logging.getLogger.return_value = mock_logger
        
        # Make stop_mock_server return a proper awaitable
        mock_stop_server.return_value = None
        
        # Mock asyncio.get_event_loop
        mock_loop = MagicMock()
        with patch("asyncio.get_event_loop", return_value=mock_loop):
            await shutdown()
        
        # Verify stop_mock_server was called
        mock_stop_server.assert_called_once()
        
        # Verify loop.stop was called
        mock_loop.stop.assert_called_once()

    @patch("pygovpub.cli.mock_server.parse_args")
    @patch("pygovpub.cli.mock_server.asyncio.run")
    def test_start_mock_server_cli_success(self, mock_run, mock_parse_args):
        """Test start_mock_server_cli with successful execution."""
        # Mock args
        mock_args = MagicMock()
        mock_parse_args.return_value = mock_args
        
        # Patch run_server to return a fake coroutine that won't cause warnings
        with patch("pygovpub.cli.mock_server.run_server", new=mock_coro()):
            # Call the function
            start_mock_server_cli()
            
            # Verify parse_args was called
            mock_parse_args.assert_called_once()
            
            # Verify asyncio.run was called
            assert mock_run.call_count == 1

    @patch("pygovpub.cli.mock_server.parse_args")
    @patch("pygovpub.cli.mock_server.asyncio.run", side_effect=KeyboardInterrupt)
    @patch("builtins.print")
    def test_start_mock_server_cli_keyboard_interrupt(self, mock_print, mock_run, mock_parse_args):
        """Test start_mock_server_cli with KeyboardInterrupt."""
        # Mock args
        mock_args = MagicMock()
        mock_parse_args.return_value = mock_args
        
        # Patch run_server to return a fake coroutine that won't cause warnings
        with patch("pygovpub.cli.mock_server.run_server", new=mock_coro()):
            # Call the function
            start_mock_server_cli()
            
            # Verify print was called with shutdown message
            mock_print.assert_called_once_with("\nShutting down mock server...")

    @patch("pygovpub.cli.mock_server.parse_args")
    @patch("pygovpub.cli.mock_server.asyncio.run", side_effect=Exception("Test error"))
    @patch("builtins.print")
    @patch("sys.exit")
    def test_start_mock_server_cli_exception(self, mock_exit, mock_print, mock_run, mock_parse_args):
        """Test start_mock_server_cli with generic exception."""
        # Mock args
        mock_args = MagicMock()
        mock_parse_args.return_value = mock_args
        
        # Patch run_server to return a fake coroutine that won't cause warnings
        with patch("pygovpub.cli.mock_server.run_server", new=mock_coro()):
            # Call the function
            start_mock_server_cli()
            
            # Verify print was called with error message
            mock_print.assert_called_once_with("Error: Test error")
            
            # Verify sys.exit was called with error code
            mock_exit.assert_called_once_with(1)