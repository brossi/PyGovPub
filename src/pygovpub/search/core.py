"""
Core search functionality.

This module provides the core search functionality for PyGovPub.
"""

import logging
import time
from datetime import datetime
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Set, Union, TypeVar, Generic, ClassVar

from pydantic import BaseModel, Field, model_validator

logger = logging.getLogger("pygovpub.search.core")

# Type aliases for clarity
DocumentId = str
SourceId = str
FieldName = str
FieldValue = Union[str, int, float, bool, List[str], List[int], List[float], datetime, None]

T = TypeVar('T')


class SearchResultType(str, Enum):
    """Type of search result."""
    BILL = "bill"
    DOCUMENT = "document"
    MEMBER = "member"
    COMMITTEE = "committee"
    CFR = "cfr"
    COURT_OPINION = "court_opinion"
    OTHER = "other"


class SearchOperator(str, Enum):
    """Operators for search queries."""
    AND = "AND"
    OR = "OR"
    NOT = "NOT"
    EXACT = "EXACT"
    FUZZY = "FUZZY"
    PREFIX = "PREFIX"
    SUFFIX = "SUFFIX"
    WILDCARD = "WILDCARD"
    RANGE = "RANGE"


class QueryComponent(BaseModel):
    """Component of a search query."""
    operator: SearchOperator = SearchOperator.AND
    field: Optional[str] = None
    value: Union[str, List[str], Dict[str, Any], None] = None
    boost: float = 1.0
    sub_components: List["QueryComponent"] = Field(default_factory=list)

    class Config:
        """Configuration for the model."""
        arbitrary_types_allowed = True


class SearchQuery(BaseModel):
    """Search query model."""
    query_text: Optional[str] = None
    components: List[QueryComponent] = Field(default_factory=list)
    filters: Dict[str, Any] = Field(default_factory=dict)
    offset: int = 0
    limit: int = 20
    sort_by: Optional[str] = None
    sort_order: str = "desc"
    highlight: bool = True
    facets: List[str] = Field(default_factory=list)
    sources: List[str] = Field(default_factory=list)
    
    @model_validator(mode='after')
    def check_query_components(self) -> 'SearchQuery':
        """Ensure query has either text or components."""
        if not self.query_text and not self.components:
            raise ValueError("Either query_text or components must be provided")
        return self


class Highlight(BaseModel):
    """Highlighted text in search results."""
    field: str
    fragments: List[str] = Field(default_factory=list)


class Facet(BaseModel):
    """Facet information for search refinement."""
    field: str
    values: Dict[str, int] = Field(default_factory=dict)


class SearchResult(BaseModel):
    """Search result model."""
    result_id: str
    type: SearchResultType
    source: str
    score: float = 0.0
    title: str
    url: Optional[str] = None
    date: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    highlights: List[Highlight] = Field(default_factory=list)
    text_snippet: Optional[str] = None


class SearchResults(BaseModel, Generic[T]):
    """Container for search results."""
    total: int = 0
    offset: int = 0
    limit: int = 20
    query: SearchQuery
    results: List[T] = Field(default_factory=list)
    facets: Dict[str, Facet] = Field(default_factory=dict)
    execution_time_ms: Optional[int] = None
    source_counts: Dict[str, int] = Field(default_factory=dict)


class SearchProvider:
    """Base class for search providers."""
    
    provider_name: ClassVar[str] = "base"
    supported_types: ClassVar[List[SearchResultType]] = []
    
    async def search(self, query: SearchQuery) -> SearchResults:
        """Execute search query.
        
        Args:
            query: Search query
            
        Returns:
            Search results
        """
        raise NotImplementedError("Subclasses must implement search")
    
    async def initialize(self) -> None:
        """Initialize the search provider."""
        pass
    
    async def shutdown(self) -> None:
        """Shut down the search provider."""
        pass
    
    def can_handle(self, query: SearchQuery) -> bool:
        """Check if this provider can handle the query.
        
        Args:
            query: Search query
            
        Returns:
            True if this provider can handle the query
        """
        if not query.sources:
            return True
        return self.provider_name in query.sources


