"""
Search API Router.

This module provides FastAPI routes for searching across government data sources
with advanced metadata filtering capabilities.
"""

import logging
from typing import List, Optional, Dict, Any, Union
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Path
from pydantic import BaseModel, Field

from pygovpub.api.router import ApiRouter
from pygovpub.auth.models import ApiSource
from pygovpub.models.documents import DocumentType
from pygovpub.exceptions import RouterError, ApiError, RouteNotFoundError, SourceUnavailableError

# Utility functions moved to module scope to avoid self reference issues

# Configure logging
logger = logging.getLogger("pygovpub.api.routers.search")

# Create router
router = APIRouter(
    prefix="/search",
    tags=["Search"],
    responses={
        404: {"description": "No results found"},
        429: {"description": "Rate limit exceeded"},
        503: {"description": "Source unavailable"}
    }
)


# Response models
class MetadataField(BaseModel):
    """Metadata field model for search results."""
    
    name: str = Field(..., description="Field name")
    value: Optional[Union[str, int, bool, List[str], Dict[str, Any]]] = Field(None, description="Field value")
    display_name: Optional[str] = Field(None, description="Human-readable field name")
    field_type: Optional[str] = Field(None, description="Field data type")
    
    class Config:
        schema_extra = {
            "example": {
                "name": "dateIssued",
                "value": "2023-01-15",
                "display_name": "Date Issued",
                "field_type": "date"
            }
        }


class SearchResult(BaseModel):
    """Generic search result model."""
    
    source: str = Field(..., description="Source API (govinfo, congress)")
    document_type: str = Field(..., description="Document type")
    document_id: str = Field(..., description="Document identifier")
    title: str = Field(..., description="Document title")
    date_issued: Optional[str] = Field(None, description="Date document was issued")
    relevance_score: Optional[float] = Field(None, description="Search relevance score")
    url: Optional[str] = Field(None, description="URL to document")
    metadata: List[MetadataField] = Field(default_factory=list, description="Additional metadata fields")
    highlights: Optional[Dict[str, List[str]]] = Field(None, description="Highlighted search terms in context")
    
    class Config:
        schema_extra = {
            "example": {
                "source": "govinfo",
                "document_type": "BILL",
                "document_id": "BILLS-117hr1234ih",
                "title": "Example Bill Title",
                "date_issued": "2023-01-15",
                "relevance_score": 0.95,
                "url": "https://www.govinfo.gov/app/details/BILLS-117hr1234ih",
                "metadata": [
                    {
                        "name": "congress",
                        "value": "117",
                        "display_name": "Congress",
                        "field_type": "integer"
                    },
                    {
                        "name": "billType",
                        "value": "hr",
                        "display_name": "Bill Type",
                        "field_type": "string"
                    }
                ],
                "highlights": {
                    "title": ["Example <em>Bill</em> Title"],
                    "text": ["This <em>bill</em> provides for...", "The <em>bill</em> includes provisions for..."]
                }
            }
        }


class MetadataSearchResponse(BaseModel):
    """Metadata search response model."""
    
    count: int = Field(..., description="Total number of results")
    offset: int = Field(..., description="Result offset")
    limit: int = Field(..., description="Result limit")
    results: List[SearchResult] = Field(..., description="Search results")
    facets: Optional[Dict[str, Dict[str, int]]] = Field(None, description="Search facets for filtering")
    
    class Config:
        schema_extra = {
            "example": {
                "count": 125,
                "offset": 0,
                "limit": 20,
                "results": [
                    {
                        "source": "govinfo",
                        "document_type": "BILL",
                        "document_id": "BILLS-117hr1234ih",
                        "title": "Example Bill Title",
                        "date_issued": "2023-01-15",
                        "relevance_score": 0.95,
                        "url": "https://www.govinfo.gov/app/details/BILLS-117hr1234ih",
                        "metadata": [
                            {
                                "name": "congress",
                                "value": "117",
                                "display_name": "Congress",
                                "field_type": "integer"
                            }
                        ]
                    }
                ],
                "facets": {
                    "document_type": {
                        "BILL": 75,
                        "FR": 30,
                        "CFR": 20
                    },
                    "source": {
                        "govinfo": 95,
                        "congress": 30
                    }
                }
            }
        }


