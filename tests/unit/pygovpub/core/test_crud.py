"""
Test suite for CRUD operations.

This module tests the generic CRUD operations for database entities.
"""

import pytest
import uuid
from typing import Optional, List, Any, Dict, Type
from sqlmodel import Field, SQLModel, Session, select, create_engine
from unittest.mock import patch, MagicMock

from pygovpub.core.database import init_db, with_transaction
from pygovpub.core.crud import (
    CRUDBase,
    create_entity,
    get_entity,
    get_entities,
    update_entity,
    delete_entity,
    count_entities
)
from pygovpub.models.base import BaseTable


# Define a test model outside of the test class to avoid warning
class TestCrudModel(BaseTable, table=True):
    """Test model for CRUD operations."""
    
    __tablename__ = "test_crud_models"
    __table_args__ = {"extend_existing": True}
    
    id: Optional[int] = None
    entity_id: str = Field(primary_key=True)
    name: str
    description: Optional[str] = None
    is_active: bool = True
    
    # Avoid the __init__ constructor warning
    model_config = {
        "arbitrary_types_allowed": True
    }


@pytest.fixture
def test_db():
    """Setup a test database with tables."""
    # Create a unique in-memory SQLite database
    db_url = f"sqlite:///:memory:{uuid.uuid4()}"
    engine = init_db(db_url)
    
    # Create TestCrudModel table explicitly
    SQLModel.metadata.create_all(engine, tables=[TestCrudModel.__table__])
    
    return engine


@pytest.fixture
def sample_entities():
    """Create sample entities for testing."""
    return [
        TestCrudModel(
            entity_id=f"test-{i}",
            name=f"Test Entity {i}",
            description=f"Description for entity {i}" if i % 2 == 0 else None,
            is_active=i % 3 != 0
        )
        for i in range(10)
    ]


def test_create_entity(test_db):
    """Test creating a new entity."""
    # Create an entity
    entity_data = {
        "entity_id": "test-create",
        "name": "Test Create",
        "description": "Test description"
    }
    
    with Session(test_db) as session:
        new_entity = create_entity(session, TestCrudModel, entity_data)
        
        # Verify entity was created with correct data
        assert new_entity.entity_id == "test-create"
        assert new_entity.name == "Test Create"
        assert new_entity.description == "Test description"
        assert new_entity.is_active is True  # Default value
        
        # Verify entity exists in database
        db_entity = session.get(TestCrudModel, "test-create")
        assert db_entity is not None
        assert db_entity.entity_id == new_entity.entity_id
        assert db_entity.name == new_entity.name


def test_get_entity(test_db, sample_entities):
    """Test retrieving a single entity."""
    # Add sample entities to database
    with Session(test_db) as session:
        for entity in sample_entities:
            session.add(entity)
        session.commit()
        
        # Get a specific entity
        entity = get_entity(session, TestCrudModel, "test-3")
        assert entity is not None
        assert entity.entity_id == "test-3"
        assert entity.name == "Test Entity 3"
        
        # Try to get a non-existent entity
        non_existent = get_entity(session, TestCrudModel, "non-existent")
        assert non_existent is None


def test_get_entities(test_db, sample_entities):
    """Test retrieving multiple entities with filtering."""
    # Add sample entities to database
    with Session(test_db) as session:
        for entity in sample_entities:
            session.add(entity)
        session.commit()
        
        # Get all entities
        all_entities = get_entities(session, TestCrudModel)
        assert len(all_entities) == 10
        
        # Count active entities to ensure we have the right number for the assertion
        active_count = sum(1 for e in sample_entities if e.is_active)
        
        # Get entities with filtering
        active_entities = get_entities(
            session, 
            TestCrudModel, 
            filters={"is_active": True}
        )
        assert len(active_entities) == active_count
        
        # Count active entities with no description
        filtered_count = sum(1 for e in sample_entities if e.is_active and e.description is None)
        
        # Get entities with multiple filters
        filtered_entities = get_entities(
            session,
            TestCrudModel,
            filters={"is_active": True, "description": None}
        )
        assert len(filtered_entities) == filtered_count
        
        # Test limit
        limited_entities = get_entities(
            session,
            TestCrudModel,
            limit=5
        )
        assert len(limited_entities) == 5
        
        # Test skip
        skipped_entities = get_entities(
            session,
            TestCrudModel,
            skip=5
        )
        assert len(skipped_entities) == 5
        assert skipped_entities[0].entity_id == "test-5"
        
        # Test ordering
        ordered_entities = get_entities(
            session,
            TestCrudModel,
            order_by="name",
            descending=True
        )
        assert ordered_entities[0].name > ordered_entities[1].name


