"""
Search providers for different data sources.

This module provides search providers for different data sources.
"""

import logging
import time
from typing import Any, Dict, List, Optional, Set, Union

from pygovpub.api.base import BaseApiClient
from pygovpub.api.clients.congress import CongressClient
from pygovpub.api.clients.govinfo import GovInfoClient
from pygovpub.auth.models import ApiSource
from pygovpub.exceptions import ApiError
from pygovpub.search.core import (
    SearchProvider, 
    SearchQuery, 
    SearchResults, 
    SearchResult,
    SearchResultType,
    Highlight,
    Facet
)
from pygovpub.search.indexing import DocumentIndexer

logger = logging.getLogger("pygovpub.search.providers")


class LocalProvider(SearchProvider):
    """Local in-memory search provider for development and testing."""
    
    provider_name = "local"
    supported_types = [t for t in SearchResultType]
    
    def __init__(self) -> None:
        """Initialize the local search provider."""
        self.indexer = DocumentIndexer()
    
    async def initialize(self) -> None:
        """Initialize the search provider."""
        await self.indexer.clear_index()
        
        # Add some sample documents
        sample_docs = [
            {
                "id": "bill-117hr1",
                "type": "bill",
                "source": "congress",
                "title": "H.R. 1 - For the People Act of 2021",
                "content": "This bill addresses voter access, election integrity, campaign finance, and ethics.",
                "url": "https://www.congress.gov/bill/117th-congress/house-bill/1",
                "congress": 117,
                "bill_type": "hr",
                "bill_number": 1,
                "introduced_date": "2021-01-04"
            },
            {
                "id": "bill-117s1",
                "type": "bill",
                "source": "congress",
                "title": "S. 1 - For the People Act of 2021",
                "content": "Senate version of the bill to expand voting rights and reduce money influence in politics.",
                "url": "https://www.congress.gov/bill/117th-congress/senate-bill/1",
                "congress": 117,
                "bill_type": "s",
                "bill_number": 1,
                "introduced_date": "2021-01-04"
            },
            {
                "id": "doc-fr-2021-12345",
                "type": "document",
                "source": "govinfo",
                "title": "Federal Register Notice on Environment",
                "content": "Environmental Protection Agency announces new regulations on carbon emissions.",
                "url": "https://www.federalregister.gov/documents/2021/01/01/2020-12345/clean-air-act",
                "agency": "EPA",
                "document_type": "notice",
                "publication_date": "2021-01-01"
            }
        ]
        
        await self.indexer.index_documents(sample_docs)
        logger.info(f"Indexed {len(sample_docs)} sample documents")
    
    async def add_document(self, id: str, title: str, content: str, metadata: dict, type: SearchResultType) -> str:
        """Add a document to the index.
        
        Args:
            id: Document ID
            title: Document title
            content: Document content
            metadata: Document metadata
            type: Document type
            
        Returns:
            Document ID
        """
        # Create a document dictionary
        doc = {
            "id": id,
            "type": type.value,
            "source": "local",
            "title": title,
            "content": content,
            "url": metadata.get("url"),
            **metadata
        }
        
        # Index the document
        await self.indexer.index_document(doc)
        return id
    
    async def search(self, query: SearchQuery) -> SearchResults:
        """Execute search query.
        
        Args:
            query: Search query
            
        Returns:
            Search results
        """
        start_time = time.time()
        
        matching_docs: Set[str] = set()
        first_component = True
        
        # Process query components
        for component in query.components:
            if component.field:
                # Field search
                if component.value is not None:
                    doc_ids = await self.indexer.search_field(component.field, component.value)
                    
                    if first_component:
                        matching_docs = doc_ids
                        first_component = False
                    elif component.operator.value == "AND":
                        matching_docs &= doc_ids
                    elif component.operator.value == "OR":
                        matching_docs |= doc_ids
                    elif component.operator.value == "NOT":
                        matching_docs -= doc_ids
            else:
                # Text search
                if component.value:
                    doc_ids = await self.indexer.search_text(str(component.value))
                    
                    if first_component:
                        matching_docs = doc_ids
                        first_component = False
                    elif component.operator.value == "AND":
                        matching_docs &= doc_ids
                    elif component.operator.value == "OR":
                        matching_docs |= doc_ids
                    elif component.operator.value == "NOT":
                        matching_docs -= doc_ids
        
        # If no components were processed, use raw query text
        if first_component and query.query_text:
            matching_docs = await self.indexer.search_text(query.query_text)
        
        # Convert matching docs to results
        results = []
        for doc_id in matching_docs:
            entry = await self.indexer.get_document(doc_id)
            if entry:
                # Create highlights for query terms
                highlights = []
                if query.highlight and query.query_text and entry.text_content:
                    # Simple highlight implementation
                    terms = query.query_text.lower().split()
                    content = entry.text_content.lower()
                    
                    # Find positions of terms
                    fragments = []
                    for term in terms:
                        pos = content.find(term)
                        if pos >= 0:
                            # Extract surrounding context
                            start = max(0, pos - 30)
                            end = min(len(content), pos + len(term) + 30)
                            
                            # Find word boundaries
                            while start > 0 and content[start].isalnum():
                                start -= 1
                                
                            while end < len(content) - 1 and content[end].isalnum():
                                end += 1
                            
                            # Extract fragment
                            fragment = entry.text_content[start:end].strip()
                            
                            # Add highlighting (in real implementation, would use HTML tags)
                            term_pos = fragment.lower().find(term)
                            if term_pos >= 0:
                                highlighted = (
                                    fragment[:term_pos] + 
                                    "<em>" + fragment[term_pos:term_pos+len(term)] + "</em>" + 
                                    fragment[term_pos+len(term):]
                                )
                                fragments.append(highlighted)
                    
                    if fragments:
                        highlights.append(Highlight(field="content", fragments=fragments))
                
                # Create result
                result = SearchResult(
                    result_id=entry.document_id,
                    type=entry.type,
                    source=entry.source,
                    title=entry.title,
                    url=entry.url,
                    date=entry.fields.get("introduced_date") or entry.fields.get("publication_date"),
                    metadata=entry.fields,
                    highlights=highlights,
                    text_snippet=entry.text_content[:100] + "..." if entry.text_content else None
                )
                results.append(result)
        
        # Build facets
        facets = {}
        if query.facets:
            for facet_field in query.facets:
                field_values = {}
                
                # Count occurrences of each value
                for doc_id in matching_docs:
                    entry = await self.indexer.get_document(doc_id)
                    if entry and facet_field in entry.fields:
                        value = entry.fields[facet_field]
                        if value is not None:
                            if isinstance(value, (list, set)):
                                for v in value:
                                    field_values[str(v)] = field_values.get(str(v), 0) + 1
                            else:
                                field_values[str(value)] = field_values.get(str(value), 0) + 1
                
                if field_values:
                    facets[facet_field] = Facet(field=facet_field, values=field_values)
        
        # Sort results
        if query.sort_by:
            def get_sort_key(result):
                if query.sort_by == "date":
                    return result.date or datetime.min
                elif query.sort_by in result.metadata:
                    return result.metadata[query.sort_by]
                else:
                    return 0
            
            results.sort(
                key=get_sort_key,
                reverse=(query.sort_order.lower() == "desc")
            )
        
        # Apply pagination
        paginated_results = results[query.offset:query.offset + query.limit]
        
        # Calculate execution time
        execution_time_ms = int((time.time() - start_time) * 1000)
        
        return SearchResults(
            total=len(results),
            offset=query.offset,
            limit=query.limit,
            query=query,
            results=paginated_results,
            facets=facets,
            execution_time_ms=execution_time_ms,
            source_counts={"local": len(results)}
        )


