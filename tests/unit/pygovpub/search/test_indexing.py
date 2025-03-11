"""
Unit tests for the search indexing module.
"""

import asyncio
import pytest
from datetime import datetime
from typing import Any, Dict, List, Set, Tuple

from pygovpub.search.core import DocumentId, SearchResultType
from pygovpub.search.indexing import DocumentIndexer, IndexEntry


class TestDocumentIndexer:
    """Tests for the DocumentIndexer class."""
    
    @pytest.fixture
    def indexer(self) -> DocumentIndexer:
        """Create a DocumentIndexer for testing."""
        return DocumentIndexer()
    
    @pytest.fixture
    def sample_document(self) -> Dict[str, Any]:
        """Create a sample document for testing."""
        return {
            "id": "doc-123",
            "type": "bill",
            "source": "congress.gov",
            "title": "Sample Bill Title",
            "url": "https://example.gov/doc-123",
            "content": "This is the full text of the sample bill. It includes various provisions and amendments.",
            "congress": 117,
            "bill_type": "hr",
            "bill_number": 1234,
            "sponsor": "Representative Smith",
            "introduced_date": "2023-01-15"
        }
    
    @pytest.fixture
    def sample_documents(self) -> List[Dict[str, Any]]:
        """Create multiple sample documents for testing."""
        return [
            {
                "id": "doc-123",
                "type": "bill",
                "source": "congress.gov",
                "title": "Sample Bill Title",
                "url": "https://example.gov/doc-123",
                "content": "This is the full text of the sample bill. It includes various provisions and amendments.",
                "congress": 117,
                "bill_type": "hr",
                "bill_number": 1234,
                "sponsor": "Representative Smith",
                "introduced_date": "2023-01-15"
            },
            {
                "id": "doc-456",
                "type": "document",
                "source": "govinfo.gov",
                "title": "Committee Report",
                "url": "https://example.gov/doc-456",
                "content": "This report summarizes the committee findings on the proposed legislation.",
                "committee": "Judiciary",
                "report_number": "789",
                "published_date": "2023-02-20"
            },
            {
                "id": "doc-789",
                "type": "bill",
                "source": "congress.gov",
                "title": "Another Bill Example",
                "url": "https://example.gov/doc-789",
                "content": "This bill proposes changes to existing regulations on environmental protection.",
                "congress": 117,
                "bill_type": "s",
                "bill_number": 5678,
                "sponsor": "Senator Jones",
                "introduced_date": "2023-03-10",
                "cosponsors": ["Senator Brown", "Senator Miller"]
            }
        ]
    
    async def test_initialization(self, indexer: DocumentIndexer):
        """Test DocumentIndexer initialization."""
        assert indexer.documents == {}
        assert indexer.text_index == {}
        assert indexer.field_index == {}
        assert isinstance(indexer.stop_words, set)
        assert "the" in indexer.stop_words
        assert "in" in indexer.stop_words
    
    async def test_tokenize(self, indexer: DocumentIndexer):
        """Test the document tokenization functionality."""
        # Test with empty text
        assert indexer._tokenize("") == []
        assert indexer._tokenize(None) == []
        
        # Test with simple text
        tokens = indexer._tokenize("This is a test")
        assert "this" in tokens
        assert "is" in tokens
        assert "test" in tokens
        assert "a" not in tokens  # Stop word should be removed
        
        # Test with mixed case and punctuation
        tokens = indexer._tokenize("The Quick Brown Fox-Jumps, Over. The Lazy Dog!")
        assert "quick" in tokens
        assert "brown" in tokens
        assert "fox" in tokens
        assert "jumps" in tokens
        assert "over" in tokens
        assert "lazy" in tokens
        assert "dog" in tokens
        assert "the" not in tokens  # Stop word should be removed
    
    async def test_index_document_basic(self, indexer: DocumentIndexer, sample_document: Dict[str, Any]):
        """Test basic document indexing functionality."""
        # Index the document
        doc_id = await indexer.index_document(sample_document)
        
        # Verify document ID returned matches input
        assert doc_id == "doc-123"
        
        # Verify document was stored
        assert doc_id in indexer.documents
        assert isinstance(indexer.documents[doc_id], IndexEntry)
        
        # Verify basic document fields
        entry = indexer.documents[doc_id]
        assert entry.document_id == "doc-123"
        assert entry.type == SearchResultType.BILL
        assert entry.source == "congress.gov"
        assert entry.title == "Sample Bill Title"
        assert entry.url == "https://example.gov/doc-123"
        assert entry.text_content == "This is the full text of the sample bill. It includes various provisions and amendments."
        
        # Verify additional fields
        assert entry.fields["congress"] == 117
        assert entry.fields["bill_type"] == "hr"
        assert entry.fields["bill_number"] == 1234
        assert entry.fields["sponsor"] == "Representative Smith"
        assert entry.fields["introduced_date"] == "2023-01-15"
        
        # Verify text was indexed
        assert "bill" in indexer.text_index
        assert "sample" in indexer.text_index
        assert "provisions" in indexer.text_index
        assert "amendments" in indexer.text_index
        
        # Verify fields were indexed
        assert ("congress", 117) in indexer.field_index
        assert ("bill_type", "hr") in indexer.field_index
        assert ("sponsor", "Representative Smith") in indexer.field_index
    
    async def test_index_document_missing_fields(self, indexer: DocumentIndexer):
        """Test indexing document with missing required fields."""
        # Missing ID
        doc_no_id = {
            "type": "bill",
            "source": "congress.gov",
            "title": "Sample Bill Title"
        }
        with pytest.raises(ValueError, match="Document must have an 'id' field"):
            await indexer.index_document(doc_no_id)
        
        # Missing type
        doc_no_type = {
            "id": "doc-123",
            "source": "congress.gov",
            "title": "Sample Bill Title"
        }
        with pytest.raises(ValueError, match="Document must have a 'type' field"):
            await indexer.index_document(doc_no_type)
        
        # Missing source
        doc_no_source = {
            "id": "doc-123",
            "type": "bill",
            "title": "Sample Bill Title"
        }
        with pytest.raises(ValueError, match="Document must have a 'source' field"):
            await indexer.index_document(doc_no_source)
        
        # Missing title
        doc_no_title = {
            "id": "doc-123",
            "type": "bill",
            "source": "congress.gov"
        }
        with pytest.raises(ValueError, match="Document must have a 'title' field"):
            await indexer.index_document(doc_no_title)
    
    async def test_index_document_complex_field_values(self, indexer: DocumentIndexer):
        """Test indexing document with complex field values (lists, dicts)."""
        document = {
            "id": "complex-doc",
            "type": "bill",
            "source": "test",
            "title": "Complex Document",
            "tags": ["important", "urgent", "legislation"],
            "metadata": {"status": "active", "priority": "high"},
            "sponsors": ["Rep1", "Rep2", "Rep3"]
        }
        
        doc_id = await indexer.index_document(document)
        
        # Verify lists are indexed properly
        assert ("tags", "important") in indexer.field_index
        assert ("tags", "urgent") in indexer.field_index
        assert ("tags", "legislation") in indexer.field_index
        assert doc_id in indexer.field_index[("tags", "important")]
        
        # Verify dict was converted to string
        # Exact format may vary, but should contain the data
        dict_entries = [k for k in indexer.field_index.keys() if k[0] == "metadata"]
        assert len(dict_entries) == 1
        assert "status" in str(dict_entries[0][1])
        assert "priority" in str(dict_entries[0][1])
    
    async def test_index_documents(self, indexer: DocumentIndexer, sample_documents: List[Dict[str, Any]]):
        """Test indexing multiple documents at once."""
        # Index all documents
        doc_ids = await indexer.index_documents(sample_documents)
        
        # Verify all documents were indexed
        assert len(doc_ids) == 3
        assert "doc-123" in doc_ids
        assert "doc-456" in doc_ids
        assert "doc-789" in doc_ids
        
        # Verify all documents are in the store
        assert len(indexer.documents) == 3
        assert "doc-123" in indexer.documents
        assert "doc-456" in indexer.documents
        assert "doc-789" in indexer.documents
        
        # Verify text index contains expected terms
        assert "bill" in indexer.text_index
        assert "committee" in indexer.text_index
        assert "environmental" in indexer.text_index
        
        # Verify field index contains expected entries
        assert ("bill_type", "hr") in indexer.field_index
        assert ("bill_type", "s") in indexer.field_index
        assert ("committee", "Judiciary") in indexer.field_index
        
        # Verify documents can be searched by content
        doc_ids_with_bill = indexer.text_index.get("bill", set())
        assert "doc-123" in doc_ids_with_bill
        assert "doc-789" in doc_ids_with_bill
        
        # Verify documents can be searched by field
        doc_ids_with_hr = indexer.field_index.get(("bill_type", "hr"), set())
        assert "doc-123" in doc_ids_with_hr
        assert "doc-789" not in doc_ids_with_hr
    
    async def test_get_document(self, indexer: DocumentIndexer, sample_document: Dict[str, Any]):
        """Test retrieving documents from the index."""
        # Index a document
        await indexer.index_document(sample_document)
        
        # Retrieve existing document
        entry = await indexer.get_document("doc-123")
        assert entry is not None
        assert entry.document_id == "doc-123"
        assert entry.title == "Sample Bill Title"
        
        # Attempt to retrieve non-existent document
        entry = await indexer.get_document("non-existent")
        assert entry is None
    
    async def test_search_text(self, indexer: DocumentIndexer, sample_documents: List[Dict[str, Any]]):
        """Test searching documents by text content."""
        # Index all documents
        await indexer.index_documents(sample_documents)
        
        # Test search with empty query
        results = await indexer.search_text("")
        assert results == set()
        
        # Test search with query that should match first document
        results = await indexer.search_text("sample bill provisions")
        assert len(results) == 1
        assert "doc-123" in results
        
        # Test search with query that should match multiple documents
        results = await indexer.search_text("bill")
        assert len(results) == 2
        assert "doc-123" in results
        assert "doc-789" in results
        
        # Test search with query that should match no documents
        results = await indexer.search_text("nonexistent terms")
        assert len(results) == 0
        
        # Test search with stop words (should be ignored)
        results = await indexer.search_text("the bill with amendments")
        assert len(results) == 1
        assert "doc-123" in results
    
    async def test_search_field(self, indexer: DocumentIndexer, sample_documents: List[Dict[str, Any]]):
        """Test searching documents by field values."""
        # Index all documents
        await indexer.index_documents(sample_documents)
        
        # Test search by congress field
        results = await indexer.search_field("congress", 117)
        assert len(results) == 2
        assert "doc-123" in results
        assert "doc-789" in results
        
        # Test search by bill_type field
        results = await indexer.search_field("bill_type", "hr")
        assert len(results) == 1
        assert "doc-123" in results
        
        # Test search by committee field
        results = await indexer.search_field("committee", "Judiciary")
        assert len(results) == 1
        assert "doc-456" in results
        
        # Test search by non-existent field
        results = await indexer.search_field("nonexistent", "value")
        assert len(results) == 0
        
        # Test search by field with non-existent value
        results = await indexer.search_field("congress", 116)
        assert len(results) == 0
    
    async def test_delete_document(self, indexer: DocumentIndexer, sample_document: Dict[str, Any]):
        """Test deleting documents from the index."""
        # Index a document
        await indexer.index_document(sample_document)
        
        # Verify document is indexed
        assert "doc-123" in indexer.documents
        assert "bill" in indexer.text_index
        assert "doc-123" in indexer.text_index["bill"]
        assert ("congress", 117) in indexer.field_index
        
        # Delete the document
        result = await indexer.delete_document("doc-123")
        assert result is True
        
        # Verify document was removed from document store
        assert "doc-123" not in indexer.documents
        
        # Verify document was removed from text index
        if "bill" in indexer.text_index:  # May be removed if it was the only doc with this term
            assert "doc-123" not in indexer.text_index["bill"]
        
        # Verify document was removed from field index
        if ("congress", 117) in indexer.field_index:  # May be removed if it was the only doc with this field
            assert "doc-123" not in indexer.field_index[("congress", 117)]
        
        # Try to delete a non-existent document
        result = await indexer.delete_document("non-existent")
        assert result is False
    
    async def test_delete_cleanup(self, indexer: DocumentIndexer, sample_document: Dict[str, Any]):
        """Test that delete properly cleans up empty index entries."""
        # Modify the document to have unique text and field values
        sample_document["content"] = "This document contains some uniqueword that no other document has."
        sample_document["unique_field"] = "unique_value"
        
        # Index the document
        await indexer.index_document(sample_document)
        
        # Verify unique entries exist
        assert "uniqueword" in indexer.text_index
        assert ("unique_field", "unique_value") in indexer.field_index
        
        # Delete the document
        await indexer.delete_document("doc-123")
        
        # Verify unique entries were completely removed 
        assert "uniqueword" not in indexer.text_index
        assert ("unique_field", "unique_value") not in indexer.field_index
    
    async def test_clear_index(self, indexer: DocumentIndexer, sample_documents: List[Dict[str, Any]]):
        """Test clearing the entire index."""
        # Index multiple documents
        await indexer.index_documents(sample_documents)
        
        # Verify documents are indexed
        assert len(indexer.documents) == 3
        assert len(indexer.text_index) > 0
        assert len(indexer.field_index) > 0
        
        # Clear the index
        await indexer.clear_index()
        
        # Verify everything was cleared
        assert len(indexer.documents) == 0
        assert len(indexer.text_index) == 0
        assert len(indexer.field_index) == 0


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])