def test_update_entity(test_db, sample_entities):
    """Test updating an entity."""
    # Add sample entities to database
    with Session(test_db) as session:
        for entity in sample_entities:
            session.add(entity)
        session.commit()
        
        # Update an entity
        update_data = {
            "name": "Updated Name",
            "description": "Updated description",
            "is_active": False
        }
        
        updated = update_entity(
            session,
            TestCrudModel,
            "test-2",
            update_data
        )
        
        # Verify entity was updated
        assert updated is not None
        assert updated.entity_id == "test-2"
        assert updated.name == "Updated Name"
        assert updated.description == "Updated description"
        assert updated.is_active is False
        
        # Verify entity is updated in database
        db_entity = session.get(TestCrudModel, "test-2")
        assert db_entity.name == "Updated Name"
        
        # Test partial update
        partial_update = {
            "name": "Partially Updated"
        }
        
        partially_updated = update_entity(
            session,
            TestCrudModel,
            "test-2",
            partial_update
        )
        
        # Verify only specified fields were updated
        assert partially_updated.name == "Partially Updated"
        assert partially_updated.description == "Updated description"  # Unchanged
        assert partially_updated.is_active is False  # Unchanged
        
        # Test updating non-existent entity
        non_existent = update_entity(
            session,
            TestCrudModel,
            "non-existent",
            update_data
        )
        assert non_existent is None


def test_delete_entity(test_db, sample_entities):
    """Test deleting an entity."""
    # Add sample entities to database
    with Session(test_db) as session:
        for entity in sample_entities:
            session.add(entity)
        session.commit()
        
        # Delete an entity
        result = delete_entity(session, TestCrudModel, "test-4")
        assert result is True
        
        # Verify entity no longer exists
        entity = session.get(TestCrudModel, "test-4")
        assert entity is None
        
        # Verify other entities still exist
        remaining = session.exec(select(TestCrudModel)).all()
        assert len(remaining) == 9
        
        # Test deleting non-existent entity
        result = delete_entity(session, TestCrudModel, "non-existent")
        assert result is False


def test_count_entities(test_db, sample_entities):
    """Test counting entities."""
    # Add sample entities to database
    with Session(test_db) as session:
        for entity in sample_entities:
            session.add(entity)
        session.commit()
        
        # Count all entities
        count = count_entities(session, TestCrudModel)
        assert count == 10
        
        # Calculate expected counts from sample_entities
        expected_active_count = sum(1 for e in sample_entities if e.is_active)
        expected_filtered_count = sum(1 for e in sample_entities if e.is_active and e.description is None)
        
        # Count with filter
        active_count = count_entities(
            session,
            TestCrudModel,
            filters={"is_active": True}
        )
        assert active_count == expected_active_count
        
        # Count with multiple filters
        filtered_count = count_entities(
            session,
            TestCrudModel,
            filters={"is_active": True, "description": None}
        )
        assert filtered_count == expected_filtered_count


def test_crud_base_class(test_db, sample_entities):
    """Test the CRUDBase class."""
    # Create a CRUD instance
    crud = CRUDBase(TestCrudModel)
    
    # Add sample entities to database
    with Session(test_db) as session:
        for entity in sample_entities:
            session.add(entity)
        session.commit()
        
        # Test create
        new_data = {
            "entity_id": "crud-test",
            "name": "CRUD Test Entity",
            "description": "Testing CRUD base class"
        }
        
        new_entity = crud.create(session, new_data)
        assert new_entity.entity_id == "crud-test"
        assert new_entity.name == "CRUD Test Entity"
        
        # Test get
        entity = crud.get(session, "crud-test")
        assert entity is not None
        assert entity.entity_id == "crud-test"
        
        # Test get_multi
        entities = crud.get_multi(session, limit=5)
        assert len(entities) == 5
        
        filtered = crud.get_multi(
            session,
            filters={"is_active": True},
            limit=3
        )
        assert len(filtered) == 3
        assert all(e.is_active for e in filtered)
        
        # Test update
        update_data = {
            "name": "Updated CRUD Entity",
            "is_active": False
        }
        
        updated = crud.update(session, "crud-test", update_data)
        assert updated.name == "Updated CRUD Entity"
        assert updated.is_active is False
        
        # Test delete
        result = crud.delete(session, "crud-test")
        assert result is True
        
        # Verify deletion
        entity = crud.get(session, "crud-test")
        assert entity is None
        
        # Calculate expected counts from sample_entities
        expected_active_count = sum(1 for e in sample_entities if e.is_active)
        
        # Test count
        count = crud.count(session)
        assert count == 10  # Original 10 sample entities
        
        # Test count with filter
        filtered_count = crud.count(session, {"is_active": True})
        assert filtered_count == expected_active_count