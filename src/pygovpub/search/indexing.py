"""
Indexing functionality for search.

This module provides indexing capabilities for search.
"""

import logging
import re
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple, Union, Iterator, TypeVar, Generic

from pydantic import BaseModel, Field

from pygovpub.search.core import DocumentId, FieldName, FieldValue, SearchResultType

logger = logging.getLogger("pygovpub.search.indexing")

T = TypeVar('T')


class IndexEntry(BaseModel):
    """Entry in a search index."""
    
    document_id: DocumentId
    type: SearchResultType
    source: str
    title: str
    fields: Dict[FieldName, FieldValue] = Field(default_factory=dict)
    text_content: Optional[str] = None
    url: Optional[str] = None
    indexed_at: datetime = Field(default_factory=datetime.now)


class Indexer(ABC, Generic[T]):
    """Base class for document indexers."""
    
    @abstractmethod
    async def index_document(self, document: T) -> DocumentId:
        """Index a document.
        
        Args:
            document: Document to index
            
        Returns:
            Document ID in the index
        """
        pass
    
    @abstractmethod
    async def index_documents(self, documents: List[T]) -> List[DocumentId]:
        """Index multiple documents.
        
        Args:
            documents: Documents to index
            
        Returns:
            List of document IDs in the index
        """
        pass
    
    @abstractmethod
    async def delete_document(self, document_id: DocumentId) -> bool:
        """Delete a document from the index.
        
        Args:
            document_id: ID of document to delete
            
        Returns:
            True if the document was deleted, False otherwise
        """
        pass
    
    @abstractmethod
    async def clear_index(self) -> None:
        """Clear the entire index."""
        pass
    
    @abstractmethod
    async def get_document(self, document_id: DocumentId) -> Optional[IndexEntry]:
        """Get a document from the index.
        
        Args:
            document_id: ID of document to retrieve
            
        Returns:
            Document entry if found, None otherwise
        """
        pass