class GovInfoProvider(SearchProvider):
    """Search provider for GovInfo.gov API."""
    
    provider_name = "govinfo"
    supported_types = [
        SearchResultType.DOCUMENT,
        SearchResultType.BILL,
        SearchResultType.CFR,
        SearchResultType.COURT_OPINION
    ]
    
    def __init__(self, client: Optional[GovInfoClient] = None):
        """Initialize the GovInfo search provider.
        
        Args:
            client: GovInfo API client
        """
        self.client = client
    
    async def initialize(self) -> None:
        """Initialize the search provider."""
        if not self.client:
            # Get client from auth manager in a real implementation
            pass
    
    async def search(self, query: SearchQuery) -> SearchResults:
        """Execute search query.
        
        Args:
            query: Search query
            
        Returns:
            Search results
        """
        if not self.client:
            logger.error("GovInfo client not initialized")
            return SearchResults(
                total=0,
                query=query,
                results=[],
                execution_time_ms=0
            )
        
        start_time = time.time()
        
        try:
            # Convert search query to API parameters
            params = {
                "query": query.query_text,
                "offset": query.offset,
                "limit": query.limit
            }
            
            # Add collection filter if document type is specified
            if "document_type" in query.filters:
                doc_type = query.filters["document_type"]
                if doc_type == "BILL":
                    params["collection"] = "BILLS"
                elif doc_type == "CFR":
                    params["collection"] = "CFR"
                elif doc_type == "COURT_OPINION":
                    params["collection"] = "USCOURTS"
                elif doc_type == "FEDERAL_REGISTER":
                    params["collection"] = "FR"
            
            # Add date filters
            if "start_date" in query.filters:
                params["start_date"] = query.filters["start_date"]
            if "end_date" in query.filters:
                params["end_date"] = query.filters["end_date"]
            
            # Execute search
            search_results = await self.client.search_packages(**params)
            
            # Process results
            results = []
            for doc in search_results.get("packages", []):
                # Determine document type
                doc_type = SearchResultType.DOCUMENT
                package_id = doc.get("packageId", "")
                if package_id.startswith("BILLS-"):
                    doc_type = SearchResultType.BILL
                elif package_id.startswith("CFR-"):
                    doc_type = SearchResultType.CFR
                elif package_id.startswith("USCOURTS-"):
                    doc_type = SearchResultType.COURT_OPINION
                elif package_id.startswith("FR-"):
                    doc_type = SearchResultType.DOCUMENT
                
                # Create highlights
                highlights = []
                highlight_data = doc.get("highlights", {})
                for field, fragments in highlight_data.items():
                    highlights.append(Highlight(field=field, fragments=fragments))
                
                # Create result
                result = SearchResult(
                    result_id=package_id,
                    type=doc_type,
                    source="govinfo",
                    score=doc.get("score", 0.0),
                    title=doc.get("title", ""),
                    url=doc.get("detailsLink"),
                    date=doc.get("dateIssued"),
                    metadata=doc.get("metadata", {}),
                    highlights=highlights
                )
                results.append(result)
            
            # Build facets
            facets = {}
            facet_data = search_results.get("facets", {})
            for field, values in facet_data.items():
                facets[field] = Facet(field=field, values=values)
            
            # Calculate execution time
            execution_time_ms = int((time.time() - start_time) * 1000)
            
            return SearchResults(
                total=search_results.get("count", len(results)),
                offset=query.offset,
                limit=query.limit,
                query=query,
                results=results,
                facets=facets,
                execution_time_ms=execution_time_ms,
                source_counts={"govinfo": search_results.get("count", len(results))}
            )
        except ApiError as e:
            logger.error(f"Error searching GovInfo: {e}")
            return SearchResults(
                total=0,
                query=query,
                results=[],
                execution_time_ms=0
            )