class CombinedSearchResponse(BaseModel):
    """Combined search response model for cross-source search."""
    
    count: int = Field(..., description="Total number of results")
    offset: int = Field(..., description="Result offset")
    limit: int = Field(..., description="Result limit")
    results: List[SearchResult] = Field(..., description="Search results")
    facets: Optional[Dict[str, Dict[str, int]]] = Field(None, description="Search facets for filtering")
    source_counts: Dict[str, int] = Field(..., description="Result counts by source")


# Routes
@router.get(
    "/metadata",
    response_model=MetadataSearchResponse,
    summary="Search by metadata",
    description="Search for documents using metadata fields and filters"
)
async def search_by_metadata(
    document_type: Optional[str] = Query(None, description="Document type (e.g., BILL, FR, CFR)"),
    source: Optional[str] = Query(None, description="Source API (govinfo, congress)"),
    start_date: Optional[str] = Query(None, description="Start date for filtering (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date for filtering (YYYY-MM-DD)"),
    congress: Optional[int] = Query(None, description="Congress number (e.g., 117)"),
    bill_type: Optional[str] = Query(None, description="Bill type (e.g., hr, s)"),
    cfr_title: Optional[int] = Query(None, description="CFR title number"),
    court: Optional[str] = Query(None, description="Court identifier (e.g., SCOTUS, CA9)"),
    metadata_fields: Optional[List[str]] = Query(None, description="Metadata fields to return"),
    include_facets: bool = Query(False, description="Include facets in the response"),
    offset: int = Query(0, description="Result offset"),
    limit: int = Query(20, description="Result limit"),
    api_router: ApiRouter = Depends()
):
    """Search documents by metadata fields."""
    try:
        # Get appropriate clients based on source parameter
        clients = {}
        if source == "govinfo" or source is None:
            clients["govinfo"] = api_router.get_client(ApiSource.GOVINFO)
        if source == "congress" or source is None:
            clients["congress"] = api_router.get_client(ApiSource.CONGRESS)
        
        # Build search parameters
        search_params = {
            "offset": offset,
            "limit": limit
        }
        
        # Add metadata filters
        if document_type:
            search_params["document_type"] = document_type
        if start_date:
            search_params["start_date"] = start_date
        if end_date:
            search_params["end_date"] = end_date
        if congress:
            search_params["congress"] = congress
        if bill_type:
            search_params["bill_type"] = bill_type
        if cfr_title:
            search_params["cfr_title"] = cfr_title
        if court:
            search_params["court"] = court
        
        # Create an empty response structure
        results = []
        facets = {} if include_facets else None
        total_count = 0
        
        # Process search for each client
        for source_name, client in clients.items():
            try:
                # Build source-specific search query
                source_params = search_params.copy()
                source_params["source"] = source_name
                
                # Execute search
                if source_name == "govinfo":
                    # For GovInfo, we need to build a more complex metadata query
                    metadata_query = []
                    if document_type:
                        if document_type == "BILL":
                            metadata_query.append("collectionCode:BILLS")
                        elif document_type == "FR":
                            metadata_query.append("collectionCode:FR")
                        elif document_type == "CFR":
                            metadata_query.append("collectionCode:CFR")
                            if cfr_title:
                                metadata_query.append(f"title:{cfr_title}")
                    
                    # Add date range to query
                    if start_date and end_date:
                        metadata_query.append(f"dateIssued:[{start_date} TO {end_date}]")
                    
                    # For bills, add congress and type if specified
                    if document_type == "BILL" and congress:
                        metadata_query.append(f"congress:{congress}")
                    if document_type == "BILL" and bill_type:
                        metadata_query.append(f"billType:{bill_type}")
                    
                    # For court opinions, add court if specified
                    if document_type == "COURT_OPINION" and court:
                        metadata_query.append(f"court:{court}")
                    
                    # Convert to query string
                    if metadata_query:
                        source_params["query"] = " AND ".join(metadata_query)
                    
                    # Execute search on GovInfo
                    search_results = await client.search_packages(**source_params)
                    
                    # Process results
                    for doc in search_results.get("packages", []):
                        # Create metadata fields list
                        metadata_fields_list = []
                        
                        # Extract metadata fields
                        for key, value in doc.get("metadata", {}).items():
                            metadata_fields_list.append(MetadataField(
                                name=key,
                                value=value,
                                display_name=key.replace("_", " ").title()
                            ))
                        
                        # Add to results
                        results.append(SearchResult(
                            source=source_name,
                            document_type=_determine_document_type(doc.get("packageId", "")),
                            document_id=doc.get("packageId", ""),
                            title=doc.get("title", ""),
                            date_issued=doc.get("dateIssued"),
                            url=doc.get("detailsLink"),
                            metadata=metadata_fields_list
                        ))
                    
                    # Update count
                    total_count += search_results.get("count", 0)
                    
                    # Add facets if requested
                    if include_facets and "facets" in search_results:
                        # Merge with existing facets
                        for facet_name, facet_values in search_results.get("facets", {}).items():
                            if facet_name not in facets:
                                facets[facet_name] = {}
                            
                            for value, count in facet_values.items():
                                if value in facets[facet_name]:
                                    facets[facet_name][value] += count
                                else:
                                    facets[facet_name][value] = count
                
                elif source_name == "congress":
                    # For Congress API, use different endpoint based on document type
                    if document_type == "BILL":
                        # Search bills
                        bill_params = {
                            "offset": offset,
                            "limit": limit
                        }
                        
                        if congress:
                            bill_params["congress"] = congress
                        if bill_type:
                            bill_params["bill_type"] = bill_type
                        
                        # Execute search
                        search_results = await client.search_bills(**bill_params)
                        
                        # Process results
                        for bill in search_results.get("bills", []):
                            # Create metadata fields list
                            metadata_fields_list = []
                            
                            # Add key metadata fields
                            if "congress" in bill:
                                metadata_fields_list.append(MetadataField(
                                    name="congress",
                                    value=bill.get("congress"),
                                    display_name="Congress",
                                    field_type="integer"
                                ))
                            
                            if "type" in bill:
                                metadata_fields_list.append(MetadataField(
                                    name="billType",
                                    value=bill.get("type"),
                                    display_name="Bill Type",
                                    field_type="string"
                                ))
                            
                            if "number" in bill:
                                metadata_fields_list.append(MetadataField(
                                    name="billNumber",
                                    value=bill.get("number"),
                                    display_name="Bill Number",
                                    field_type="integer"
                                ))
                            
                            # Add bill sponsor if available
                            if "sponsor" in bill:
                                sponsor_info = bill.get("sponsor", {})
                                metadata_fields_list.append(MetadataField(
                                    name="sponsor",
                                    value=sponsor_info.get("name", ""),
                                    display_name="Sponsor",
                                    field_type="string"
                                ))
                            
                            # Add to results
                            results.append(SearchResult(
                                source=source_name,
                                document_type="BILL",
                                document_id=bill.get("congress_gov_url", "").split("/")[-1],
                                title=bill.get("title", ""),
                                date_issued=bill.get("introduced_date"),
                                url=bill.get("congress_gov_url"),
                                metadata=metadata_fields_list
                            ))
                        
                        # Update count
                        total_count += search_results.get("count", 0)
                    
                    elif document_type == "MEMBER":
                        # Search members
                        member_params = {
                            "offset": offset,
                            "limit": limit
                        }
                        
                        if congress:
                            member_params["congress"] = congress
                        
                        # Execute search
                        search_results = await client.search_members(**member_params)
                        
                        # Process results
                        for member in search_results.get("members", []):
                            # Create metadata fields list
                            metadata_fields_list = []
                            
                            # Add key metadata fields
                            if "chamber" in member:
                                metadata_fields_list.append(MetadataField(
                                    name="chamber",
                                    value=member.get("chamber"),
                                    display_name="Chamber",
                                    field_type="string"
                                ))
                            
                            if "state" in member:
                                metadata_fields_list.append(MetadataField(
                                    name="state",
                                    value=member.get("state"),
                                    display_name="State",
                                    field_type="string"
                                ))
                            
                            if "party" in member:
                                metadata_fields_list.append(MetadataField(
                                    name="party",
                                    value=member.get("party"),
                                    display_name="Party",
                                    field_type="string"
                                ))
                            
                            # Add to results
                            results.append(SearchResult(
                                source=source_name,
                                document_type="MEMBER",
                                document_id=member.get("id", ""),
                                title=member.get("name", ""),
                                url=member.get("url"),
                                metadata=metadata_fields_list
                            ))
                        
                        # Update count
                        total_count += search_results.get("count", 0)
            
            except ApiError as e:
                logger.warning(f"API error during metadata search for source {source_name}: {e}")
                # Continue with other sources
        
        # If no results found, return empty response
        if not results:
            return MetadataSearchResponse(
                count=0,
                offset=offset,
                limit=limit,
                results=[],
                facets=facets
            )
        
        # Sort results by date if available
        results.sort(
            key=lambda x: x.date_issued if x.date_issued else "0000-00-00",
            reverse=True
        )
        
        # Return response
        return MetadataSearchResponse(
            count=total_count,
            offset=offset,
            limit=limit,
            results=results,
            facets=facets
        )
    except SourceUnavailableError as e:
        logger.error(f"Source unavailable for metadata search: {e}")
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception(f"Unexpected error in metadata search: {e}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


@router.get(
    "/combined",
    response_model=CombinedSearchResponse,
    summary="Combined search",
    description="Search across all data sources with both full-text and metadata filtering"
)
async def combined_search(
    query: str = Query(..., description="Search query text"),
    document_type: Optional[str] = Query(None, description="Document type (e.g., BILL, FR, CFR)"),
    source: Optional[str] = Query(None, description="Source API (govinfo, congress)"),
    start_date: Optional[str] = Query(None, description="Start date for filtering (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date for filtering (YYYY-MM-DD)"),
    include_highlights: bool = Query(True, description="Include search term highlights"),
    include_facets: bool = Query(False, description="Include facets in the response"),
    offset: int = Query(0, description="Result offset"),
    limit: int = Query(20, description="Result limit"),
    api_router: ApiRouter = Depends()
):
    """Search across all data sources with both text and metadata filtering."""
    try:
        # Get appropriate clients based on source parameter
        clients = {}
        if source == "govinfo" or source is None:
            clients["govinfo"] = api_router.get_client(ApiSource.GOVINFO)
        if source == "congress" or source is None:
            clients["congress"] = api_router.get_client(ApiSource.CONGRESS)
        
        # Build search parameters
        search_params = {
            "query": query,
            "offset": offset,
            "limit": limit
        }
        
        # Add metadata filters
        if document_type:
            search_params["document_type"] = document_type
        if start_date:
            search_params["start_date"] = start_date
        if end_date:
            search_params["end_date"] = end_date
        
        # Create an empty response structure
        results = []
        facets = {} if include_facets else None
        total_count = 0
        source_counts = {"govinfo": 0, "congress": 0}
        
        # Process search for each client
        for source_name, client in clients.items():
            try:
                # Build source-specific search query
                source_params = search_params.copy()
                
                # Execute search
                if source_name == "govinfo":
                    # Execute search on GovInfo
                    search_results = await client.search_packages(**source_params)
                    
                    # Process results
                    for doc in search_results.get("packages", []):
                        # Create metadata fields list
                        metadata_fields_list = []
                        
                        # Extract metadata fields
                        for key, value in doc.get("metadata", {}).items():
                            metadata_fields_list.append(MetadataField(
                                name=key,
                                value=value,
                                display_name=key.replace("_", " ").title()
                            ))
                        
                        # Extract highlights if available and requested
                        highlights = None
                        if include_highlights and "highlights" in doc:
                            highlights = doc.get("highlights", {})
                        
                        # Add to results
                        results.append(SearchResult(
                            source=source_name,
                            document_type=_determine_document_type(doc.get("packageId", "")),
                            document_id=doc.get("packageId", ""),
                            title=doc.get("title", ""),
                            date_issued=doc.get("dateIssued"),
                            relevance_score=doc.get("score"),
                            url=doc.get("detailsLink"),
                            metadata=metadata_fields_list,
                            highlights=highlights
                        ))
                    
                    # Update counts
                    count = search_results.get("count", 0)
                    total_count += count
                    source_counts["govinfo"] = count
                    
                    # Add facets if requested
                    if include_facets and "facets" in search_results:
                        # Merge with existing facets
                        for facet_name, facet_values in search_results.get("facets", {}).items():
                            if facet_name not in facets:
                                facets[facet_name] = {}
                            
                            for value, count in facet_values.items():
                                if value in facets[facet_name]:
                                    facets[facet_name][value] += count
                                else:
                                    facets[facet_name][value] = count
                
                elif source_name == "congress":
                    # For Congress API, use combined search endpoint
                    search_results = await client.search(**source_params)
                    
                    # Process results
                    for item in search_results.get("results", []):
                        item_type = item.get("type", "").upper()
                        
                        # Skip if document_type filter doesn't match
                        if document_type and item_type != document_type:
                            continue
                        
                        # Create metadata fields list
                        metadata_fields_list = []
                        
                        # Process based on item type
                        if item_type == "BILL":
                            # Extract bill metadata
                            if "congress" in item:
                                metadata_fields_list.append(MetadataField(
                                    name="congress",
                                    value=item.get("congress"),
                                    display_name="Congress",
                                    field_type="integer"
                                ))
                            
                            if "bill_type" in item:
                                metadata_fields_list.append(MetadataField(
                                    name="billType",
                                    value=item.get("bill_type"),
                                    display_name="Bill Type",
                                    field_type="string"
                                ))
                            
                            if "bill_number" in item:
                                metadata_fields_list.append(MetadataField(
                                    name="billNumber",
                                    value=item.get("bill_number"),
                                    display_name="Bill Number",
                                    field_type="integer"
                                ))
                        
                        elif item_type == "MEMBER":
                            # Extract member metadata
                            if "chamber" in item:
                                metadata_fields_list.append(MetadataField(
                                    name="chamber",
                                    value=item.get("chamber"),
                                    display_name="Chamber",
                                    field_type="string"
                                ))
                            
                            if "state" in item:
                                metadata_fields_list.append(MetadataField(
                                    name="state",
                                    value=item.get("state"),
                                    display_name="State",
                                    field_type="string"
                                ))
                            
                            if "party" in item:
                                metadata_fields_list.append(MetadataField(
                                    name="party",
                                    value=item.get("party"),
                                    display_name="Party",
                                    field_type="string"
                                ))
                        
                        # Extract highlights if available and requested
                        highlights = None
                        if include_highlights and "highlights" in item:
                            highlights = item.get("highlights", {})
                        
                        # Add to results
                        results.append(SearchResult(
                            source=source_name,
                            document_type=item_type,
                            document_id=item.get("id", ""),
                            title=item.get("title", ""),
                            date_issued=item.get("date"),
                            relevance_score=item.get("score"),
                            url=item.get("url"),
                            metadata=metadata_fields_list,
                            highlights=highlights
                        ))
                    
                    # Update counts
                    count = search_results.get("count", 0)
                    total_count += count
                    source_counts["congress"] = count
            
            except ApiError as e:
                logger.warning(f"API error during combined search for source {source_name}: {e}")
                # Continue with other sources
        
        # Sort results by relevance score if available, otherwise by date
        results.sort(
            key=lambda x: (x.relevance_score or 0, x.date_issued if x.date_issued else "0000-00-00"),
            reverse=True
        )
        
        # If no results found, return empty response
        if not results:
            return CombinedSearchResponse(
                count=0,
                offset=offset,
                limit=limit,
                results=[],
                facets=facets,
                source_counts=source_counts
            )
        
        # Return response
        return CombinedSearchResponse(
            count=total_count,
            offset=offset,
            limit=limit,
            results=results,
            facets=facets,
            source_counts=source_counts
        )
    except SourceUnavailableError as e:
        logger.error(f"Source unavailable for combined search: {e}")
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception(f"Unexpected error in combined search: {e}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


# Utility methods
def _determine_document_type(package_id: str) -> str:
    """Determine document type from package ID.
    
    Args:
        package_id: Package ID
        
    Returns:
        Document type string
    """
    if package_id.startswith("BILLS-"):
        return "BILL"
    if package_id.startswith("FR-"):
        return "FEDERAL_REGISTER"
    if package_id.startswith("CREC-"):
        return "CONGRESSIONAL_RECORD"
    if package_id.startswith("CFR-"):
        return "CODE_OF_FEDERAL_REGULATIONS"
    if package_id.startswith("STATUTE-"):
        return "STATUTE"
    if package_id.startswith("PLAW-"):
        return "PUBLIC_LAW"
    if package_id.startswith("CHRG-"):
        return "CONGRESSIONAL_HEARING"
    if package_id.startswith("CPRT-"):
        return "CONGRESSIONAL_REPORT"
    if package_id.startswith("CDOC-"):
        return "CONGRESSIONAL_DOCUMENT"
    if package_id.startswith("USCOURTS-"):
        return "COURT_OPINION"
    return "OTHER"