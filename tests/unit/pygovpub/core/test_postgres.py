"""
Test PostgreSQL specific functionality.

This module contains tests that verify the database functionality with PostgreSQL.
These tests are skipped if PostgreSQL is not available.
"""

import os
import pytest
import json
import sqlalchemy
from sqlalchemy import Column, JSON, ARRAY, String, text
from sqlmodel import SQLModel, Field, Session, select
from typing import Optional, ClassVar, Dict, List, Any
import uuid

from pygovpub.core.database import init_db, get_connection_url
from pygovpub.core.crud import CRUDBase, create_entity, get_entity
from pygovpub.models.base import BaseTable


# Check if we can connect to PostgreSQL
def can_connect_to_postgres():
    """Check if PostgreSQL is available by trying to connect."""
    if os.environ.get("SKIP_POSTGRES_TESTS", "false").lower() == "true":
        return False
    
    try:
        # First check if PostgreSQL environment variables are set
        if not all([
            os.environ.get("DB_TYPE") == "postgresql",
            os.environ.get("DB_HOST"),
            os.environ.get("DB_NAME"),
            os.environ.get("DB_USER"),
            os.environ.get("DB_PASSWORD")
        ]):
            return False
        
        # Try to connect
        url = get_connection_url()
        engine = init_db(url)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


# Skip all tests if PostgreSQL is not available
postgres_available = pytest.mark.skipif(
    not can_connect_to_postgres(),
    reason="PostgreSQL not available or configured"
)


# Only create this model when using PostgreSQL
# This way we avoid SQLite compatibility issues with PostgreSQL-specific column types
@postgres_available
def get_postgres_test_model():
    """Create the PostgreSQL test model class with PostgreSQL-specific column types."""
    class PostgresTestModel(BaseTable, table=True):
        """Test model for PostgreSQL-specific functionality."""
        
        __tablename__ = "postgres_test_models"
        __table_args__ = {"extend_existing": True}
        
        test_id: str = Field(primary_key=True)
        name: str
        description: Optional[str] = None
        # PostgreSQL-specific JSON field
        metadata_json: Optional[Dict[str, Any]] = Field(
            default=None, 
            sa_column=Column(JSON)
        )
        # PostgreSQL-specific array field (only used in PostgreSQL tests)
        # We use ARRAY(String) instead of VARCHAR[] for better SQLAlchemy compatibility
        tags: Optional[List[str]] = Field(
            default=None,
            sa_column=Column(ARRAY(String))
        )
    
    return PostgresTestModel


@postgres_available
def test_connect_to_postgres():
    """Test connection to PostgreSQL."""
    url = get_connection_url()
    engine = init_db(url)
    
    # Verify we can execute a query
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1 as result")).scalar()
        assert result == 1


@postgres_available
def test_create_postgres_tables():
    """Test creating tables in PostgreSQL with PostgreSQL-specific column types."""
    # Get the PostgreSQL model
    PostgresTestModel = get_postgres_test_model()
    
    url = get_connection_url()
    engine = init_db(url)
    
    # Create tables
    SQLModel.metadata.drop_all(engine)  # Ensure clean state
    SQLModel.metadata.create_all(engine)
    
    # Verify tables were created
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'postgres_test_models'
            )
        """)).scalar()
        assert result is True
        
        # Check for JSONB column
        result = conn.execute(text("""
            SELECT data_type 
            FROM information_schema.columns 
            WHERE table_name = 'postgres_test_models' AND column_name = 'metadata_json'
        """)).scalar()
        assert result.lower() == "jsonb"
        
        # Check for array column
        result = conn.execute(text("""
            SELECT data_type 
            FROM information_schema.columns 
            WHERE table_name = 'postgres_test_models' AND column_name = 'tags'
        """)).scalar()
        assert "array" in result.lower()


@postgres_available
def test_postgres_crud_operations():
    """Test CRUD operations with PostgreSQL-specific data types."""
    # Get the PostgreSQL model
    PostgresTestModel = get_postgres_test_model()
    
    url = get_connection_url()
    engine = init_db(url)
    
    # Ensure tables exist
    SQLModel.metadata.create_all(engine)
    
    # Create a session
    with Session(engine) as session:
        # Test creating with JSON and array data
        test_id = str(uuid.uuid4())
        model = PostgresTestModel(
            test_id=test_id,
            name="PostgreSQL Test",
            description="Testing PostgreSQL functionality",
            metadata_json={"key1": "value1", "key2": 123, "nested": {"a": "b"}},
            tags=["tag1", "tag2", "tag3"]
        )
        session.add(model)
        session.commit()
        session.refresh(model)
        
        # Test querying with PostgreSQL-specific operators
        # Query by JSON path
        result = session.exec(
            select(PostgresTestModel).where(
                PostgresTestModel.metadata_json["key1"].as_string() == "value1"
            )
        ).one_or_none()
        assert result is not None
        assert result.test_id == test_id
        
        # Query with array contains
        result = session.exec(
            select(PostgresTestModel).where(
                PostgresTestModel.tags.contains(["tag2"])
            )
        ).one_or_none()
        assert result is not None
        assert result.test_id == test_id
        
        # Update JSON and array data
        model.metadata_json = {"updated": True, "nested": {"c": "d"}}
        model.tags = ["updated", "tags"]
        session.add(model)
        session.commit()
        session.refresh(model)
        
        # Verify update
        updated = session.get(PostgresTestModel, test_id)
        assert updated.metadata_json == {"updated": True, "nested": {"c": "d"}}
        assert updated.tags == ["updated", "tags"]
        
        # Delete
        session.delete(model)
        session.commit()
        deleted = session.get(PostgresTestModel, test_id)
        assert deleted is None


@postgres_available
def test_postgres_with_crud_module():
    """Test the CRUD module with PostgreSQL."""
    # Get the PostgreSQL model
    PostgresTestModel = get_postgres_test_model()
    
    url = get_connection_url()
    engine = init_db(url)
    
    # Ensure tables exist
    SQLModel.metadata.create_all(engine)
    
    # Create a CRUD instance
    crud = CRUDBase(PostgresTestModel)
    
    with Session(engine) as session:
        # Create
        test_id = str(uuid.uuid4())
        new_entity = crud.create(session, {
            "test_id": test_id,
            "name": "CRUD Test",
            "metadata_json": {"source": "crud_module"},
            "tags": ["crud", "test"]
        })
        assert new_entity.test_id == test_id
        
        # Read
        entity = crud.get(session, test_id)
        assert entity is not None
        assert entity.name == "CRUD Test"
        assert entity.metadata_json == {"source": "crud_module"}
        assert entity.tags == ["crud", "test"]
        
        # Update
        updated = crud.update(session, test_id, {
            "name": "Updated Name",
            "metadata_json": {"updated": True}
        })
        assert updated.name == "Updated Name"
        assert updated.metadata_json == {"updated": True}
        assert updated.tags == ["crud", "test"]  # Unchanged
        
        # Delete
        result = crud.delete(session, test_id)
        assert result is True
        
        # Verify deletion
        entity = crud.get(session, test_id)
        assert entity is None