class CongressProvider(SearchProvider):
    """Search provider for Congress.gov API."""
    
    provider_name = "congress"
    supported_types = [
        SearchResultType.BILL,
        SearchResultType.MEMBER,
        SearchResultType.COMMITTEE
    ]
    
    def __init__(self, client: Optional[CongressClient] = None):
        """Initialize the Congress search provider.
        
        Args:
            client: Congress API client
        """
        self.client = client
    
    async def initialize(self) -> None:
        """Initialize the search provider."""
        if not self.client:
            # Get client from auth manager in a real implementation
            pass
    
    async def search(self, query: SearchQuery) -> SearchResults:
        """Execute search query.
        
        Args:
            query: Search query
            
        Returns:
            Search results
        """
        if not self.client:
            logger.error("Congress client not initialized")
            return SearchResults(
                total=0,
                query=query,
                results=[],
                execution_time_ms=0
            )
        
        start_time = time.time()
        
        try:
            # Based on document type, call the appropriate endpoint
            if "document_type" in query.filters and query.filters["document_type"] == "BILL":
                return await self._search_bills(query)
            elif "document_type" in query.filters and query.filters["document_type"] == "MEMBER":
                return await self._search_members(query)
            elif "document_type" in query.filters and query.filters["document_type"] == "COMMITTEE":
                return await self._search_committees(query)
            else:
                # Generic search
                return await self._search_all(query)
        except ApiError as e:
            logger.error(f"Error searching Congress: {e}")
            return SearchResults(
                total=0,
                query=query,
                results=[],
                execution_time_ms=0
            )
    
    async def _search_bills(self, query: SearchQuery) -> SearchResults:
        """Search bills.
        
        Args:
            query: Search query
            
        Returns:
            Search results
        """
        start_time = time.time()
        
        # Convert search query to API parameters
        params = {
            "query": query.query_text,
            "offset": query.offset,
            "limit": query.limit
        }
        
        # Add filters
        if "congress" in query.filters:
            params["congress"] = query.filters["congress"]
        if "bill_type" in query.filters:
            params["bill_type"] = query.filters["bill_type"]
        
        # Execute search
        search_results = await self.client.search_bills(**params)
        
        # Process results
        results = []
        for bill in search_results.get("bills", []):
            # Extract bill ID
            bill_id = bill.get("congress_gov_url", "").split("/")[-1]
            
            # Create result
            result = SearchResult(
                result_id=bill_id,
                type=SearchResultType.BILL,
                source="congress",
                title=bill.get("title", ""),
                url=bill.get("congress_gov_url"),
                date=bill.get("introduced_date"),
                metadata={
                    "congress": bill.get("congress"),
                    "bill_type": bill.get("bill_type"),
                    "bill_number": bill.get("number"),
                    "sponsor": bill.get("sponsor", {}).get("name")
                }
            )
            results.append(result)
        
        # Calculate execution time
        execution_time_ms = int((time.time() - start_time) * 1000)
        
        return SearchResults(
            total=search_results.get("count", len(results)),
            offset=query.offset,
            limit=query.limit,
            query=query,
            results=results,
            execution_time_ms=execution_time_ms,
            source_counts={"congress": search_results.get("count", len(results))}
        )
    
    async def _search_members(self, query: SearchQuery) -> SearchResults:
        """Search members.
        
        Args:
            query: Search query
            
        Returns:
            Search results
        """
        start_time = time.time()
        
        # Convert search query to API parameters
        params = {
            "query": query.query_text,
            "offset": query.offset,
            "limit": query.limit
        }
        
        # Add filters
        if "congress" in query.filters:
            params["congress"] = query.filters["congress"]
        if "chamber" in query.filters:
            params["chamber"] = query.filters["chamber"]
        if "state" in query.filters:
            params["state"] = query.filters["state"]
        
        # Execute search
        search_results = await self.client.search_members(**params)
        
        # Process results
        results = []
        for member in search_results.get("members", []):
            # Create result
            result = SearchResult(
                result_id=member.get("id", ""),
                type=SearchResultType.MEMBER,
                source="congress",
                title=member.get("name", ""),
                url=member.get("url"),
                metadata={
                    "chamber": member.get("chamber"),
                    "state": member.get("state"),
                    "party": member.get("party"),
                    "district": member.get("district")
                }
            )
            results.append(result)
        
        # Calculate execution time
        execution_time_ms = int((time.time() - start_time) * 1000)
        
        return SearchResults(
            total=search_results.get("count", len(results)),
            offset=query.offset,
            limit=query.limit,
            query=query,
            results=results,
            execution_time_ms=execution_time_ms,
            source_counts={"congress": search_results.get("count", len(results))}
        )
    
    async def _search_committees(self, query: SearchQuery) -> SearchResults:
        """Search committees.
        
        Args:
            query: Search query
            
        Returns:
            Search results
        """
        start_time = time.time()
        
        # Convert search query to API parameters
        params = {
            "query": query.query_text,
            "offset": query.offset,
            "limit": query.limit
        }
        
        # Add filters
        if "congress" in query.filters:
            params["congress"] = query.filters["congress"]
        if "chamber" in query.filters:
            params["chamber"] = query.filters["chamber"]
        
        # Execute search
        search_results = await self.client.search_committees(**params)
        
        # Process results
        results = []
        for committee in search_results.get("committees", []):
            # Create result
            result = SearchResult(
                result_id=committee.get("id", ""),
                type=SearchResultType.COMMITTEE,
                source="congress",
                title=committee.get("name", ""),
                url=committee.get("url"),
                metadata={
                    "chamber": committee.get("chamber"),
                    "committee_type": committee.get("type"),
                    "parent_committee": committee.get("parent_committee", {}).get("name")
                }
            )
            results.append(result)
        
        # Calculate execution time
        execution_time_ms = int((time.time() - start_time) * 1000)
        
        return SearchResults(
            total=search_results.get("count", len(results)),
            offset=query.offset,
            limit=query.limit,
            query=query,
            results=results,
            execution_time_ms=execution_time_ms,
            source_counts={"congress": search_results.get("count", len(results))}
        )
    
    async def _search_all(self, query: SearchQuery) -> SearchResults:
        """Search all content types.
        
        Args:
            query: Search query
            
        Returns:
            Search results
        """
        start_time = time.time()
        
        # Convert search query to API parameters
        params = {
            "query": query.query_text,
            "offset": query.offset,
            "limit": query.limit
        }
        
        # Execute search
        search_results = await self.client.search(**params)
        
        # Process results
        results = []
        for item in search_results.get("results", []):
            # Determine result type
            item_type = item.get("type", "").upper()
            if item_type == "BILL":
                result_type = SearchResultType.BILL
            elif item_type == "MEMBER":
                result_type = SearchResultType.MEMBER
            elif item_type == "COMMITTEE":
                result_type = SearchResultType.COMMITTEE
            else:
                result_type = SearchResultType.OTHER
            
            # Create highlights
            highlights = []
            highlight_data = item.get("highlights", {})
            for field, fragments in highlight_data.items():
                highlights.append(Highlight(field=field, fragments=fragments))
            
            # Create result
            result = SearchResult(
                result_id=item.get("id", ""),
                type=result_type,
                source="congress",
                score=item.get("score", 0.0),
                title=item.get("title", ""),
                url=item.get("url"),
                date=item.get("date"),
                metadata=item.get("metadata", {}),
                highlights=highlights,
                text_snippet=item.get("snippet")
            )
            results.append(result)
        
        # Calculate execution time
        execution_time_ms = int((time.time() - start_time) * 1000)
        
        return SearchResults(
            total=search_results.get("count", len(results)),
            offset=query.offset,
            limit=query.limit,
            query=query,
            results=results,
            execution_time_ms=execution_time_ms,
            source_counts={"congress": search_results.get("count", len(results))}
        )