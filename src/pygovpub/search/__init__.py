"""
Search module for PyGovPub.

This module provides search capabilities for government documents
and other data sources.
"""

from pygovpub.search.core import SearchManager, SearchResult, SearchQuery
from pygovpub.search.parsers import QueryParser, MetadataParser
from pygovpub.search.indexing import Indexer, DocumentIndexer

__all__ = [
    'SearchManager',
    'SearchResult',
    'SearchQuery',
    'QueryParser',
    'MetadataParser',
    'Indexer',
    'DocumentIndexer',
]