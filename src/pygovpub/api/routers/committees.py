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
    subcommittees: Optional[List["CommitteeResponse"]] = Field(None, description="Subcommittees")
    
    class Config:
        json_schema_extra = {
            "example": {
                "committee_id": "HSAG",
                "name": "Committee on Agriculture",
                "chamber": "House",
                "congress": 117,
                "parent_committee_id": None,
                "type": "standing",
                "url": "https://www.congress.gov/committee/house-agriculture/hsag",
                "subcommittees": [
                    {
                        "committee_id": "HSAG01",
                        "name": "Subcommittee on Conservation and Forestry",
                        "chamber": "House",
                        "congress": 117,
                        "parent_committee_id": "HSAG"
                    }
                ]
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
    role: Optional[str] = Field(None, description="Role in committee")
    
    class Config:
        json_schema_extra = {
            "example": {
                "bioguide_id": "S000148",
                "first_name": "Chuck",
                "last_name": "Schumer",
                "state": "NY",
                "party": "D",
                "rank": 1,
                "title": "Chairman",
                "role": "Chair"
            }
        }


class CommitteeListResponse(BaseModel):
    """Committee list response model."""
    
    count: int = Field(..., description="Total number of results")
    congress: int = Field(..., description="Congress number")
    committees: List[CommitteeResponse] = Field(..., description="List of committees")


class CommitteeHearingResponse(BaseModel):
    """Committee hearing response model."""
    
    hearing_id: str = Field(..., description="Hearing ID")
    title: str = Field(..., description="Hearing title")
    committee_id: str = Field(..., description="Committee ID")
    date: Optional[str] = Field(None, description="Hearing date (YYYY-MM-DD)")
    time: Optional[str] = Field(None, description="Hearing time")
    location: Optional[str] = Field(None, description="Hearing location")
    url: Optional[str] = Field(None, description="URL to hearing page")
    
    class Config:
        json_schema_extra = {
            "example": {
                "hearing_id": "H001",
                "title": "Farm Bill Implementation",
                "committee_id": "HSAG",
                "date": "2023-03-15",
                "time": "10:00 AM",
                "location": "1300 Longworth House Office Building",
                "url": "https://www.congress.gov/committee-hearing/example"
            }
        }


class CommitteeHearingsResponse(BaseModel):
    """Committee hearings list response model."""
    
    committee_id: str = Field(..., description="Committee ID")
    congress: int = Field(..., description="Congress number")
    count: int = Field(..., description="Total number of results")
    offset: int = Field(..., description="Result offset")
    limit: int = Field(..., description="Result limit")
    hearings: List[CommitteeHearingResponse] = Field(..., description="List of hearings")


class CommitteeReportResponse(BaseModel):
    """Committee report response model."""
    
    report_id: str = Field(..., description="Report ID")
    title: str = Field(..., description="Report title")
    committee_id: str = Field(..., description="Committee ID")
    congress: int = Field(..., description="Congress number")
    date: Optional[str] = Field(None, description="Report date (YYYY-MM-DD)")
    url: Optional[str] = Field(None, description="URL to report page")
    
    class Config:
        json_schema_extra = {
            "example": {
                "report_id": "HRPT-117-123",
                "title": "Agriculture Committee Report",
                "committee_id": "HSAG",
                "congress": 117,
                "date": "2023-04-01",
                "url": "https://www.congress.gov/congressional-report/example"
            }
        }


class CommitteeReportsResponse(BaseModel):
    """Committee reports list response model."""
    
    committee_id: str = Field(..., description="Committee ID")
    congress: int = Field(..., description="Congress number")
    count: int = Field(..., description="Total number of results")
    offset: int = Field(..., description="Result offset")
    limit: int = Field(..., description="Result limit")
    reports: List[CommitteeReportResponse] = Field(..., description="List of reports")


class CommitteeMembershipResponse(BaseModel):
    """Committee membership list response model."""
    
    committee_id: str = Field(..., description="Committee ID")
    congress: int = Field(..., description="Congress number")
    count: int = Field(..., description="Total number of results")
    offset: int = Field(..., description="Result offset")
    limit: int = Field(..., description="Result limit")
    members: List[CommitteeMemberResponse] = Field(..., description="List of members")


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
        response = CommitteeResponse(
            committee_id=committee_data.get("committee_id", committee_id),
            name=committee_data.get("name", ""),
            chamber=committee_data.get("chamber", ""),
            congress=committee_data.get("congress", congress),
            parent_committee_id=committee_data.get("parent_committee_id"),
            type=committee_data.get("type"),
            url=committee_data.get("url")
        )
        
        # Add subcommittees if present
        if "subcommittees" in committee_data and committee_data["subcommittees"]:
            subcommittees = []
            for sub in committee_data["subcommittees"]:
                subcommittees.append(CommitteeResponse(
                    committee_id=sub.get("committee_id", ""),
                    name=sub.get("name", ""),
                    chamber=response.chamber,  # Inherit from parent
                    congress=response.congress,  # Inherit from parent
                    parent_committee_id=response.committee_id,
                    type="subcommittee",
                    url=sub.get("url")
                ))
            response.subcommittees = subcommittees
            
        return response
    except RouterError as e:
        logger.error(f"Router error getting committee {committee_id}: {e}")
        # Special handling for SourceUnavailableError subclass
        if isinstance(e, SourceUnavailableError):
            raise HTTPException(status_code=503, detail=str(e))
        else:
            raise HTTPException(status_code=500, detail=str(e))
    except RouteNotFoundError as e:
        logger.error(f"Route not found for committee {committee_id}: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except ApiError as e:
        logger.error(f"API error getting committee {committee_id}: {e}")
        if "Not Found" in str(e) or e.status_code == 404:
            raise HTTPException(status_code=404, detail=f"Committee {committee_id} not found")
        raise HTTPException(status_code=e.status_code, detail=str(e))
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
        # Prepare parameters
        params = {
            "congress": congress
        }
        
        if chamber:
            params["chamber"] = chamber
        if type:
            params["type"] = type
        
        # Route request
        committees_data = await api_router.route_request(
            request_type="committee",
            method="list_committees",
            **params
        )
        
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
        # Special handling for SourceUnavailableError subclass
        if isinstance(e, SourceUnavailableError):
            raise HTTPException(status_code=503, detail=str(e))
        else:
            raise HTTPException(status_code=500, detail=str(e))
    except RouteNotFoundError as e:
        logger.error(f"Route not found for listing committees: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except ApiError as e:
        logger.error(f"API error listing committees: {e}")
        if "Not Found" in str(e) or e.status_code == 404:
            raise HTTPException(status_code=404, detail="Committees not found")
        raise HTTPException(status_code=e.status_code, detail=str(e))
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
        if "Not Found" in str(e) or e.status_code == 404:
            raise HTTPException(status_code=404, detail=f"Committee {committee_id} not found")
        raise HTTPException(status_code=e.status_code, detail=str(e))
    except Exception as e:
        logger.exception(f"Unexpected error getting committee members for {committee_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


@router.get(
    "/{committee_id}/hearings",
    response_model=CommitteeHearingsResponse,
    summary="Get committee hearings",
    description="Retrieve hearings for a specific committee"
)
async def get_committee_hearings(
    committee_id: str = Path(..., description="Committee ID"),
    congress: int = Query(..., description="Congress number"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
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
        
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        
        # Route request
        hearings_data = await api_router.route_request(
            request_type="committee",
            method="get_committee_hearings",
            **params
        )
        
        # Format results
        hearings = []
        for hearing in hearings_data.get("hearings", []):
            hearings.append(CommitteeHearingResponse(
                hearing_id=hearing.get("hearing_id", ""),
                title=hearing.get("title", ""),
                committee_id=hearing.get("committee_id", committee_id),
                date=hearing.get("date"),
                time=hearing.get("time"),
                location=hearing.get("location"),
                url=hearing.get("url")
            ))
        
        return CommitteeHearingsResponse(
            committee_id=committee_id,
            congress=congress,
            count=hearings_data.get("pagination", {}).get("count", len(hearings)),
            offset=0 if offset is None else offset,
            limit=20 if limit is None else limit,
            hearings=hearings
        )
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
        if "Not Found" in str(e) or e.status_code == 404:
            raise HTTPException(status_code=404, detail=f"Committee {committee_id} not found")
        raise HTTPException(status_code=e.status_code, detail=str(e))
    except Exception as e:
        logger.exception(f"Unexpected error getting committee hearings for {committee_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


@router.get(
    "/{committee_id}/reports",
    response_model=CommitteeReportsResponse,
    summary="Get committee reports",
    description="Retrieve reports from a specific committee"
)
async def get_committee_reports(
    committee_id: str = Path(..., description="Committee ID"),
    congress: int = Query(..., description="Congress number"),
    offset: int = Query(0, description="Result offset"),
    limit: int = Query(20, description="Result limit"),
    api_router: ApiRouter = Depends()
):
    """Get committee reports."""
    try:
        # Prepare parameters
        params = {
            "committee_id": committee_id,
            "congress": congress,
            "offset": offset,
            "limit": limit
        }
        
        # Route request
        reports_data = await api_router.route_request(
            request_type="committee",
            method="get_committee_reports",
            **params
        )
        
        # Format results
        reports = []
        for report in reports_data.get("reports", []):
            reports.append(CommitteeReportResponse(
                report_id=report.get("report_id", ""),
                title=report.get("title", ""),
                committee_id=report.get("committee_id", committee_id),
                congress=report.get("congress", congress),
                date=report.get("date"),
                url=report.get("url")
            ))
        
        return CommitteeReportsResponse(
            committee_id=committee_id,
            congress=congress,
            count=reports_data.get("pagination", {}).get("count", len(reports)),
            offset=0 if offset is None else offset,
            limit=20 if limit is None else limit,
            reports=reports
        )
    except RouterError as e:
        logger.error(f"Router error getting committee reports for {committee_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except RouteNotFoundError as e:
        logger.error(f"Route not found for committee reports {committee_id}: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except SourceUnavailableError as e:
        logger.error(f"Source unavailable for committee reports {committee_id}: {e}")
        raise HTTPException(status_code=503, detail=str(e))
    except ApiError as e:
        logger.error(f"API error getting committee reports for {committee_id}: {e}")
        if "Not Found" in str(e) or e.status_code == 404:
            raise HTTPException(status_code=404, detail=f"Committee {committee_id} not found")
        raise HTTPException(status_code=e.status_code, detail=str(e))
    except Exception as e:
        logger.exception(f"Unexpected error getting committee reports for {committee_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


@router.get(
    "/{committee_id}/membership",
    response_model=CommitteeMembershipResponse,
    summary="Get committee membership",
    description="Retrieve detailed membership information for a specific committee"
)
async def get_committee_membership(
    committee_id: str = Path(..., description="Committee ID"),
    congress: int = Query(..., description="Congress number"),
    offset: int = Query(0, description="Result offset"),
    limit: int = Query(20, description="Result limit"),
    api_router: ApiRouter = Depends()
):
    """Get committee membership."""
    try:
        # Prepare parameters
        params = {
            "committee_id": committee_id,
            "congress": congress,
            "offset": offset,
            "limit": limit
        }
        
        # Route request
        membership_data = await api_router.route_request(
            request_type="committee",
            method="get_committee_membership",
            **params
        )
        
        # Format results
        members = []
        for member in membership_data.get("members", []):
            members.append(CommitteeMemberResponse(
                bioguide_id=member.get("bioguide_id", ""),
                first_name=member.get("first_name", ""),
                last_name=member.get("last_name", ""),
                state=member.get("state"),
                party=member.get("party"),
                rank=member.get("rank"),
                title=member.get("title"),
                role=member.get("role")
            ))
        
        return CommitteeMembershipResponse(
            committee_id=committee_id,
            congress=congress,
            count=membership_data.get("pagination", {}).get("count", len(members)),
            offset=0 if offset is None else offset,
            limit=20 if limit is None else limit,
            members=members
        )
    except RouterError as e:
        logger.error(f"Router error getting committee membership for {committee_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except RouteNotFoundError as e:
        logger.error(f"Route not found for committee membership {committee_id}: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except SourceUnavailableError as e:
        logger.error(f"Source unavailable for committee membership {committee_id}: {e}")
        raise HTTPException(status_code=503, detail=str(e))
    except ApiError as e:
        logger.error(f"API error getting committee membership for {committee_id}: {e}")
        if "Not Found" in str(e) or e.status_code == 404:
            raise HTTPException(status_code=404, detail=f"Committee {committee_id} not found")
        raise HTTPException(status_code=e.status_code, detail=str(e))
    except Exception as e:
        logger.exception(f"Unexpected error getting committee membership for {committee_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")