class SearchManager:
    """Manager for search operations across providers."""
    
    def __init__(self):
        """Initialize search manager."""
        self.providers: Dict[str, SearchProvider] = {}
        self.initialized = False
    
    def register_provider(self, provider: SearchProvider) -> None:
        """Register a search provider.
        
        Args:
            provider: Search provider to register
        """
        self.providers[provider.provider_name] = provider
        logger.info(f"Registered search provider: {provider.provider_name}")
    
    async def initialize(self) -> None:
        """Initialize all registered providers."""
        if self.initialized:
            return
        
        for name, provider in self.providers.items():
            try:
                await provider.initialize()
                logger.info(f"Initialized search provider: {name}")
            except Exception as e:
                logger.exception(f"Failed to initialize search provider {name}: {e}")
        
        self.initialized = True
    
    async def shutdown(self) -> None:
        """Shut down all registered providers."""
        for name, provider in self.providers.items():
            try:
                await provider.shutdown()
                logger.info(f"Shut down search provider: {name}")
            except Exception as e:
                logger.exception(f"Failed to shut down search provider {name}: {e}")
        
        self.initialized = False
    
    async def search(self, query: SearchQuery) -> SearchResults:
        """Execute search query across appropriate providers.
        
        Args:
            query: Search query
            
        Returns:
            Combined search results
        """
        start_time = time.time()
        
        if not self.initialized:
            await self.initialize()
        
        # Log the search query details
        components_summary = []
        for comp in query.components:
            if comp.field:
                components_summary.append(f"{comp.field}={comp.value}")
            elif comp.sub_components:
                sub_comps = [f"{sc.field}={sc.value}" for sc in comp.sub_components if sc.field]
                components_summary.append(f"({','.join(sub_comps)})")
            elif comp.value:
                components_summary.append(f"{comp.value}")
                
        logger.debug(f"Search query: text='{query.query_text}', components=[{', '.join(components_summary)}], offset={query.offset}, limit={query.limit}")
        
        # Determine which providers to use
        providers_to_use = []
        for name, provider in self.providers.items():
            if provider.can_handle(query):
                providers_to_use.append(provider)
                logger.debug(f"Using provider: {name}")
        
        if not providers_to_use:
            logger.warning(f"No providers available for query: {query}")
            return SearchResults(
                total=0,
                query=query,
                results=[],
                execution_time_ms=0
            )
        
        # Execute search on each provider and combine results
        all_results = []
        total_count = 0
        source_counts = {}
        provider_timings = {}
        
        for provider in providers_to_use:
            try:
                provider_start = time.time()
                provider_results = await provider.search(query)
                provider_end = time.time()
                provider_time_ms = int((provider_end - provider_start) * 1000)
                
                all_results.extend(provider_results.results)
                total_count += provider_results.total
                
                # Track source counts
                source_counts[provider.provider_name] = provider_results.total
                provider_timings[provider.provider_name] = provider_time_ms
                
                logger.debug(f"Provider {provider.provider_name} returned {provider_results.total} results in {provider_time_ms}ms")
                
                # Merge facets
                # For now, we'll take the union of facet fields
                # and the sum of facet counts
                # TODO: Improve facet merging logic
            except Exception as e:
                logger.exception(f"Error searching with provider {provider.provider_name}: {e}")
        
        # Sort results by score
        sorting_start = time.time()
        all_results.sort(key=lambda x: x.score, reverse=True)
        sorting_time_ms = int((time.time() - sorting_start) * 1000)
        
        # Apply offset and limit
        paginated_results = all_results[query.offset:query.offset + query.limit]
        
        # Calculate total execution time
        end_time = time.time()
        execution_time_ms = int((end_time - start_time) * 1000)
        
        # Log performance metrics
        logger.debug(f"Search completed in {execution_time_ms}ms (sorting: {sorting_time_ms}ms)")
        logger.debug(f"Provider timings: {provider_timings}")
        logger.debug(f"Total results: {total_count}, Source counts: {source_counts}")
        
        return SearchResults(
            total=total_count,
            offset=query.offset,
            limit=query.limit,
            query=query,
            results=paginated_results,
            source_counts=source_counts,
            execution_time_ms=execution_time_ms
        )