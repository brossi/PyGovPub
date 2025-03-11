"""
Committees API Router.

This module provides FastAPI routes for accessing congressional committee 
information from Congress.gov API.
"""

import logging
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Path
from pydantic import BaseModel, Field

from pygovpub.api.router import ApiRouter
from pygovpub.auth.models import ApiSource
from pygovpub.exceptions import RouterError, ApiError, RouteNotFoundError, SourceUnavailableError

# Configure logging
logger = logging.getLogger("pygovpub.api.routers.committees")

# Create router
router = APIRouter(
    prefix="/committees",
    tags=["Committees"],
    responses={
        404: {"description": "Committee not found"},
        429: {"description": "Rate limit exceeded"},
        503: {"description": "Source unavailable"}
    }
)


# Response models
class CommitteeResponse(BaseModel):
    """Committee response model."""
    
    committee_id: str = Field(..., description="Committee ID")
    name: str = Field(..., description="Committee name")
    chamber: str = Field(..., description="Chamber (House, Senate, or Joint)")
    congress: int = Field(..., description="Congress number")
    parent_committee_id: Optional[str] = Field(None, description="Parent committee ID")
    type: Optional[str] = Field(None, description="Committee type")
    url: Optional[str] = Field(None, description="URL to committee's page")
    
    class Config:
        schema_extra = {
            "example": {
                "committee_id": "HSAG",
                "name": "Committee on Agriculture",
                "chamber": "House",
                "congress": 117,
                "parent_committee_id": None,
                "type": "standing",
                "url": "https://www.congress.gov/committee/house-agriculture/hsag"
            }
        }


class CommitteeMemberResponse(BaseModel):
    """Committee member response model."""
    
    bioguide_id: str = Field(..., description="Bioguide ID")
    first_name: str = Field(..., description="First name")
    last_name: str = Field(..., description="Last name")
    state: Optional[str] = Field(None, description="State")
    party: Optional[str] = Field(None, description="Party affiliation")
    rank: Optional[int] = Field(None, description="Rank in committee")
    title: Optional[str] = Field(None, description="Title in committee")
    
    class Config:
        schema_extra = {
            "example": {
                "bioguide_id": "S000148",
                "first_name": "Chuck",
                "last_name": "Schumer",
                "state": "NY",
                "party": "D",
                "rank": 1,
                "title": "Chairman"
            }
        }


class CommitteeListResponse(BaseModel):
    """Committee list response model."""
    
    count: int = Field(..., description="Total number of results")
    congress: int = Field(..., description="Congress number")
    committees: List[CommitteeResponse] = Field(..., description="List of committees")


