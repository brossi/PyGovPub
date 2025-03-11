"""
Unit tests for the search parsers module.
"""

import pytest
from datetime import datetime
from typing import Dict, List, Any

from pygovpub.search.core import (
    SearchQuery, 
    QueryComponent, 
    SearchOperator
)
from pygovpub.search.parsers import (
    QueryParser,
    SimpleQueryParser, 
    AdvancedQueryParser, 
    MetadataParser
)


class TestQueryParser:
    """Tests for the base QueryParser class."""
    
    def test_query_parser_base(self):
        """Test the base QueryParser class."""
        parser = QueryParser()
        with pytest.raises(NotImplementedError, match="Subclasses must implement parse"):
            parser.parse("test query")


class TestSimpleQueryParser:
    """Tests for the SimpleQueryParser class."""
    
    @pytest.fixture
    def parser(self):
        """Create a SimpleQueryParser for testing."""
        return SimpleQueryParser()
    
    def test_parse_empty_query(self, parser):
        """Test parsing an empty query."""
        result = parser.parse("")
        assert isinstance(result, list)
        assert len(result) == 0
        
        result = parser.parse(None)
        assert isinstance(result, list)
        assert len(result) == 0
    
    def test_parse_single_term(self, parser):
        """Test parsing a single term query."""
        result = parser.parse("congress")
        
        assert len(result) == 1
        assert isinstance(result[0], QueryComponent)
        assert result[0].operator == SearchOperator.AND
        assert result[0].value == "congress"
        assert result[0].field is None
    
    def test_parse_multiple_terms(self, parser):
        """Test parsing a query with multiple terms."""
        result = parser.parse("legislative bill HR1234")
        
        assert len(result) == 3
        
        # Check each component
        assert result[0].value == "legislative"
        assert result[0].operator == SearchOperator.AND
        
        assert result[1].value == "bill"
        assert result[1].operator == SearchOperator.AND
        
        assert result[2].value == "HR1234"
        assert result[2].operator == SearchOperator.AND
    
    def test_parse_preserves_term_order(self, parser):
        """Test that term order is preserved when parsing."""
        terms = ["first", "second", "third", "fourth"]
        query = " ".join(terms)
        
        result = parser.parse(query)
        
        assert len(result) == len(terms)
        for i, term in enumerate(terms):
            assert result[i].value == term


