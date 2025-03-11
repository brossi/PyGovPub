"""
Bills API Router.

This module provides FastAPI routes for accessing bill information
from Congress.gov and GovInfo.gov.
"""

import logging
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Path
from pydantic import BaseModel, Field

from pygovpub.api.router import ApiRouter
from pygovpub.auth.models import ApiSource
from pygovpub.models.legislative import Bill, BillType, Chamber
from pygovpub.exceptions import RouterError, ApiError, RouteNotFoundError, SourceUnavailableError

# Configure logging
logger = logging.getLogger("pygovpub.api.routers.bills")

# Create router
router = APIRouter(
    prefix="/bills",
    tags=["Bills"],
    responses={
        404: {"description": "Bill not found"},
        429: {"description": "Rate limit exceeded"},
        503: {"description": "Source unavailable"}
    }
)


# Response models
class BillResponse(BaseModel):
    """Bill response model."""
    
    bill_id: str = Field(..., description="Unique bill identifier")
    congress: int = Field(..., description="Congress number")
    bill_type: str = Field(..., description="Bill type")
    bill_number: int = Field(..., description="Bill number")
    title: str = Field(..., description="Bill title")
    introduced_date: Optional[str] = Field(None, description="Date bill was introduced")
    status: Optional[str] = Field(None, description="Current bill status")
    latest_action: Optional[Dict[str, Any]] = Field(None, description="Latest action on bill")
    source_url: Optional[str] = Field(None, description="URL to bill on source website")
    
    class Config:
        schema_extra = {
            "example": {
                "bill_id": "hr1234-117",
                "congress": 117,
                "bill_type": "hr",
                "bill_number": 1234,
                "title": "Example Bill Title",
                "introduced_date": "2023-01-15",
                "status": "INTRODUCED",
                "latest_action": {
                    "date": "2023-01-20",
                    "text": "Referred to the Committee on Example"
                },
                "source_url": "https://www.congress.gov/bill/117th-congress/house-bill/1234"
            }
        }


class BillSearchResponse(BaseModel):
    """Bill search response model."""
    
    count: int = Field(..., description="Total number of results")
    offset: int = Field(..., description="Result offset")
    limit: int = Field(..., description="Result limit")
    bills: List[BillResponse] = Field(..., description="List of bills")