# Routes
@router.get(
    "/{committee_id}",
    response_model=CommitteeResponse,
    summary="Get committee information",
    description="Retrieve detailed information about a specific committee"
)
async def get_committee(
    committee_id: str = Path(..., description="Committee ID"),
    congress: int = Query(..., description="Congress number"),
    api_router: ApiRouter = Depends()
):
    """Get committee information by ID."""
    try:
        # Route request
        committee_data = await api_router.route_request(
            request_type="committee",
            method="get_committee",
            committee_id=committee_id,
            congress=congress
        )
        
        # Convert to response model
        return CommitteeResponse(
            committee_id=committee_data.get("committee_id", committee_id),
            name=committee_data.get("name", ""),
            chamber=committee_data.get("chamber", ""),
            congress=committee_data.get("congress", congress),
            parent_committee_id=committee_data.get("parent_committee_id"),
            type=committee_data.get("type"),
            url=committee_data.get("url")
        )
    except RouterError as e:
        logger.error(f"Router error getting committee {committee_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except RouteNotFoundError as e:
        logger.error(f"Route not found for committee {committee_id}: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except SourceUnavailableError as e:
        logger.error(f"Source unavailable for committee {committee_id}: {e}")
        raise HTTPException(status_code=503, detail=str(e))
    except ApiError as e:
        logger.error(f"API error getting committee {committee_id}: {e}")
        if "Not Found" in str(e):
            raise HTTPException(status_code=404, detail=f"Committee {committee_id} not found")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.exception(f"Unexpected error getting committee {committee_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


@router.get(
    "/",
    response_model=CommitteeListResponse,
    summary="List committees",
    description="Retrieve a list of committees for a specific congress with optional filters"
)
async def list_committees(
    congress: int = Query(..., description="Congress number"),
    chamber: Optional[str] = Query(None, description="Chamber (House, Senate, or Joint)"),
    type: Optional[str] = Query(None, description="Committee type"),
    api_router: ApiRouter = Depends()
):
    """List committees."""
    try:
        # Get Congress client
        congress_client = api_router.get_client(ApiSource.CONGRESS)
        
        # Prepare parameters
        params = {
            "congress": congress
        }
        
        if chamber:
            params["chamber"] = chamber
        if type:
            params["type"] = type
        
        # Execute request
        committees_data = await congress_client.list_committees(**params)
        
        # Format results
        committees = []
        for committee in committees_data.get("committees", []):
            committees.append(CommitteeResponse(
                committee_id=committee.get("committee_id", ""),
                name=committee.get("name", ""),
                chamber=committee.get("chamber", ""),
                congress=committee.get("congress", congress),
                parent_committee_id=committee.get("parent_committee_id"),
                type=committee.get("type"),
                url=committee.get("url")
            ))
        
        return CommitteeListResponse(
            count=len(committees),
            congress=congress,
            committees=committees
        )
    except RouterError as e:
        logger.error(f"Router error listing committees: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except RouteNotFoundError as e:
        logger.error(f"Route not found for listing committees: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except SourceUnavailableError as e:
        logger.error(f"Source unavailable for listing committees: {e}")
        raise HTTPException(status_code=503, detail=str(e))
    except ApiError as e:
        logger.error(f"API error listing committees: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.exception(f"Unexpected error listing committees: {e}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


@router.get(
    "/{committee_id}/members",
    response_model=List[CommitteeMemberResponse],
    summary="Get committee members",
    description="Retrieve members of a specific committee"
)
async def get_committee_members(
    committee_id: str = Path(..., description="Committee ID"),
    congress: int = Query(..., description="Congress number"),
    api_router: ApiRouter = Depends()
):
    """Get committee members."""
    try:
        # Route request
        members_data = await api_router.route_request(
            request_type="committee",
            method="get_committee_members",
            committee_id=committee_id,
            congress=congress
        )
        
        # Format results
        members = []
        for member in members_data.get("members", []):
            members.append(CommitteeMemberResponse(
                bioguide_id=member.get("bioguide_id", ""),
                first_name=member.get("first_name", ""),
                last_name=member.get("last_name", ""),
                state=member.get("state"),
                party=member.get("party"),
                rank=member.get("rank"),
                title=member.get("title")
            ))
        
        return members
    except RouterError as e:
        logger.error(f"Router error getting committee members for {committee_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except RouteNotFoundError as e:
        logger.error(f"Route not found for committee members {committee_id}: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except SourceUnavailableError as e:
        logger.error(f"Source unavailable for committee members {committee_id}: {e}")
        raise HTTPException(status_code=503, detail=str(e))
    except ApiError as e:
        logger.error(f"API error getting committee members for {committee_id}: {e}")
        if "Not Found" in str(e):
            raise HTTPException(status_code=404, detail=f"Committee {committee_id} not found")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.exception(f"Unexpected error getting committee members for {committee_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


@router.get(
    "/{committee_id}/hearings",
    response_model=Dict[str, Any],
    summary="Get committee hearings",
    description="Retrieve hearings for a specific committee"
)
async def get_committee_hearings(
    committee_id: str = Path(..., description="Committee ID"),
    congress: int = Query(..., description="Congress number"),
    offset: int = Query(0, description="Result offset"),
    limit: int = Query(20, description="Result limit"),
    api_router: ApiRouter = Depends()
):
    """Get committee hearings."""
    try:
        # Prepare parameters
        params = {
            "committee_id": committee_id,
            "congress": congress,
            "offset": offset,
            "limit": limit
        }
        
        # Route request
        hearings_data = await api_router.route_request(
            request_type="committee",
            method="get_committee_hearings",
            **params
        )
        
        # Format results
        hearings = []
        for hearing in hearings_data.get("hearings", []):
            hearings.append({
                "hearing_id": hearing.get("hearing_id", ""),
                "title": hearing.get("title", ""),
                "date": hearing.get("date"),
                "time": hearing.get("time"),
                "location": hearing.get("location"),
                "url": hearing.get("url")
            })
        
        return {
            "committee_id": committee_id,
            "congress": congress,
            "count": hearings_data.get("pagination", {}).get("count", len(hearings)),
            "offset": offset,
            "limit": limit,
            "hearings": hearings
        }
    except RouterError as e:
        logger.error(f"Router error getting committee hearings for {committee_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except RouteNotFoundError as e:
        logger.error(f"Route not found for committee hearings {committee_id}: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except SourceUnavailableError as e:
        logger.error(f"Source unavailable for committee hearings {committee_id}: {e}")
        raise HTTPException(status_code=503, detail=str(e))
    except ApiError as e:
        logger.error(f"API error getting committee hearings for {committee_id}: {e}")
        if "Not Found" in str(e):
            raise HTTPException(status_code=404, detail=f"Committee {committee_id} not found")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.exception(f"Unexpected error getting committee hearings for {committee_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")