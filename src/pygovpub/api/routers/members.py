"""
Members API Router.

This module provides FastAPI routes for accessing congressional member
information from Congress.gov API.
"""

import logging
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Path
from pydantic import BaseModel, Field

from pygovpub.api.router import ApiRouter
from pygovpub.auth.models import ApiSource
from pygovpub.models.legislative_db import Member
from pygovpub.exceptions import RouterError, ApiError, RouteNotFoundError, SourceUnavailableError

# Configure logging
logger = logging.getLogger("pygovpub.api.routers.members")

# Create router
router = APIRouter(
    prefix="/members",
    tags=["Members"],
    responses={
        404: {"description": "Member not found"},
        429: {"description": "Rate limit exceeded"},
        503: {"description": "Source unavailable"}
    }
)


# Response models
class MemberResponse(BaseModel):
    """Member response model."""

    bioguide_id: str = Field(..., description="Bioguide ID")
    first_name: str = Field(..., description="First name")
    last_name: str = Field(..., description="Last name")
    state: Optional[str] = Field(None, description="State")
    party: Optional[str] = Field(None, description="Party affiliation")
    chamber: Optional[str] = Field(None, description="Chamber")
    district: Optional[str] = Field(None, description="Congressional district (if House member)")
    term_start: Optional[str] = Field(None, description="Term start date")
    term_end: Optional[str] = Field(None, description="Term end date")
    url: Optional[str] = Field(None, description="URL to member's page")

    class Config:
       json_schema_extra = {
            "example": {
                "bioguide_id": "S000148",
                "first_name": "Chuck",
                "last_name": "Schumer",
                "state": "NY",
                "party": "D",
                "chamber": "Senate",
                "district": None,
                "term_start": "2023-01-03",
                "term_end": "2029-01-03",
                "url": "https://www.congress.gov/member/charles-schumer/S000148"
            }
        }


class MemberSearchResponse(BaseModel):
    """Member search response model."""

    count: int = Field(..., description="Total number of results")
    offset: int = Field(..., description="Result offset")
    limit: int = Field(..., description="Result limit")
    members: List[MemberResponse] = Field(..., description="List of members")


