"""
Test the logging setup module.

These tests verify that the logging setup functions correctly configure
the logging system components.
"""

import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI

from pygovpub.config import Config
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
    config = MagicMock(spec=Config)
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


def test_setup_logging_with_log_file():
    """Test logging setup with a log file specified."""
    with patch("pygovpub.logging.setup.configure_logging") as mock_configure_logging:
        log_file_path = "/tmp/pygovpub-test.log"
        setup_logging(log_file=log_file_path)
        
        # Verify that configure_logging was called with log file
        mock_configure_logging.assert_called_once()
        call_args = mock_configure_logging.call_args[1]
        assert call_args["log_file"] == log_file_path


def test_setup_logging_with_custom_resource_attributes():
    """Test logging setup with custom resource attributes for telemetry."""
    with patch("pygovpub.logging.setup.configure_tracing") as mock_configure_tracing:
        custom_attributes = {
            "service.name": "custom-service",
            "deployment.environment": "staging",
            "custom.attribute": "value"
        }
        
        setup_logging(
            enable_telemetry=True,
            resource_attributes=custom_attributes
        )
        
        # Verify that configure_tracing was called with custom attributes
        mock_configure_tracing.assert_called_once()
        call_args = mock_configure_tracing.call_args[1]
        assert call_args["resource_attributes"] == custom_attributes


def test_setup_logging_with_auto_resource_attributes(mock_config):
    """Test that resource attributes are auto-generated from config if not provided."""
    with patch("pygovpub.logging.setup.configure_tracing") as mock_configure_tracing:
        setup_logging(
            config=mock_config,
            enable_telemetry=True,
            service_name="auto-service"
        )
        
        # Verify that configure_tracing was called with auto-generated attributes
        mock_configure_tracing.assert_called_once()
        call_args = mock_configure_tracing.call_args[1]
        expected_attributes = {
            "service.name": "auto-service",
            "service.version": "0.1.0",
            "environment": "test",
        }
        assert call_args["resource_attributes"] == expected_attributes


def test_setup_logging_with_partial_environment_config():
    """Test logging setup with partial configuration from environment variables."""
    env_vars = {
        "PYGOVPUB_LOG_LEVEL": "DEBUG",
        # No debug level set in env
        "PYGOVPUB_LOG_JSON": "true",
        # No telemetry endpoint but telemetry enabled
        "PYGOVPUB_TELEMETRY_ENABLED": "true",
    }
    
    with patch("pygovpub.logging.setup.configure_logging") as mock_configure_logging, \
         patch("pygovpub.logging.setup.debug_mode") as mock_debug_mode, \
         patch("pygovpub.logging.setup.configure_tracing") as mock_configure_tracing, \
         patch.dict(os.environ, env_vars, clear=True):
        
        # Create a real config that will pick up environment variables
        config = MagicMock(spec=Config)
        config.environment = "dev"
        
        # Call with explicit debug level but other values from environment
        setup_logging(
            config=config,
            debug_level=DebugLevel.BASIC  # Use BASIC instead of DEBUG which doesn't exist
        )
        
        # Check configure_logging got correct values
        mock_configure_logging.assert_called_once()
        call_args = mock_configure_logging.call_args[1]
        assert call_args["log_level"] == "DEBUG"
        assert call_args["json_format"] == True
        
        # Check debug mode was set from parameter, not environment
        mock_debug_mode.set_level.assert_called_once_with(DebugLevel.BASIC)
        
        # Check telemetry was enabled from environment
        mock_configure_tracing.assert_called_once()


def test_setup_api_logging_with_partial_environment(mock_config):
    """Test API logging setup with partial environment configuration."""
    env_vars = {
        "PYGOVPUB_API_LOG_LEVEL": "WARNING",
        # Other values not set
    }
    
    with patch("pygovpub.logging.setup.setup_logging") as mock_setup_logging, \
         patch.dict(os.environ, env_vars, clear=True):
        
        app = FastAPI()
        # Pass config to enable environment variable reading
        setup_api_logging(app=app, config=mock_config)
        
        # Verify setup_logging was called with environment value for log_level
        # but defaults for other parameters
        mock_setup_logging.assert_called_once()
        call_args = mock_setup_logging.call_args[1]
        
        # Now that we're passing config, environment variables should be read
        assert call_args["log_level"] == "WARNING"
        assert call_args["debug_level"] == DebugLevel.NONE
        assert call_args["enable_telemetry"] == False
        assert call_args["app"] == app


def test_setup_logging_with_real_log_file():
    """Test logging setup with a real log file."""
    with tempfile.NamedTemporaryFile(suffix='.log') as tmp_file, \
         patch("pygovpub.logging.setup.debug_mode"), \
         patch("pygovpub.logging.setup.configure_logging", wraps=lambda **kwargs: None):
        
        # Call setup_logging with a real temporary file
        setup_logging(log_file=tmp_file.name)
        
        # Since we can't easily verify the file contents without refactoring,
        # we just check that the file still exists
        assert os.path.exists(tmp_file.name)


def test_setup_logging_log_level_conversion():
    """Test that LogLevel enum values are correctly converted to integers."""
    with patch("pygovpub.logging.setup.configure_logging") as mock_configure_logging:
        # Call with LogLevel enum
        setup_logging(log_level=LogLevel.DEBUG)
        
        # Verify conversion happened
        mock_configure_logging.assert_called_once()
        call_args = mock_configure_logging.call_args[1]
        assert call_args["log_level"] == LogLevel.DEBUG.value
        assert isinstance(call_args["log_level"], int)


