"""
Pytest configuration for test directory.

This file contains pytest fixtures specific to the tests directory.
"""

import pytest
import os
from pathlib import Path
from typing import Generator, Optional
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


@pytest.fixture
def test_engine(temp_db_path) -> Engine:
    """
    Create a SQLAlchemy engine for testing using the temp_db_path fixture.
    
    This ensures that each test gets a fresh database, and the database
    file is properly cleaned up after the test.
    
    Args:
        temp_db_path: Path to a temporary SQLite database
        
    Returns:
        SQLAlchemy engine connected to a temporary database
    """
    engine = create_engine(temp_db_path, echo=False)
    
    try:
        yield engine
    finally:
        # Close engine connections
        engine.dispose()


@pytest.fixture
def test_session(test_engine) -> Generator[Session, None, None]:
    """
    Create a SQLAlchemy session for testing.
    
    Args:
        test_engine: SQLAlchemy engine from the test_engine fixture
        
    Returns:
        SQLAlchemy session connected to a temporary database
    """
    # Create a sessionmaker
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    
    # Create a new session for each test
    session = SessionLocal()
    
    try:
        yield session
    finally:
        # Close and rollback the session to prevent test state from leaking
        session.rollback()
        session.close()


@pytest.fixture
def test_cache_dir() -> Generator[Path, None, None]:
    """
    Create a temporary directory for test caches.
    
    Returns:
        Path to a temporary cache directory that will be cleaned up after the test.
    """
    # Create a unique directory in our test_artifacts/cache folder
    import uuid
    import shutil
    
    base_dir = Path(__file__).parent / ".." / "test_artifacts" / "cache"
    base_dir = base_dir.resolve()  # Get the absolute path
    base_dir.mkdir(parents=True, exist_ok=True)
    
    # Create a unique subdirectory
    cache_dir = base_dir / f"cache_{uuid.uuid4().hex}"
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        yield cache_dir
    finally:
        # Cleanup after test
        if cache_dir.exists():
            shutil.rmtree(cache_dir)