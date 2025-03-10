"""
Test suite for multi-database support.

This module tests our ability to use both SQLite and PostgreSQL with the same code.
Tests are skipped if PostgreSQL is not available.
"""

import pytest
from typing import Dict, List, Optional, Union, Any
from sqlalchemy import text
from sqlmodel import SQLModel, Field, Session, select

class MultiDBTestModel(SQLModel, table=True):
    """Model for database testing operations across multiple database types."""
    
    __tablename__ = "multi_db_test_models"
    
    id: int = Field(primary_key=True)
    name: str
    description: Optional[str] = None


@pytest.mark.parametrize('any_db_engine', ['sqlite'], indirect=True)
def test_sqlite_operations(any_db_engine):
    """Test that basic operations work with SQLite."""
    # Create tables
    SQLModel.metadata.create_all(any_db_engine)
    
    # Create a session
    with Session(any_db_engine) as session:
        # Create a test model
        model = MultiDBTestModel(id=1, name="SQLite Test", description="Testing with SQLite")
        session.add(model)
        session.commit()
        
        # Query the model
        result = session.exec(select(MultiDBTestModel)).first()
        
        # Verify the result
        assert result is not None
        assert result.id == 1
        assert result.name == "SQLite Test"
        assert result.description == "Testing with SQLite"


@pytest.mark.parametrize('any_db_engine', ['postgres'], indirect=True)
def test_postgres_operations(any_db_engine):
    """Test that basic operations work with PostgreSQL."""
    # This test will be skipped if PostgreSQL is not available
    
    # Create tables
    SQLModel.metadata.create_all(any_db_engine)
    
    # Create a session
    with Session(any_db_engine) as session:
        # Create a test model
        model = MultiDBTestModel(id=1, name="PostgreSQL Test", description="Testing with PostgreSQL")
        session.add(model)
        session.commit()
        
        # Query the model
        result = session.exec(select(MultiDBTestModel)).first()
        
        # Verify the result
        assert result is not None
        assert result.id == 1
        assert result.name == "PostgreSQL Test"
        assert result.description == "Testing with PostgreSQL"


@pytest.mark.parametrize('any_db_session', ['sqlite'], indirect=True)
def test_sqlite_session_operations(any_db_session):
    """Test operations using the any_db_session fixture with SQLite."""
    # Get the engine from the session
    engine = any_db_session.get_bind()
    
    # Create tables
    SQLModel.metadata.create_all(engine)
    
    # Create a test model
    model = MultiDBTestModel(id=1, name="SQLite Session Test", description="Testing with SQLite Session")
    any_db_session.add(model)
    any_db_session.commit()
    
    # Query the model
    result = any_db_session.exec(select(MultiDBTestModel)).first()
    
    # Verify the result
    assert result is not None
    assert result.id == 1
    assert result.name == "SQLite Session Test"
    assert result.description == "Testing with SQLite Session"


@pytest.mark.parametrize('any_db_session', ['postgres'], indirect=True)
def test_postgres_session_operations(any_db_session):
    """Test operations using the any_db_session fixture with PostgreSQL."""
    # This test will be skipped if PostgreSQL is not available
    
    # Get the engine from the session
    engine = any_db_session.get_bind()
    
    # Create tables
    SQLModel.metadata.create_all(engine)
    
    # Create a test model
    model = MultiDBTestModel(id=1, name="PostgreSQL Session Test", description="Testing with PostgreSQL Session")
    any_db_session.add(model)
    any_db_session.commit()
    
    # Query the model
    result = any_db_session.exec(select(MultiDBTestModel)).first()
    
    # Verify the result
    assert result is not None
    assert result.id == 1
    assert result.name == "PostgreSQL Session Test"
    assert result.description == "Testing with PostgreSQL Session"