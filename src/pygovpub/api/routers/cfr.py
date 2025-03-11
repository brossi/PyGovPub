"""
CFR (Code of Federal Regulations) API Router.

This module provides FastAPI routes for accessing the Code of Federal Regulations
from GovInfo.gov API.
"""

import logging
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Path
from pydantic import BaseModel, Field

from pygovpub.api.router import ApiRouter
from pygovpub.auth.models import ApiSource
from pygovpub.models.documents import DocumentType
from pygovpub.exceptions import RouterError, ApiError, RouteNotFoundError, SourceUnavailableError

# Configure logging
logger = logging.getLogger("pygovpub.api.routers.cfr")

# Create router
router = APIRouter(
    prefix="/cfr",
    tags=["CFR"],
    responses={
        404: {"description": "CFR document not found"},
        429: {"description": "Rate limit exceeded"},
        503: {"description": "Source unavailable"}
    }
)


# Response models
class CfrTitleResponse(BaseModel):
    """CFR title response model."""
    
    title_number: int = Field(..., description="CFR title number")
    title_name: str = Field(..., description="CFR title name")
    chapters: Optional[List[Dict[str, Any]]] = Field(None, description="Chapters in this title")
    
    class Config:
        schema_extra = {
            "example": {
                "title_number": 40,
                "title_name": "Protection of Environment",
                "chapters": [
                    {
                        "chapter_number": "I",
                        "chapter_name": "Environmental Protection Agency"
                    }
                ]
            }
        }


class CfrDocumentResponse(BaseModel):
    """CFR document response model."""
    
    package_id: str = Field(..., description="GovInfo package ID")
    title_number: int = Field(..., description="CFR title number")
    title_name: str = Field(..., description="CFR title name") 
    part_number: Optional[int] = Field(None, description="CFR part number")
    section_number: Optional[str] = Field(None, description="CFR section number")
    heading: Optional[str] = Field(None, description="Section heading")
    year: int = Field(..., description="Year of CFR edition")
    date_issued: Optional[str] = Field(None, description="Date document was issued")
    pdf_url: Optional[str] = Field(None, description="URL to PDF version")
    xml_url: Optional[str] = Field(None, description="URL to XML version")
    html_url: Optional[str] = Field(None, description="URL to HTML version")
    
    class Config:
        schema_extra = {
            "example": {
                "package_id": "CFR-2023-title40-vol1",
                "title_number": 40,
                "title_name": "Protection of Environment",
                "part_number": 50,
                "section_number": "50.1",
                "heading": "Definitions",
                "year": 2023,
                "date_issued": "2023-07-01",
                "pdf_url": "https://www.govinfo.gov/content/pkg/CFR-2023-title40-vol1/pdf/CFR-2023-title40-vol1.pdf",
                "xml_url": "https://www.govinfo.gov/content/pkg/CFR-2023-title40-vol1/xml/CFR-2023-title40-vol1.xml",
                "html_url": "https://www.govinfo.gov/content/pkg/CFR-2023-title40-vol1/html/CFR-2023-title40-vol1.htm"
            }
        }


class CfrSearchResponse(BaseModel):
    """CFR search response model."""
    
    count: int = Field(..., description="Total number of results")
    offset: int = Field(..., description="Result offset")
    limit: int = Field(..., description="Result limit")
    results: List[CfrDocumentResponse] = Field(..., description="List of CFR documents")


