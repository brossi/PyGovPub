"""
Tests for unified data response models.

This module tests the core response models used to create a consistent
format across all API responses in PyGovPub.
"""

import pytest
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pygovpub.auth.models import ApiSource
from pygovpub.models.response import (
    ResponseMetadata, 
    PaginationInfo, 
    ApiResponse,
    ApiError
)


class TestResponseMetadata:
    """Tests for ResponseMetadata class."""
    
    def test_init_with_required_fields(self):
        """Test initialization with only required fields."""
        timestamp = datetime.now(timezone.utc)
        metadata = ResponseMetadata(
            source=ApiSource.CONGRESS,
            timestamp=timestamp
        )
        
        assert metadata.source == ApiSource.CONGRESS
        assert metadata.timestamp == timestamp
        assert metadata.request_id is None
        assert metadata.processing_time_ms is None
        assert metadata.count is None
        assert metadata.source_updated_at is None
        
    def test_init_with_all_fields(self):
        """Test initialization with all fields."""
        timestamp = datetime.now(timezone.utc)
        source_updated = datetime.now(timezone.utc)
        metadata = ResponseMetadata(
            source=ApiSource.GOVINFO,
            timestamp=timestamp,
            request_id="req-123",
            processing_time_ms=150,
            count=42,
            source_updated_at=source_updated
        )
        
        assert metadata.source == ApiSource.GOVINFO
        assert metadata.timestamp == timestamp
        assert metadata.request_id == "req-123"
        assert metadata.processing_time_ms == 150
        assert metadata.count == 42
        assert metadata.source_updated_at == source_updated
    
    def test_model_validation(self):
        """Test model validation for invalid values."""
        timestamp = datetime.now(timezone.utc)
        
        # Test with invalid processing_time_ms
        with pytest.raises(ValueError):
            ResponseMetadata(
                source=ApiSource.CONGRESS,
                timestamp=timestamp,
                processing_time_ms=-10  # Negative value should be invalid
            )
        
        # Test with invalid count
        with pytest.raises(ValueError):
            ResponseMetadata(
                source=ApiSource.CONGRESS,
                timestamp=timestamp,
                count=-5  # Negative value should be invalid
            )
    
    def test_to_dict(self):
        """Test conversion to dictionary."""
        timestamp = datetime.now(timezone.utc)
        metadata = ResponseMetadata(
            source=ApiSource.CONGRESS,
            timestamp=timestamp,
            request_id="req-456",
            processing_time_ms=200
        )
        
        result = metadata.model_dump()
        assert result["source"] == ApiSource.CONGRESS
        assert result["timestamp"] == timestamp
        assert result["request_id"] == "req-456"
        assert result["processing_time_ms"] == 200


class TestPaginationInfo:
    """Tests for PaginationInfo class."""
    
    def test_init_with_required_fields(self):
        """Test initialization with only required fields."""
        pagination = PaginationInfo(
            total_count=100,
            count=20,
            offset=0
        )
        
        assert pagination.total_count == 100
        assert pagination.count == 20
        assert pagination.offset == 0
        assert pagination.limit == None
        assert pagination.next_page_url is None
        assert pagination.previous_page_url is None
    
    def test_init_with_all_fields(self):
        """Test initialization with all fields."""
        pagination = PaginationInfo(
            total_count=500,
            count=50,
            offset=100,
            limit=50,
            next_page_url="https://api.example.com/resources?offset=150&limit=50",
            previous_page_url="https://api.example.com/resources?offset=50&limit=50"
        )
        
        assert pagination.total_count == 500
        assert pagination.count == 50
        assert pagination.offset == 100
        assert pagination.limit == 50
        assert pagination.next_page_url == "https://api.example.com/resources?offset=150&limit=50"
        assert pagination.previous_page_url == "https://api.example.com/resources?offset=50&limit=50"
    
    def test_model_validation(self):
        """Test model validation for invalid values."""
        # Test with invalid total_count
        with pytest.raises(ValueError):
            PaginationInfo(
                total_count=-100,  # Negative value should be invalid
                count=20,
                offset=0
            )
        
        # Test with invalid count
        with pytest.raises(ValueError):
            PaginationInfo(
                total_count=100,
                count=-20,  # Negative value should be invalid
                offset=0
            )
        
        # Test with invalid offset
        with pytest.raises(ValueError):
            PaginationInfo(
                total_count=100,
                count=20,
                offset=-10  # Negative value should be invalid
            )
    
    def test_has_next_page(self):
        """Test has_next_page property."""
        # When has next page URL
        pagination = PaginationInfo(
            total_count=100,
            count=20,
            offset=0,
            next_page_url="https://api.example.com/resources?offset=20"
        )
        assert pagination.has_next_page is True
        
        # When offset + count < total_count
        pagination = PaginationInfo(
            total_count=100,
            count=20,
            offset=0
        )
        assert pagination.has_next_page is True
        
        # When at the last page
        pagination = PaginationInfo(
            total_count=100,
            count=20,
            offset=80
        )
        assert pagination.has_next_page is False
        
        # When beyond the last page
        pagination = PaginationInfo(
            total_count=100,
            count=0,
            offset=100
        )
        assert pagination.has_next_page is False
    
    def test_has_previous_page(self):
        """Test has_previous_page property."""
        # When has previous page URL
        pagination = PaginationInfo(
            total_count=100,
            count=20,
            offset=20,
            previous_page_url="https://api.example.com/resources?offset=0"
        )
        assert pagination.has_previous_page is True
        
        # When offset > 0
        pagination = PaginationInfo(
            total_count=100,
            count=20,
            offset=20
        )
        assert pagination.has_previous_page is True
        
        # When at the first page
        pagination = PaginationInfo(
            total_count=100,
            count=20,
            offset=0
        )
        assert pagination.has_previous_page is False


