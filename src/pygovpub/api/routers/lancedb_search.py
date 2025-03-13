"""
Vector search router demonstrating router-specific connection pooling.

This module provides an example of how to implement router-specific connection pools 
for the LanceDB provider, which is useful for high-traffic search endpoints that 
require dedicated connection resources.
"""

import logging
from typing import List, Optional, Dict, Any, Union
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Path
from pydantic import BaseModel, Field

from pygovpub.storage.providers.lancedb_provider import LanceDBProvider, get_connection_pool
from pygovpub.api.router import ApiRouter, get_router
from pygovpub.auth.models import ApiSource
from pygovpub.exceptions import RouterError, ApiError
from pygovpub.models.documents import DocumentType


# Configure logging
logger = logging.getLogger("pygovpub.api.routers.lancedb_search")

# Initialize router-specific connection pool at module load time
SEARCH_POOL = None
try:
    # Initialize a dedicated connection pool for vector search operations with larger capacity
    SEARCH_POOL = get_connection_pool(
        uri=None,  # Will use default path
        pool_id="vector_search_router",
        max_size=15,  # Higher capacity for search operations 
        min_size=5,   # Higher min_size to avoid connection creation overhead
        idle_timeout=600.0  # 10 minute idle timeout for search connections
    )
except Exception as e:
    logger.warning(f"Failed to initialize vector search connection pool: {str(e)}")

# Create router
router = APIRouter(
    prefix="/vector-search",
    tags=["Search"],
    responses={
        404: {"description": "No results found"},
        429: {"description": "Rate limit exceeded"},
        503: {"description": "Source unavailable"}
    }
)


# Create a search-optimized provider factory
def get_vector_search_provider():
    """
    Factory function to create a LanceDB provider with optimized connection pooling
    specifically for vector search operations.
    """
    try:
        return LanceDBProvider(
            uri=None,  # Will use default path
            use_connection_pool=True,
            pool_id="vector_search_router",  # Reuse the pool created above
            vector_dim=384
        )
    except Exception as e:
        logger.error(f"Failed to create vector search provider: {str(e)}")
        return None


# Model definitions
class VectorSearchResult(BaseModel):
    """Vector search result model."""
    
    id: str = Field(..., description="Document identifier")
    title: str = Field(..., description="Document title")
    content: Optional[str] = Field(None, description="Document content snippet")
    score: float = Field(..., description="Vector similarity score (0-1)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Document metadata")


class VectorSearchResponse(BaseModel):
    """Vector search response model."""
    
    results: List[VectorSearchResult] = Field(..., description="Search results")
    count: int = Field(..., description="Total number of results")
    query_vector_dim: int = Field(..., description="Dimension of query vector")
    pool_stats: Optional[Dict[str, Any]] = Field(None, description="Connection pool statistics")


# Routes
@router.post(
    "/",
    response_model=VectorSearchResponse,
    summary="Vector similarity search",
    description="Search documents by vector similarity"
)
async def vector_search(
    query_vector: List[float] = Field(..., description="Query vector for similarity search"),
    document_type: Optional[str] = Query(None, description="Filter by document type"),
    filter_text: Optional[str] = Query(None, description="Text filter to apply"),
    include_pool_stats: bool = Query(False, description="Include connection pool statistics"),
    limit: int = Query(10, description="Maximum number of results to return"),
    api_router: ApiRouter = Depends(get_router)
):
    """
    Search documents by vector similarity.
    
    This endpoint demonstrates router-specific connection pooling for improved performance
    under high load scenarios.
    """
    try:
        # Get the search provider with optimized connection pooling
        provider = get_vector_search_provider()
        if not provider:
            raise HTTPException(status_code=503, detail="Vector search provider unavailable")
        
        # Verify vector dimensions
        if len(query_vector) != provider.vector_dim:
            raise HTTPException(
                status_code=400, 
                detail=f"Query vector must have {provider.vector_dim} dimensions"
            )
        
        # Build filter criteria
        filter_criteria = {}
        if document_type:
            filter_criteria["document_type"] = document_type
        if filter_text:
            filter_criteria["__text_filter"] = filter_text
        
        # Perform vector search using the connection pool
        from pygovpub.models.documents import Document
        
        results = provider.vector_search(
            model_class=Document,
            query_vector=query_vector,
            limit=limit,
            filter_criteria=filter_criteria,
            analyze_query=True
        )
        
        # Convert to response model
        search_results = []
        for result in results:
            try:
                search_results.append(VectorSearchResult(
                    id=result.get("id", ""),
                    title=result.get("title", "Untitled"),
                    content=result.get("content", "")[:200] if result.get("content") else None,
                    score=result.get("score", 0.0),
                    metadata=result.get("metadata", {})
                ))
            except Exception as e:
                logger.warning(f"Failed to process search result: {e}")
                continue
        
        # Get pool stats if requested
        pool_stats = None
        if include_pool_stats and SEARCH_POOL:
            pool_stats = SEARCH_POOL.get_stats()
        
        return VectorSearchResponse(
            results=search_results,
            count=len(search_results),
            query_vector_dim=len(query_vector),
            pool_stats=pool_stats
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.exception(f"Error in vector search: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Vector search error: {str(e)}")


@router.get(
    "/pool-stats",
    response_model=Dict[str, Any],
    summary="Connection pool statistics",
    description="Get statistics about the vector search connection pool"
)
async def connection_pool_stats():
    """
    Get statistics about the vector search connection pool.
    
    Returns information about the current state of the connection pool
    used for vector search operations, including the number of available 
    and in-use connections.
    """
    if not SEARCH_POOL:
        raise HTTPException(status_code=503, detail="Vector search connection pool not initialized")
    
    try:
        return SEARCH_POOL.get_stats()
    except Exception as e:
        logger.exception(f"Error getting pool stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting pool stats: {str(e)}")


@router.post(
    "/cleanup-pool",
    response_model=Dict[str, Any],
    summary="Clean up idle connections",
    description="Clean up idle connections in the vector search pool"
)
async def cleanup_idle_connections():
    """
    Clean up idle connections in the vector search pool.
    
    This endpoint can be called periodically to clean up idle connections
    that have exceeded their idle timeout.
    """
    if not SEARCH_POOL:
        raise HTTPException(status_code=503, detail="Vector search connection pool not initialized")
    
    try:
        cleaned_up = SEARCH_POOL.cleanup_idle_connections()
        return {
            "cleaned_up": cleaned_up,
            "pool_stats": SEARCH_POOL.get_stats()
        }
    except Exception as e:
        logger.exception(f"Error cleaning up idle connections: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error cleaning up idle connections: {str(e)}")