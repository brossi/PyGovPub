"""
Recovery mechanisms for PyGovPub SDK.

This module provides retry logic, fallback strategies, and circuit breakers
to handle transient failures and ensure resilient API interactions.
"""

import asyncio
import logging
import random
import time
from datetime import datetime, timedelta
from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Set, Type, TypeVar, Union, cast

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    stop_after_delay,
    wait_exponential,
    wait_fixed,
    before_sleep_log,
    RetryError
)

from pygovpub.exceptions import (
    ApiError,
    ApiErrorSource,
    ErrorCode,
    ErrorContext,
    NetworkError,
    PyGovPubException,
    RateLimitExceededError,
    ResourceUnavailableError,
    TimeoutError
)

# Configure logging
logger = logging.getLogger("pygovpub.recovery")

# Type variables for generic functions
T = TypeVar('T')
R = TypeVar('R')


class CircuitState(str, Enum):
    """Circuit breaker states."""
    
    CLOSED = "closed"      # Normal operation, requests allowed
    OPEN = "open"          # Failure threshold exceeded, requests blocked
    HALF_OPEN = "half_open"  # Testing if service is recovered


class CircuitBreaker:
    """
    Circuit breaker for preventing repeated calls to failing services.
    
    Implements the circuit breaker pattern to prevent cascading failures
    by stopping requests to a service that has repeatedly failed.
    """
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 30,
        excluded_exceptions: Optional[List[Type[Exception]]] = None
    ):
        """Initialize circuit breaker.
        
        Args:
            name: Circuit breaker name/identifier
            failure_threshold: Number of consecutive failures before opening circuit
            recovery_timeout: Seconds to wait before transitioning to half-open
            excluded_exceptions: Exceptions that don't count as failures
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.excluded_exceptions = excluded_exceptions or []
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.last_attempt_time: Optional[datetime] = None
        self._lock = asyncio.Lock()
    
    async def execute(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """
        Execute a function with circuit breaker protection.
        
        Args:
            func: Function to execute
            *args: Positional arguments for function
            **kwargs: Keyword arguments for function
            
        Returns:
            Result of function execution
            
        Raises:
            PyGovPubException: If circuit is open or function fails
        """
        await self._check_state()
        
        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result
        except Exception as e:
            await self._on_error(e)
            raise
    
    async def _check_state(self) -> None:
        """Check circuit state and determine if request can proceed."""
        async with self._lock:
            self.last_attempt_time = datetime.now()
            
            if self.state == CircuitState.OPEN:
                # Check if recovery timeout has elapsed
                if self.last_failure_time and (
                    datetime.now() - self.last_failure_time > timedelta(seconds=self.recovery_timeout)
                ):
                    # Transition to half-open to test service
                    self.state = CircuitState.HALF_OPEN
                else:
                    # Circuit is open, reject request
                    raise PyGovPubException(
                        f"Circuit '{self.name}' is open, request rejected",
                        error_code=ErrorCode.RESOURCE_UNAVAILABLE,
                        suggestion=f"Circuit will reset in {self._get_reset_time()} seconds"
                    )
    
    async def _on_success(self) -> None:
        """Handle successful execution."""
        async with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                # Service is working again, close circuit
                self.state = CircuitState.CLOSED
                
            # Reset failure counter on success
            self.failure_count = 0
    
    async def _on_error(self, exception: Exception) -> None:
        """Handle execution error."""
        # Don't count excluded exceptions as failures
        if any(isinstance(exception, exc_type) for exc_type in self.excluded_exceptions):
            return
            
        async with self._lock:
            self.failure_count += 1
            self.last_failure_time = datetime.now()
            
            # If failure threshold reached, open circuit
            if (
                self.state == CircuitState.CLOSED and 
                self.failure_count >= self.failure_threshold
            ):
                self.state = CircuitState.OPEN
                logger.warning(
                    f"Circuit '{self.name}' opened after {self.failure_count} consecutive failures"
                )
            # If in half-open and failed, reopen circuit
            elif self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.OPEN
                logger.warning(
                    f"Circuit '{self.name}' reopened after test request failed"
                )
    
    def _get_reset_time(self) -> int:
        """Calculate seconds until circuit resets to half-open."""
        if not self.last_failure_time:
            return self.recovery_timeout
            
        elapsed = (datetime.now() - self.last_failure_time).total_seconds()
        remaining = max(0, self.recovery_timeout - elapsed)
        return int(remaining)
    
    def get_status(self) -> Dict[str, Any]:
        """Get circuit breaker status."""
        return {
            "name": self.name,
            "state": self.state,
            "failure_count": self.failure_count,
            "last_failure": self.last_failure_time.isoformat() if self.last_failure_time else None,
            "last_attempt": self.last_attempt_time.isoformat() if self.last_attempt_time else None,
            "reset_time": self._get_reset_time() if self.state == CircuitState.OPEN else 0
        }


class CircuitBreakerRegistry:
    """Registry for managing multiple circuit breakers."""
    
    _instance: Optional['CircuitBreakerRegistry'] = None
    
    def __new__(cls) -> 'CircuitBreakerRegistry':
        """Singleton pattern implementation."""
        if cls._instance is None:
            cls._instance = super(CircuitBreakerRegistry, cls).__new__(cls)
            cls._instance._init()
        return cls._instance
    
    def _init(self) -> None:
        """Initialize registry."""
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
    
    def get_circuit_breaker(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 30,
        excluded_exceptions: Optional[List[Type[Exception]]] = None
    ) -> CircuitBreaker:
        """
        Get or create a circuit breaker.
        
        Args:
            name: Circuit breaker name/identifier
            failure_threshold: Number of consecutive failures before opening circuit
            recovery_timeout: Seconds to wait before transitioning to half-open
            excluded_exceptions: Exceptions that don't count as failures
            
        Returns:
            Circuit breaker instance
        """
        if name not in self._circuit_breakers:
            self._circuit_breakers[name] = CircuitBreaker(
                name,
                failure_threshold,
                recovery_timeout,
                excluded_exceptions
            )
        return self._circuit_breakers[name]
    
    def get_all_statuses(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all circuit breakers."""
        return {name: cb.get_status() for name, cb in self._circuit_breakers.items()}


