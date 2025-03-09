"""
Tests for the logging system in PyGovPub SDK.

These tests verify the core logging functionality including:
- Log level handling
- Structured logging format
- Integration with Python's logging system
- Request tracing
- Performance monitoring
"""

import io
import json
import logging
import re
import uuid
from unittest.mock import MagicMock, patch

import pytest
import structlog
from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.testclient import TestClient

from pygovpub.logging import LogCategory, LogLevel, configure_logging, get_logger


class TestLogConfiguration:
    """Test the log configuration functionality."""

    def test_log_level_handling(self):
        """Test that log levels are properly handled."""
        # Setup a string buffer to capture log output
        log_output = io.StringIO()
        handler = logging.StreamHandler(log_output)
        
        # Configure logging with our handler
        configure_logging(log_level="DEBUG", handlers=[handler])
        
        # Get a logger and emit logs at different levels
        logger = get_logger("test")
        logger.debug("debug message")
        logger.info("info message")
        logger.warning("warning message")
        logger.error("error message")
        
        # Check the output
        output = log_output.getvalue()
        assert "debug message" in output
        assert "info message" in output
        assert "warning message" in output
        assert "error message" in output
        
        # Reset the log buffer
        log_output.seek(0)
        log_output.truncate(0)
        
        # Reconfigure with INFO level
        configure_logging(log_level="INFO", handlers=[handler])
        
        # Get a new logger and emit logs
        logger = get_logger("test2")
        logger.debug("debug message 2")
        logger.info("info message 2")
        
        # Check the output - debug should be suppressed
        output = log_output.getvalue()
        assert "debug message 2" not in output
        assert "info message 2" in output

    def test_structured_format(self):
        """Test that logs are properly structured."""
        # Setup a string buffer to capture log output
        log_output = io.StringIO()
        handler = logging.StreamHandler(log_output)
        
        # Configure logging to output JSON
        configure_logging(log_level="INFO", json_format=True, handlers=[handler])
        
        # Get a logger with some context
        logger = get_logger("test").bind(request_id="123", user="test_user")
        
        # Emit a log
        logger.info("test message", extra_data={"key": "value"})
        
        # Check the output is valid JSON and contains expected fields
        output = log_output.getvalue()
        log_entry = json.loads(output)
        
        assert log_entry["event"] == "test message"
        assert log_entry["logger"] == "test"
        assert log_entry["level"] == "info"
        assert log_entry["request_id"] == "123"
        assert log_entry["user"] == "test_user"
        assert log_entry["extra_data"] == {"key": "value"}
        assert "timestamp" in log_entry

    def test_context_propagation(self):
        """Test that context is properly propagated between loggers."""
        # Setup capture
        log_output = io.StringIO()
        handler = logging.StreamHandler(log_output)
        configure_logging(log_level="INFO", json_format=True, handlers=[handler])
        
        # Import the bind_context function
        from pygovpub.logging import bind_context, clear_context
        
        # Create a logger with context
        logger1 = get_logger("logger1")
        
        # Bind context
        bind_context(request_id="REQ123")
        
        # Log with the context
        logger1.info("first message")
        
        # Create another logger that should inherit the context
        logger2 = get_logger("logger2")
        logger2.info("second message")
        
        # Clear context
        clear_context()
        
        # Create a third logger outside the context
        logger3 = get_logger("logger3")
        logger3.info("third message")
        
        # Check outputs
        outputs = log_output.getvalue().strip().split("\n")
        entry1 = json.loads(outputs[0])
        entry2 = json.loads(outputs[1])
        entry3 = json.loads(outputs[2])
        
        assert entry1["request_id"] == "REQ123"
        assert entry1["event"] == "first message"
        
        assert entry2["request_id"] == "REQ123"
        assert entry2["event"] == "second message"
        
        assert "request_id" not in entry3
        assert entry3["event"] == "third message"


@pytest.fixture
def test_app():
    """Create a test FastAPI app with logging middleware."""
    app = FastAPI()
    
    @app.get("/test")
    async def test_endpoint():
        logger = get_logger("test_endpoint")
        logger.info("Endpoint called")
        return {"status": "ok"}
    
    @app.get("/error")
    async def error_endpoint():
        logger = get_logger("error_endpoint")
        logger.error("Something went wrong")
        raise ValueError("Test error")
    
    return app