class TestAdvancedQueryParser:
    """Tests for the AdvancedQueryParser class."""
    
    @pytest.fixture
    def parser(self):
        """Create an AdvancedQueryParser for testing."""
        return AdvancedQueryParser()
    
    def test_parse_empty_query(self, parser):
        """Test parsing an empty query."""
        result = parser.parse("")
        assert isinstance(result, list)
        assert len(result) == 0
        
        result = parser.parse(None)
        assert isinstance(result, list)
        assert len(result) == 0
    
    def test_parse_quoted_phrases(self, parser):
        """Test parsing quoted phrases."""
        result = parser.parse('"legislative process" congress')
        
        # Should have two components: the quoted phrase and the term
        assert len(result) == 2
        
        # Check the quoted phrase component
        quoted_component = [c for c in result if c.operator == SearchOperator.EXACT][0]
        assert quoted_component.value == "legislative process"
        assert quoted_component.operator == SearchOperator.EXACT
        
        # Check the regular term
        term_component = [c for c in result if c.value == "congress"][0]
        assert term_component.operator == SearchOperator.AND
    
    def test_parse_multiple_quoted_phrases(self, parser):
        """Test parsing multiple quoted phrases."""
        result = parser.parse('"first phrase" "second phrase" "third phrase"')
        
        assert len(result) == 3
        
        # All components should be EXACT
        for component in result:
            assert component.operator == SearchOperator.EXACT
        
        # Check values
        values = [c.value for c in result]
        assert "first phrase" in values
        assert "second phrase" in values
        assert "third phrase" in values
    
    def test_parse_field_queries(self, parser):
        """Test parsing field:value queries."""
        result = parser.parse('title:legislation congress')
        
        assert len(result) == 2
        
        # Check the field component
        field_component = [c for c in result if c.field == "title"][0]
        assert field_component.value == "legislation"
        assert field_component.operator == SearchOperator.AND
        
        # Check the regular term
        term_component = [c for c in result if c.value == "congress"][0]
        assert term_component.field is None
    
    def test_parse_wildcard_queries(self, parser):
        """Test parsing field:value* wildcard queries."""
        result = parser.parse('title:legis* congress')
        
        assert len(result) == 2
        
        # Check the wildcard component
        wildcard_component = [c for c in result if c.field == "title"][0]
        assert wildcard_component.value == "legis"
        assert wildcard_component.operator == SearchOperator.WILDCARD
    
    def test_parse_range_queries(self, parser):
        """Test parsing range queries."""
        result = parser.parse('date:[2020-01-01 TO 2020-12-31] congress')
        
        assert len(result) == 2
        
        # Check the range component
        range_component = [c for c in result if c.operator == SearchOperator.RANGE][0]
        assert range_component.field == "date"
        assert isinstance(range_component.value, dict)
        assert range_component.value["start"] == "2020-01-01"
        assert range_component.value["end"] == "2020-12-31"
    
    def test_parse_boolean_operators(self, parser):
        """Test parsing boolean operators."""
        result = parser.parse('congress AND senate OR house NOT committee')
        
        assert len(result) == 4
        
        # Check operators
        operators = {c.value: c.operator for c in result}
        assert operators["congress"] == SearchOperator.AND
        assert operators["senate"] == SearchOperator.AND
        assert operators["house"] == SearchOperator.OR
        assert operators["committee"] == SearchOperator.NOT
    
    def test_parse_complex_query(self, parser):
        """Test parsing a complex query with multiple features."""
        result = parser.parse('title:bill "healthcare reform" date:[2021-01-01 TO 2021-12-31] sponsor:* congress AND senate')
        
        # Count expected components
        assert len(result) == 6
        
        # Check field component
        title_component = [c for c in result if c.field == "title"][0]
        assert title_component.value == "bill"
        
        # Check quoted phrase
        quoted_component = [c for c in result if c.operator == SearchOperator.EXACT][0]
        assert quoted_component.value == "healthcare reform"
        
        # Check range
        range_component = [c for c in result if c.operator == SearchOperator.RANGE][0]
        assert range_component.field == "date"
        
        # Check wildcard
        wildcard_component = [c for c in result if c.operator == SearchOperator.WILDCARD][0]
        assert wildcard_component.field == "sponsor"
        
        # Check boolean operators
        congress_component = [c for c in result if c.value == "congress"][0]
        assert congress_component.operator == SearchOperator.AND
        
        senate_component = [c for c in result if c.value == "senate"][0]
        assert senate_component.operator == SearchOperator.AND


