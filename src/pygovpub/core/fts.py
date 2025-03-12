"""
Full-text search integration for PyGovPub using PostgreSQL's capabilities.

This module provides tools for implementing and using PostgreSQL's full-text search
features with SQLAlchemy models, including tsvector columns, GIN indexes, and
language-specific tokenization.
"""

import logging
import re
from typing import List, Dict, Any, Optional, Union, Type, TypeVar, Set, cast
from enum import Enum

import sqlalchemy
from sqlalchemy import Column, Table, event, text, Index
from sqlalchemy.sql import select, func, expression
from sqlalchemy.sql.expression import ClauseElement
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import Session, Query, MappedColumn
from sqlalchemy.schema import DDL
from sqlalchemy.types import UserDefinedType
from sqlmodel import SQLModel, Field

from pygovpub.core.database import get_engine

# Configure logging
logger = logging.getLogger(__name__)

# Type variables
T = TypeVar('T', bound=SQLModel)


class TSVectorType(UserDefinedType):
    """
    SQLAlchemy Type for PostgreSQL tsvector.
    
    Provides conversion between Python and PostgreSQL for tsvector columns.
    """
    
    def get_col_spec(self, **kw):
        """
        Return SQL to use for creating this column.
        """
        return "TSVECTOR"
    
    def bind_processor(self, dialect):
        """
        Return a processor that converts a value to its database form.
        """
        def process(value):
            # tsvector comes from database, no processing needed on bind
            return value
        return process
    
    def result_processor(self, dialect, coltype):
        """
        Return a processor that converts a database value to its Python form.
        """
        def process(value):
            # Return tsvector as string
            return value
        return process


class SearchLanguage(str, Enum):
    """Supported languages for full-text search."""
    ENGLISH = "english"
    SPANISH = "spanish"
    FRENCH = "french"
    GERMAN = "german"
    RUSSIAN = "russian"
    SIMPLE = "simple"  # Language-agnostic


class SearchWeightCategory(str, Enum):
    """Weight categories for search ranking (A=highest, D=lowest)."""
    A = "A"  # Most important text (e.g., titles)
    B = "B"  # Important text (e.g., summaries)
    C = "C"  # Regular content
    D = "D"  # Less important content (e.g., footnotes)


class FTSConfigType(str, Enum):
    """Configuration types for full-text search."""
    STANDARD = "standard"      # Default configuration for the language
    PHRASE = "phrase"          # Better for exact phrase matching
    LEGISLATIVE = "legislative"  # Custom for legislative content


