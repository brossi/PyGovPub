"""
Congress API Router.

This module provides FastAPI routes for accessing congress information
from Congress.gov and GovInfo.gov.
"""

import logging
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Path
from pydantic import BaseModel, Field

from pygovpub.api.router import ApiRouter
from pygovpub.auth.models import ApiSource
from pygovpub.exceptions import RouterError, ApiError, RouteNotFoundError, SourceUnavailableError

# Define the API router dependency (will be registered from app.py later)
def get_api_router():
    """Get API router.
    
    This is a dependency function that will be overridden by app.py.
    """
    raise NotImplementedError("get_api_router not registered - this is a placeholder")

# Configure logging
logger = logging.getLogger("pygovpub.api.routers.congress")

# Create router
router = APIRouter(
    prefix="/congress",
    tags=["Congress"],
    responses={
        404: {"description": "Not found"},
        429: {"description": "Rate limit exceeded"},
        503: {"description": "Source unavailable"}
    }
)


# Response models
class CongressSession(BaseModel):
    """Congress session data model."""
    
    congress: int = Field(..., description="Congress number")
    session: int = Field(..., description="Session number")
    start_date: str = Field(..., description="Start date of session")
    end_date: Optional[str] = Field(None, description="End date of session")
    is_current: bool = Field(False, description="Whether this is the current session")
    chamber_sessions: Dict[str, Any] = Field({}, description="Chamber-specific session data")


class CongressListResponse(BaseModel):
    """Response model for list of congresses."""
    
    congresses: List[int] = Field(..., description="List of congress numbers")
    current_congress: int = Field(..., description="Current congress number")
    count: int = Field(..., description="Total count of congresses")


class CongressSessionsResponse(BaseModel):
    """Response model for congress sessions."""
    
    congress: int = Field(..., description="Congress number")
    start_date: str = Field(..., description="Start date of congress")
    end_date: Optional[str] = Field(None, description="End date of congress")
    sessions: List[CongressSession] = Field(..., description="Sessions of this congress")


@router.get("/", response_model=CongressListResponse)
async def list_congresses(
    limit: int = Query(20, description="Maximum number of congresses to return"),
    offset: int = Query(0, description="Offset for pagination"),
    api_router: ApiRouter = Depends(get_api_router)
) -> CongressListResponse:
    """List congresses.
    
    Returns a list of congress numbers, with pagination.
    
    Args:
        limit: Maximum number of congresses to return
        offset: Offset for pagination
    
    Returns:
        List of congress numbers
    """
    try:
        # Get client
        client = api_router.get_client(ApiSource.CONGRESS)
        
        # Get congresses from Congress.gov API
        congresses_data = await client.list_congresses(limit=limit, offset=offset)
        
        # Return response
        return CongressListResponse(
            congresses=congresses_data.get("congresses", []),
            current_congress=congresses_data.get("current_congress", 0),
            count=congresses_data.get("count", 0)
        )
    except (RouterError, ApiError) as e:
        # Log error and return HTTP exception
        logger.error(f"Error listing congresses: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error listing congresses: {str(e)}"
        )
    except SourceUnavailableError as e:
        # Source unavailable
        logger.error(f"Source unavailable: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Source unavailable: {str(e)}"
        )


@router.get("/{congress}", response_model=CongressSessionsResponse)
async def get_congress_sessions(
    congress: int = Path(..., description="Congress number", ge=1, le=150),
    api_router: ApiRouter = Depends(get_api_router)
) -> CongressSessionsResponse:
    """Get congress sessions.
    
    Returns detailed information about a specific congress including its sessions.
    
    Args:
        congress: Congress number
    
    Returns:
        Congress session information
    
    Raises:
        HTTPException: If congress not found
    """
    try:
        # Get client
        client = api_router.get_client(ApiSource.CONGRESS)
        
        # Get congress sessions from Congress.gov API
        congress_data = await client.get_congress(congress=congress)
        
        # Return response
        return CongressSessionsResponse(
            congress=congress_data.get("congress", congress),
            start_date=congress_data.get("start_date", ""),
            end_date=congress_data.get("end_date"),
            sessions=[
                CongressSession(
                    congress=congress,
                    session=session.get("session", 0),
                    start_date=session.get("start_date", ""),
                    end_date=session.get("end_date"),
                    is_current=session.get("is_current", False),
                    chamber_sessions=session.get("chamber_sessions", {})
                )
                for session in congress_data.get("sessions", [])
            ]
        )
    except (RouterError, ApiError) as e:
        # Log error and return HTTP exception
        logger.error(f"Error retrieving congress {congress}: {e}")
        raise HTTPException(
            status_code=404,
            detail=f"Congress not found: {congress}"
        )
    except SourceUnavailableError as e:
        # Source unavailable
        logger.error(f"Source unavailable: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Source unavailable: {str(e)}"
        )


@router.get("/{congress}/calendar", response_model=Dict[str, Any])
async def get_congress_calendar(
    congress: int = Path(..., description="Congress number", ge=1, le=150),
    year: Optional[int] = Query(None, description="Calendar year (optional)"),
    chamber: Optional[str] = Query(None, description="Chamber (house or senate)"),
    api_router: ApiRouter = Depends(get_api_router)
) -> Dict[str, Any]:
    """Get congress calendar.
    
    Returns calendar information for a specific congress.
    
    Args:
        congress: Congress number
        year: Calendar year (optional)
        chamber: Chamber (house or senate, optional)
    
    Returns:
        Congress calendar information
    """
    try:
        # Get client
        client = api_router.get_client(ApiSource.CONGRESS)
        
        # Get congress calendar from Congress.gov API
        calendar_data = await client.get_congress_calendar(
            congress=congress,
            year=year,
            chamber=chamber
        )
        
        # Return calendar data directly
        return calendar_data
    except (RouterError, ApiError) as e:
        # Log error and return HTTP exception
        logger.error(f"Error retrieving congress calendar {congress}: {e}")
        raise HTTPException(
            status_code=404,
            detail=f"Congress calendar not found: {congress}"
        )
    except SourceUnavailableError as e:
        # Source unavailable
        logger.error(f"Source unavailable: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Source unavailable: {str(e)}"
        )