class TestApiError:
    """Tests for ApiError class."""
    
    def test_init_with_required_fields(self):
        """Test initialization with only required fields."""
        error = ApiError(
            message="Resource not found",
            status_code=404
        )
        
        assert error.message == "Resource not found"
        assert error.status_code == 404
        assert error.error_code is None
        assert error.details is None
    
    def test_init_with_all_fields(self):
        """Test initialization with all fields."""
        details = {"resource_id": "123", "resource_type": "bill"}
        error = ApiError(
            message="Rate limit exceeded",
            status_code=429,
            error_code="RATE_LIMIT_EXCEEDED",
            details=details
        )
        
        assert error.message == "Rate limit exceeded"
        assert error.status_code == 429
        assert error.error_code == "RATE_LIMIT_EXCEEDED"
        assert error.details == details
    
    def test_model_dump(self):
        """Test conversion to dictionary."""
        details = {"resource_id": "123", "resource_type": "bill"}
        error = ApiError(
            message="Invalid request",
            status_code=400,
            error_code="INVALID_PARAMETERS",
            details=details
        )
        
        result = error.model_dump()
        assert result["message"] == "Invalid request"
        assert result["status_code"] == 400
        assert result["error_code"] == "INVALID_PARAMETERS"
        assert result["details"] == details


class TestApiResponse:
    """Tests for ApiResponse class."""
    
    def test_init_success_response(self):
        """Test initialization of a successful response."""
        timestamp = datetime.now(timezone.utc)
        metadata = ResponseMetadata(
            source=ApiSource.CONGRESS,
            timestamp=timestamp,
            request_id="req-789",
            processing_time_ms=300
        )
        
        pagination = PaginationInfo(
            total_count=200,
            count=20,
            offset=0,
            limit=20
        )
        
        data = [{"id": 1, "name": "Item 1"}, {"id": 2, "name": "Item 2"}]
        
        response = ApiResponse[List[Dict[str, Any]]](
            metadata=metadata,
            pagination=pagination,
            data=data
        )
        
        assert response.metadata == metadata
        assert response.pagination == pagination
        assert response.data == data
        assert response.error is None
        assert response.is_success is True
    
    def test_init_error_response(self):
        """Test initialization of an error response."""
        timestamp = datetime.now(timezone.utc)
        metadata = ResponseMetadata(
            source=ApiSource.GOVINFO,
            timestamp=timestamp
        )
        
        error = ApiError(
            message="Resource not found",
            status_code=404,
            error_code="RESOURCE_NOT_FOUND"
        )
        
        response = ApiResponse[None](
            metadata=metadata,
            error=error
        )
        
        assert response.metadata == metadata
        assert response.pagination is None
        assert response.data is None
        assert response.error == error
        assert response.is_success is False
    
    def test_from_data(self):
        """Test creation from data using the classmethod."""
        data = [{"id": 1, "name": "Item 1"}, {"id": 2, "name": "Item 2"}]
        
        response = ApiResponse.from_data(
            data=data,
            source=ApiSource.CONGRESS,
            total_count=100,
            count=2,
            offset=0
        )
        
        assert response.data == data
        assert response.metadata.source == ApiSource.CONGRESS
        assert response.pagination.total_count == 100
        assert response.pagination.count == 2
        assert response.pagination.offset == 0
        assert response.error is None
        assert response.is_success is True
    
    def test_from_error(self):
        """Test creation from error using the classmethod."""
        error = ApiError(
            message="Rate limit exceeded",
            status_code=429,
            error_code="RATE_LIMIT_EXCEEDED"
        )
        
        response = ApiResponse.from_error(
            error=error,
            source=ApiSource.GOVINFO
        )
        
        assert response.data is None
        assert response.metadata.source == ApiSource.GOVINFO
        assert response.pagination is None
        assert response.error == error
        assert response.is_success is False
    
    def test_model_dump(self):
        """Test conversion to dictionary."""
        timestamp = datetime.now(timezone.utc)
        metadata = ResponseMetadata(
            source=ApiSource.CONGRESS,
            timestamp=timestamp,
            request_id="req-abc",
            processing_time_ms=150
        )
        
        pagination = PaginationInfo(
            total_count=50,
            count=10,
            offset=0,
            limit=10
        )
        
        data = [{"id": 1, "name": "Item 1"}, {"id": 2, "name": "Item 2"}]
        
        response = ApiResponse[List[Dict[str, Any]]](
            metadata=metadata,
            pagination=pagination,
            data=data
        )
        
        result = response.model_dump()
        assert result["metadata"] == metadata.model_dump()
        assert result["pagination"] == pagination.model_dump()
        assert result["data"] == data
        assert "error" not in result
        
        # Try with error response
        error = ApiError(
            message="Invalid request",
            status_code=400
        )
        
        error_response = ApiResponse[None](
            metadata=metadata,
            error=error
        )
        
        error_result = error_response.model_dump()
        assert error_result["metadata"] == metadata.model_dump()
        assert "pagination" not in error_result
        assert "data" not in error_result
        assert error_result["error"] == error.model_dump()