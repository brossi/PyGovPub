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
    ApiError,
    ApiErrorSource,
    AuthenticationError,
    ConfigurationError, 
    ConnectionError,
    CongressApiError,
    DataParsingError,
    DataValidationError,
    ErrorCode,
    ErrorContext,
    ErrorSeverity,
    GovInfoApiError,
    InvalidApiKeyError,
    InvalidRequestError,
    MissingApiKeyError,
    MockServerError,
    NetworkError,
    RateLimitExceededError,
    ResourceNotFoundError,
    ResourceUnavailableError,
    TimeoutError
)

__all__ = [
    "__version__",
    "Config",
    "config",
    "PyGovPubException",
    "ApiError",
    "ApiErrorSource",
    "AuthenticationError",
    "ConfigurationError", 
    "ConnectionError",
    "CongressApiError",
    "DataParsingError",
    "DataValidationError",
    "ErrorCode",
    "ErrorContext",
    "ErrorSeverity",
    "GovInfoApiError",
    "InvalidApiKeyError",
    "InvalidRequestError",
    "MissingApiKeyError",
    "MockServerError",
    "NetworkError",
    "RateLimitExceededError",
    "ResourceNotFoundError",
    "ResourceUnavailableError",
    "TimeoutError"
]