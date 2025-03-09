"""
Logging system setup and configuration.

This module provides a comprehensive setup function for initializing
all logging components in one call.
"""

import os
from typing import Dict, List, Optional, Union

from fastapi import FastAPI
from opentelemetry.trace import SpanKind

from pygovpub.config import Config
from pygovpub.logging import LogLevel, configure_logging
from pygovpub.logging.debug import DebugLevel, debug_mode
from pygovpub.logging.middleware import add_logging_middleware
from pygovpub.logging.telemetry import configure_tracing, instrument_fastapi


def setup_logging(
    config: Optional[Config] = None,
    log_level: Union[str, int, LogLevel] = LogLevel.INFO,
    debug_level: Union[int, DebugLevel] = DebugLevel.NONE,
    log_file: Optional[str] = None,
    json_format: bool = False,
    enable_telemetry: bool = False,
    telemetry_endpoint: Optional[str] = None,
    app: Optional[FastAPI] = None,
    service_name: str = "pygovpub",
    resource_attributes: Optional[Dict[str, str]] = None,
) -> None:
    """
    Set up all logging components.
    
    This function configures the entire logging system, including:
    - Structured logging
    - Debug mode
    - Telemetry/tracing
    - FastAPI integration (if an app is provided)
    
    Args:
        config: SDK configuration (optional)
        log_level: Logging level
        debug_level: Debug level
        log_file: Path to log file
        json_format: Whether to format logs as JSON
        enable_telemetry: Whether to enable OpenTelemetry tracing
        telemetry_endpoint: Endpoint for telemetry export
        app: FastAPI app to instrument (optional)
        service_name: Service name for telemetry
        resource_attributes: Additional resource attributes for telemetry
    """
    # Convert log level if needed
    if isinstance(log_level, LogLevel):
        log_level = log_level.value
    
    # Configure environment variables from config
    if config:
        # Use environment for logging configuration
        if "PYGOVPUB_LOG_LEVEL" in os.environ:
            log_level = os.environ["PYGOVPUB_LOG_LEVEL"]
        
        if "PYGOVPUB_LOG_FILE" in os.environ:
            log_file = os.environ["PYGOVPUB_LOG_FILE"]
        
        if "PYGOVPUB_LOG_JSON" in os.environ:
            json_format = os.environ["PYGOVPUB_LOG_JSON"].lower() == "true"
        
        if "PYGOVPUB_DEBUG_LEVEL" in os.environ:
            debug_level = int(os.environ["PYGOVPUB_DEBUG_LEVEL"])
        
        if "PYGOVPUB_TELEMETRY_ENABLED" in os.environ:
            enable_telemetry = os.environ["PYGOVPUB_TELEMETRY_ENABLED"].lower() == "true"
        
        if "PYGOVPUB_TELEMETRY_ENDPOINT" in os.environ:
            telemetry_endpoint = os.environ["PYGOVPUB_TELEMETRY_ENDPOINT"]
    
    # Configure base logging
    configure_logging(
        log_level=log_level,
        json_format=json_format,
        log_file=log_file,
    )
    
    # Set debug level
    debug_mode.set_level(debug_level)
    
    # Configure telemetry if enabled
    if enable_telemetry:
        # Create resource attributes from config if not provided
        if config and not resource_attributes:
            resource_attributes = {
                "service.name": service_name,
                "service.version": "0.1.0",  # TODO: Get from package version
                "environment": config.environment,
            }
        
        # Configure tracing
        configure_tracing(
            service_name=service_name,
            enable_console_export=debug_mode.is_enabled(DebugLevel.TRACE),
            otlp_endpoint=telemetry_endpoint,
            resource_attributes=resource_attributes,
        )
    
    # Instrument FastAPI app if provided
    if app:
        # Add logging middleware
        add_logging_middleware(
            app,
            exclude_paths=["/health", "/metrics"],
        )
        
        # Instrument with OpenTelemetry if enabled
        if enable_telemetry:
            instrument_fastapi(
                app,
                excluded_urls=["^/health", "^/metrics"],
            )


def setup_api_logging(
    app: FastAPI,
    config: Optional[Config] = None,
    log_level: Union[str, int, LogLevel] = LogLevel.INFO,
    debug_level: Union[int, DebugLevel] = DebugLevel.NONE,
) -> None:
    """
    Set up logging specifically for a FastAPI application.
    
    This is a convenience function for API-specific setup that
    configures middleware and tracing.
    
    Args:
        app: FastAPI application
        config: SDK configuration (optional)
        log_level: Logging level
        debug_level: Debug level
    """
    # Get environment variables from config
    enable_telemetry = False
    telemetry_endpoint = None
    service_name = "pygovpub-api"
    log_file = None
    json_format = True
    
    if config:
        # Use environment for logging configuration
        if "PYGOVPUB_API_LOG_LEVEL" in os.environ:
            log_level = os.environ["PYGOVPUB_API_LOG_LEVEL"]
        
        if "PYGOVPUB_API_LOG_FILE" in os.environ:
            log_file = os.environ["PYGOVPUB_API_LOG_FILE"]
        
        if "PYGOVPUB_API_DEBUG_LEVEL" in os.environ:
            debug_level = int(os.environ["PYGOVPUB_API_DEBUG_LEVEL"])
        
        if "PYGOVPUB_API_TELEMETRY_ENABLED" in os.environ:
            enable_telemetry = os.environ["PYGOVPUB_API_TELEMETRY_ENABLED"].lower() == "true"
        
        if "PYGOVPUB_API_TELEMETRY_ENDPOINT" in os.environ:
            telemetry_endpoint = os.environ["PYGOVPUB_API_TELEMETRY_ENDPOINT"]
        
        if "PYGOVPUB_API_SERVICE_NAME" in os.environ:
            service_name = os.environ["PYGOVPUB_API_SERVICE_NAME"]
    
    # Configure using main setup function
    setup_logging(
        config=config,
        log_level=log_level,
        debug_level=debug_level,
        log_file=log_file,
        json_format=json_format,
        enable_telemetry=enable_telemetry,
        telemetry_endpoint=telemetry_endpoint,
        app=app,
        service_name=service_name,
    )