"""
Transformation utilities for API responses.

This module provides functions for transforming different API response formats 
into the unified PyGovPub response format.
"""

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, TypeVar, Union, cast
import logging

from pygovpub.auth.models import ApiSource
from pygovpub.models.response import ApiError, ApiResponse, ResponseMetadata, PaginationInfo
from pygovpub.core.schema_monitor import validate_response as validate_schema

logger = logging.getLogger(__name__)

# Generic type variable for response data
T = TypeVar('T')


def transform_congress_response(
    congress_response: Dict[str, Any],
    resource_type: str,
    offset: int = 0,
    endpoint: str = "",
    version_string: Optional[str] = None
) -> ApiResponse[List[Dict[str, Any]]]:
    """
    Transform a Congress.gov API response to the unified PyGovPub format.
    
    Args:
        congress_response: The Congress.gov API response dictionary
        resource_type: The type of resource in the response (bills, members, etc.)
        offset: The offset used in the request (defaults to 0)
        endpoint: The API endpoint that generated this response
        version_string: API version string if known
        
    Returns:
        Unified API response object
    """
    # Validate schema if endpoint is provided
    if endpoint:
        is_valid, changes = validate_schema(
            api_source=ApiSource.CONGRESS,
            endpoint=endpoint,
            response_data=congress_response,
            version_string=version_string
        )
        
        # Log any schema changes
        if changes:
            breaking_changes = [c for c in changes if c.is_breaking]
            if breaking_changes:
                logger.warning(f"Breaking schema changes detected in Congress API response for {endpoint}")
            else:
                logger.info(f"Schema changes detected in Congress API response for {endpoint}")
                
        # If schema validation failed, log a warning
        if not is_valid:
            logger.warning(f"Congress API response failed schema validation for {endpoint}")
    
    # Extract pagination data
    pagination_data = congress_response.get("pagination", {})
    count = pagination_data.get("count", 0)
    next_page = pagination_data.get("nextPage")
    
    # Extract results
    results = congress_response.get("results", [])
    
    # Check for full empty response (API might send an empty object)
    if not results and not pagination_data:
        # Create empty response
        return ApiResponse.from_data(
            data=[],
            source=ApiSource.CONGRESS,
            total_count=0,
            count=0,
            offset=offset
        )
    
    # Extract update date from the first result if available
    source_updated_at = None
    if results and len(results) > 0:
        # Try to find the latest update date in any of the results
        update_dates = []
        
        # Look for various date fields that might indicate last update
        for result in results:
            # Check for updateDateIncludingText first (most comprehensive)
            if "updateDateIncludingText" in result:
                try:
                    update_dates.append(datetime.strptime(
                        result["updateDateIncludingText"], "%Y-%m-%d"
                    ))
                except (ValueError, TypeError):
                    pass
                    
            # Fall back to updateDate if no text-inclusive date
            elif "updateDate" in result:
                try:
                    update_dates.append(datetime.strptime(
                        result["updateDate"], "%Y-%m-%d"
                    ))
                except (ValueError, TypeError):
                    pass
        
        # Use the most recent date if any were found
        if update_dates:
            source_updated_at = max(update_dates)
    
    # Create unified response
    return ApiResponse.from_data(
        data=results,
        source=ApiSource.CONGRESS,
        total_count=count,  # Congress API doesn't provide total_count, so use count
        count=count,
        offset=offset,
        next_page_url=next_page,
        source_updated_at=source_updated_at,
        api_version=version_string,
        endpoint=endpoint
    )


def transform_govinfo_response(
    govinfo_response: Dict[str, Any],
    resource_type: str,
    endpoint: str = "",
    version_string: Optional[str] = None
) -> ApiResponse[List[Dict[str, Any]]]:
    """
    Transform a GovInfo.gov API response to the unified PyGovPub format.
    
    Args:
        govinfo_response: The GovInfo.gov API response dictionary
        resource_type: The type of resource in the response (packages, granules, etc.)
        endpoint: The API endpoint that generated this response
        version_string: API version string if known
        
    Returns:
        Unified API response object
    """
    # Validate schema if endpoint is provided
    if endpoint:
        is_valid, changes = validate_schema(
            api_source=ApiSource.GOVINFO,
            endpoint=endpoint,
            response_data=govinfo_response,
            version_string=version_string
        )
        
        # Log any schema changes
        if changes:
            breaking_changes = [c for c in changes if c.is_breaking]
            if breaking_changes:
                logger.warning(f"Breaking schema changes detected in GovInfo API response for {endpoint}")
            else:
                logger.info(f"Schema changes detected in GovInfo API response for {endpoint}")
                
        # If schema validation failed, log a warning
        if not is_valid:
            logger.warning(f"GovInfo API response failed schema validation for {endpoint}")
    
    # Extract pagination data
    count = govinfo_response.get("count", 0)
    offset = govinfo_response.get("offset", 0)
    page_size = govinfo_response.get("pageSize", 0)
    next_page = govinfo_response.get("nextPage")
    previous_page = govinfo_response.get("previousPage")
    
    # Extract data based on resource type
    if resource_type == "packages":
        data = govinfo_response.get("packages", [])
    elif resource_type == "granules":
        data = govinfo_response.get("granules", [])
    elif resource_type == "collections":
        data = govinfo_response.get("collections", [])
    else:
        # For single item responses (not collections)
        # Remove pagination fields for single items
        single_item = {k: v for k, v in govinfo_response.items() 
                        if k not in ["count", "offset", "pageSize", "nextPage", "previousPage"]}
        data = [single_item] if single_item else []
        
    # Look for the latest lastModified date in the data
    source_updated_at = None
    last_modified_dates = []
    
    for item in data:
        if "lastModified" in item:
            try:
                last_modified_dates.append(datetime.strptime(
                    item["lastModified"], "%Y-%m-%dT%H:%M:%SZ"
                ))
            except (ValueError, TypeError):
                pass
    
    if last_modified_dates:
        source_updated_at = max(last_modified_dates)
    
    # Create unified response
    return ApiResponse.from_data(
        data=data,
        source=ApiSource.GOVINFO,
        total_count=count,
        count=len(data),
        offset=offset,
        limit=page_size if page_size > 0 else None,
        next_page_url=next_page,
        previous_page_url=previous_page,
        source_updated_at=source_updated_at,
        api_version=version_string,
        endpoint=endpoint
    )


def create_error_response(
    message: Optional[str] = None,
    exception: Optional[Exception] = None,
    status_code: int = 500,
    source: ApiSource = ApiSource.INTERNAL,
    error_code: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None,
    processing_time_ms: Optional[int] = None
) -> ApiResponse[None]:
    """
    Create an error response in the unified format.
    
    Args:
        message: Human-readable error message
        exception: Exception that caused the error (alternative to message)
        status_code: HTTP status code for the error
        source: API source that generated the error
        error_code: Application-specific error code
        details: Additional error details
        request_id: Unique identifier for the request
        processing_time_ms: Time taken to process the request
        
    Returns:
        Error response object
    """
    # Use exception message if no message was provided
    if message is None and exception is not None:
        message = str(exception)
    elif message is None:
        message = "An unknown error occurred"
        
    # Create and return error response
    return ApiResponse.from_error(
        error=message,
        source=source,
        status_code=status_code,
        error_code=error_code,
        details=details,
        request_id=request_id,
        processing_time_ms=processing_time_ms
    )