# Routes
@router.get(
    "/{bill_id}",
    response_model=BillResponse,
    summary="Get bill information",
    description="Retrieve detailed information about a specific bill"
)
async def get_bill(
    bill_id: str = Path(..., description="Bill ID (format: {type}{number}-{congress})"),
    api_router: ApiRouter = Depends()
):
    """Get bill information by ID."""
    try:
        # Parse bill ID
        try:
            parts = bill_id.split("-")
            if len(parts) != 2:
                raise HTTPException(status_code=400, detail="Invalid bill ID format. Expected: {type}{number}-{congress}")
            
            bill_number_type = parts[0]
            congress = int(parts[1])
            
            import re
            bill_type_match = re.match(r"([a-z]+)(\d+)", bill_number_type)
            if not bill_type_match:
                raise HTTPException(status_code=400, detail="Invalid bill ID format. Expected: {type}{number}-{congress}")
            
            bill_type = bill_type_match.group(1)
            bill_number = int(bill_type_match.group(2))
        except (ValueError, IndexError) as e:
            raise HTTPException(status_code=400, detail=f"Invalid bill ID format: {e}")
        
        # Get bill from API router
        normalized_bill = await api_router.get_normalized_bill(
            congress=congress,
            bill_type=bill_type,
            bill_number=bill_number
        )
        
        # Convert to response model
        return BillResponse(
            bill_id=normalized_bill.get("id", ""),
            congress=congress,
            bill_type=bill_type,
            bill_number=bill_number,
            title=normalized_bill.get("title", ""),
            introduced_date=normalized_bill.get("introduced_date"),
            status=normalized_bill.get("status", ""),
            latest_action=normalized_bill.get("latest_action", {}),
            source_url=normalized_bill.get("source_url", "")
        )
    except RouterError as e:
        logger.error(f"Router error getting bill {bill_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except ApiError as e:
        logger.error(f"API error getting bill {bill_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except RouteNotFoundError as e:
        logger.error(f"Route not found for bill {bill_id}: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except SourceUnavailableError as e:
        logger.error(f"Source unavailable for bill {bill_id}: {e}")
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception(f"Unexpected error getting bill {bill_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


@router.get(
    "/congress/{congress}",
    response_model=BillSearchResponse,
    summary="Search bills by congress",
    description="Search for bills in a specific congress with optional filters"
)
async def search_bills_by_congress(
    congress: int = Path(..., description="Congress number"),
    bill_type: Optional[str] = Query(None, description="Bill type (e.g. 'hr', 's')"),
    offset: int = Query(0, description="Result offset"),
    limit: int = Query(20, description="Result limit"),
    api_router: ApiRouter = Depends()
):
    """Search bills by congress."""
    try:
        # Get Congress client
        congress_client = api_router.get_client(ApiSource.CONGRESS)
        
        # Call search_bills method
        search_params = {
            "congress": congress,
            "offset": offset,
            "limit": limit
        }
        
        if bill_type:
            search_params["bill_type"] = bill_type
        
        search_results = await congress_client.search_bills(**search_params)
        
        # Convert to response model
        bills = []
        for bill in search_results.get("bills", []):
            normalized = api_router._normalize_congress_bill(bill)
            
            # Extract bill ID parts
            bill_id = normalized.get("id", "")
            parts = bill_id.split("-")
            bill_number_type = parts[0] if len(parts) > 0 else ""
            
            # Split bill number and type
            import re
            bill_type_match = re.match(r"([a-z]+)(\d+)", bill_number_type)
            bill_type_str = bill_type_match.group(1) if bill_type_match else ""
            bill_number = int(bill_type_match.group(2)) if bill_type_match else 0
            
            # Congress is the second part of the ID
            congress_num = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
            
            bills.append(BillResponse(
                bill_id=bill_id,
                congress=congress_num,
                bill_type=bill_type_str,
                bill_number=bill_number,
                title=normalized.get("title", ""),
                introduced_date=normalized.get("introduced_date"),
                status=normalized.get("status", ""),
                latest_action=normalized.get("latest_action", {}),
                source_url=normalized.get("source_url", "")
            ))
        
        return BillSearchResponse(
            count=search_results.get("pagination", {}).get("count", len(bills)),
            offset=offset,
            limit=limit,
            bills=bills
        )
    except RouterError as e:
        logger.error(f"Router error searching bills for congress {congress}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except ApiError as e:
        logger.error(f"API error searching bills for congress {congress}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except RouteNotFoundError as e:
        logger.error(f"Route not found for congress {congress}: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except SourceUnavailableError as e:
        logger.error(f"Source unavailable for congress {congress}: {e}")
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception(f"Unexpected error searching bills for congress {congress}: {e}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


@router.get(
    "/{bill_id}/text",
    response_model=Dict[str, Any],
    summary="Get bill text",
    description="Retrieve the full text of a specific bill version"
)
async def get_bill_text(
    bill_id: str = Path(..., description="Bill ID (format: {type}{number}-{congress})"),
    version_code: str = Query("ih", description="Bill version code"),
    api_router: ApiRouter = Depends()
):
    """Get bill text."""
    try:
        # Parse bill ID
        try:
            parts = bill_id.split("-")
            if len(parts) != 2:
                raise HTTPException(status_code=400, detail="Invalid bill ID format. Expected: {type}{number}-{congress}")
            
            bill_number_type = parts[0]
            congress = int(parts[1])
            
            import re
            bill_type_match = re.match(r"([a-z]+)(\d+)", bill_number_type)
            if not bill_type_match:
                raise HTTPException(status_code=400, detail="Invalid bill ID format. Expected: {type}{number}-{congress}")
            
            bill_type = bill_type_match.group(1)
            bill_number = int(bill_type_match.group(2))
        except (ValueError, IndexError) as e:
            raise HTTPException(status_code=400, detail=f"Invalid bill ID format: {e}")
        
        # Get GovInfo client
        govinfo_client = api_router.get_client(ApiSource.GOVINFO)
        
        # Resolve bill package ID
        package_id = await govinfo_client.resolve_bill_package_id(
            congress=congress,
            bill_type=bill_type,
            bill_number=bill_number,
            version_code=version_code
        )
        
        # Get bill content
        content = await govinfo_client.get_package_content(package_id=package_id)
        
        return {
            "bill_id": bill_id,
            "version_code": version_code,
            "package_id": package_id,
            "content_type": content.get("content_type", "text/html"),
            "content": content.get("content", "No content available"),
            "source_url": content.get("source_url", "")
        }
    except RouterError as e:
        logger.error(f"Router error getting bill text for {bill_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except ApiError as e:
        logger.error(f"API error getting bill text for {bill_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except RouteNotFoundError as e:
        logger.error(f"Route not found for bill text {bill_id}: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except SourceUnavailableError as e:
        logger.error(f"Source unavailable for bill text {bill_id}: {e}")
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception(f"Unexpected error getting bill text for {bill_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


@router.get(
    "/{bill_id}/status",
    response_model=Dict[str, Any],
    summary="Get bill status",
    description="Retrieve the current status of a specific bill"
)
async def get_bill_status(
    bill_id: str = Path(..., description="Bill ID (format: {type}{number}-{congress})"),
    api_router: ApiRouter = Depends()
):
    """Get bill status."""
    try:
        # Parse bill ID
        try:
            parts = bill_id.split("-")
            if len(parts) != 2:
                raise HTTPException(status_code=400, detail="Invalid bill ID format. Expected: {type}{number}-{congress}")
            
            bill_number_type = parts[0]
            congress = int(parts[1])
            
            import re
            bill_type_match = re.match(r"([a-z]+)(\d+)", bill_number_type)
            if not bill_type_match:
                raise HTTPException(status_code=400, detail="Invalid bill ID format. Expected: {type}{number}-{congress}")
            
            bill_type = bill_type_match.group(1)
            bill_number = int(bill_type_match.group(2))
        except (ValueError, IndexError) as e:
            raise HTTPException(status_code=400, detail=f"Invalid bill ID format: {e}")
        
        # Route request
        status_data = await api_router.route_request(
            request_type="bill",
            method="get_bill_status",
            congress=congress,
            bill_type=bill_type,
            bill_number=bill_number
        )
        
        # Format response
        return {
            "bill_id": bill_id,
            "congress": congress,
            "bill_type": bill_type,
            "bill_number": bill_number,
            "status": status_data.get("status", ""),
            "status_date": status_data.get("status_date", ""),
            "latest_action": status_data.get("latest_action", {}),
            "actions": status_data.get("actions", [])
        }
    except RouterError as e:
        logger.error(f"Router error getting bill status for {bill_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except ApiError as e:
        logger.error(f"API error getting bill status for {bill_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except RouteNotFoundError as e:
        logger.error(f"Route not found for bill status {bill_id}: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except SourceUnavailableError as e:
        logger.error(f"Source unavailable for bill status {bill_id}: {e}")
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception(f"Unexpected error getting bill status for {bill_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")