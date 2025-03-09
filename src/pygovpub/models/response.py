"""
Core response models for PyGovPub SDK.

This module defines the standard response format for all API responses
in the PyGovPub SDK, ensuring consistent data structures across APIs.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Generic, List, Optional, TypeVar, Union
from pydantic import BaseModel, Field, field_validator, model_validator

from pygovpub.auth.models import ApiSource


class ResponseMetadata(BaseModel):
    """Metadata about the API response."""
    
    source: ApiSource
    """Source API that provided the data."""
    
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    """When the response was generated."""
    
    request_id: Optional[str] = None
    """Unique identifier for the request (if available)."""
    
    processing_time_ms: Optional[int] = None
    """Time taken to process the request in milliseconds."""
    
    count: Optional[int] = None
    """Number of items in the response (if applicable)."""
    
    source_updated_at: Optional[datetime] = None
    """When the data was last updated at the source API."""
    
    api_version: Optional[str] = None
    """API version string reported by the source API."""
    
    schema_version: Optional[str] = None
    """Schema version hash for the response data."""
    
    @field_validator('processing_time_ms', 'count')
    @classmethod
    def validate_non_negative(cls, value: Optional[int]) -> Optional[int]:
        """Validate that numeric fields are non-negative."""
        if value is not None and value < 0:
            raise ValueError("Value must be non-negative")
        return value


class PaginationInfo(BaseModel):
    """Pagination information for API responses."""
    
    total_count: int
    """Total number of items available."""
    
    count: int
    """Number of items in the current response."""
    
    offset: int
    """Offset from the beginning of the result set."""
    
    limit: Optional[int] = None
    """Maximum number of items per page."""
    
    next_page_url: Optional[str] = None
    """URL for the next page of results (if available)."""
    
    previous_page_url: Optional[str] = None
    """URL for the previous page of results (if available)."""
    
    @field_validator('total_count', 'count', 'offset')
    @classmethod
    def validate_non_negative(cls, value: int) -> int:
        """Validate that numeric fields are non-negative."""
        if value < 0:
            raise ValueError("Value must be non-negative")
        return value
    
    @property
    def has_next_page(self) -> bool:
        """Whether there is a next page of results."""
        if self.next_page_url is not None:
            return True
        return self.offset + self.count < self.total_count
    
    @property
    def has_previous_page(self) -> bool:
        """Whether there is a previous page of results."""
        if self.previous_page_url is not None:
            return True
        return self.offset > 0


class ApiError(BaseModel):
    """Error information for API responses."""
    
    message: str
    """Human-readable error message."""
    
    status_code: int
    """HTTP status code associated with the error."""
    
    error_code: Optional[str] = None
    """Application-specific error code."""
    
    details: Optional[Dict[str, Any]] = None
    """Additional error details, if available."""


# Define a generic type variable for the data field
T = TypeVar('T')

class ApiResponse(BaseModel, Generic[T]):
    """Generic API response model with consistent structure."""
    
    metadata: ResponseMetadata
    """Metadata about the response."""
    
    pagination: Optional[PaginationInfo] = None
    """Pagination information, if applicable."""
    
    data: Optional[T] = None
    """Response data, if successful."""
    
    error: Optional[ApiError] = None
    """Error information, if unsuccessful."""
    
    @property
    def is_success(self) -> bool:
        """Whether the response was successful."""
        return self.error is None
    
    @model_validator(mode='after')
    def check_success_or_error(self) -> 'ApiResponse':
        """Validate that a response has either data or an error, not both."""
        if self.data is not None and self.error is not None:
            raise ValueError("A response cannot have both data and an error")
        return self
    
    @classmethod
    def from_data(
        cls,
        data: T,
        source: ApiSource,
        total_count: int,
        count: Optional[int] = None,
        offset: int = 0,
        limit: Optional[int] = None,
        next_page_url: Optional[str] = None,
        previous_page_url: Optional[str] = None,
        request_id: Optional[str] = None,
        processing_time_ms: Optional[int] = None,
        source_updated_at: Optional[datetime] = None,
        api_version: Optional[str] = None,
        schema_version: Optional[str] = None,
        endpoint: Optional[str] = None
    ) -> 'ApiResponse[T]':
        """Create a successful response with data.
        
        Args:
            data: The response data
            source: Source API that provided the data
            total_count: Total number of items available
            count: Number of items in the current response (defaults to len(data) for sequences)
            offset: Offset from the beginning of the result set
            limit: Maximum number of items per page
            next_page_url: URL for the next page of results
            previous_page_url: URL for the previous page of results
            request_id: Unique identifier for the request
            processing_time_ms: Time taken to process the request in milliseconds
            source_updated_at: When the data was last updated at the source API
            api_version: API version string reported by the source
            schema_version: Schema version hash for validation
            endpoint: API endpoint that generated this response
            
        Returns:
            An ApiResponse instance with the provided data
        """
        # Try to determine count from data if not provided
        if count is None:
            try:
                count = len(data)  # type: ignore
            except (TypeError, AttributeError):
                count = 1 if data is not None else 0
                
        # Get schema version from monitoring if not provided
        if schema_version is None and endpoint:
            from pygovpub.core.schema_monitor import default_monitor
            key = f"{source.value}:{endpoint}"
            if hasattr(default_monitor, "versions") and key in default_monitor.versions:
                schema_version = default_monitor.versions[key].schema_hash
        
        # Create metadata
        metadata = ResponseMetadata(
            source=source,
            timestamp=datetime.now(timezone.utc),
            request_id=request_id,
            processing_time_ms=processing_time_ms,
            count=count,
            source_updated_at=source_updated_at,
            api_version=api_version,
            schema_version=schema_version
        )
        
        # Create pagination
        pagination = PaginationInfo(
            total_count=total_count,
            count=count,
            offset=offset,
            limit=limit,
            next_page_url=next_page_url,
            previous_page_url=previous_page_url
        )
        
        # Create and return response
        return cls(
            metadata=metadata,
            pagination=pagination,
            data=data
        )
    
    @classmethod
    def from_error(
        cls,
        error: Union[ApiError, str, Exception],
        source: ApiSource,
        status_code: int = 500,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
        processing_time_ms: Optional[int] = None
    ) -> 'ApiResponse[None]':
        """Create an error response.
        
        Args:
            error: The error information (ApiError, message string, or Exception)
            source: Source API that encountered the error
            status_code: HTTP status code associated with the error
            error_code: Application-specific error code
            details: Additional error details
            request_id: Unique identifier for the request
            processing_time_ms: Time taken to process the request in milliseconds
            
        Returns:
            An ApiResponse instance with the error information
        """
        # Create metadata
        metadata = ResponseMetadata(
            source=source,
            timestamp=datetime.now(timezone.utc),
            request_id=request_id,
            processing_time_ms=processing_time_ms
        )
        
        # Create error object if not already an ApiError
        if isinstance(error, ApiError):
            api_error = error
        elif isinstance(error, str):
            api_error = ApiError(
                message=error,
                status_code=status_code,
                error_code=error_code,
                details=details
            )
        elif isinstance(error, Exception):
            api_error = ApiError(
                message=str(error),
                status_code=status_code,
                error_code=error_code,
                details=details
            )
        else:
            raise TypeError(f"Unsupported error type: {type(error)}")
        
        # Create and return response
        return cls(
            metadata=metadata,
            error=api_error
        )
        
    def model_dump(self, **kwargs) -> Dict[str, Any]:
        """Convert to dictionary, excluding None fields by default."""
        result = super().model_dump(**kwargs)
        # Remove None values to make the response cleaner
        return {k: v for k, v in result.items() if v is not None}