"""
Performance monitoring module for PyGovPub SDK.

This module provides tools for monitoring and measuring performance,
including metrics collection, timing decorators, and resource usage tracking.
"""

import functools
import inspect
import time
from contextlib import contextmanager
from typing import Any, Callable, Dict, List, Optional, TypeVar, Union, cast

from pygovpub.logging import LogCategory, get_logger

# Type variable for function return type
T = TypeVar('T')

# Global performance metrics
_metrics: Dict[str, Dict[str, Any]] = {
    "counters": {},
    "gauges": {},
    "histograms": {},
}

# Logger for performance metrics
_logger = get_logger("pygovpub.performance")


def timed(
    name: Optional[str] = None,
    threshold_ms: Optional[float] = None,
    log_args: bool = False,
) -> Callable:
    """
    Decorator to measure and log function execution time.
    
    Args:
        name: Custom name for the timer (default: function name)
        threshold_ms: Only log if execution time exceeds this threshold
        log_args: Whether to include function arguments in the log
        
    Returns:
        Decorated function
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        # Get function signature for better logging
        sig = inspect.signature(func)
        
        # Use function qualname (with module) as default name
        metric_name = name or f"{func.__module__}.{func.__qualname__}"
        
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            # Record start time
            start_time = time.perf_counter()
            
            # Prepare log context
            log_context = {}
            
            # Add call arguments if requested
            if log_args:
                # Bind arguments to signature parameters
                bound_args = sig.bind(*args, **kwargs)
                bound_args.apply_defaults()
                
                # Convert args to a safe representation
                safe_args = {}
                for param_name, param_val in bound_args.arguments.items():
                    # Skip self/cls for methods
                    if param_name in ('self', 'cls') and inspect.ismethod(func):
                        continue
                    
                    # Use str() for complex objects to avoid serialization issues
                    if hasattr(param_val, '__dict__'):
                        safe_val = f"{type(param_val).__name__}"
                    else:
                        try:
                            # Check if value is JSON serializable
                            safe_val = param_val
                        except (TypeError, ValueError):
                            safe_val = str(param_val)
                    
                    safe_args[param_name] = safe_val
                
                log_context["args"] = safe_args
            
            try:
                # Call the original function
                result = func(*args, **kwargs)
                return result
            finally:
                # Measure elapsed time
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                
                # Update histogram metrics
                if metric_name not in _metrics["histograms"]:
                    _metrics["histograms"][metric_name] = {
                        "count": 0,
                        "sum": 0,
                        "min": float('inf'),
                        "max": 0,
                    }
                
                hist = _metrics["histograms"][metric_name]
                hist["count"] += 1
                hist["sum"] += elapsed_ms
                hist["min"] = min(hist["min"], elapsed_ms)
                hist["max"] = max(hist["max"], elapsed_ms)
                
                # Log if above threshold or always if no threshold set
                if threshold_ms is None or elapsed_ms >= threshold_ms:
                    _logger.info(
                        "function_timed",
                        category=LogCategory.PERFORMANCE,
                        function=metric_name,
                        duration_ms=elapsed_ms,
                        **log_context
                    )
        
        return wrapper
    
    # Handle case where decorator is used without parentheses
    if callable(name):
        func = name
        name = None
        return decorator(func)
    
    return decorator


@contextmanager
def timer(
    name: str,
    threshold_ms: Optional[float] = None,
    extra_context: Optional[Dict[str, Any]] = None,
):
    """
    Context manager for timing a block of code.
    
    Args:
        name: Name of the operation being timed
        threshold_ms: Only log if execution time exceeds this threshold
        extra_context: Additional context to include in the log
        
    Yields:
        None
    """
    start_time = time.perf_counter()
    
    try:
        yield
    finally:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        
        # Add to metrics
        if name not in _metrics["histograms"]:
            _metrics["histograms"][name] = {
                "count": 0,
                "sum": 0,
                "min": float('inf'),
                "max": 0,
            }
        
        hist = _metrics["histograms"][name]
        hist["count"] += 1
        hist["sum"] += elapsed_ms
        hist["min"] = min(hist["min"], elapsed_ms)
        hist["max"] = max(hist["max"], elapsed_ms)
        
        # Log if above threshold or always if no threshold set
        if threshold_ms is None or elapsed_ms >= threshold_ms:
            context = extra_context or {}
            _logger.info(
                "operation_timed",
                category=LogCategory.PERFORMANCE,
                operation=name,
                duration_ms=elapsed_ms,
                **context
            )


def increment_counter(name: str, value: int = 1, tags: Optional[Dict[str, str]] = None) -> None:
    """
    Increment a counter metric.
    
    Args:
        name: Counter name
        value: Value to increment by
        tags: Additional tags for the metric
    """
    if name not in _metrics["counters"]:
        _metrics["counters"][name] = {"value": 0, "tags": tags or {}}
    
    _metrics["counters"][name]["value"] += value
    
    # Update tags if provided
    if tags:
        _metrics["counters"][name]["tags"].update(tags)
    
    # Log the increment
    _logger.debug(
        "counter_incremented",
        category=LogCategory.PERFORMANCE,
        counter=name,
        value=value,
        total=_metrics["counters"][name]["value"],
        tags=tags,
    )


def set_gauge(name: str, value: Union[int, float], tags: Optional[Dict[str, str]] = None) -> None:
    """
    Set a gauge metric value.
    
    Args:
        name: Gauge name
        value: Value to set
        tags: Additional tags for the metric
    """
    _metrics["gauges"][name] = {"value": value, "tags": tags or {}}
    
    # Log the gauge setting
    _logger.debug(
        "gauge_set",
        category=LogCategory.PERFORMANCE,
        gauge=name,
        value=value,
        tags=tags,
    )


def get_metrics() -> Dict[str, Dict[str, Any]]:
    """
    Get all collected metrics.
    
    Returns:
        Dictionary of all metrics
    """
    return _metrics.copy()


def reset_metrics() -> None:
    """Reset all metrics."""
    _metrics["counters"] = {}
    _metrics["gauges"] = {}
    _metrics["histograms"] = {}


class BottleneckDetector:
    """
    Analyzes performance metrics to detect bottlenecks.
    
    This class uses collected timing information to identify slow operations
    that might be bottlenecks in the application.
    """
    
    def __init__(self, threshold_ms: float = 200):
        """
        Initialize the bottleneck detector.
        
        Args:
            threshold_ms: Threshold for considering an operation slow (in ms)
        """
        self.threshold_ms = threshold_ms
        self.logger = get_logger("pygovpub.bottleneck")
    
    def analyze(self) -> List[Dict[str, Any]]:
        """
        Analyze current metrics and detect bottlenecks.
        
        Returns:
            List of detected bottlenecks
        """
        bottlenecks = []
        
        # Analyze histograms
        for name, data in _metrics["histograms"].items():
            # Skip metrics with insufficient data
            if data["count"] < 5:
                continue
            
            avg_duration = data["sum"] / data["count"]
            
            # Check if average duration exceeds threshold
            if avg_duration > self.threshold_ms:
                bottleneck = {
                    "name": name,
                    "avg_duration_ms": avg_duration,
                    "min_duration_ms": data["min"],
                    "max_duration_ms": data["max"],
                    "call_count": data["count"],
                }
                bottlenecks.append(bottleneck)
                
                # Log the bottleneck
                self.logger.warning(
                    "bottleneck_detected",
                    category=LogCategory.PERFORMANCE,
                    operation=name,
                    avg_duration_ms=avg_duration,
                    threshold_ms=self.threshold_ms,
                    call_count=data["count"],
                )
        
        return bottlenecks