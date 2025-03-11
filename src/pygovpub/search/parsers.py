"""
Query parsers for search functionality.

This module provides parsers for search queries.
"""

import logging
import re
from datetime import datetime
from typing import Dict, List, Optional, Any, Union, Tuple

from pygovpub.search.core import (
    SearchQuery, 
    QueryComponent, 
    SearchOperator
)

logger = logging.getLogger("pygovpub.search.parsers")


class QueryParser:
    """Base class for query parsers."""
    
    def parse(self, query_text: str) -> List[QueryComponent]:
        """Parse query text into query components.
        
        Args:
            query_text: Query text
            
        Returns:
            List of query components
        """
        raise NotImplementedError("Subclasses must implement parse")


class SimpleQueryParser(QueryParser):
    """Simple query parser that splits on whitespace."""
    
    def parse(self, query_text: str) -> List[QueryComponent]:
        """Parse query text into query components.
        
        Args:
            query_text: Query text
            
        Returns:
            List of query components
        """
        if not query_text:
            return []
        
        # Split on whitespace
        terms = query_text.split()
        
        # Create a component for each term
        components = []
        for term in terms:
            component = QueryComponent(
                operator=SearchOperator.AND,
                value=term
            )
            components.append(component)
        
        return components


class AdvancedQueryParser(QueryParser):
    """Advanced query parser with support for operators and field specifiers."""
    
    # Regular expressions for parsing
    FIELD_PATTERN = re.compile(r'(\w+):')
    QUOTED_PATTERN = re.compile(r'"([^"]*)"')
    RANGE_PATTERN = re.compile(r'(\w+):\[([^\]]*) TO ([^\]]*)\]')
    OPERATOR_PATTERN = re.compile(r'\b(AND|OR|NOT)\b')
    
    def parse(self, query_text: str) -> List[QueryComponent]:
        """Parse query text into query components.
        
        Args:
            query_text: Query text
            
        Returns:
            List of query components
        """
        if not query_text:
            return []
        
        components = []
        
        # Handle quoted phrases
        quoted_phrases = self.QUOTED_PATTERN.findall(query_text)
        for phrase in quoted_phrases:
            query_text = query_text.replace(f'"{phrase}"', '')
            components.append(QueryComponent(
                operator=SearchOperator.EXACT,
                value=phrase
            ))
        
        # Handle field:value syntax
        field_matches = self.FIELD_PATTERN.findall(query_text)
        for field in field_matches:
            # Find the value for this field
            field_pattern = re.compile(f'{field}:([^\\s]+)')
            field_values = field_pattern.findall(query_text)
            
            if field_values:
                value = field_values[0]
                query_text = query_text.replace(f'{field}:{value}', '')
                
                # Check if it's a wildcard search
                if '*' in value:
                    components.append(QueryComponent(
                        operator=SearchOperator.WILDCARD,
                        field=field,
                        value=value.replace('*', '')
                    ))
                else:
                    components.append(QueryComponent(
                        operator=SearchOperator.AND,
                        field=field,
                        value=value
                    ))
        
        # Handle range queries
        range_matches = self.RANGE_PATTERN.findall(query_text)
        for field, start, end in range_matches:
            query_text = query_text.replace(f'{field}:[{start} TO {end}]', '')
            components.append(QueryComponent(
                operator=SearchOperator.RANGE,
                field=field,
                value={"start": start, "end": end}
            ))
        
        # Handle remaining terms
        remaining_query = query_text.strip()
        if remaining_query:
            # Split on operators
            parts = self.OPERATOR_PATTERN.split(remaining_query)
            parts = [p.strip() for p in parts if p.strip()]
            
            # Parse operators
            operators = self.OPERATOR_PATTERN.findall(remaining_query)
            
            # Create components
            current_operator = SearchOperator.AND
            for i, part in enumerate(parts):
                # Update operator if we have one
                if i > 0 and i - 1 < len(operators):
                    op_str = operators[i - 1]
                    if op_str == "AND":
                        current_operator = SearchOperator.AND
                    elif op_str == "OR":
                        current_operator = SearchOperator.OR
                    elif op_str == "NOT":
                        current_operator = SearchOperator.NOT
                
                if part.strip():
                    components.append(QueryComponent(
                        operator=current_operator,
                        value=part.strip()
                    ))
        
        return components


class MetadataParser:
    """Parser for metadata filters."""
    
    def parse_filters(self, filters: Dict[str, Any]) -> List[QueryComponent]:
        """Parse metadata filters into query components.
        
        Args:
            filters: Dictionary of filters
            
        Returns:
            List of query components
        """
        components = []
        
        for field, value in filters.items():
            if isinstance(value, dict) and "start" in value and "end" in value:
                # Range filter
                components.append(QueryComponent(
                    operator=SearchOperator.RANGE,
                    field=field,
                    value=value
                ))
            elif isinstance(value, list):
                # Multi-value filter
                sub_components = []
                for v in value:
                    sub_components.append(QueryComponent(
                        operator=SearchOperator.OR,
                        field=field,
                        value=v
                    ))
                
                if sub_components:
                    components.append(QueryComponent(
                        operator=SearchOperator.AND,
                        field=field,
                        sub_components=sub_components
                    ))
            else:
                # Simple value filter
                components.append(QueryComponent(
                    operator=SearchOperator.AND,
                    field=field,
                    value=value
                ))
        
        return components
    
    def build_query(self, 
        query_text: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        offset: int = 0,
        limit: int = 20,
        sort_by: Optional[str] = None,
        sort_order: str = "desc",
        highlight: bool = True,
        facets: Optional[List[str]] = None,
        sources: Optional[List[str]] = None,
        query_parser: Optional[QueryParser] = None
    ) -> SearchQuery:
        """Build a complete search query.
        
        Args:
            query_text: Free text query
            filters: Metadata filters
            offset: Result offset
            limit: Result limit
            sort_by: Field to sort by
            sort_order: Sort direction ("asc" or "desc")
            highlight: Whether to highlight results
            facets: Fields to generate facets for
            sources: Sources to search
            query_parser: Parser for the query text
            
        Returns:
            Search query object
        """
        components = []
        
        # Parse query text if provided
        if query_text and query_parser:
            text_components = query_parser.parse(query_text)
            components.extend(text_components)
        
        # Parse filters if provided
        if filters:
            filter_components = self.parse_filters(filters)
            components.extend(filter_components)
        
        # Create the query object
        query = SearchQuery(
            query_text=query_text,
            components=components,
            filters=filters or {},
            offset=offset,
            limit=limit,
            sort_by=sort_by,
            sort_order=sort_order,
            highlight=highlight,
            facets=facets or [],
            sources=sources or []
        )
        
        return query