class DocumentIndexer(Indexer[Dict[str, Any]]):
    """In-memory document indexer for testing and development."""
    
    def __init__(self):
        """Initialize the document indexer."""
        self.documents: Dict[DocumentId, IndexEntry] = {}
        self.text_index: Dict[str, Set[DocumentId]] = {}
        self.field_index: Dict[Tuple[FieldName, FieldValue], Set[DocumentId]] = {}
        
        # For tokenization and normalization
        self.stop_words = {"a", "an", "the", "in", "on", "at", "of", "for", "by", "with"}
        self.token_pattern = re.compile(r'\b\w+\b')
    
    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text into words.
        
        Args:
            text: Text to tokenize
            
        Returns:
            List of tokens
        """
        if not text:
            return []
        
        # Convert to lowercase and extract tokens
        text = text.lower()
        tokens = self.token_pattern.findall(text)
        
        # Remove stop words
        tokens = [t for t in tokens if t not in self.stop_words]
        
        return tokens
    
    def _index_text(self, document_id: DocumentId, text: str) -> None:
        """Index text content.
        
        Args:
            document_id: Document ID
            text: Text to index
        """
        if not text:
            return
        
        tokens = self._tokenize(text)
        
        # Add document to token index
        for token in tokens:
            if token not in self.text_index:
                self.text_index[token] = set()
            self.text_index[token].add(document_id)
    
    def _index_field(self, document_id: DocumentId, field: FieldName, value: FieldValue) -> None:
        """Index a field.
        
        Args:
            document_id: Document ID
            field: Field name
            value: Field value
        """
        if value is None:
            return
        
        # Handle different value types
        if isinstance(value, (list, set)):
            # For lists, index each value
            for v in value:
                self._index_field(document_id, field, v)
        else:
            # Convert to hashable if necessary
            if isinstance(value, dict):
                # Can't index dictionaries directly, so convert to string
                value = str(value)
            
            # Add to field index
            key = (field, value)
            if key not in self.field_index:
                self.field_index[key] = set()
            self.field_index[key].add(document_id)
    
    async def index_document(self, document: Dict[str, Any]) -> DocumentId:
        """Index a document.
        
        Args:
            document: Document to index
            
        Returns:
            Document ID in the index
        """
        # Extract required fields
        document_id = document.get("id")
        if not document_id:
            raise ValueError("Document must have an 'id' field")
        
        doc_type = document.get("type")
        if not doc_type:
            raise ValueError("Document must have a 'type' field")
        
        source = document.get("source")
        if not source:
            raise ValueError("Document must have a 'source' field")
        
        title = document.get("title")
        if not title:
            raise ValueError("Document must have a 'title' field")
        
        # Create index entry
        entry = IndexEntry(
            document_id=document_id,
            type=SearchResultType(doc_type),
            source=source,
            title=title,
            url=document.get("url"),
            text_content=document.get("content"),
            indexed_at=datetime.now()
        )
        
        # Extract other fields for indexing
        for key, value in document.items():
            if key not in ["id", "type", "source", "title", "url", "content"]:
                entry.fields[key] = value
        
        # Store the document
        self.documents[document_id] = entry
        
        # Index text content
        if entry.text_content:
            self._index_text(document_id, entry.text_content)
        
        # Also index title
        self._index_text(document_id, entry.title)
        
        # Index fields
        for field, value in entry.fields.items():
            self._index_field(document_id, field, value)
        
        return document_id
    
    async def index_documents(self, documents: List[Dict[str, Any]]) -> List[DocumentId]:
        """Index multiple documents.
        
        Args:
            documents: Documents to index
            
        Returns:
            List of document IDs in the index
        """
        ids = []
        for doc in documents:
            doc_id = await self.index_document(doc)
            ids.append(doc_id)
        return ids
    
    async def delete_document(self, document_id: DocumentId) -> bool:
        """Delete a document from the index.
        
        Args:
            document_id: ID of document to delete
            
        Returns:
            True if the document was deleted, False otherwise
        """
        if document_id not in self.documents:
            return False
        
        # Remove from document store
        entry = self.documents.pop(document_id)
        
        # Remove from text index
        for token, doc_ids in list(self.text_index.items()):
            if document_id in doc_ids:
                doc_ids.remove(document_id)
                if not doc_ids:
                    self.text_index.pop(token)
        
        # Remove from field index
        for key, doc_ids in list(self.field_index.items()):
            if document_id in doc_ids:
                doc_ids.remove(document_id)
                if not doc_ids:
                    self.field_index.pop(key)
        
        return True
    
    async def clear_index(self) -> None:
        """Clear the entire index."""
        self.documents.clear()
        self.text_index.clear()
        self.field_index.clear()
    
    async def get_document(self, document_id: DocumentId) -> Optional[IndexEntry]:
        """Get a document from the index.
        
        Args:
            document_id: ID of document to retrieve
            
        Returns:
            Document entry if found, None otherwise
        """
        return self.documents.get(document_id)
    
    async def search_text(self, query: str) -> Set[DocumentId]:
        """Search for documents by text.
        
        Args:
            query: Text query
            
        Returns:
            Set of matching document IDs
        """
        if not query:
            return set()
        
        tokens = self._tokenize(query)
        if not tokens:
            return set()
        
        # Find documents containing all tokens
        matches = None
        for token in tokens:
            if token in self.text_index:
                doc_ids = self.text_index[token]
                if matches is None:
                    matches = doc_ids.copy()
                else:
                    matches &= doc_ids
            else:
                # If any token has no matches, return empty set
                return set()
        
        return matches or set()
    
    async def search_field(self, field: FieldName, value: FieldValue) -> Set[DocumentId]:
        """Search for documents by field value.
        
        Args:
            field: Field name
            value: Field value
            
        Returns:
            Set of matching document IDs
        """
        key = (field, value)
        return self.field_index.get(key, set())