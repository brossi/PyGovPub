"""
Test the logging setup module.

These tests verify that the logging setup functions correctly configure
the logging system components.
"""

import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI

from pygovpub.logging import LogLevel
from pygovpub.logging.debug import DebugLevel
from pygovpub.logging.setup import setup_logging, setup_api_logging


@pytest.fixture
def mock_fastapi_app():
    """Create a mock FastAPI application."""
    return FastAPI()


@pytest.fixture
def mock_config():
    """Create a mock configuration object."""
    config = MagicMock()
    config.environment = "test"
    return config


def test_setup_logging_basic():
    """Test basic logging setup with default parameters."""
    with patch("pygovpub.logging.setup.configure_logging") as mock_configure_logging, \
         patch("pygovpub.logging.setup.debug_mode") as mock_debug_mode:
        
        # Call setup_logging with minimal parameters
        setup_logging()
        
        # Verify that configure_logging was called with expected defaults
        mock_configure_logging.assert_called_once()
        call_args = mock_configure_logging.call_args[1]
        assert call_args["log_level"] == LogLevel.INFO.value
        assert "json_format" in call_args
        
        # Verify debug mode was set
        mock_debug_mode.set_level.assert_called_once_with(DebugLevel.NONE)


def test_setup_logging_with_config():
    """Test logging setup with configuration object."""
    mock_config = MagicMock()
    mock_config.environment = "test"
    
    with patch("pygovpub.logging.setup.configure_logging") as mock_configure_logging, \
         patch("pygovpub.logging.setup.debug_mode") as mock_debug_mode, \
         patch("pygovpub.logging.setup.os.environ", {"PYGOVPUB_LOG_LEVEL": "DEBUG", 
                                                    "PYGOVPUB_DEBUG_LEVEL": "2"}):
        
        # Call setup_logging with config
        setup_logging(config=mock_config)
        
        # Verify that configure_logging was called with environment values
        mock_configure_logging.assert_called_once()
        call_args = mock_configure_logging.call_args[1]
        assert call_args["log_level"] == "DEBUG"
        
        # Verify debug mode was set from environment
        mock_debug_mode.set_level.assert_called_once_with(2)


def test_setup_logging_with_telemetry():
    """Test logging setup with telemetry enabled."""
    with patch("pygovpub.logging.setup.configure_logging") as mock_configure_logging, \
         patch("pygovpub.logging.setup.debug_mode") as mock_debug_mode, \
         patch("pygovpub.logging.setup.configure_tracing") as mock_configure_tracing:
        
        # Call setup_logging with telemetry enabled
        setup_logging(enable_telemetry=True, service_name="test-service")
        
        # Verify tracing was configured
        mock_configure_tracing.assert_called_once()
        assert mock_configure_tracing.call_args[1]["service_name"] == "test-service"


def test_setup_logging_with_app(mock_fastapi_app):
    """Test logging setup with FastAPI app."""
    with patch("pygovpub.logging.setup.configure_logging") as mock_configure_logging, \
         patch("pygovpub.logging.setup.debug_mode") as mock_debug_mode, \
         patch("pygovpub.logging.setup.add_logging_middleware") as mock_add_middleware, \
         patch("pygovpub.logging.setup.instrument_fastapi") as mock_instrument_fastapi:
        
        # Call setup_logging with app
        setup_logging(app=mock_fastapi_app, enable_telemetry=True)
        
        # Verify middleware was added
        mock_add_middleware.assert_called_once_with(
            mock_fastapi_app,
            exclude_paths=["/health", "/metrics"],
        )
        
        # Verify app was instrumented for telemetry
        mock_instrument_fastapi.assert_called_once()


def test_setup_api_logging(mock_fastapi_app, mock_config):
    """Test API-specific logging setup."""
    with patch("pygovpub.logging.setup.setup_logging") as mock_setup_logging, \
         patch.dict(os.environ, {"PYGOVPUB_API_LOG_LEVEL": "DEBUG", 
                               "PYGOVPUB_API_DEBUG_LEVEL": "3",
                               "PYGOVPUB_API_TELEMETRY_ENABLED": "true",
                               "PYGOVPUB_API_TELEMETRY_ENDPOINT": "http://tempo:4317",
                               "PYGOVPUB_API_SERVICE_NAME": "test-api"}):
        
        # Call setup_api_logging
        setup_api_logging(app=mock_fastapi_app, config=mock_config)
        
        # Verify setup_logging was called with correct parameters
        mock_setup_logging.assert_called_once()
        call_args = mock_setup_logging.call_args[1]
        assert call_args["config"] == mock_config
        assert call_args["log_level"] == "DEBUG"
        assert call_args["debug_level"] == 3
        assert call_args["enable_telemetry"] == True
        assert call_args["telemetry_endpoint"] == "http://tempo:4317"
        assert call_args["service_name"] == "test-api"
        assert call_args["app"] == mock_fastapi_app


def test_setup_api_logging_defaults(mock_fastapi_app):
    """Test API-specific logging setup with default values."""
    with patch("pygovpub.logging.setup.setup_logging") as mock_setup_logging:
        
        # Call setup_api_logging with minimal parameters
        setup_api_logging(app=mock_fastapi_app)
        
        # Verify setup_logging was called with default parameters
        mock_setup_logging.assert_called_once()
        call_args = mock_setup_logging.call_args[1]
        assert call_args["log_level"] == LogLevel.INFO
        assert call_args["debug_level"] == DebugLevel.NONE
        assert call_args["enable_telemetry"] == False
        assert call_args["service_name"] == "pygovpub-api"
        assert call_args["app"] == mock_fastapi_app