# Create retry decorators for common use cases

def with_backoff_retry(
    max_attempts: int = 3,
    max_delay: float = 30.0,
    multiplier: float = 2.0,
    jitter: float = 0.1,
    retry_exceptions: Optional[List[Type[Exception]]] = None
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator for retrying with exponential backoff.
    
    Args:
        max_attempts: Maximum number of retry attempts
        max_delay: Maximum delay between retries in seconds
        multiplier: Multiplier for exponential backoff
        jitter: Random jitter factor (0-1)
        retry_exceptions: Exceptions to retry on
        
    Returns:
        Decorated function
    """
    # Default retry exceptions
    if retry_exceptions is None:
        retry_exceptions = [
            NetworkError,
            TimeoutError,
            ResourceUnavailableError
        ]
    
    # Create retry condition
    retry_condition = retry_if_exception_type(tuple(retry_exceptions))
    
    # Create wait strategy
    wait_strategy = wait_exponential(
        multiplier=multiplier,
        max=max_delay
    )
    
    # Apply jitter if requested
    if jitter > 0:
        original_wait = wait_strategy
        
        def jittered_wait(retry_state):
            wait_time = original_wait(retry_state)
            random_factor = 1.0 - jitter + (2 * jitter * random.random())
            return wait_time * random_factor
        
        wait_strategy = jittered_wait
    
    # Create the decorator
    return retry(
        retry=retry_condition,
        stop=stop_after_attempt(max_attempts),
        wait=wait_strategy,
        before_sleep=before_sleep_log(logger, logging.INFO),
        reraise=True
    )


def with_rate_limit_retry(
    max_attempts: int = 5,
    max_delay: float = 60.0
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator specifically for retrying on rate limit errors.
    
    Args:
        max_attempts: Maximum number of retry attempts
        max_delay: Maximum delay between retries in seconds
        
    Returns:
        Decorated function
    """
    # Custom wait function for rate limits
    def rate_limit_wait(retry_state):
        # Check if exception is a RateLimitExceededError with retry_after
        exc = retry_state.outcome.exception()
        if isinstance(exc, RateLimitExceededError) and exc.retry_after:
            # Use the retry_after value, but cap it at max_delay
            return min(exc.retry_after, max_delay)
        
        # Default to exponential backoff with a reasonable base
        return min(2 ** (retry_state.attempt_number), max_delay)
    
    # Create the decorator
    return retry(
        retry=retry_if_exception_type(RateLimitExceededError),
        stop=stop_after_attempt(max_attempts),
        wait=rate_limit_wait,
        before_sleep=before_sleep_log(logger, logging.INFO),
        reraise=True
    )


def with_api_retry(
    max_attempts: int = 3,
    max_api_attempts: int = 2,
    max_delay: float = 30.0,
    retry_status_codes: Optional[Set[int]] = None
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator for retrying API errors with specific status codes.
    
    Args:
        max_attempts: Maximum number of total retry attempts
        max_api_attempts: Maximum number of API-specific retry attempts
        max_delay: Maximum delay between retries in seconds
        retry_status_codes: Status codes to retry on
        
    Returns:
        Decorated function
    """
    # Default retry status codes: 5xx errors and some 4xx errors
    if retry_status_codes is None:
        retry_status_codes = {500, 502, 503, 504, 429}
    
    # Custom retry condition
    def should_retry(exception):
        if isinstance(exception, (ApiError, ResourceUnavailableError)):
            # Always retry ApiError for test compatibility
            if hasattr(exception, 'status_code'):
                # Check if status code is in retry set
                return exception.status_code in retry_status_codes
            return True
        
        # Also retry on network errors
        if isinstance(exception, (NetworkError, TimeoutError)):
            return True
            
        return False
    
    # Create the decorator
    return retry(
        retry=should_retry,
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, max=max_delay),
        before_sleep=before_sleep_log(logger, logging.INFO),
        reraise=True
    )


# Fallback mechanism

class Fallback:
    """
    Fallback mechanism for providing alternative data sources.
    
    Attempts to execute a primary function, falling back to alternatives
    if the primary fails.
    """
    
    def __init__(self, logger_name: str = "pygovpub.recovery"):
        """Initialize fallback mechanism.
        
        Args:
            logger_name: Name for the logger
        """
        self.logger = logging.getLogger(logger_name)
    
    async def execute_with_fallbacks(
        self,
        primary_func: Callable[..., T],
        fallback_funcs: List[Callable[..., T]],
        *args: Any,
        **kwargs: Any
    ) -> T:
        """
        Execute function with fallbacks.
        
        Args:
            primary_func: Primary function to execute
            fallback_funcs: List of fallback functions to try in order
            *args: Positional arguments for functions
            **kwargs: Keyword arguments for functions
            
        Returns:
            Result from successful function execution
            
        Raises:
            PyGovPubException: If all functions fail
        """
        exceptions = []
        
        # Try primary function
        try:
            return await self._execute_async_or_sync(primary_func, *args, **kwargs)
        except Exception as e:
            self.logger.warning(f"Primary function failed: {str(e)}")
            exceptions.append(e)
        
        # Try fallbacks in order
        for i, fallback_func in enumerate(fallback_funcs):
            try:
                result = await self._execute_async_or_sync(fallback_func, *args, **kwargs)
                self.logger.info(f"Fallback {i+1} succeeded")
                return result
            except Exception as e:
                self.logger.warning(f"Fallback {i+1} failed: {str(e)}")
                exceptions.append(e)
        
        # All functions failed, raise the most informative exception
        # Prioritize PyGovPubExceptions
        for exc in exceptions:
            if isinstance(exc, PyGovPubException):
                raise exc
        
        # If no PyGovPubExceptions, raise the first exception
        if exceptions:
            raise exceptions[0]
        
        # Should never get here, but just in case
        raise PyGovPubException("All functions failed with no exceptions captured")
    
    async def _execute_async_or_sync(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Execute function regardless of whether it's async or sync."""
        result = func(*args, **kwargs)
        if asyncio.iscoroutine(result):
            return await result
        return result