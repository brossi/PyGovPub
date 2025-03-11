"""
Documents API Router.

This module provides FastAPI routes for accessing government documents
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
logger = logging.getLogger("pygovpub.api.routers.documents")

# Create router
router = APIRouter(
    prefix="/documents",
    tags=["Documents"],
    responses={
        404: {"description": "Document not found"},
        429: {"description": "Rate limit exceeded"},
        503: {"description": "Source unavailable"}
    }
)


# Response models
class DocumentResponse(BaseModel):
    """Document response model."""
    
    package_id: str = Field(..., description="GovInfo package ID")
    title: str = Field(..., description="Document title")
    collection: str = Field(..., description="Document collection")
    date_issued: Optional[str] = Field(None, description="Date document was issued")
    last_modified: Optional[str] = Field(None, description="Date document was last modified")
    pdf_url: Optional[str] = Field(None, description="URL to PDF version")
    xml_url: Optional[str] = Field(None, description="URL to XML version")
    html_url: Optional[str] = Field(None, description="URL to HTML version")
    mods_url: Optional[str] = Field(None, description="URL to MODS metadata")
    details_url: Optional[str] = Field(None, description="URL to document details")
    
    class Config:
        schema_extra = {
            "example": {
                "package_id": "BILLS-117hr1234ih",
                "title": "Example Bill Title",
                "collection": "BILLS",
                "date_issued": "2023-01-15",
                "last_modified": "2023-01-15",
                "pdf_url": "https://www.govinfo.gov/content/pkg/BILLS-117hr1234ih/pdf/BILLS-117hr1234ih.pdf",
                "xml_url": "https://www.govinfo.gov/content/pkg/BILLS-117hr1234ih/xml/BILLS-117hr1234ih.xml",
                "html_url": "https://www.govinfo.gov/content/pkg/BILLS-117hr1234ih/html/BILLS-117hr1234ih.htm",
                "mods_url": "https://www.govinfo.gov/metadata/pkg/BILLS-117hr1234ih/mods.xml",
                "details_url": "https://www.govinfo.gov/app/details/BILLS-117hr1234ih"
            }
        }


class DocumentSearchResponse(BaseModel):
    """Document search response model."""
    
    count: int = Field(..., description="Total number of results")
    offset: int = Field(..., description="Result offset")
    limit: int = Field(..., description="Result limit")
    documents: List[DocumentResponse] = Field(..., description="List of documents")


class CollectionResponse(BaseModel):
    """Collection response model."""
    
    collection_code: str = Field(..., description="Collection code")
    collection_name: str = Field(..., description="Collection name")
    package_count: Optional[int] = Field(None, description="Number of packages in collection")
    description: Optional[str] = Field(None, description="Collection description")
    
    class Config:
        schema_extra = {
            "example": {
                "collection_code": "BILLS",
                "collection_name": "Congressional Bills",
                "package_count": 12345,
                "description": "Congressional bills and resolutions"
            }
        }


# Routes
@router.get(
    "/collections",
    response_model=List[CollectionResponse],
    summary="List collections",
    description="Retrieve a list of available collections"
)
async def list_collections(
    api_router: ApiRouter = Depends()
):
    """List available collections."""
    try:
        # Get GovInfo client
        govinfo_client = api_router.get_client(ApiSource.GOVINFO)
        
        # Get collections
        collections_data = await govinfo_client.list_collections()
        
        # Format response
        collections = []
        for collection in collections_data.get("collections", []):
            collections.append(CollectionResponse(
                collection_code=collection.get("collection_code", ""),
                collection_name=collection.get("collection_name", ""),
                package_count=collection.get("package_count"),
                description=collection.get("description")
            ))
        
        return collections
    except SourceUnavailableError as e:
        logger.error(f"Source unavailable for listing collections: {e}")
        raise HTTPException(status_code=503, detail=str(e))
    except ApiError as e:
        logger.error(f"API error listing collections: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.exception(f"Unexpected error listing collections: {e}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


@router.get(
    "/{package_id}",
    response_model=DocumentResponse,
    summary="Get document information",
    description="Retrieve detailed information about a specific document"
)
async def get_document(
    package_id: str = Path(..., description="GovInfo package ID"),
    api_router: ApiRouter = Depends()
):
    """Get document information by package ID."""
    try:
        # Get GovInfo client
        govinfo_client = api_router.get_client(ApiSource.GOVINFO)
        
        # Get package summary
        package_data = await govinfo_client.get_package_summary(package_id=package_id)
        
        # Format response
        download_urls = package_data.get("download", {})
        
        return DocumentResponse(
            package_id=package_id,
            title=package_data.get("title", ""),
            collection=package_data.get("collection", ""),
            date_issued=package_data.get("dateIssued"),
            last_modified=package_data.get("lastModified"),
            pdf_url=download_urls.get("pdfLink"),
            xml_url=download_urls.get("xmlLink"),
            html_url=download_urls.get("htmlLink"),
            mods_url=download_urls.get("modsLink"),
            details_url=package_data.get("detailsLink")
        )
    except SourceUnavailableError as e:
        logger.error(f"Source unavailable for document {package_id}: {e}")
        raise HTTPException(status_code=503, detail=str(e))
    except ApiError as e:
        logger.error(f"API error getting document {package_id}: {e}")
        if "Not Found" in str(e):
            raise HTTPException(status_code=404, detail=f"Document {package_id} not found")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.exception(f"Unexpected error getting document {package_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


@router.get(
    "/{package_id}/content",
    response_model=Dict[str, Any],
    summary="Get document content",
    description="Retrieve the content of a specific document"
)
async def get_document_content(
    package_id: str = Path(..., description="GovInfo package ID"),
    content_type: Optional[str] = Query("html", description="Content type (html, pdf, xml, mods)"),
    api_router: ApiRouter = Depends()
):
    """Get document content."""
    try:
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
        logger.error(f"Source unavailable for document content {package_id}: {e}")
        raise HTTPException(status_code=503, detail=str(e))
    except ApiError as e:
        logger.error(f"API error getting document content {package_id}: {e}")
        if "Not Found" in str(e):
            raise HTTPException(status_code=404, detail=f"Document {package_id} not found")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.exception(f"Unexpected error getting document content {package_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


@router.get(
    "/search",
    response_model=DocumentSearchResponse,
    summary="Search documents",
    description="Search for documents with optional filters"
)
async def search_documents(
    collection: Optional[str] = Query(None, description="Collection code (e.g., 'BILLS', 'FR')"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    query: Optional[str] = Query(None, description="Search query"),
    offset: int = Query(0, description="Result offset"),
    limit: int = Query(20, description="Result limit"),
    api_router: ApiRouter = Depends()
):
    """Search documents."""
    try:
        # Get GovInfo client
        govinfo_client = api_router.get_client(ApiSource.GOVINFO)
        
        # Prepare search parameters
        search_params = {
            "offset": offset,
            "limit": limit
        }
        
        if collection:
            search_params["collection"] = collection
        if start_date:
            search_params["start_date"] = start_date
        if end_date:
            search_params["end_date"] = end_date
        if query:
            search_params["query"] = query
        
        # Execute search
        search_results = await govinfo_client.search_packages(**search_params)
        
        # Format results
        documents = []
        for doc in search_results.get("packages", []):
            download_urls = doc.get("download", {})
            documents.append(DocumentResponse(
                package_id=doc.get("packageId", ""),
                title=doc.get("title", ""),
                collection=doc.get("collection", ""),
                date_issued=doc.get("dateIssued"),
                last_modified=doc.get("lastModified"),
                pdf_url=download_urls.get("pdfLink"),
                xml_url=download_urls.get("xmlLink"),
                html_url=download_urls.get("htmlLink"),
                mods_url=download_urls.get("modsLink"),
                details_url=doc.get("detailsLink")
            ))
        
        return DocumentSearchResponse(
            count=search_results.get("count", len(documents)),
            offset=offset,
            limit=limit,
            documents=documents
        )
    except SourceUnavailableError as e:
        logger.error(f"Source unavailable for document search: {e}")
        raise HTTPException(status_code=503, detail=str(e))
    except ApiError as e:
        logger.error(f"API error searching documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.exception(f"Unexpected error searching documents: {e}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")