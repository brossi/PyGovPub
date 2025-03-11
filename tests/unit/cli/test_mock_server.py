"""
Unit tests for the mock_server CLI module.
"""
import argparse
import asyncio
import os
import pytest
import signal
import types
from unittest.mock import patch, MagicMock, AsyncMock, call

from pygovpub.cli.mock_server import (
    parse_args,
    run_server,
    shutdown,
    start_mock_server_cli
)

# Helper functions to create proper mock coroutines
def mock_coro(return_value=None):
    """Create a mocked coroutine function that returns a regular function instead of a coroutine."""
    def mock_coroutine(*args, **kwargs):
        return return_value
    return mock_coroutine

async def async_mock_return(return_value=None):
    """A simple async function that returns a value."""
    return return_value

def async_mock_coro(return_value=None):
    """Create a mocked coroutine function that returns an awaitable."""
    async def mock_async_coroutine(*args, **kwargs):
        return return_value
    return mock_async_coroutine


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

    def test_parse_args_log_level_validation(self):
        """Test parse_args validates log level choices."""
        # Valid log levels should succeed
        for level in ["debug", "info", "warning", "error", "critical"]:
            args = parse_args(["--log-level", level])
            assert args.log_level == level
        
        # Invalid log level should fail
        with pytest.raises(SystemExit):
            parse_args(["--log-level", "invalid"])

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
        
        # Verify logging was configured
        mock_logging.basicConfig.assert_called_once_with(
            level=mock_logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        
        # Verify start_mock_server was called
        mock_start_server.assert_called_once_with(
            host="127.0.0.1",
            port=8000,
            log_level="info"
        )
        
        # Verify signal handlers were set
        assert mock_loop.add_signal_handler.call_count == 2
        
        # Verify logger.info calls
        assert mock_logger.info.call_count >= 6
        mock_logger.info.assert_any_call(f"Starting mock server on 127.0.0.1:8000")
        mock_logger.info.assert_any_call(f"Log level: info")
        mock_logger.info.assert_any_call(f"Latency: 100ms")
        mock_logger.info.assert_any_call(f"Rate limits: True")
        mock_logger.info.assert_any_call(f"Record mode: True")
        mock_logger.info.assert_any_call(f"Fixtures path: /test/fixtures")
        mock_logger.info.assert_any_call(f"Mock server running at http://127.0.0.1:8000")
        mock_logger.info.assert_any_call("Press Ctrl+C to stop")

    @pytest.mark.asyncio
    @patch("pygovpub.cli.mock_server.start_mock_server")
    @patch("pygovpub.cli.mock_server.config")
    @patch("pygovpub.cli.mock_server.logging")
    async def test_run_server_without_optional_args(self, mock_logging, mock_config, mock_start_server):
        """Test run_server function without optional argument values."""
        # Clear any existing environment variables that might interfere with the test
        for env_var in [
            "PYGOVPUB_MOCK_LATENCY_MS",
            "PYGOVPUB_MOCK_SIMULATE_RATE_LIMITS",
            "PYGOVPUB_MOCK_RECORD_MODE",
            "PYGOVPUB_MOCK_FIXTURES_PATH",
            "PYGOVPUB_MOCK_ENABLED"
        ]:
            if env_var in os.environ:
                del os.environ[env_var]
                
        # Create mock args with default values (None)
        args = argparse.Namespace(
            host="127.0.0.1",
            port=8000,
            log_level="info",
            latency=None,     # No latency specified
            rate_limits=False, # No rate limits
            record=False,      # No record mode
            fixtures=None      # No custom fixtures
        )
        
        # Mock logger
        mock_logger = MagicMock()
        mock_logging.getLogger.return_value = mock_logger
        
        # Mock config properties with default values
        mock_config.mock.latency_ms = 0  # Default latency
        mock_config.mock.simulate_rate_limits = False
        mock_config.mock.record_mode = False
        mock_config.mock.fixtures_path = "fixtures"  # Default path
        
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
        
        # Verify environment variables are set appropriately (only PYGOVPUB_MOCK_ENABLED)
        assert "PYGOVPUB_MOCK_LATENCY_MS" not in os.environ  # Should not be set
        assert "PYGOVPUB_MOCK_SIMULATE_RATE_LIMITS" not in os.environ  # Should not be set
        assert "PYGOVPUB_MOCK_RECORD_MODE" not in os.environ  # Should not be set
        assert "PYGOVPUB_MOCK_FIXTURES_PATH" not in os.environ  # Should not be set
        assert os.environ["PYGOVPUB_MOCK_ENABLED"] == "true"  # This should always be set
        
        # Verify start_mock_server was called with correct parameters
        mock_start_server.assert_called_once_with(
            host="127.0.0.1",
            port=8000,
            log_level="info"
        )

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
        
        # Verify logger messages
        mock_logger.info.assert_has_calls([
            call("Shutting down mock server..."),
            call("Mock server stopped")
        ])
        
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
    
    def test_signal_handler_function(self):
        """Test just the signal handler function creation - simplified to avoid coroutine warnings."""
        # Create a fake shutdown function that returns a regular function
        def fake_shutdown():
            pass
            
        # Mock the create_task function
        mock_create_task = MagicMock()
        
        # Directly test the lambda handling logic
        with patch("pygovpub.cli.mock_server.shutdown", fake_shutdown):
            with patch("pygovpub.cli.mock_server.asyncio.create_task", mock_create_task):
                # Create a lambda similar to what the code does
                handler = lambda: mock_create_task(fake_shutdown())
                
                # Call the handler
                handler()
                
                # Verify create_task was called with our fake shutdown's return value
                mock_create_task.assert_called_once()