# Routes
@router.get(
    "/{bioguide_id}",
    response_model=MemberResponse,
    summary="Get member information",
    description="Retrieve detailed information about a specific member of Congress"
)
async def get_member(
    bioguide_id: str = Path(..., description="Bioguide ID"),
    api_router: ApiRouter = Depends()
):
    """Get member information by Bioguide ID."""
    try:
        # Route request
        member_data = await api_router.route_request(
            request_type="member",
            method="get_member",
            bioguide_id=bioguide_id
        )

        # Convert to response model
        return MemberResponse(
            bioguide_id=member_data.get("bioguide_id", bioguide_id),
            first_name=member_data.get("first_name", ""),
            last_name=member_data.get("last_name", ""),
            state=member_data.get("state"),
            party=member_data.get("party"),
            chamber=member_data.get("chamber"),
            district=member_data.get("district"),
            term_start=member_data.get("term_start"),
            term_end=member_data.get("term_end"),
            url=member_data.get("url")
        )
    except RouteNotFoundError as e:
        logger.error(f"Route not found for member {bioguide_id}: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except SourceUnavailableError as e:
        logger.error(f"Source unavailable for member {bioguide_id}: {e}")
        raise HTTPException(status_code=503, detail=str(e))
    except ApiError as e:
        logger.error(f"API error getting member {bioguide_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.exception(f"Unexpected error getting member {bioguide_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


@router.get(
    "/",
    response_model=MemberSearchResponse,
    summary="Search members",
    description="Search for members of Congress with optional filters"
)
async def search_members(
    congress: Optional[int] = Query(None, description="Congress number"),
    chamber: Optional[str] = Query(None, description="Chamber (House or Senate)"),
    state: Optional[str] = Query(None, description="State abbreviation"),
    party: Optional[str] = Query(None, description="Party (D, R, I)"),
    name: Optional[str] = Query(None, description="Name search"),
    offset: int = Query(0, description="Result offset"),
    limit: int = Query(20, description="Result limit"),
    api_router: ApiRouter = Depends()
):
    """Search members."""
    try:
        # Get Congress client
        congress_client = api_router.get_client(ApiSource.CONGRESS)

        # Prepare search parameters
        search_params = {
            "offset": offset,
            "limit": limit
        }

        if congress:
            search_params["congress"] = congress
        if chamber:
            search_params["chamber"] = chamber
        if state:
            search_params["state"] = state
        if party:
            search_params["party"] = party
        if name:
            search_params["name"] = name

        # Execute search
        search_results = await congress_client.search_members(**search_params)

        # Format results
        members = []
        for member in search_results.get("members", []):
            members.append(MemberResponse(
                bioguide_id=member.get("bioguide_id", ""),
                first_name=member.get("first_name", ""),
                last_name=member.get("last_name", ""),
                state=member.get("state"),
                party=member.get("party"),
                chamber=member.get("chamber"),
                district=member.get("district"),
                term_start=member.get("term_start"),
                term_end=member.get("term_end"),
                url=member.get("url")
            ))

        return MemberSearchResponse(
            count=search_results.get("pagination", {}).get("count", len(members)),
            offset=offset,
            limit=limit,
            members=members
        )
    except RouteNotFoundError as e:
        logger.error(f"Route not found for member search: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except SourceUnavailableError as e:
        logger.error(f"Source unavailable for member search: {e}")
        raise HTTPException(status_code=503, detail=str(e))
    except ApiError as e:
        logger.error(f"API error searching members: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.exception(f"Unexpected error searching members: {e}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


@router.get(
    "/{bioguide_id}/sponsored-bills",
    response_model=Dict[str, Any],
    summary="Get member sponsored bills",
    description="Retrieve bills sponsored by a specific member of Congress"
)
async def get_member_sponsored_bills(
    bioguide_id: str = Path(..., description="Bioguide ID"),
    congress: Optional[int] = Query(None, description="Congress number"),
    offset: int = Query(0, description="Result offset"),
    limit: int = Query(20, description="Result limit"),
    api_router: ApiRouter = Depends()
):
    """Get bills sponsored by a member."""
    try:
        # Prepare parameters
        params = {
            "bioguide_id": bioguide_id,
            "offset": offset,
            "limit": limit
        }

        if congress:
            params["congress"] = congress

        # Route request
        bills_data = await api_router.route_request(
            request_type="member",
            method="get_member_sponsored_bills",
            **params
        )

        # Process results (format similar to bill search response)
        bills = []
        for bill in bills_data.get("bills", []):
            # Normalize bill data
            normalized = api_router._normalize_congress_bill(bill)

            bills.append({
                "bill_id": normalized.get("id", ""),
                "title": normalized.get("title", ""),
                "introduced_date": normalized.get("introduced_date"),
                "status": normalized.get("status", ""),
                "latest_action": normalized.get("latest_action", {}),
                "source_url": normalized.get("source_url", "")
            })

        return {
            "bioguide_id": bioguide_id,
            "congress": congress,
            "count": bills_data.get("pagination", {}).get("count", len(bills)),
            "offset": offset,
            "limit": limit,
            "bills": bills
        }
    except RouteNotFoundError as e:
        logger.error(f"Route not found for sponsored bills of member {bioguide_id}: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except SourceUnavailableError as e:
        logger.error(f"Source unavailable for sponsored bills of member {bioguide_id}: {e}")
        raise HTTPException(status_code=503, detail=str(e))
    except ApiError as e:
        logger.error(f"API error getting sponsored bills for member {bioguide_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.exception(f"Unexpected error getting sponsored bills for member {bioguide_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


@router.get(
    "/{bioguide_id}/cosponsored-bills",
    response_model=Dict[str, Any],
    summary="Get member cosponsored bills",
    description="Retrieve bills cosponsored by a specific member of Congress"
)
async def get_member_cosponsored_bills(
    bioguide_id: str = Path(..., description="Bioguide ID"),
    congress: Optional[int] = Query(None, description="Congress number"),
    offset: int = Query(0, description="Result offset"),
    limit: int = Query(20, description="Result limit"),
    api_router: ApiRouter = Depends()
):
    """Get bills cosponsored by a member."""
    try:
        # Prepare parameters
        params = {
            "bioguide_id": bioguide_id,
            "offset": offset,
            "limit": limit
        }

        if congress:
            params["congress"] = congress

        # Route request
        bills_data = await api_router.route_request(
            request_type="member",
            method="get_member_cosponsored_bills",
            **params
        )

        # Process results (format similar to bill search response)
        bills = []
        for bill in bills_data.get("bills", []):
            # Normalize bill data
            normalized = api_router._normalize_congress_bill(bill)

            bills.append({
                "bill_id": normalized.get("id", ""),
                "title": normalized.get("title", ""),
                "introduced_date": normalized.get("introduced_date"),
                "status": normalized.get("status", ""),
                "latest_action": normalized.get("latest_action", {}),
                "source_url": normalized.get("source_url", "")
            })

        return {
            "bioguide_id": bioguide_id,
            "congress": congress,
            "count": bills_data.get("pagination", {}).get("count", len(bills)),
            "offset": offset,
            "limit": limit,
            "bills": bills
        }
    except RouteNotFoundError as e:
        logger.error(f"Route not found for cosponsored bills of member {bioguide_id}: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except SourceUnavailableError as e:
        logger.error(f"Source unavailable for cosponsored bills of member {bioguide_id}: {e}")
        raise HTTPException(status_code=503, detail=str(e))
    except ApiError as e:
        logger.error(f"API error getting cosponsored bills for member {bioguide_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.exception(f"Unexpected error getting cosponsored bills for member {bioguide_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")
