# PyGovPub Testing Framework

This directory contains the test suite for the PyGovPub project. The testing framework is designed to be modular and extensible, supporting multiple database backends and test strategies.

## Directory Structure

- `tests/` - Root test directory
  - `unit/` - Unit tests for individual components
  - `integration/` - Tests of component interactions
    - `auth/` - Authentication integration tests
    - `logging/` - Logging system integration tests
    - `search/` - Search functionality integration tests
  - `performance/` - Load and memory tests
  - `simple/` - Basic smoke tests
  - `fixtures/` - Test data and fixtures
  - `conftest.py` - PyTest configuration and fixtures

## Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=pygovpub

# Run specific test modules
pytest tests/unit/
pytest tests/integration/search/
```

## Warning Management

PyGovPub uses pytest's warning management system to handle warnings during testing. This helps identify deprecated features, potential issues, and improves test quality.

### Warning Configuration

Warning configuration is defined in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
filterwarnings = [
    "error::DeprecationWarning",
    "error::PendingDeprecationWarning",
    "ignore::DeprecationWarning:pkg_resources.*",
    "ignore::DeprecationWarning:pydantic.*",
]
```

### Recording Warnings

The `warning_recorder` fixture can be used to record and analyze warnings during tests:

```python
def test_example(warning_recorder):
    # Test code that might generate warnings
    result = some_function()
    
    # Check for unexpected warnings
    assert len(warning_recorder) == 0, f"Unexpected warnings: {warning_recorder}"
```

### Common Warning Patterns

1. **Pydantic V2 Warnings**: These must be fixed immediately by updating to the current API
2. **SQLAlchemy Deprecation Warnings**: These should be fixed promptly
3. **RuntimeWarnings**: These should be addressed during development
4. **asyncio Warnings**: Verify proper usage of async/await

All warnings are treated as errors by default to maintain code quality. The PyGovPub project policy is to fix ALL warnings rather than ignore them.

## TODO: Integrated Testing Dashboard

TODO: Implement a refactored test CLI reporting view that integrates all testing, code coverage, and refactoring analysis data into a clean and understandable report. The dashboard should:

- Consolidate data from pytest, coverage reports, and refactoring analysis
- Provide a unified view of test status, coverage metrics, and code quality
- Support filtering and drill-down capabilities for detailed analysis
- Highlight areas needing improvement with actionable recommendations
- Include trend analysis to track progress over time
- Generate exportable reports in multiple formats (JSON, Markdown, HTML)
- Support CI/CD integration with configurable thresholds and gates

This will replace the current separate reporting tools and provide a single source of truth for project quality metrics.

## Database Testing Architecture

The PyGovPub testing framework is designed to support multiple database backends through a modular connection manager system. This allows tests to run against different database types with minimal changes to the test code.

### Current Database Support

- **SQLite**: In-memory and file-based databases for simple testing
- **PostgreSQL**: Full-featured relational database with JSON and array support

### Adding New Database Types

To add support for a new database type (like a vector or graph database), follow this template pattern:

```python
"""
Connection manager for NewDBType databases.

This module provides fixtures and connection management for NewDBType.
"""

import pytest
from typing import Generator, Optional
import newdb_client  # Import the necessary client library

# Global variables and configuration
_NEWDB_CONNECTION = None  # Singleton connection instance

class NewDBConnectionManager:
    """Connection manager for NewDBType databases."""
    
    def __init__(self, connection_string: str):
        """Initialize the connection manager.
        
        Args:
            connection_string: Connection URL or parameters for the database
        """
        self.connection_string = connection_string
        self.client = None
    
    def connect(self) -> 'newdb_client.Client':
        """Connect to the database.
        
        Returns:
            Connected client instance
        """
        if self.client is None:
            self.client = newdb_client.connect(self.connection_string)
        return self.client
    
    def close(self):
        """Close the database connection."""
        if self.client is not None:
            self.client.close()
            self.client = None
    
    # Add database-specific methods for operations
    def execute_query(self, query: str):
        """Execute a query against the database."""
        client = self.connect()
        return client.execute(query)
    
    # Add methods to convert between standard models and database-specific formats
    def to_db_format(self, model_data: dict) -> dict:
        """Convert standard model data to database-specific format."""
        # Implementation specific to this database type
        return model_data


# Utilities for checking availability
def is_newdb_available() -> bool:
    """Check if NewDBType is available for testing."""
    try:
        # Check connection, version, permissions, etc.
        test_connection = newdb_client.connect("test://connection")
        test_connection.ping()
        test_connection.close()
        return True
    except Exception:
        return False


# PyTest fixtures
@pytest.fixture(scope="session")
def newdb_connection_string() -> str:
    """Get connection string for NewDBType tests."""
    # Get from environment variables or use default test server
    return "newdb://username:password@localhost:9999/testdb"


@pytest.fixture
def newdb_connection(newdb_connection_string) -> Generator[NewDBConnectionManager, None, None]:
    """Provide a NewDBType connection manager.
    
    Yields:
        Connected NewDBConnectionManager instance
    """
    # Create and connect manager
    manager = NewDBConnectionManager(newdb_connection_string)
    
    try:
        yield manager
    finally:
        # Clean up
        manager.close()


@pytest.fixture
def any_db_client(request) -> Generator:
    """
    Generic database client fixture that can be parameterized to use different databases.
    
    Example:
        @pytest.mark.parametrize('any_db_client', ['sqlite', 'postgres', 'newdb'], indirect=True)
        def test_with_multiple_dbs(any_db_client):
            # Test runs with each database type
    
    Args:
        request: Pytest request object with parameter for database type
        
    Yields:
        Appropriate database client based on the specified type
    """
    db_type = getattr(request, 'param', 'sqlite')
    
    if db_type == 'newdb':
        if not is_newdb_available():
            pytest.skip("NewDBType is not available for testing")
            
        # Get a connection and prepare test database
        connection_string = request.getfixturevalue('newdb_connection_string')
        manager = NewDBConnectionManager(connection_string)
        
        try:
            # Set up test environment
            manager.execute_query("CREATE TESTSPACE")
            yield manager.connect()
        finally:
            # Clean up
            manager.execute_query("DROP TESTSPACE")
            manager.close()
    else:
        # Use existing database fixtures
        yield request.getfixturevalue(f"{db_type}_engine")
```

### Integration with Existing Test Code

Once you've created a connection manager for your new database type, update the `any_db_client` fixture in `conftest.py` to support the new database type. This allows existing tests to be parameterized to run against all supported databases.

## Model Compatibility Patterns

For cross-database testing, models should handle database-specific features gracefully:

```python
# Example model with database-specific fields
class CrossDBModel:
    """Model that works across different database types."""
    
    def __init__(self, name: str, data: dict = None):
        self.name = name
        self.data = data or {}
    
    @classmethod
    def from_sqlite(cls, row):
        """Create from SQLite data."""
        return cls(name=row['name'], data=json.loads(row.get('data', '{}')))
    
    @classmethod
    def from_postgres(cls, record):
        """Create from PostgreSQL data."""
        return cls(name=record.name, data=record.data)  # PostgreSQL has native JSON
        
    @classmethod
    def from_newdb(cls, document):
        """Create from NewDB data."""
        return cls(name=document.properties.name, 
                  data=document.properties.data)
    
    def to_db_format(self, db_type: str) -> dict:
        """Convert to format appropriate for given database type."""
        base_data = {"name": self.name}
        
        if db_type == "sqlite":
            base_data["data"] = json.dumps(self.data)
        elif db_type == "postgres":
            base_data["data"] = self.data  # Native JSON support
        elif db_type == "newdb":
            # Handle special conversions for this DB type
            base_data["data"] = {
                "type": "object",
                "properties": self.data
            }
            
        return base_data
```

## Testing Strategy

When adding a new database type:

1. **Isolation**: Begin with isolated tests specific to the new database
2. **Integration**: Update the `any_db_client` fixture to support the new type
3. **Parameterization**: Add the new type to existing tests where it makes sense
4. **Specialization**: Create specific tests for features unique to the new database

## Best Practices

- Use the `@pytest.mark.parametrize` decorator with `indirect=True` to test with multiple database types
- Create specialized test models for each database when needed
- Use `pytest.skipif` decorators to skip tests when specific database features aren't available
- Provide clear error messages when database-specific tests are skipped
- Maintain backward compatibility with existing test code when adding new database types