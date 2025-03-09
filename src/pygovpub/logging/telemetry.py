"""
OpenTelemetry integration for PyGovPub SDK.

This module provides integration with OpenTelemetry for distributed tracing,
allowing for advanced request tracing across service boundaries.
"""

import functools
from typing import Any, Callable, Dict, Optional, TypeVar, Union, cast

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.trace import SpanKind, Status, StatusCode

from pygovpub.logging import get_logger

# Type variable for function return type
T = TypeVar('T')

# Get a logger for telemetry module
_logger = get_logger("pygovpub.telemetry")


def configure_tracing(
    service_name: str = "pygovpub",
    enable_console_export: bool = False,
    otlp_endpoint: Optional[str] = None,
    resource_attributes: Optional[Dict[str, str]] = None,
) -> None:
    """
    Configure OpenTelemetry tracing for the application.
    
    Args:
        service_name: Name of the service for telemetry reporting
        enable_console_export: Whether to export spans to console (for development)
        otlp_endpoint: OTLP endpoint URL for sending traces
        resource_attributes: Additional resource attributes to include
    """
    # Create resource with service info
    attributes = resource_attributes or {}
    attributes["service.name"] = service_name
    
    resource = Resource.create(attributes)
    
    # Create trace provider
    tracer_provider = TracerProvider(resource=resource)
    
    # Set up exporters
    if enable_console_export:
        # Console exporter for local development
        tracer_provider.add_span_processor(
            BatchSpanProcessor(ConsoleSpanExporter())
        )
    
    if otlp_endpoint:
        # OTLP exporter for sending to collection backend
        otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
        tracer_provider.add_span_processor(
            BatchSpanProcessor(otlp_exporter)
        )
    
    # Set global tracer provider
    trace.set_tracer_provider(tracer_provider)
    
    # Get a tracer
    tracer = trace.get_tracer(__name__, tracer_provider=tracer_provider)
    
    _logger.info(
        "tracing_configured",
        service_name=service_name,
        console_export=enable_console_export,
        otlp_endpoint=otlp_endpoint,
    )
    
    return tracer


def instrument_fastapi(app, excluded_urls=None):
    """
    Instrument a FastAPI application with OpenTelemetry.
    
    This adds automatic tracing to all FastAPI routes.
    
    Args:
        app: FastAPI application instance
        excluded_urls: List of URL patterns to exclude from instrumentation
    """
    FastAPIInstrumentor.instrument_app(
        app,
        excluded_urls=excluded_urls,
    )
    
    _logger.info(
        "fastapi_instrumented",
        excluded_urls=excluded_urls,
    )


def trace_function(
    name: Optional[str] = None,
    kind: SpanKind = SpanKind.INTERNAL,
    attributes: Optional[Dict[str, Union[str, int, float, bool]]] = None,
) -> Callable:
    """
    Decorator to trace a function with OpenTelemetry.
    
    Args:
        name: Custom name for the span (default: function name)
        kind: Span kind (SERVER, CLIENT, PRODUCER, CONSUMER, INTERNAL)
        attributes: Additional attributes to add to the span
        
    Returns:
        Decorated function
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        # Default name is the function's qualified name
        span_name = name or f"{func.__module__}.{func.__qualname__}"
        
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            # Get current tracer
            tracer = trace.get_tracer(func.__module__)
            
            # Start a span
            with tracer.start_as_current_span(
                span_name,
                kind=kind,
                attributes=attributes,
            ) as span:
                try:
                    # Call the original function
                    result = func(*args, **kwargs)
                    
                    # Mark span as successful
                    span.set_status(Status(StatusCode.OK))
                    
                    return result
                except Exception as e:
                    # Record error details
                    span.record_exception(e)
                    span.set_status(
                        Status(StatusCode.ERROR, str(e))
                    )
                    
                    # Re-raise the exception
                    raise
        
        return wrapper
    
    # Handle case where decorator is used without parentheses
    if callable(name):
        func = name
        name = None
        return decorator(func)
    
    return decorator


class TraceContext:
    """Helper for manual span creation and management."""
    
    @staticmethod
    def start_span(
        name: str,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes: Optional[Dict[str, Union[str, int, float, bool]]] = None,
    ):
        """
        Start a new span.
        
        Args:
            name: Span name
            kind: Span kind
            attributes: Span attributes
            
        Returns:
            The newly created span
        """
        tracer = trace.get_tracer(__name__)
        return tracer.start_span(
            name,
            kind=kind,
            attributes=attributes,
        )
    
    @staticmethod
    def add_event(
        name: str,
        attributes: Optional[Dict[str, Union[str, int, float, bool]]] = None,
    ) -> None:
        """
        Add an event to the current span.
        
        Args:
            name: Event name
            attributes: Event attributes
        """
        current_span = trace.get_current_span()
        current_span.add_event(name, attributes=attributes)
    
    @staticmethod
    def set_attribute(key: str, value: Union[str, int, float, bool]) -> None:
        """
        Set an attribute on the current span.
        
        Args:
            key: Attribute key
            value: Attribute value
        """
        current_span = trace.get_current_span()
        current_span.set_attribute(key, value)
    
    @staticmethod
    def record_exception(exception: Exception) -> None:
        """
        Record an exception on the current span.
        
        Args:
            exception: Exception to record
        """
        current_span = trace.get_current_span()
        current_span.record_exception(exception)
        current_span.set_status(Status(StatusCode.ERROR, str(exception)))
    
    @staticmethod
    def end_span() -> None:
        """End the current span."""
        current_span = trace.get_current_span()
        current_span.end()