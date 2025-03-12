"""
Database fixtures for testing in PyGovPub.

This module provides specialized database fixtures for testing complex 
database operations, including versioned records, relationships,
and full-text search content.
"""

import logging
import random
import copy
import contextlib
import threading
from typing import Dict, List, Any, Optional, Union, Callable, Type, TypeVar, Set, Tuple
from datetime import datetime, timedelta
from enum import Enum
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor

import sqlalchemy
from sqlalchemy import text, exc, event, inspect
from sqlalchemy.orm import Session, Query, sessionmaker
from sqlalchemy.sql import Select
from sqlmodel import SQLModel, Field

from pygovpub.core.database import get_engine, with_transaction

# Configure logging
logger = logging.getLogger(__name__)

# Type variables
T = TypeVar('T', bound=SQLModel)


class PermissionDeniedError(Exception):
    """Error raised when attempting write operations on a read-only session."""
    pass


class ReadOnlySession(Session):
    """
    Read-only SQLAlchemy session that raises errors on write attempts.
    
    This session class is useful for testing code that should not modify data.
    """
    
    def __init__(self, *args, **kwargs):
        """Initialize read-only session."""
        super().__init__(*args, **kwargs)
        self.read_only = True
    
    def add(self, instance, _warn=True):
        """Override add to prevent writes."""
        if self.read_only:
            raise PermissionDeniedError("Cannot add to a read-only session")
        super().add(instance, _warn=_warn)
    
    def add_all(self, instances):
        """Override add_all to prevent writes."""
        if self.read_only:
            raise PermissionDeniedError("Cannot add_all to a read-only session")
        super().add_all(instances)
    
    def delete(self, instance):
        """Override delete to prevent writes."""
        if self.read_only:
            raise PermissionDeniedError("Cannot delete from a read-only session")
        super().delete(instance)
    
    def commit(self):
        """Override commit to prevent writes."""
        if self.read_only:
            raise PermissionDeniedError("Cannot commit to a read-only session")
        super().commit()
    
    def execute(self, statement, params=None, **kw):
        """Override execute to prevent writes."""
        # Allow all SELECT statements
        if isinstance(statement, (Select, sqlalchemy.sql.selectable.Select)):
            return super().execute(statement, params, **kw)
        
        # For text/string statements, check if it's a SELECT
        if isinstance(statement, (str, sqlalchemy.sql.elements.TextClause)):
            stmt_str = str(statement).strip().upper()
            if stmt_str.startswith("SELECT"):
                return super().execute(statement, params, **kw)
        
        # Block all other statements in read-only mode
        if self.read_only:
            raise PermissionDeniedError("Cannot execute write operations in a read-only session")
        
        return super().execute(statement, params, **kw)


def create_read_only_session(engine=None):
    """
    Create a read-only database session.
    
    Args:
        engine: SQLAlchemy engine (uses default engine if None)
    
    Returns:
        ReadOnlySession instance
    
    Example:
        ```python
        session = create_read_only_session()
        try:
            # This will work
            results = session.query(Bill).all()
            
            # This will raise PermissionDeniedError
            session.add(Bill(title="New Bill"))
            session.commit()
        except PermissionDeniedError as e:
            print(f"Write operation blocked: {e}")
        ```
    """
    engine = engine or get_engine()
    session = ReadOnlySession(bind=engine)
    return session


@contextmanager
def with_multi_database(database_names: List[str], engine=None):
    """
    Context manager for testing with multiple database connections.
    
    Args:
        database_names: List of database names/aliases to create sessions for
        engine: Base SQLAlchemy engine (uses default engine if None)
    
    Yields:
        Dictionary mapping database names to Session objects
    
    Example:
        ```python
        with with_multi_database(["primary", "replica"]) as sessions:
            # Primary database operations
            sessions["primary"].add(Bill(title="New Bill"))
            sessions["primary"].commit()
            
            # Replica database operations
            results = sessions["replica"].query(Bill).all()
        ```
    """
    engine = engine or get_engine()
    sessions = {}
    
    try:
        # Create a session for each database name
        for db_name in database_names:
            # In a real implementation, you would create connections to different databases
            # For testing, we'll just create separate sessions on the same engine
            sessions[db_name] = Session(bind=engine)
        
        yield sessions
    finally:
        # Close all sessions
        for session in sessions.values():
            session.close()