class TestRequestTracing:
    """Test the request tracing functionality."""
    
    def test_trace_id_generation(self, test_app):
        """Test that trace IDs are generated for requests without them."""
        with patch("uuid.uuid4") as mock_uuid:
            mock_uuid.return_value = uuid.UUID("12345678-1234-5678-1234-567812345678")
            
            # Add middleware
            from pygovpub.logging.middleware import RequestLoggingMiddleware
            test_app.add_middleware(RequestLoggingMiddleware)
            client = TestClient(test_app)
            
            # Make a request without trace ID
            response = client.get("/test")
            
            # Verify that uuid4 was called to generate a trace ID
            assert mock_uuid.called
    
    def test_trace_id_propagation(self, test_app):
        """Test that trace IDs are propagated through the request."""
        # Setup log capture
        log_output = io.StringIO()
        handler = logging.StreamHandler(log_output)
        configure_logging(log_level="INFO", json_format=True, handlers=[handler])
        
        # Add middleware
        from pygovpub.logging.middleware import RequestLoggingMiddleware
        test_app.add_middleware(RequestLoggingMiddleware)
        client = TestClient(test_app)
        
        # Make a request with trace ID
        trace_id = "12345678-1234-5678-1234-567812345678"
        response = client.get("/test", headers={"X-Trace-ID": trace_id})
        
        # Check the logs
        outputs = log_output.getvalue().strip().split("\n")
        
        # At least two logs should exist - one from middleware, one from endpoint
        assert len(outputs) >= 2
        
        # All logs should have the same trace ID
        for output in outputs:
            log_entry = json.loads(output)
            if "trace_id" in log_entry:  # Some logs might not have trace_id
                assert log_entry["trace_id"] == trace_id


class TestPerformanceMonitoring:
    """Test the performance monitoring functionality."""
    
    def test_request_timing(self, test_app):
        """Test that request timing is captured."""
        # Setup log capture
        log_output = io.StringIO()
        handler = logging.StreamHandler(log_output)
        configure_logging(log_level="INFO", json_format=True, handlers=[handler])
        
        # Add middleware with timing
        from pygovpub.logging.middleware import RequestLoggingMiddleware
        test_app.add_middleware(RequestLoggingMiddleware)
        client = TestClient(test_app)
        
        # Make a request
        response = client.get("/test")
        
        # Check the logs for timing information
        outputs = log_output.getvalue().strip().split("\n")
        request_complete_log = None
        
        for output in outputs:
            log_entry = json.loads(output)
            if log_entry.get("event") == "request_completed":
                request_complete_log = log_entry
                break
        
        assert request_complete_log is not None
        assert "duration_ms" in request_complete_log
        assert isinstance(request_complete_log["duration_ms"], (int, float))
        assert request_complete_log["duration_ms"] >= 0


class TestErrorLogging:
    """Test the error logging functionality."""
    
    def test_exception_logging(self, test_app):
        """Test that exceptions are properly logged."""
        # Setup log capture
        log_output = io.StringIO()
        handler = logging.StreamHandler(log_output)
        configure_logging(log_level="INFO", json_format=True, handlers=[handler])
        
        # Add middleware
        from pygovpub.logging.middleware import RequestLoggingMiddleware
        test_app.add_middleware(RequestLoggingMiddleware)
        client = TestClient(test_app)
        
        # Make a request that raises an exception
        with pytest.raises(ValueError):
            # Use the client directly to avoid TestClient catching the exception
            client.get("/error")
        
        # Check the logs
        outputs = log_output.getvalue().strip().split("\n")
        error_logs = []
        
        for output in outputs:
            log_entry = json.loads(output)
            if log_entry.get("level") == "error":
                error_logs.append(log_entry)
        
        # We should have at least one error log (there may be multiple due to middleware)
        assert len(error_logs) > 0
        
        # Find the endpoint log (from the view function)
        endpoint_log = None
        middleware_log = None
        
        for log in error_logs:
            if log.get("event") == "Something went wrong":
                endpoint_log = log
            if log.get("event") == "request_failed":
                middleware_log = log
        
        # Either the endpoint log or middleware log should exist
        assert endpoint_log is not None or middleware_log is not None
        
        # If middleware log exists, check for exception details
        if middleware_log:
            assert "exception" in middleware_log