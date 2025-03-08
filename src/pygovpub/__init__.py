"""
PyGovPub: Python SDK for unified access to U.S. Federal Government data.

This SDK provides a unified interface to Congress.gov and GovInfo.gov APIs,
enabling seamless access to legislative and regulatory data with authentication
management, rate limiting, and data normalization.
"""

__version__ = "0.1.0"

from .config import Config, config
from .exceptions import (
    PyGovPubException,
    ConfigurationError, 
    AuthenticationError,
    RateLimitExceededError,
    ResourceNotFound,
    InvalidRequest,
    ApiError,
    MockServerError
)

__all__ = [
    "__version__",
    "Config",
    "config",
    "PyGovPubException",
    "ConfigurationError", 
    "AuthenticationError",
    "RateLimitExceededError",
    "ResourceNotFound",
    "InvalidRequest",
    "ApiError",
    "MockServerError"
]