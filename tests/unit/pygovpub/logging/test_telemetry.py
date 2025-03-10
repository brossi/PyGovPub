"""
Test the telemetry module.

These tests verify that the telemetry module correctly configures
the OpenTelemetry tracing and instruments FastAPI applications.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from opentelemetry.trace import SpanKind, Status, StatusCode

from pygovpub.logging.telemetry import (
    configure_tracing,
    instrument_fastapi,
    trace_function,
    TraceContext,
)


@pytest.fixture
def mock_fastapi_app():
    """Create a mock FastAPI application."""
    return FastAPI()


def test_configure_tracing():
    """Test configuring OpenTelemetry tracing."""
    with patch("pygovpub.logging.telemetry.Resource") as mock_resource, \
         patch("pygovpub.logging.telemetry.TracerProvider") as mock_provider, \
         patch("pygovpub.logging.telemetry.ConsoleSpanExporter") as mock_console_exporter, \
         patch("pygovpub.logging.telemetry.BatchSpanProcessor") as mock_batch_processor, \
         patch("pygovpub.logging.telemetry.OTLPSpanExporter") as mock_otlp_exporter, \
         patch("pygovpub.logging.telemetry.trace") as mock_trace, \
         patch("pygovpub.logging.telemetry._logger") as mock_logger:
        
        # Setup mocks
        mock_resource.create.return_value = MagicMock()
        mock_provider.return_value = MagicMock()
        mock_trace.get_tracer.return_value = MagicMock()
        
        # Call function
        result = configure_tracing(
            service_name="test-service",
            enable_console_export=True,
            otlp_endpoint="http://localhost:4317",
            resource_attributes={"custom_key": "custom_value"}
        )
        
        # Verify resource creation
        mock_resource.create.assert_called_once()
        resource_call = mock_resource.create.call_args[0][0]
        assert "service.name" in resource_call
        assert resource_call["service.name"] == "test-service"
        assert resource_call["custom_key"] == "custom_value"
        
        # Verify tracer provider setup
        mock_provider.assert_called_once()
        
        # Verify console exporter
        mock_console_exporter.assert_called_once()
        mock_batch_processor.assert_called()
        
        # Verify OTLP exporter
        mock_otlp_exporter.assert_called_once_with(endpoint="http://localhost:4317")
        
        # Verify tracer setup
        assert mock_trace.set_tracer_provider.called
        assert mock_provider.return_value.add_span_processor.call_count >= 2  # At least 2 processors should be added
        
        # Verify logger call
        mock_logger.info.assert_called_once()
        
        # Verify result is a tracer
        assert result == mock_trace.get_tracer.return_value


def test_configure_tracing_minimal():
    """Test configuring tracing with minimal parameters."""
    with patch("pygovpub.logging.telemetry.Resource") as mock_resource, \
         patch("pygovpub.logging.telemetry.TracerProvider") as mock_provider, \
         patch("pygovpub.logging.telemetry.ConsoleSpanExporter") as mock_console_exporter, \
         patch("pygovpub.logging.telemetry.BatchSpanProcessor") as mock_batch_processor, \
         patch("pygovpub.logging.telemetry.OTLPSpanExporter") as mock_otlp_exporter, \
         patch("pygovpub.logging.telemetry.trace") as mock_trace, \
         patch("pygovpub.logging.telemetry._logger") as mock_logger:
        
        # Call function with minimal parameters
        configure_tracing(service_name="test-service")
        
        # Verify minimal setup
        mock_console_exporter.assert_not_called()  # Console disabled by default
        mock_otlp_exporter.assert_not_called()  # No OTLP endpoint provided


def test_instrument_fastapi(mock_fastapi_app):
    """Test instrumenting a FastAPI application."""
    with patch("pygovpub.logging.telemetry.FastAPIInstrumentor") as mock_instrumentor, \
         patch("pygovpub.logging.telemetry._logger") as mock_logger:
        
        # Call function
        instrument_fastapi(
            app=mock_fastapi_app,
            excluded_urls=["^/health", "^/metrics"]
        )
        
        # Verify instrumentation
        mock_instrumentor.instrument_app.assert_called_once_with(
            mock_fastapi_app,
            excluded_urls=["^/health", "^/metrics"],
        )
        
        # Verify logging
        mock_logger.info.assert_called_once()


def test_trace_function_decorator():
    """Test the trace_function decorator."""
    with patch("pygovpub.logging.telemetry.trace") as mock_trace:
        # Set up mocks
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_trace.get_tracer.return_value = mock_tracer
        mock_tracer.start_as_current_span.return_value.__enter__.return_value = mock_span
        
        # Create a decorated function
        @trace_function
        def test_function(a, b=2):
            return a + b
        
        # Call the decorated function
        result = test_function(1, b=3)
        
        # Verify tracer was obtained for correct module
        mock_trace.get_tracer.assert_called_with(test_function.__module__)
        
        # Verify span was created with correct name
        span_name = f"{test_function.__module__}.{test_function.__qualname__}"
        mock_tracer.start_as_current_span.assert_called_once()
        assert mock_tracer.start_as_current_span.call_args[0][0] == span_name
        
        # Verify span was marked as successful
        mock_span.set_status.assert_called_once()
        status_arg = mock_span.set_status.call_args[0][0]
        assert status_arg.status_code == StatusCode.OK
        
        # Verify result
        assert result == 4


def test_trace_function_with_error():
    """Test trace_function with an exception."""
    with patch("pygovpub.logging.telemetry.trace") as mock_trace:
        # Set up mocks
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_trace.get_tracer.return_value = mock_tracer
        mock_tracer.start_as_current_span.return_value.__enter__.return_value = mock_span
        
        # Create a decorated function that raises an exception
        @trace_function
        def error_function():
            raise ValueError("Test error")
        
        # Call the decorated function
        with pytest.raises(ValueError):
            error_function()
        
        # Verify error recording
        mock_span.record_exception.assert_called_once()
        mock_span.set_status.assert_called_once()
        # The status should be ERROR with the exception message
        status_call = mock_span.set_status.call_args[0][0]
        assert status_call.status_code == StatusCode.ERROR
        assert "Test error" in status_call.description


def test_trace_function_with_explicit_parameters():
    """Test trace_function with explicit parameters."""
    with patch("pygovpub.logging.telemetry.trace") as mock_trace:
        # Set up mocks
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_trace.get_tracer.return_value = mock_tracer
        mock_tracer.start_as_current_span.return_value.__enter__.return_value = mock_span
        
        # Create a decorated function with explicit parameters
        @trace_function(name="custom_span", kind=SpanKind.CLIENT, attributes={"key": "value"})
        def test_function():
            return "result"
        
        # Call the decorated function
        result = test_function()
        
        # Verify span creation with the right parameters
        mock_tracer.start_as_current_span.assert_called_once()
        call_args = mock_tracer.start_as_current_span.call_args
        assert call_args[0][0] == "custom_span"
        assert call_args[1]["kind"] == SpanKind.CLIENT
        assert call_args[1]["attributes"] == {"key": "value"}
        
        # Verify result
        assert result == "result"


def test_trace_context_start_span():
    """Test TraceContext.start_span method."""
    with patch("pygovpub.logging.telemetry.trace") as mock_trace:
        # Set up mocks
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_trace.get_tracer.return_value = mock_tracer
        mock_tracer.start_span.return_value = mock_span
        
        # Call function
        span = TraceContext.start_span(
            name="test_span",
            kind=SpanKind.SERVER,
            attributes={"key": "value"}
        )
        
        # Verify tracer was obtained
        mock_trace.get_tracer.assert_called_once()
        
        # Verify span was created with correct parameters
        mock_tracer.start_span.assert_called_once_with(
            "test_span",
            kind=SpanKind.SERVER,
            attributes={"key": "value"}
        )
        
        # Verify returned span
        assert span == mock_span


def test_trace_context_add_event():
    """Test TraceContext.add_event method."""
    with patch("pygovpub.logging.telemetry.trace") as mock_trace:
        # Set up mocks
        mock_span = MagicMock()
        mock_trace.get_current_span.return_value = mock_span
        
        # Call function
        TraceContext.add_event(
            name="test_event",
            attributes={"key": "value"}
        )
        
        # Verify current span retrieval
        mock_trace.get_current_span.assert_called_once()
        
        # Verify event was added with correct parameters
        mock_span.add_event.assert_called_once_with(
            "test_event",
            attributes={"key": "value"}
        )


def test_trace_context_set_attribute():
    """Test TraceContext.set_attribute method."""
    with patch("pygovpub.logging.telemetry.trace") as mock_trace:
        # Set up mocks
        mock_span = MagicMock()
        mock_trace.get_current_span.return_value = mock_span
        
        # Call function
        TraceContext.set_attribute("test_key", "test_value")
        
        # Verify current span retrieval
        mock_trace.get_current_span.assert_called_once()
        
        # Verify attribute was set correctly
        mock_span.set_attribute.assert_called_once_with("test_key", "test_value")


def test_trace_context_record_exception():
    """Test TraceContext.record_exception method."""
    with patch("pygovpub.logging.telemetry.trace") as mock_trace:
        # Set up mocks
        mock_span = MagicMock()
        mock_trace.get_current_span.return_value = mock_span
        
        # Create exception
        exception = ValueError("Test error")
        
        # Call function
        TraceContext.record_exception(exception)
        
        # Verify current span retrieval
        mock_trace.get_current_span.assert_called_once()
        
        # Verify exception recording
        mock_span.record_exception.assert_called_once_with(exception)
        
        # Verify status setting
        mock_span.set_status.assert_called_once()
        status_call = mock_span.set_status.call_args[0][0]
        assert status_call.status_code == StatusCode.ERROR
        assert "Test error" in status_call.description


def test_trace_context_end_span():
    """Test TraceContext.end_span method."""
    with patch("pygovpub.logging.telemetry.trace") as mock_trace:
        # Set up mocks
        mock_span = MagicMock()
        mock_trace.get_current_span.return_value = mock_span
        
        # Call function
        TraceContext.end_span()
        
        # Verify current span retrieval
        mock_trace.get_current_span.assert_called_once()
        
        # Verify span ending
        mock_span.end.assert_called_once()