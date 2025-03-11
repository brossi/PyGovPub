"""
Pytest configuration for test directory.

This file contains pytest fixtures specific to the tests directory.
"""

import pytest
import os
import socket
import subprocess
import time
import uuid
from pathlib import Path
from typing import Generator, Optional, Dict, Any
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import Session


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
    Create a SQLModel session for testing.
    
    Args:
        test_engine: SQLAlchemy engine from the test_engine fixture
        
    Returns:
        SQLModel session connected to a temporary database
    """
    # Create a SQLModel session directly
    session = Session(test_engine)
    
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


# PostgreSQL specific fixtures
def is_postgres_available() -> bool:
    """
    Check if PostgreSQL is available for testing.
    
    This checks if PostgreSQL server is running locally on default port.
    
    Returns:
        True if PostgreSQL is available, False otherwise
    """
    # Try connecting to PostgreSQL on default port
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        result = sock.connect_ex(('localhost', 5432))
        return result == 0  # If connection succeeded, PostgreSQL may be available
    except:
        return False
    finally:
        sock.close()


def get_test_postgres_config() -> Dict[str, Any]:
    """
    Get PostgreSQL configuration for tests from the environment.
    
    Returns:
        Dictionary with PostgreSQL connection parameters.
    """
    # Default test database configuration
    config = {
        'host': os.environ.get('TEST_POSTGRES_HOST', 'localhost'),
        'port': os.environ.get('TEST_POSTGRES_PORT', '5432'),
        'user': os.environ.get('TEST_POSTGRES_USER', 'postgres'),
        'password': os.environ.get('TEST_POSTGRES_PASSWORD', 'postgres'),
        'database': os.environ.get('TEST_POSTGRES_DB', 'postgres')
    }
    
    return config


@pytest.fixture
def pg_test_db_name() -> str:
    """
    Generate a unique PostgreSQL test database name.
    
    Returns:
        Unique database name for testing
    """
    # Create a unique database name with test_ prefix
    db_name = f"test_{uuid.uuid4().hex[:16]}"
    
    return db_name


@pytest.fixture
def pg_test_db_url(pg_test_db_name) -> Optional[str]:
    """
    Create a PostgreSQL database URL for testing.
    
    This will create a temporary PostgreSQL database for testing
    and drop it afterward. Skip if PostgreSQL is not available.
    
    Args:
        pg_test_db_name: Name of test database to create
        
    Returns:
        PostgreSQL connection URL or None if PostgreSQL is not available
    """
    # Skip if PostgreSQL is not available
    if not is_postgres_available():
        pytest.skip("PostgreSQL is not available for testing")
    
    # Get PostgreSQL configuration
    config = get_test_postgres_config()
    
    # Create admin connection URL (to postgres database)
    admin_url = f"postgresql://{config['user']}:{config['password']}@{config['host']}:{config['port']}/{config['database']}"
    
    # Create test database connection URL
    test_url = f"postgresql://{config['user']}:{config['password']}@{config['host']}:{config['port']}/{pg_test_db_name}"
    
    # Connect to PostgreSQL and create test database
    engine = create_engine(admin_url)
    conn = engine.connect()
    conn.execute(text(f"COMMIT"))  # Explicitly commit any open transaction
    conn.execute(text(f"CREATE DATABASE {pg_test_db_name}"))
    conn.close()
    engine.dispose()
    
    try:
        yield test_url
    finally:
        # Connect to PostgreSQL and drop test database
        engine = create_engine(admin_url)
        conn = engine.connect()
        conn.execute(text(f"COMMIT"))  # Explicitly commit any open transaction
        
        # Terminate any existing connections to the test database
        conn.execute(text(
            f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '{pg_test_db_name}'"
        ))
        
        # Drop the test database
        conn.execute(text(f"DROP DATABASE IF EXISTS {pg_test_db_name}"))
        conn.close()
        engine.dispose()


@pytest.fixture
def any_db_engine(request) -> Generator[Engine, None, None]:
    """
    Create a database engine for testing using either SQLite or PostgreSQL.
    
    This fixture takes a parameter 'db_type' to specify which database to use.
    Valid values are 'sqlite' and 'postgres'. If PostgreSQL is not available
    and 'postgres' is requested, it will skip the test.
    
    Example:
        @pytest.mark.parametrize('any_db_engine', ['sqlite', 'postgres'], indirect=True)
        def test_with_multiple_dbs(any_db_engine):
            # This test will run twice, once with SQLite, once with PostgreSQL
            ...
    
    Args:
        request: Pytest request object with the 'db_type' parameter
        
    Returns:
        SQLAlchemy engine connected to the specified database
    """
    db_type = getattr(request, 'param', 'sqlite')
    
    if db_type == 'postgres':
        # Use PostgreSQL
        if not is_postgres_available():
            pytest.skip("PostgreSQL is not available for testing")
            
        # Get a PostgreSQL connection URL
        pg_test_db_name = f"test_{uuid.uuid4().hex[:16]}"
        config = get_test_postgres_config()
        
        # Create admin connection URL (to postgres database)
        admin_url = f"postgresql://{config['user']}:{config['password']}@{config['host']}:{config['port']}/{config['database']}"
        
        # Create test database connection URL
        test_url = f"postgresql://{config['user']}:{config['password']}@{config['host']}:{config['port']}/{pg_test_db_name}"
        
        # Connect to PostgreSQL and create test database
        admin_engine = create_engine(admin_url)
        conn = admin_engine.connect()
        conn.execute(text(f"COMMIT"))  # Explicitly commit any open transaction
        conn.execute(text(f"CREATE DATABASE {pg_test_db_name}"))
        conn.close()
        admin_engine.dispose()
        
        # Create engine with test database
        engine = create_engine(test_url)
        
        try:
            yield engine
        finally:
            # Close engine connections
            engine.dispose()
            
            # Connect to PostgreSQL and drop test database
            admin_engine = create_engine(admin_url)
            conn = admin_engine.connect()
            conn.execute(text(f"COMMIT"))  # Explicitly commit any open transaction
            
            # Terminate any existing connections to the test database
            conn.execute(text(
                f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '{pg_test_db_name}'"
            ))
            
            # Drop the test database
            conn.execute(text(f"DROP DATABASE IF EXISTS {pg_test_db_name}"))
            conn.close()
            admin_engine.dispose()
    else:
        # Use SQLite (default)
        # Get a temporary SQLite database path
        db_path = request.getfixturevalue('temp_db_path')
        
        # Create engine
        engine = create_engine(db_path, echo=False)
        
        try:
            yield engine
        finally:
            # Close engine connections
            engine.dispose()
@pytest.fixture
def any_db_session(any_db_engine) -> Generator[Session, None, None]:
    """
    Create a SQLModel session connected to any database type (SQLite or PostgreSQL).
    
    This fixture uses the any_db_engine fixture and can be parameterized the same way.
    
    Args:
        any_db_engine: Engine to create session for
        
    Returns:
        SQLModel session connected to the specified database
    """
    # Create a SQLModel session directly
    session = Session(any_db_engine)
    
    try:
        yield session
    finally:
        # Close and rollback the session to prevent test state from leaking
        session.rollback()
        session.close()


@pytest.fixture
def warning_recorder():
    """
    Record warnings during test execution.
    
    This fixture allows you to capture and verify warnings emitted during a test.
    
    Returns:
        List of warnings recorded during the test
    """
    recorded_warnings = []
    
    with pytest.warns() as record:
        yield record
        
    # Convert to a more usable format
    for warning in record:
        recorded_warnings.append({
            "message": str(warning.message),
            "category": warning.category.__name__,
            "filename": warning.filename,
            "lineno": warning.lineno
        })
        
    return recorded_warnings