def create_versioned_records(
    model_class: Type[T],
    base_record: Dict[str, Any],
    versions: int = 3,
    version_changes: Dict[str, Union[List[Any], Callable[[int, Dict[str, Any]], Any]]] = None,
    engine=None
) -> List[Dict[str, Any]]:
    """
    Create versioned records for testing.
    
    Args:
        model_class: SQLModel class to create instances of
        base_record: Base record data dictionary
        versions: Number of versions to create
        version_changes: Map of field names to either:
                         - List of values (one per version)
                         - Callable that takes version number and record and returns value
        engine: SQLAlchemy engine (uses default engine if None)
    
    Returns:
        List of created record dictionaries
    
    Example:
        ```python
        bills = create_versioned_records(
            Bill,
            {
                "id": 1,
                "congress": 117,
                "bill_number": 1234,
                "bill_type": "HR",
                "title": "Initial Bill",
                "status": "INTRODUCED"
            },
            versions=3,
            version_changes={
                "title": ["Initial Bill", "Amended Bill", "Final Bill"],
                "status": ["INTRODUCED", "REPORTED", "PASSED"],
                "updated_at": lambda v, r: datetime.now() + timedelta(days=v*10)
            }
        )
        ```
    """
    engine = engine or get_engine()
    version_changes = version_changes or {}
    records = []
    
    # Make a deep copy of the base record to avoid modifying the original
    current_record = copy.deepcopy(base_record)
    
    # Create each version
    for version in range(1, versions + 1):
        # Set version field if model has one
        if hasattr(model_class, "version"):
            current_record["version"] = version
        
        # Apply version-specific changes
        for field, value_or_func in version_changes.items():
            if callable(value_or_func):
                # Call function to get value
                current_record[field] = value_or_func(version, current_record)
            elif isinstance(value_or_func, list) and len(value_or_func) >= version:
                # Use value from list
                current_record[field] = value_or_func[version - 1]
        
        # Save record to database
        with with_transaction() as session:
            # Check if record already exists
            if "id" in current_record:
                existing = session.get(model_class, current_record["id"])
                if existing and hasattr(existing, "version"):
                    existing_version = getattr(existing, "version")
                    if existing_version == version:
                        # Update existing record
                        for key, value in current_record.items():
                            setattr(existing, key, value)
                        session.add(existing)
                        # Add updated record to result
                        records.append(copy.deepcopy(current_record))
                        continue
            
            # Create new record
            instance = model_class(**current_record)
            session.add(instance)
        
        # Add record to result
        records.append(copy.deepcopy(current_record))
    
    return records