# Routes
@router.get(
    "/titles",
    response_model=List[CfrTitleResponse],
    summary="List CFR titles",
    description="Retrieve a list of all Code of Federal Regulations titles"
)
async def list_cfr_titles(
    api_router: ApiRouter = Depends()
):
    """List all CFR titles."""
    try:
        # Get GovInfo client
        govinfo_client = api_router.get_client(ApiSource.GOVINFO)
        
        # Get the titles from the CFR collection directly
        cfr_titles_data = await govinfo_client.get_cfr_titles()
        
        # Format response
        titles = []
        for title in cfr_titles_data.get("titles", []):
            titles.append(CfrTitleResponse(
                title_number=title.get("number"),
                title_name=title.get("name"),
                chapters=title.get("chapters")
            ))
        
        return titles
    except SourceUnavailableError as e:
        logger.error(f"Source unavailable for CFR titles: {e}")
        raise HTTPException(status_code=503, detail=str(e))
    except ApiError as e:
        logger.error(f"API error listing CFR titles: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.exception(f"Unexpected error listing CFR titles: {e}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


@router.get(
    "/title/{title_number}",
    response_model=CfrTitleResponse,
    summary="Get CFR title",
    description="Retrieve information about a specific CFR title"
)
async def get_cfr_title(
    title_number: int = Path(..., description="CFR title number (1-50)"),
    year: Optional[int] = Query(None, description="CFR year/edition"),
    api_router: ApiRouter = Depends()
):
    """Get a specific CFR title by number."""
    try:
        # Validate title number
        if title_number < 1 or title_number > 50:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid title number: {title_number}. Must be between 1 and 50."
            )
        
        # Get GovInfo client
        govinfo_client = api_router.get_client(ApiSource.GOVINFO)
        
        # Get CFR title information
        title_data = await govinfo_client.get_cfr_title(title_number=title_number, year=year)
        
        # Format response
        return CfrTitleResponse(
            title_number=title_data.get("number"),
            title_name=title_data.get("name"),
            chapters=title_data.get("chapters")
        )
    except SourceUnavailableError as e:
        logger.error(f"Source unavailable for CFR title {title_number}: {e}")
        raise HTTPException(status_code=503, detail=str(e))
    except ApiError as e:
        logger.error(f"API error getting CFR title {title_number}: {e}")
        if "Not Found" in str(e):
            raise HTTPException(status_code=404, detail=f"CFR title {title_number} not found")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.exception(f"Unexpected error getting CFR title {title_number}: {e}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


@router.get(
    "/search",
    response_model=CfrSearchResponse,
    summary="Search CFR",
    description="Search the Code of Federal Regulations by various criteria"
)
async def search_cfr(
    title: Optional[int] = Query(None, description="CFR title number"),
    part: Optional[int] = Query(None, description="CFR part number"),
    section: Optional[str] = Query(None, description="CFR section number"),
    year: Optional[int] = Query(None, description="CFR year/edition"),
    query: Optional[str] = Query(None, description="Search query text"),
    offset: int = Query(0, description="Result offset"),
    limit: int = Query(20, description="Result limit"),
    api_router: ApiRouter = Depends()
):
    """Search CFR documents."""
    try:
        # Get GovInfo client
        govinfo_client = api_router.get_client(ApiSource.GOVINFO)
        
        # Build search parameters
        search_params = {
            "collection": "CFR",
            "offset": offset,
            "limit": limit
        }
        
        # Add optional parameters
        if year:
            search_params["year"] = year
        
        # Build a more specific query if title, part, or section specified
        query_parts = []
        if query:
            query_parts.append(query)
        if title:
            query_parts.append(f"title:{title}")
        if part:
            query_parts.append(f"part:{part}")
        if section:
            query_parts.append(f"section:{section}")
        
        if query_parts:
            search_params["query"] = " AND ".join(query_parts)
        
        # Search for CFR documents
        search_results = await govinfo_client.search_packages(**search_params)
        
        # Format results
        results = []
        for doc in search_results.get("packages", []):
            # Parse CFR-specific fields from metadata
            title_number = None
            title_name = None
            part_number = None
            section_number = None
            year_value = None
            
            # Try to extract structured data from package ID and metadata
            package_id = doc.get("packageId", "")
            
            # CFR package IDs often have format like "CFR-2023-title40-vol1"
            if package_id.startswith("CFR-"):
                parts = package_id.split("-")
                if len(parts) > 2:
                    try:
                        year_value = int(parts[1])
                    except ValueError:
                        pass
                    
                    # Try to extract title from the ID
                    title_part = next((p for p in parts if p.startswith("title")), None)
                    if title_part:
                        try:
                            title_number = int(title_part[5:])  # Remove "title" prefix
                        except ValueError:
                            pass
            
            # Extract other metadata from additional fields
            metadata = doc.get("metadata", {})
            if not title_name:
                title_name = metadata.get("titleName")
            if not title_number and "titleNumber" in metadata:
                try:
                    title_number = int(metadata.get("titleNumber"))
                except (ValueError, TypeError):
                    pass
            if not part_number and "partNumber" in metadata:
                try:
                    part_number = int(metadata.get("partNumber"))
                except (ValueError, TypeError):
                    pass
            if not section_number:
                section_number = metadata.get("sectionNumber")
            if not year_value and "year" in metadata:
                try:
                    year_value = int(metadata.get("year"))
                except (ValueError, TypeError):
                    pass
            
            # Download URLs
            download_urls = doc.get("download", {})
            
            # Create response object
            results.append(CfrDocumentResponse(
                package_id=package_id,
                title_number=title_number or 0,
                title_name=title_name or doc.get("title", ""),
                part_number=part_number,
                section_number=section_number,
                heading=doc.get("heading") or metadata.get("heading"),
                year=year_value or 0,
                date_issued=doc.get("dateIssued"),
                pdf_url=download_urls.get("pdfLink"),
                xml_url=download_urls.get("xmlLink"),
                html_url=download_urls.get("htmlLink")
            ))
        
        return CfrSearchResponse(
            count=search_results.get("count", len(results)),
            offset=offset,
            limit=limit,
            results=results
        )
    except SourceUnavailableError as e:
        logger.error(f"Source unavailable for CFR search: {e}")
        raise HTTPException(status_code=503, detail=str(e))
    except ApiError as e:
        logger.error(f"API error searching CFR: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.exception(f"Unexpected error searching CFR: {e}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


@router.get(
    "/{package_id}/content",
    response_model=Dict[str, Any],
    summary="Get CFR document content",
    description="Retrieve the content of a specific CFR document"
)
async def get_cfr_content(
    package_id: str = Path(..., description="GovInfo package ID"),
    content_type: Optional[str] = Query("html", description="Content type (html, pdf, xml)"),
    api_router: ApiRouter = Depends()
):
    """Get CFR document content."""
    try:
        # Get GovInfo client
        govinfo_client = api_router.get_client(ApiSource.GOVINFO)
        
        # Validate that this is a CFR document
        if not package_id.startswith("CFR-"):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid CFR package ID: {package_id}. Must start with 'CFR-'."
            )
        
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
        logger.error(f"Source unavailable for CFR content {package_id}: {e}")
        raise HTTPException(status_code=503, detail=str(e))
    except ApiError as e:
        logger.error(f"API error getting CFR content {package_id}: {e}")
        if "Not Found" in str(e):
            raise HTTPException(status_code=404, detail=f"CFR document {package_id} not found")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.exception(f"Unexpected error getting CFR content {package_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")