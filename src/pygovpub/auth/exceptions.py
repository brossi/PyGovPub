"""
Custom exceptions for the auth module.

This module defines exceptions specific to authentication and API key management.
"""

from typing import Optional


class ApiKeyNotFoundError(Exception):
    """Raised when an API key is not found for a given source."""

    def __init__(self, message: str = "API key not found", source: Optional[str] = None):
        """Initialize with optional message and source."""
        if source:
            message = f"{message} for source: {source}"
        super().__init__(message)


class ApiKeyValidationError(Exception):
    """Raised when an API key fails validation."""

    def __init__(self, message: str = "API key validation failed"):
        """Initialize with optional message."""
        super().__init__(message)


class VersionCompatibilityError(Exception):
    """Raised when API version is not compatible."""

    def __init__(
        self,
        message: str = "API version not compatible",
        version: Optional[str] = None,
        min_supported: Optional[str] = None,
        max_supported: Optional[str] = None
    ):
        """Initialize with optional message and version details."""
        if version and (min_supported or max_supported):
            details = []
            if min_supported:
                details.append(f"minimum supported: {min_supported}")
            if max_supported:
                details.append(f"maximum supported: {max_supported}")
            message = f"{message} - version: {version} ({', '.join(details)})"
        super().__init__(message)
