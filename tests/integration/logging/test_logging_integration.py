"""
Integration tests for the PyGovPub logging system.

These tests verify that the entire logging system works 
correctly when used in realistic scenarios.
"""

import io
import json
import logging
import os
import tempfile
from contextlib import redirect_stdout

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from pygovpub.logging import LogCategory, LogLevel, bind_context, configure_logging, get_logger
from pygovpub.logging.client import LoggingClient
from pygovpub.logging.debug import DebugLevel, debug_mode
from pygovpub.logging.middleware import RequestLoggingMiddleware, add_logging_middleware
from pygovpub.logging.performance import increment_counter, set_gauge, timer
from pygovpub.logging.setup import setup_api_logging, setup_logging


def test_logging_middleware_integration():
    """Test that logging middleware integrates properly with FastAPI."""
    # Create a test app
    app = FastAPI()
    
    # Configure logging
    log_output = io.StringIO()
    handler = logging.StreamHandler(log_output)
    configure_logging(log_level="INFO", json_format=True, handlers=[handler])
    
    # Add middleware
    add_logging_middleware(app)
    
    # Add routes
    @app.get("/test")
    async def test_route():
        logger = get_logger("test_route")
        logger.info("Route accessed")
        return {"status": "ok"}
    
    @app.get("/error")
    async def error_route():
        logger = get_logger("error_route")
        logger.error("Error encountered")
        raise ValueError("Test error")
    
    # Create test client
    client = TestClient(app)
    
    # Make a request
    response = client.get("/test")
    assert response.status_code == 200
    
    # Check logs
    logs = log_output.getvalue()
    
    # There should be at least two log entries (request start and complete)
    assert "request_started" in logs
    assert "request_completed" in logs
    assert "Route accessed" in logs


def test_performance_monitoring_integration():
    """Test performance monitoring integration."""
    # Configure logging
    log_output = io.StringIO()
    handler = logging.StreamHandler(log_output)
    configure_logging(log_level="INFO", json_format=True, handlers=[handler])
    
    # Test timer
    with timer("test_operation"):
        # Simulate work
        for _ in range(100000):
            pass
    
    # Test counters and gauges
    increment_counter("api_calls", 5, {"api": "test"})
    set_gauge("memory_usage", 1024, {"component": "test"})
    
    # Check logs
    logs = log_output.getvalue()
    
    # There should be a log entry for the timer
    assert "operation_timed" in logs
    assert "test_operation" in logs


def test_debug_mode_integration():
    """Test debug mode integration."""
    # Set up a file to capture debug output
    with tempfile.NamedTemporaryFile(mode='w+', delete=False) as debug_file:
        try:
            # Set debug output to file
            debug_mode.set_output(debug_file.name)
            
            # Set debug level
            debug_mode.set_level(DebugLevel.DETAILED)
            
            # Enable http category
            debug_mode.enable_category("http")
            
            # Capture a request
            debug_mode.capture_request(
                method="GET",
                url="https://example.com/test",
                headers={"Authorization": "Bearer token", "Content-Type": "application/json"},
                params={"param1": "value1"}
            )
            
            # Capture a response
            debug_mode.capture_response(
                status_code=200,
                headers={"Content-Type": "application/json"},
                content=json.dumps({"result": "success"}),
                elapsed=0.1
            )
            
            # Close file to ensure it's written
            debug_file.close()
            
            # Read debug output
            with open(debug_file.name, 'r') as f:
                debug_output = f.read()
            
            # Check debug output
            assert "Outgoing HTTP Request" in debug_output
            assert "HTTP Response: 200" in debug_output
            assert "[REDACTED]" in debug_output  # Sensitive headers should be redacted
            
        finally:
            # Clean up temp file
            os.unlink(debug_file.name)


def test_logging_client_integration():
    """Test LoggingClient integration."""
    # Set up logging
    log_output = io.StringIO()
    handler = logging.StreamHandler(log_output)
    configure_logging(log_level="INFO", json_format=True, handlers=[handler])
    
    # Create a mock http server
    import http.server
    import socketserver
    import threading
    
    class MockHandler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode())
        
        def log_message(self, format, *args):
            # Suppress logging
            pass
    
    # Find an available port
    with socketserver.TCPServer(("", 0), MockHandler) as httpd:
        port = httpd.server_address[1]
        
        # Start server in a thread
        server_thread = threading.Thread(target=httpd.serve_forever)
        server_thread.daemon = True
        server_thread.start()
        
        try:
            # Create client
            client = LoggingClient(f"http://localhost:{port}")
            
            # Make a request
            response = client.get("/test")
            
            # Check response
            assert response.status_code == 200
            assert response.json() == {"status": "ok"}
            
            # Check logs
            logs = log_output.getvalue()
            
            # There should be log entries for the request
            assert "HTTP Request" in logs
            assert "operation_timed" in logs
            
        finally:
            # Shut down server
            httpd.shutdown()
            server_thread.join()


def test_setup_integration():
    """Test setup module integration."""
    # Create FastAPI app
    app = FastAPI()
    
    # Setup logging
    setup_logging(
        log_level=LogLevel.INFO,
        debug_level=DebugLevel.BASIC,
        json_format=True,
        app=app
    )
    
    # Add a route
    @app.get("/test")
    async def test_route():
        logger = get_logger("test_route")
        logger.info("Route accessed")
        return {"status": "ok"}
    
    # Create test client
    client = TestClient(app)
    
    # Make a request
    response = client.get("/test")
    assert response.status_code == 200
    
    # Check that we got expected log output
    assert response.status_code == 200