class TestMetadataParser:
    """Tests for the MetadataParser class."""
    
    @pytest.fixture
    def parser(self):
        """Create a MetadataParser for testing."""
        return MetadataParser()
    
    def test_parse_empty_filters(self, parser):
        """Test parsing empty filters."""
        result = parser.parse_filters({})
        assert isinstance(result, list)
        assert len(result) == 0
    
    def test_parse_simple_filter(self, parser):
        """Test parsing a simple key-value filter."""
        filters = {"congress": 117}
        result = parser.parse_filters(filters)
        
        assert len(result) == 1
        assert result[0].field == "congress"
        assert result[0].value == "117"  # Value is converted to string
        assert result[0].operator == SearchOperator.AND
    
    def test_parse_range_filter(self, parser):
        """Test parsing a range filter."""
        filters = {"date": {"start": "2021-01-01", "end": "2021-12-31"}}
        result = parser.parse_filters(filters)
        
        assert len(result) == 1
        assert result[0].field == "date"
        assert result[0].operator == SearchOperator.RANGE
        assert result[0].value["start"] == "2021-01-01"
        assert result[0].value["end"] == "2021-12-31"
    
    def test_parse_list_filter(self, parser):
        """Test parsing a list filter."""
        filters = {"bill_type": ["hr", "s", "hjres"]}
        result = parser.parse_filters(filters)
        
        assert len(result) == 1
        assert result[0].field == "bill_type"
        assert result[0].operator == SearchOperator.AND
        
        # Check sub-components
        assert len(result[0].sub_components) == 3
        
        # Each sub-component should be OR
        for sub in result[0].sub_components:
            assert sub.operator == SearchOperator.OR
            assert sub.field == "bill_type"
        
        # Check values
        values = [sub.value for sub in result[0].sub_components]
        assert "hr" in values
        assert "s" in values
        assert "hjres" in values
    
    def test_parse_multiple_filters(self, parser):
        """Test parsing multiple filters of different types."""
        filters = {
            "congress": 117,
            "bill_type": ["hr", "s"],
            "introduced_date": {"start": "2021-01-01", "end": "2021-12-31"}
        }
        result = parser.parse_filters(filters)
        
        assert len(result) == 3
        
        # Find each filter component by field
        components_by_field = {c.field: c for c in result}
        
        # Check simple filter
        assert components_by_field["congress"].value == "117"  # Value is converted to string
        assert components_by_field["congress"].operator == SearchOperator.AND
        
        # Check list filter
        assert len(components_by_field["bill_type"].sub_components) == 2
        
        # Check range filter
        assert components_by_field["introduced_date"].operator == SearchOperator.RANGE
        assert components_by_field["introduced_date"].value["start"] == "2021-01-01"
    
    def test_build_query_with_text(self, parser):
        """Test building a query with text only."""
        text_parser = SimpleQueryParser()
        query = parser.build_query(
            query_text="legislative bill",
            query_parser=text_parser
        )
        
        assert query.query_text == "legislative bill"
        assert len(query.components) == 2
        assert query.components[0].value == "legislative"
        assert query.components[1].value == "bill"
    
    def test_build_query_with_filters(self, parser):
        """Test building a query with filters only."""
        filters = {"congress": 117, "bill_type": "hr"}
        query = parser.build_query(filters=filters)
        
        assert query.filters == filters
        assert len(query.components) == 2
        
        # Components should match filters
        components_by_field = {c.field: c for c in query.components}
        assert components_by_field["congress"].value == "117"  # Value is converted to string
        assert components_by_field["bill_type"].value == "hr"
    
    def test_build_query_with_text_and_filters(self, parser):
        """Test building a query with both text and filters."""
        text_parser = SimpleQueryParser()
        filters = {"congress": 117}
        
        query = parser.build_query(
            query_text="healthcare",
            filters=filters,
            query_parser=text_parser
        )
        
        assert query.query_text == "healthcare"
        assert query.filters == filters
        
        # Should have components from both text and filters
        assert len(query.components) == 2
        
        # One component should be from text
        text_components = [c for c in query.components if c.field is None]
        assert len(text_components) == 1
        assert text_components[0].value == "healthcare"
        
        # One component should be from filters
        filter_components = [c for c in query.components if c.field == "congress"]
        assert len(filter_components) == 1
        assert filter_components[0].value == "117"  # Value is converted to string
    
    def test_build_query_with_pagination_and_sorting(self, parser):
        """Test building a query with pagination and sorting options."""
        query = parser.build_query(
            query_text="test",
            query_parser=SimpleQueryParser(),
            offset=10,
            limit=50,
            sort_by="introduced_date",
            sort_order="asc"
        )
        
        assert query.offset == 10
        assert query.limit == 50
        assert query.sort_by == "introduced_date"
        assert query.sort_order == "asc"
    
    def test_build_query_with_all_options(self, parser):
        """Test building a query with all available options."""
        text_parser = AdvancedQueryParser()
        filters = {
            "congress": 117,
            "bill_type": ["hr", "s"],
            "introduced_date": {"start": "2021-01-01", "end": "2021-12-31"}
        }
        
        query = parser.build_query(
            query_text='title:"healthcare reform"',
            filters=filters,
            query_parser=text_parser,
            offset=20,
            limit=100,
            sort_by="introduced_date",
            sort_order="desc",
            highlight=True,
            facets=["bill_type", "sponsor_party"],
            sources=["congress.gov"]
        )
        
        # Check basic properties
        assert query.query_text == 'title:"healthcare reform"'
        assert query.filters == filters
        assert query.offset == 20
        assert query.limit == 100
        assert query.sort_by == "introduced_date"
        assert query.sort_order == "desc"
        assert query.highlight is True
        assert "bill_type" in query.facets
        assert "sponsor_party" in query.facets
        assert "congress.gov" in query.sources
        
        # Check components from advanced text parsing
        text_components = [c for c in query.components if c.operator == SearchOperator.EXACT]
        assert len(text_components) == 1
        assert text_components[0].value == "healthcare reform"
        
        # Check filter components
        filter_components = [c for c in query.components if c.field in filters.keys()]
        assert len(filter_components) == 3


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])