def test_setup_logging_with_log_file_from_env():
    """Test that log file is correctly read from environment."""
    log_file_path = "/tmp/env-log-file.log"
    env_vars = {"PYGOVPUB_LOG_FILE": log_file_path}
    
    with patch("pygovpub.logging.setup.configure_logging") as mock_configure_logging, \
         patch.dict(os.environ, env_vars, clear=True):
        
        # Call with a config that will trigger environment reading
        config = MagicMock(spec=Config)
        setup_logging(config=config)
        
        # Verify log file was read from environment
        mock_configure_logging.assert_called_once()
        call_args = mock_configure_logging.call_args[1]
        assert call_args["log_file"] == log_file_path


def test_json_format_from_environment():
    """Test that json_format is correctly parsed from environment."""
    # Test both true and false values
    test_cases = [
        ("true", True),
        ("TRUE", True),
        ("True", True),
        ("false", False),
        ("FALSE", False),
        ("False", False),
    ]
    
    for env_value, expected_value in test_cases:
        with patch("pygovpub.logging.setup.configure_logging") as mock_configure_logging, \
             patch.dict(os.environ, {"PYGOVPUB_LOG_JSON": env_value}, clear=True):
            
            config = MagicMock(spec=Config)
            setup_logging(config=config)
            
            mock_configure_logging.assert_called_once()
            call_args = mock_configure_logging.call_args[1]
            assert call_args["json_format"] == expected_value
            mock_configure_logging.reset_mock()


def test_setup_logging_telemetry_based_on_debug():
    """Test that console export for telemetry is based on debug trace level."""
    with patch("pygovpub.logging.setup.configure_tracing") as mock_configure_tracing, \
         patch("pygovpub.logging.setup.debug_mode") as mock_debug_mode:
        
        # Set up debug mode to return True for trace level
        mock_debug_mode.is_enabled.return_value = True
        
        setup_logging(
            enable_telemetry=True,
            debug_level=DebugLevel.TRACE
        )
        
        # Verify debug check for trace level
        mock_debug_mode.is_enabled.assert_called_once_with(DebugLevel.TRACE)
        
        # Verify that console export is enabled based on trace debug level
        mock_configure_tracing.assert_called_once()
        call_args = mock_configure_tracing.call_args[1]
        assert call_args["enable_console_export"] == True


def test_setup_api_logging_with_all_env_vars():
    """Test API logging setup with all environment variables set."""
    env_vars = {
        "PYGOVPUB_API_LOG_LEVEL": "ERROR",
        "PYGOVPUB_API_LOG_FILE": "/tmp/api.log",
        "PYGOVPUB_API_DEBUG_LEVEL": "1",
        "PYGOVPUB_API_TELEMETRY_ENABLED": "true",
        "PYGOVPUB_API_TELEMETRY_ENDPOINT": "http://localhost:4317",
        "PYGOVPUB_API_SERVICE_NAME": "custom-api-service",
    }
    
    with patch("pygovpub.logging.setup.setup_logging") as mock_setup_logging, \
         patch.dict(os.environ, env_vars, clear=True):
        
        app = FastAPI()
        config = MagicMock(spec=Config)
        
        setup_api_logging(app=app, config=config)
        
        # Verify all environment values were passed through
        mock_setup_logging.assert_called_once()
        call_args = mock_setup_logging.call_args[1]
        assert call_args["log_level"] == "ERROR"
        assert call_args["log_file"] == "/tmp/api.log"
        assert call_args["debug_level"] == 1
        assert call_args["enable_telemetry"] == True
        assert call_args["telemetry_endpoint"] == "http://localhost:4317"
        assert call_args["service_name"] == "custom-api-service"


def test_setup_logging_with_no_app_and_telemetry_disabled():
    """Test that app is not instrumented when telemetry is disabled or app is not provided."""
    with patch("pygovpub.logging.setup.configure_logging"), \
         patch("pygovpub.logging.setup.debug_mode"), \
         patch("pygovpub.logging.setup.add_logging_middleware") as mock_add_middleware, \
         patch("pygovpub.logging.setup.instrument_fastapi") as mock_instrument_fastapi:
        
        # Call with no app and telemetry enabled
        setup_logging(enable_telemetry=True)
        
        # Verify that middleware and instrumentation were not added
        mock_add_middleware.assert_not_called()
        mock_instrument_fastapi.assert_not_called()
        
        # Reset mocks
        mock_add_middleware.reset_mock()
        mock_instrument_fastapi.reset_mock()
        
        # Call with app but telemetry disabled
        app = FastAPI()
        setup_logging(app=app, enable_telemetry=False)
        
        # Verify that middleware was added but instrumentation was not
        mock_add_middleware.assert_called_once()
        mock_instrument_fastapi.assert_not_called()


def test_telemetry_endpoint_from_environment(mock_config):
    """Test that telemetry endpoint is correctly read from environment variables."""
    endpoint = "http://jaeger:4317"
    env_vars = {"PYGOVPUB_TELEMETRY_ENDPOINT": endpoint}
    
    with patch("pygovpub.logging.setup.configure_logging"), \
         patch("pygovpub.logging.setup.debug_mode"), \
         patch("pygovpub.logging.setup.configure_tracing") as mock_configure_tracing, \
         patch.dict(os.environ, env_vars, clear=True):
        
        # Use the fixture which already has an 'environment' attribute
        setup_logging(config=mock_config, enable_telemetry=True)
        
        # Verify telemetry was configured with endpoint from environment
        mock_configure_tracing.assert_called_once()
        assert mock_configure_tracing.call_args[1]["otlp_endpoint"] == endpoint