class FullTextSearchable:
    """
    Mixin for SQLModel classes to make them full-text searchable.
    
    Adds tsvector column and GIN index for PostgreSQL full-text search.
    
    Example:
        ```python
        class Bill(SQLModel, FullTextSearchable, table=True):
            __tablename__ = "bills"
            
            id: int = Field(primary_key=True)
            title: str
            description: str
            
            __searchable_columns__ = {
                "title": {"weight": SearchWeightCategory.A},
                "description": {"weight": SearchWeightCategory.B}
            }
            __search_language__ = SearchLanguage.ENGLISH
        ```
    """
    
    __searchable_columns__: Dict[str, Dict[str, Any]] = {}
    __search_language__: SearchLanguage = SearchLanguage.ENGLISH
    __fts_config_type__: FTSConfigType = FTSConfigType.STANDARD
    __search_triggers_created__: bool = False
    
    @declared_attr
    def search_vector(cls):
        """
        Define the tsvector column for full-text search.
        """
        return Column(TSVectorType, nullable=True)
    
    @classmethod
    def create_search_index(cls, engine=None):
        """
        Create GIN index for the search_vector column.
        
        Args:
            engine: SQLAlchemy engine to use (defaults to global engine)
        """
        engine = engine or get_engine()
        
        # Get table information
        table_name = cls.__tablename__
        index_name = f"idx_{table_name}_search_vector"
        
        # Create GIN index SQL
        sql = f"""
        CREATE INDEX IF NOT EXISTS {index_name} 
        ON {table_name} USING GIN(search_vector);
        """
        
        # Execute statement
        with engine.connect() as conn:
            conn.execute(text(sql))
            conn.commit()
        
        logger.info(f"Created GIN index {index_name} on {table_name}.search_vector")
    
    @classmethod
    def create_search_triggers(cls, engine=None):
        """
        Create triggers to automatically update search_vector on insert/update.
        
        Args:
            engine: SQLAlchemy engine to use (defaults to global engine)
        """
        if cls.__search_triggers_created__:
            return
        
        engine = engine or get_engine()
        
        # Get table information
        table_name = cls.__tablename__
        
        # Build the tsvector update expression
        update_parts = []
        for col_name, col_config in cls.__searchable_columns__.items():
            weight = col_config.get("weight", SearchWeightCategory.D)
            update_parts.append(
                f"setweight(to_tsvector('{cls.__search_language__}', COALESCE(NEW.{col_name}, '')), '{weight}')"
            )
        
        if not update_parts:
            logger.warning(f"No searchable columns defined for {cls.__name__}")
            return
        
        # Join parts with || operator (tsvector concatenation)
        update_expression = " || ".join(update_parts)
        
        # Create trigger function
        function_name = f"{table_name}_search_vector_update"
        trigger_name = f"{table_name}_search_trigger"
        
        function_sql = f"""
        CREATE OR REPLACE FUNCTION {function_name}() RETURNS TRIGGER AS $$
        BEGIN
            NEW.search_vector = {update_expression};
            RETURN NEW;
        END
        $$ LANGUAGE plpgsql;
        """
        
        # Create trigger
        trigger_sql = f"""
        DROP TRIGGER IF EXISTS {trigger_name} ON {table_name};
        CREATE TRIGGER {trigger_name}
        BEFORE INSERT OR UPDATE ON {table_name}
        FOR EACH ROW EXECUTE FUNCTION {function_name}();
        """
        
        # Execute statements
        with engine.connect() as conn:
            conn.execute(text(function_sql))
            conn.execute(text(trigger_sql))
            conn.commit()
        
        cls.__search_triggers_created__ = True
        logger.info(f"Created search triggers for {table_name}")
    
    @classmethod
    def update_existing_records(cls, session: Session):
        """
        Update search_vector for all existing records.
        
        Args:
            session: SQLAlchemy session
        """
        if not cls.__searchable_columns__:
            logger.warning(f"No searchable columns defined for {cls.__name__}")
            return
        
        # Build the tsvector update expression
        update_parts = []
        for col_name, col_config in cls.__searchable_columns__.items():
            weight = col_config.get("weight", SearchWeightCategory.D)
            update_parts.append(
                f"setweight(to_tsvector('{cls.__search_language__}', COALESCE({col_name}, '')), '{weight}')"
            )
        
        # Join parts with || operator (tsvector concatenation)
        update_expression = " || ".join(update_parts)
        
        # Update all records
        update_sql = f"""
        UPDATE {cls.__tablename__}
        SET search_vector = {update_expression};
        """
        
        session.execute(text(update_sql))
        session.commit()
        
        logger.info(f"Updated search_vector for all existing records in {cls.__tablename__}")


def setup_fts_legislative_configuration(engine=None):
    """
    Create a custom PostgreSQL text search configuration for legislative documents.
    
    This creates a custom configuration that handles specific legislative terminology,
    legal citations, and reference formats.
    
    Args:
        engine: SQLAlchemy engine to use (defaults to global engine)
    """
    engine = engine or get_engine()
    
    # Create custom configuration based on english
    config_sql = """
    -- Create legislative configuration based on english
    CREATE TEXT SEARCH CONFIGURATION IF NOT EXISTS legislative (COPY = english);
    
    -- Add custom dictionaries for legal terms
    CREATE TEXT SEARCH DICTIONARY legislative_dict (
        TEMPLATE = synonym,
        SYNONYMS = legislative_dict
    );
    
    -- Create synonym file if it doesn't exist
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_ts_dict WHERE dictname = 'legislative_dict'
        ) THEN
            -- Create synonym dictionary file
            CREATE TABLE _temp_legislative_syn (line text);
            INSERT INTO _temp_legislative_syn VALUES
                ('USC,United States Code'),
                ('CFR,Code of Federal Regulations'),
                ('FR,Federal Register'),
                ('Stat,Statutes at Large');
                
            -- Write to file using COPY
            COPY _temp_legislative_syn TO '/tmp/legislative_dict.syn';
            DROP TABLE _temp_legislative_syn;
        END IF;
    EXCEPTION WHEN OTHERS THEN
        -- If file operations fail, just log the error
        RAISE NOTICE 'Could not create synonym file: %', SQLERRM;
    END $$;
    
    -- Map dictionaries
    ALTER TEXT SEARCH CONFIGURATION legislative
        ALTER MAPPING FOR asciiword, word, numword, asciihword, hword, numhword
        WITH legislative_dict, english_stem;
    """
    
    try:
        with engine.connect() as conn:
            conn.execute(text(config_sql))
            conn.commit()
        logger.info("Created legislative full-text search configuration")
    except Exception as e:
        logger.error(f"Failed to create legislative search configuration: {e}")
        # Fallback to standard configuration
        logger.info("Using standard configuration for legislative content")


