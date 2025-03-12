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
    
    def _index_text(self, document_id: DocumentId, text: str, field: Optional[str] = None) -> None:
        """Index text content.
        
        Args:
            document_id: Document ID
            text: Text to index
            field: Optional field name (for field-specific text indexing)
        """
        if not text:
            return
        
        tokens = self._tokenize(text)
        
        # Add document to token index
        for token in tokens:
            if token not in self.text_index:
                self.text_index[token] = set()
            self.text_index[token].add(document_id)
            
            # If field is provided, create a field-specific text index entry
            if field:
                field_token_key = f"{field}:{token}"
                if field_token_key not in self.text_index:
                    self.text_index[field_token_key] = set()
                self.text_index[field_token_key].add(document_id)
    
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
                # For dictionaries, index each field recursively
                for key, val in value.items():
                    nested_field = f"{field}.{key}"
                    self._index_field(document_id, nested_field, val)
                # Also index the full dict as a string for direct matches
                str_value = str(value)
                key = (field, str_value)
                if key not in self.field_index:
                    self.field_index[key] = set()
                self.field_index[key].add(document_id)
            else:
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
            self._index_text(document_id, entry.text_content, field="content")
        
        # Also index title
        self._index_text(document_id, entry.title, field="title")
        
        # Index fields
        for field, value in entry.fields.items():
            self._index_field(document_id, field, value)
            
            # If field value is a string, also index it as text for better search
            if isinstance(value, str) and len(value) > 3:  # Only index meaningful text
                self._index_text(document_id, value, field=field)
            
        # Special handling for metadata field to ensure proper indexing of nested fields
        if 'metadata' in entry.fields and isinstance(entry.fields['metadata'], dict):
            metadata = entry.fields['metadata']
            
            # Create compound field indexes with the 'metadata.' prefix
            for key, value in metadata.items():
                metadata_field = f"metadata.{key}"
                self._index_field(document_id, metadata_field, value)
                
                # If value is a string, also index it as text
                if isinstance(value, str) and len(value) > 3:
                    self._index_text(document_id, value, field=metadata_field)
                
            # Log metadata indexing
            logger.debug(f"Indexed metadata fields for document {document_id}: {list(metadata.keys())}")
        
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
        # Special handling for known text fields: title and content
        if field in ["title", "content"] and isinstance(value, str):
            logger.debug(f"Performing text field search on {field}: {value}")
            
            # First try direct field match
            key = (field, value)
            direct_matches = self.field_index.get(key, set())
            
            # If no direct match, try using the text index with field prefix
            if not direct_matches:
                # Tokenize the search value
                tokens = self._tokenize(value)
                if tokens:
                    field_token_key = f"{field}:{tokens[0]}"  # Use first token for field search
                    matches = self.text_index.get(field_token_key, set())
                    
                    # If multiple tokens, intersect results
                    for token in tokens[1:]:
                        field_token_key = f"{field}:{token}"
                        token_matches = self.text_index.get(field_token_key, set())
                        matches &= token_matches
                        if not matches:
                            break
                    
                    logger.debug(f"Text field search on {field}={value} found {len(matches)} matches")
                    return matches
            
            logger.debug(f"Direct field match for {field}={value} found {len(direct_matches)} matches")
            return direct_matches
            
        # Handle different value types for comparison
        if isinstance(value, dict):
            value = str(value)
        
        # Check for nested field search (contains '.')
        if '.' in field:
            logger.debug(f"Detected nested field search: {field}={value}")
            field_parts = field.split('.')
            
            # Handle metadata.* fields specially
            if field_parts[0] == 'metadata':
                nested_field = '.'.join(field_parts[1:])
                logger.debug(f"Searching in metadata field: {nested_field}={value}")
                
                # For metadata fields, try direct match first with metadata prefix
                key = (field, value)
                direct_matches = self.field_index.get(key, set())
                
                # If no direct matches, try searching in the nested field
                if not direct_matches:
                    nested_key = (nested_field, value)
                    nested_matches = self.field_index.get(nested_key, set())
                    
                    # Try text search if value is a string and no direct matches
                    if not nested_matches and isinstance(value, str):
                        field_token_key = f"{field}:{self._tokenize(value)[0]}" if self._tokenize(value) else None
                        if field_token_key and field_token_key in self.text_index:
                            nested_matches = self.text_index.get(field_token_key, set())
                            logger.debug(f"Found {len(nested_matches)} text matches for nested field: {field}")
                    
                    # If still no matches, search all documents and check metadata manually
                    if not nested_matches:
                        logger.debug(f"No indexed matches for {field}, checking all documents manually")
                        nested_matches = set()
                        for doc_id, doc in self.documents.items():
                            # Check if the document has metadata field
                            if 'metadata' in doc.fields:
                                metadata = doc.fields['metadata']
                                # Check if nested field exists in metadata with matching value
                                if nested_field in metadata and metadata[nested_field] == value:
                                    nested_matches.add(doc_id)
                    
                    logger.debug(f"Found {len(nested_matches)} matches for nested field: {nested_field}={value}")
                    return nested_matches
                
                logger.debug(f"Found {len(direct_matches)} direct matches for: {field}={value}")
                return direct_matches
        
        # Direct field match for non-nested fields
        key = (field, value)
        direct_matches = self.field_index.get(key, set())
        
        # If no direct matches and value is a string, try text search
        if not direct_matches and isinstance(value, str):
            tokens = self._tokenize(value)
            if tokens:
                # Try field-specific token search
                field_token_key = f"{field}:{tokens[0]}"
                if field_token_key in self.text_index:
                    text_matches = self.text_index.get(field_token_key, set())
                    logger.debug(f"Text field search for {field}:{tokens[0]} found {len(text_matches)} matches")
                    return text_matches
        
        # Log debugging info
        logger.debug(f"Field search: {field}={value}, found {len(direct_matches)} direct matches")
        
        return direct_matches