"""
Court Opinions API Router.

This module provides FastAPI routes for accessing court opinions
from GovInfo.gov API.
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Path
from pydantic import BaseModel, Field

from pygovpub.api.router import ApiRouter
from pygovpub.auth.models import ApiSource
from pygovpub.models.documents import DocumentType
from pygovpub.exceptions import RouterError, ApiError, RouteNotFoundError, SourceUnavailableError

# Configure logging
logger = logging.getLogger("pygovpub.api.routers.court_opinions")

# Create router
router = APIRouter(
    prefix="/court-opinions",
    tags=["Court Opinions"],
    responses={
        404: {"description": "Court opinion not found"},
        429: {"description": "Rate limit exceeded"},
        503: {"description": "Source unavailable"}
    }
)


# Response models
class CourtResponse(BaseModel):
    """Court information response model."""
    
    court_code: str = Field(..., description="Court code")
    court_name: str = Field(..., description="Court name")
    opinion_count: Optional[int] = Field(None, description="Number of opinions from this court")
    
    class Config:
        schema_extra = {
            "example": {
                "court_code": "SCOTUS",
                "court_name": "Supreme Court of the United States",
                "opinion_count": 1245
            }
        }


class OpinionResponse(BaseModel):
    """Court opinion response model."""
    
    package_id: str = Field(..., description="GovInfo package ID")
    title: str = Field(..., description="Opinion title")
    court: str = Field(..., description="Court name")
    docket_number: Optional[str] = Field(None, description="Docket number")
    part_name: Optional[str] = Field(None, description="Name of part within volume")
    date_issued: Optional[str] = Field(None, description="Date opinion was issued")
    year: Optional[int] = Field(None, description="Year of opinion")
    pdf_url: Optional[str] = Field(None, description="URL to PDF version")
    xml_url: Optional[str] = Field(None, description="URL to XML version")
    html_url: Optional[str] = Field(None, description="URL to HTML version")
    
    class Config:
        schema_extra = {
            "example": {
                "package_id": "USCOURTS-ca1-12-1234",
                "title": "Example Opinion Title",
                "court": "United States Court of Appeals for the First Circuit",
                "docket_number": "12-1234",
                "part_name": "Opinion of the Court",
                "date_issued": "2023-01-15",
                "year": 2023,
                "pdf_url": "https://www.govinfo.gov/content/pkg/USCOURTS-ca1-12-1234/pdf/USCOURTS-ca1-12-1234.pdf",
                "xml_url": "https://www.govinfo.gov/content/pkg/USCOURTS-ca1-12-1234/xml/USCOURTS-ca1-12-1234.xml",
                "html_url": "https://www.govinfo.gov/content/pkg/USCOURTS-ca1-12-1234/html/USCOURTS-ca1-12-1234.htm"
            }
        }


class OpinionSearchResponse(BaseModel):
    """Court opinion search response model."""
    
    count: int = Field(..., description="Total number of results")
    offset: int = Field(..., description="Result offset")
    limit: int = Field(..., description="Result limit")
    opinions: List[OpinionResponse] = Field(..., description="List of court opinions")


# Routes
@router.get(
    "/courts",
    response_model=List[CourtResponse],
    summary="List courts",
    description="Retrieve a list of courts with available opinions"
)
async def list_courts(
    api_router: ApiRouter = Depends()
):
    """List courts with available opinions."""
    try:
        # Get GovInfo client
        govinfo_client = api_router.get_client(ApiSource.GOVINFO)
        
        # Get courts data
        courts_data = await govinfo_client.get_courts()
        
        # Format response
        courts = []
        for court in courts_data.get("courts", []):
            courts.append(CourtResponse(
                court_code=court.get("code", ""),
                court_name=court.get("name", ""),
                opinion_count=court.get("opinionCount")
            ))
        
        return courts
    except SourceUnavailableError as e:
        logger.error(f"Source unavailable for courts list: {e}")
        raise HTTPException(status_code=503, detail=str(e))
    except ApiError as e:
        logger.error(f"API error listing courts: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.exception(f"Unexpected error listing courts: {e}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


@router.get(
    "/search",
    response_model=OpinionSearchResponse,
    summary="Search court opinions",
    description="Search for court opinions with optional filters"
)
async def search_opinions(
    court: Optional[str] = Query(None, description="Court code (e.g., 'SCOTUS', 'CA1')"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    query: Optional[str] = Query(None, description="Search query"),
    docket: Optional[str] = Query(None, description="Docket number"),
    offset: int = Query(0, description="Result offset"),
    limit: int = Query(20, description="Result limit"),
    api_router: ApiRouter = Depends()
):
    """Search court opinions."""
    try:
        # Get GovInfo client
        govinfo_client = api_router.get_client(ApiSource.GOVINFO)
        
        # Prepare search parameters
        search_params = {
            "collection": "USCOURTS",
            "offset": offset,
            "limit": limit
        }
        
        # Add optional date filters
        if start_date:
            search_params["start_date"] = start_date
        if end_date:
            search_params["end_date"] = end_date
        
        # Build query string
        query_parts = []
        if query:
            query_parts.append(query)
        if court:
            query_parts.append(f"court:{court}")
        if docket:
            query_parts.append(f"docket:{docket}")
        
        if query_parts:
            search_params["query"] = " AND ".join(query_parts)
        
        # Execute search
        search_results = await govinfo_client.search_packages(**search_params)
        
        # Format results
        opinions = []
        for doc in search_results.get("packages", []):
            # Extract metadata
            metadata = doc.get("metadata", {})
            download_urls = doc.get("download", {})
            
            # Extract year from date if available
            year = None
            if doc.get("dateIssued"):
                try:
                    year = int(doc.get("dateIssued").split("-")[0])
                except (ValueError, IndexError, AttributeError):
                    pass
            
            opinions.append(OpinionResponse(
                package_id=doc.get("packageId", ""),
                title=doc.get("title", ""),
                court=metadata.get("court", ""),
                docket_number=metadata.get("docketNumber"),
                part_name=metadata.get("partName"),
                date_issued=doc.get("dateIssued"),
                year=year,
                pdf_url=download_urls.get("pdfLink"),
                xml_url=download_urls.get("xmlLink"),
                html_url=download_urls.get("htmlLink")
            ))
        
        return OpinionSearchResponse(
            count=search_results.get("count", len(opinions)),
            offset=offset,
            limit=limit,
            opinions=opinions
        )
    except SourceUnavailableError as e:
        logger.error(f"Source unavailable for opinion search: {e}")
        raise HTTPException(status_code=503, detail=str(e))
    except ApiError as e:
        logger.error(f"API error searching opinions: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.exception(f"Unexpected error searching opinions: {e}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


@router.get(
    "/{package_id}",
    response_model=OpinionResponse,
    summary="Get court opinion",
    description="Retrieve detailed information about a specific court opinion"
)
async def get_opinion(
    package_id: str = Path(..., description="GovInfo package ID"),
    api_router: ApiRouter = Depends()
):
    """Get court opinion information by package ID."""
    try:
        # Validate that this is a court opinion
        if not package_id.startswith("USCOURTS-"):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid court opinion package ID: {package_id}. Must start with 'USCOURTS-'."
            )
        
        # Get GovInfo client
        govinfo_client = api_router.get_client(ApiSource.GOVINFO)
        
        # Get package summary
        package_data = await govinfo_client.get_package_summary(package_id=package_id)
        
        # Extract metadata
        metadata = package_data.get("metadata", {})
        download_urls = package_data.get("download", {})
        
        # Extract year from date if available
        year = None
        if package_data.get("dateIssued"):
            try:
                year = int(package_data.get("dateIssued").split("-")[0])
            except (ValueError, IndexError, AttributeError):
                pass
        
        return OpinionResponse(
            package_id=package_id,
            title=package_data.get("title", ""),
            court=metadata.get("court", ""),
            docket_number=metadata.get("docketNumber"),
            part_name=metadata.get("partName"),
            date_issued=package_data.get("dateIssued"),
            year=year,
            pdf_url=download_urls.get("pdfLink"),
            xml_url=download_urls.get("xmlLink"),
            html_url=download_urls.get("htmlLink")
        )
    except SourceUnavailableError as e:
        logger.error(f"Source unavailable for opinion {package_id}: {e}")
        raise HTTPException(status_code=503, detail=str(e))
    except ApiError as e:
        logger.error(f"API error getting opinion {package_id}: {e}")
        if "Not Found" in str(e):
            raise HTTPException(status_code=404, detail=f"Court opinion {package_id} not found")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.exception(f"Unexpected error getting opinion {package_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


@router.get(
    "/{package_id}/content",
    response_model=Dict[str, Any],
    summary="Get court opinion content",
    description="Retrieve the content of a specific court opinion"
)
async def get_opinion_content(
    package_id: str = Path(..., description="GovInfo package ID"),
    content_type: Optional[str] = Query("html", description="Content type (html, pdf, xml)"),
    api_router: ApiRouter = Depends()
):
    """Get court opinion content."""
    try:
        # Validate that this is a court opinion
        if not package_id.startswith("USCOURTS-"):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid court opinion package ID: {package_id}. Must start with 'USCOURTS-'."
            )
        
        # Get GovInfo client
        govinfo_client = api_router.get_client(ApiSource.GOVINFO)
        
        # Get package content
        content = await govinfo_client.get_package_content(
            package_id=package_id,
            content_type=content_type
        )
        
        return {
            "package_id": package_id,
            "content_type": content.get("content_type", "text/html"),
            "content": content.get("content", "No content available"),
            "source_url": content.get("source_url", "")
        }
    except SourceUnavailableError as e:
        logger.error(f"Source unavailable for opinion content {package_id}: {e}")
        raise HTTPException(status_code=503, detail=str(e))
    except ApiError as e:
        logger.error(f"API error getting opinion content {package_id}: {e}")
        if "Not Found" in str(e):
            raise HTTPException(status_code=404, detail=f"Court opinion {package_id} not found")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.exception(f"Unexpected error getting opinion content {package_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")