def search_query(model_class: Type[T], search_term: str, 
                language: Optional[SearchLanguage] = None,
                filter_condition: Optional[ClauseElement] = None) -> Query:
    """
    Create a full-text search query for a model.
    
    Args:
        model_class: The SQLModel class to search (must use FullTextSearchable)
        search_term: Text to search for
        language: Language for search (defaults to model's language)
        filter_condition: Additional filter conditions
    
    Returns:
        SQLAlchemy Query object with search results ordered by rank
    
    Example:
        ```python
        query = search_query(Bill, "healthcare reform")
        results = session.execute(query).scalars().all()
        ```
    """
    if not issubclass(model_class, FullTextSearchable):
        raise TypeError(f"{model_class.__name__} must inherit from FullTextSearchable")
    
    # Use model's language if not specified
    search_language = language or model_class.__search_language__
    
    # Parse search term and apply tsquery conversion
    processed_term = process_search_term(search_term)
    
    # Build the query
    query = select(model_class).where(
        model_class.search_vector.op('@@')(
            func.to_tsquery(search_language, processed_term)
        )
    )
    
    # Add additional filter if provided
    if filter_condition is not None:
        query = query.where(filter_condition)
    
    # Add ranking
    ts_rank = func.ts_rank(
        model_class.search_vector,
        func.to_tsquery(search_language, processed_term)
    ).label('rank')
    
    query = query.order_by(sqlalchemy.desc(ts_rank))
    
    return query


def process_search_term(search_term: str) -> str:
    """
    Process a search term for use with to_tsquery.
    
    Args:
        search_term: Raw search term from user
    
    Returns:
        Processed search term for to_tsquery
    """
    # Remove special characters except allowed operators
    clean_term = re.sub(r'[^\w\s&|!:*()"-]', '', search_term)
    
    # Replace spaces with & for AND operations if no explicit operators
    if not any(op in clean_term for op in ['&', '|', '!']):
        words = clean_term.split()
        clean_term = ' & '.join(words)
    
    return clean_term


def highlight_search_results(text: str, search_term: str, 
                           language: SearchLanguage = SearchLanguage.ENGLISH,
                           max_fragments: int = 2) -> List[str]:
    """
    Generate highlighted fragments of text containing search matches.
    
    Args:
        text: Full text to search in
        search_term: Search term to highlight
        language: Language for search
        max_fragments: Maximum number of fragments to return
    
    Returns:
        List of text fragments with highlights
    
    Example:
        ```python
        bill_text = "The healthcare reform initiative will improve access..."
        highlights = highlight_search_results(bill_text, "healthcare reform")
        ```
    """
    engine = get_engine()
    
    # Process search term
    processed_term = process_search_term(search_term)
    
    # Use PostgreSQL's ts_headline function
    highlight_sql = text("""
    SELECT ts_headline(:language, :text, to_tsquery(:language, :query),
                      'MaxFragments=:max_fragments, FragmentDelimiter=" ... "')
    """)
    
    with engine.connect() as conn:
        result = conn.execute(
            highlight_sql, 
            {
                "language": language,
                "text": text,
                "query": processed_term,
                "max_fragments": max_fragments
            }
        )
        headline = result.scalar()
    
    # Split into fragments
    if headline:
        return headline.split(" ... ")
    return []


# Initialize FTS environment when this module is imported
engine = get_engine()
try:
    setup_fts_legislative_configuration(engine)
except Exception as e:
    logger.error(f"Failed to initialize FTS environment: {e}")
    logger.info("Basic FTS functionality will still be available")