def create_relationship_test_data(
    models: Dict[str, Type[SQLModel]],
    relationships: List[Tuple[str, str, str, str]],
    counts: Dict[str, int],
    distribution: Dict[str, List[int]] = None,
    engine=None
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Create complex relationship test data.
    
    Args:
        models: Dictionary mapping entity names to SQLModel classes
        relationships: List of (from_entity, from_field, to_entity, to_field) tuples
        counts: Dictionary mapping entity names to number of instances to create
        distribution: Dictionary mapping relationship distribution keys to instance counts
                     (e.g., {"documents_per_author": [2, 1]} means first author gets 2 docs, second gets 1)
        engine: SQLAlchemy engine (uses default engine if None)
    
    Returns:
        Dictionary mapping entity names to lists of created instances
    
    Example:
        ```python
        data = create_relationship_test_data(
            models={"authors": Author, "documents": Document, "tags": Tag},
            relationships=[
                ("documents", "author_id", "authors", "id"),
                ("document_tags", "document_id", "documents", "id"),
                ("document_tags", "tag_id", "tags", "id")
            ],
            counts={"authors": 3, "documents": 5, "tags": 10, "document_tags": 15},
            distribution={
                "documents_per_author": [2, 2, 1],
                "tags_per_document": [3, 3, 3, 3, 3]
            }
        )
        ```
    """
    engine = engine or get_engine()
    distribution = distribution or {}
    result = {}
    
    # Construct a relationship graph
    relationship_map = {}
    for from_entity, from_field, to_entity, to_field in relationships:
        if from_entity not in relationship_map:
            relationship_map[from_entity] = []
        relationship_map[from_entity].append({
            "from_field": from_field,
            "to_entity": to_entity,
            "to_field": to_field
        })
    
    # Dependency sorting
    dependency_order = []
    visited = set()
    
    def visit(entity):
        if entity in visited:
            return
        visited.add(entity)
        
        # Visit dependencies first
        if entity in relationship_map:
            for rel in relationship_map[entity]:
                visit(rel["to_entity"])
        
        dependency_order.append(entity)
    
    # Visit all entities to build dependency order
    for entity in models:
        visit(entity)
    
    # Create instances in dependency order
    with with_transaction() as session:
        for entity in dependency_order:
            if entity not in models or entity not in counts:
                continue
            
            model_class = models[entity]
            entity_count = counts[entity]
            instances = []
            
            # Generate base field data
            for i in range(entity_count):
                instance_data = {}
                
                # Add ID field if applicable
                if hasattr(model_class, "id"):
                    instance_data["id"] = i + 1
                
                # Add basic fields
                for field_name, field in inspect(model_class).c.items():
                    if field_name == "id":
                        continue
                    
                    # Skip relationship fields
                    if field_name.endswith("_id"):
                        continue
                    
                    # Generate appropriate data based on field type
                    field_type = str(field.type)
                    if "CHAR" in field_type or "VARCHAR" in field_type or "TEXT" in field_type:
                        instance_data[field_name] = f"{entity.title()} {i + 1} {field_name}"
                    elif "INT" in field_type:
                        instance_data[field_name] = i + 1
                    elif "TIMESTAMP" in field_type or "DATE" in field_type:
                        instance_data[field_name] = datetime.now()
                    elif "BOOLEAN" in field_type:
                        instance_data[field_name] = i % 2 == 0
                
                instances.append(instance_data)
            
            # Apply relationship constraints
            if entity in relationship_map:
                for i, instance_data in enumerate(instances):
                    for rel in relationship_map[entity]:
                        to_entity = rel["to_entity"]
                        to_field = rel["to_field"]
                        from_field = rel["from_field"]
                        
                        # If the target entity has been created
                        if to_entity in result:
                            target_instances = result[to_entity]
                            
                            # Apply distribution if specified
                            dist_key = f"{entity}_per_{to_entity}"
                            if dist_key in distribution and i < len(distribution[dist_key]):
                                target_count = distribution[dist_key][i]
                                target_pool = target_instances[:target_count]
                            else:
                                # Use round-robin distribution
                                target_idx = i % len(target_instances)
                                target_pool = [target_instances[target_idx]]
                            
                            # Set relationship field
                            if target_pool:
                                target = random.choice(target_pool)
                                instance_data[from_field] = target[to_field]
            
            # Store created data
            result[entity] = instances
            
            # Create instances in database
            for instance_data in instances:
                instance = model_class(**instance_data)
                session.add(instance)
    
    return result


# Common legislative terminology for generating realistic content
LEGISLATIVE_TERMS = {
    "healthcare": [
        "healthcare reform", "medical insurance", "coverage expansion",
        "pre-existing conditions", "patient protection", "affordable care",
        "medicare", "medicaid", "health savings account", "prescription drugs"
    ],
    "environment": [
        "environmental protection", "climate change", "emissions reduction",
        "renewable energy", "clean water act", "endangered species",
        "conservation", "EPA", "carbon tax", "wilderness preservation"
    ],
    "tax": [
        "tax reform", "income tax", "tax credit", "tax deduction",
        "corporate tax", "capital gains", "estate tax", "tax exemption",
        "tax bracket", "revenue"
    ],
    "infrastructure": [
        "infrastructure investment", "transportation funding", "highway trust fund",
        "public transit", "bridges", "airports", "water systems",
        "broadband expansion", "electric grid", "public works"
    ],
    "education": [
        "education funding", "student loans", "higher education",
        "elementary education", "school choice", "teachers", "scholarships",
        "STEM", "community college", "vocational training"
    ]
}

BILL_TYPES = ["HR", "S", "HRES", "SRES", "HJRES", "SJRES", "HCONRES", "SCONRES"]
BILL_STATUS = ["INTRODUCED", "REFERRED", "REPORTED", "FLOOR", "PASSED", "ENACTED"]
BILL_VERSION_CODES = ["IH", "IS", "RH", "RS", "EH", "ES", "PL"]


def create_legislative_text_corpus(
    count: int = 10,
    topics: List[str] = None,
    include_metadata: bool = True,
    congress: int = 117,
    min_length: int = 100,
    max_length: int = 1000,
    engine=None
) -> List[Dict[str, Any]]:
    """
    Create a corpus of legislative text for testing full-text search.
    
    Args:
        count: Number of documents to create
        topics: List of topics to include (from LEGISLATIVE_TERMS)
        include_metadata: Whether to include metadata in result
        congress: Congress number for metadata
        min_length: Minimum text length
        max_length: Maximum text length
        engine: SQLAlchemy engine (uses default engine if None)
    
    Returns:
        List of dictionaries with title, text, and optional metadata
    
    Example:
        ```python
        corpus = create_legislative_text_corpus(
            count=20,
            topics=["healthcare", "environment"],
            include_metadata=True
        )
        ```
    """
    topics = topics or list(LEGISLATIVE_TERMS.keys())
    corpus = []
    
    # Ensure requested topics exist
    valid_topics = [t for t in topics if t in LEGISLATIVE_TERMS]
    if not valid_topics:
        valid_topics = list(LEGISLATIVE_TERMS.keys())
    
    for i in range(count):
        # Select a random topic
        topic = random.choice(valid_topics)
        topic_terms = LEGISLATIVE_TERMS[topic]
        
        # Generate a title
        title_term = random.choice(topic_terms)
        title = f"{title_term.title()} Act of {2020 + random.randint(0, 5)}"
        
        # Generate text
        paragraphs = []
        text_length = random.randint(min_length, max_length)
        remaining_length = text_length
        
        while remaining_length > 0:
            # Generate a paragraph
            sentences = []
            paragraph_length = min(remaining_length, random.randint(50, 200))
            paragraph_remaining = paragraph_length
            
            while paragraph_remaining > 0:
                # Generate a sentence
                terms = random.sample(topic_terms, min(3, len(topic_terms)))
                sentence = f"This legislation addresses {', '.join(terms)}. "
                sentences.append(sentence)
                paragraph_remaining -= len(sentence)
            
            paragraph = "".join(sentences)
            paragraphs.append(paragraph)
            remaining_length -= len(paragraph)
        
        text = "\n\n".join(paragraphs)
        
        # Create document
        document = {
            "title": title,
            "text": text
        }
        
        # Add metadata if requested
        if include_metadata:
            document["metadata"] = {
                "congress": congress,
                "bill_type": random.choice(BILL_TYPES),
                "bill_number": random.randint(1, 9999),
                "status": random.choice(BILL_STATUS),
                "version_code": random.choice(BILL_VERSION_CODES),
                "introduced_date": datetime.now() - timedelta(days=random.randint(0, 365)),
                "topic": topic
            }
        
        corpus.append(document)
    
    return corpus


def create_bill_hierarchy(
    congress: int = 117,
    bill_type: str = "HR",
    bill_number: int = 1234,
    version_count: int = 3,
    action_count: int = 5,
    sponsor_count: int = 2,
    engine=None
) -> Dict[str, Any]:
    """
    Create a bill hierarchy with versions, actions, and sponsors.
    
    Args:
        congress: Congress number
        bill_type: Bill type code
        bill_number: Bill number
        version_count: Number of versions to create
        action_count: Number of actions to create
        sponsor_count: Number of sponsors to create
        engine: SQLAlchemy engine (uses default engine if None)
    
    Returns:
        Dictionary with bill, versions, actions, and sponsors
    
    Example:
        ```python
        bill_data = create_bill_hierarchy(
            congress=117,
            bill_type="HR",
            bill_number=1234,
            version_count=3,
            action_count=5,
            sponsor_count=2
        )
        ```
    """
    # Determine topic
    topic = random.choice(list(LEGISLATIVE_TERMS.keys()))
    topic_terms = LEGISLATIVE_TERMS[topic]
    title_term = random.choice(topic_terms)
    title = f"{title_term.title()} Act of {2020 + random.randint(0, 5)}"
    
    # Create bill
    bill = {
        "id": 1,
        "congress": congress,
        "bill_type": bill_type,
        "bill_number": bill_number,
        "title": title,
        "introduced_date": datetime.now() - timedelta(days=random.randint(0, 365)),
        "status": "INTRODUCED"
    }
    
    # Create versions
    versions = []
    version_codes = ["IH", "RH", "EH"] if bill_type.startswith("H") else ["IS", "RS", "ES"]
    version_titles = [
        "Introduced in House", "Reported in House", "Engrossed in House"
    ] if bill_type.startswith("H") else [
        "Introduced in Senate", "Reported in Senate", "Engrossed in Senate"
    ]
    
    for i in range(min(version_count, len(version_codes))):
        versions.append({
            "id": i + 1,
            "bill_id": 1,
            "version_code": version_codes[i],
            "title": version_titles[i],
            "created_at": datetime.now() - timedelta(days=random.randint(0, 300))
        })
    
    # Create actions
    actions = []
    action_codes = ["INTRO", "CMTEE", "REPORT", "FLOOR", "VOTE", "PASS"]
    action_texts = [
        "Introduced in House", 
        "Referred to Committee", 
        "Reported by Committee",
        "Placed on House Calendar",
        "Considered and Voted on",
        "Passed House"
    ] if bill_type.startswith("H") else [
        "Introduced in Senate", 
        "Referred to Committee", 
        "Reported by Committee",
        "Placed on Senate Calendar",
        "Considered and Voted on",
        "Passed Senate"
    ]
    
    for i in range(min(action_count, len(action_codes))):
        actions.append({
            "id": i + 1,
            "bill_id": 1,
            "action_code": action_codes[i],
            "text": action_texts[i],
            "action_date": datetime.now() - timedelta(days=random.randint(0, 300))
        })
    
    # Create sponsors
    sponsors = []
    for i in range(sponsor_count):
        sponsors.append({
            "id": i + 1,
            "bill_id": 1,
            "name": f"Representative Smith{i}" if bill_type.startswith("H") else f"Senator Jones{i}",
            "is_primary": i == 0,
            "state": random.choice(["CA", "NY", "TX", "FL", "IL"]),
            "sponsor_date": datetime.now() - timedelta(days=random.randint(0, 365))
        })
    
    return {
        "bill": bill,
        "versions": versions,
        "actions": actions,
        "sponsors": sponsors
    }


def cleanup_fixtures(tables: List[str] = None, engine=None):
    """
    Clean up test fixtures by truncating specified tables.
    
    Args:
        tables: List of table names to truncate (defaults to all tables)
        engine: SQLAlchemy engine (uses default engine if None)
    
    Example:
        ```python
        cleanup_fixtures(["test_authors", "test_documents"])
        ```
    """
    engine = engine or get_engine()
    
    if not tables:
        # Get all tables
        inspector = sqlalchemy.inspect(engine)
        tables = inspector.get_table_names()
    
    # Truncate each table
    with engine.connect() as conn:
        for table in tables:
            try:
                conn.execute(text(f"TRUNCATE TABLE {table} CASCADE"))
                logger.debug(f"Truncated table {table}")
            except exc.SQLAlchemyError as e:
                logger.warning(f"Error truncating table {table}: {e}")
        
        conn.commit()
    
    logger.info(f"Cleaned up {len(tables)} tables")