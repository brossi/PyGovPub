# Database Module Documentation

The PyGovPub database module provides a robust database connection system with support for:

- Multiple database backends (PostgreSQL, SQLite)
- Connection pooling
- Transaction management
- Schema migrations
- CRUD operations
- Asynchronous database operations
- Comprehensive testing fixtures

## Models Architecture

PyGovPub uses SQLModel for object-relational mapping, which combines SQLAlchemy with Pydantic. This provides both robust ORM capabilities and strong type validation.

### Base Models

All database models inherit from `BaseTable`:

```python
class BaseTable(SQLModel):
    """Base table model with timestamp fields."""
    
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        index=True
    )
    
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), 
        index=True
    )
```

For tables that need an auto-increment ID, use the `BaseEntity` class:

```python
class BaseEntity(SQLModel, table=True):
    """Base entity model with ID field."""
    
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
```

## Database Connection Management

### Connection Initialization

```python
from pygovpub.core.database import init_db, get_connection_url

# Get connection URL from environment variables
url = get_connection_url()

# Initialize the database engine
engine = init_db(url)
```

### Using the Engine Singleton

```python
from pygovpub.core.database import get_engine

# Get the global engine singleton
engine = get_engine()

# Force a new engine instance
engine = get_engine(force_new=True)
```

## Session Management

### Synchronous Sessions

```python
from pygovpub.core.database import get_session, with_transaction
from sqlmodel import Session

# Basic session usage
session = get_session()
try:
    # Perform database operations
    session.commit()
finally:
    session.close()

# Context manager - automatically handles commit/rollback
with Session(get_engine()) as session:
    # Perform database operations
    session.commit()

# Transaction context manager - automatic commit/rollback
with with_transaction() as session:
    # Perform database operations
    # Automatically commits if no exceptions, rolls back on error
```

### Asynchronous Sessions

```python
from pygovpub.core.database import get_async_session, with_async_transaction
import asyncio

async def example():
    # Basic async session usage
    async with get_async_session() as session:
        # Perform async database operations
        await session.commit()
    
    # Transaction context manager
    async with with_async_transaction() as session:
        # Perform database operations
        # Automatically commits if no exceptions, rolls back on error

asyncio.run(example())
```

## Table Management

```python
from pygovpub.core.database import create_tables, drop_tables

# Create all tables defined in SQLModel metadata
create_tables()

# Drop all tables defined in SQLModel metadata
drop_tables()
```

## Migration System

The migration system allows you to manage database schema changes in a controlled way.

### Managing Migrations

```python
from pygovpub.core.database import MigrationManager, get_engine
from sqlmodel import Session

# Create a migration manager
manager = MigrationManager(get_engine())

# Define migration functions
def migrate_to_v1_0_0(session: Session) -> None:
    """Migration to version 1.0.0"""
    session.execute("CREATE TABLE example (id INTEGER PRIMARY KEY, name TEXT)")

def rollback_from_v1_0_0(session: Session) -> None:
    """Rollback from version 1.0.0"""
    session.execute("DROP TABLE example")

# Register the migration
manager.register_migration(
    "1.0.0", 
    migrate_to_v1_0_0, 
    rollback_from_v1_0_0
)

# Run all pending migrations
manager.run_migrations()

# Run migrations to a specific version
manager.run_migrations(target_version="1.0.0")

# Get current schema version
current_version = manager.get_current_version()

# Roll back a specific migration
manager.rollback_migration("1.0.0")
```

### Using Migration Convenience Functions

```python
from pygovpub.core.database import get_migration_version, run_migrations

# Get current schema version
version = get_migration_version()

# Run migrations
run_migrations()

# Run migrations to a specific version
run_migrations(target_version="1.1.0")
```

## CRUD Operations

The CRUD module provides standardized functions for database operations.

### Using CRUD Functions

```python
from sqlmodel import Session
from pygovpub.core.crud import (
    create_entity, 
    get_entity,
    get_entities,
    update_entity,
    delete_entity,
    count_entities
)
from pygovpub.core.database import get_engine
from your_app.models import YourModel

with Session(get_engine()) as session:
    # Create
    new_entity = create_entity(session, YourModel, {
        "id": "unique-id",
        "name": "New Entity",
        "description": "Description"
    })
    
    # Read one
    entity = get_entity(session, YourModel, "unique-id")
    
    # Read many with filtering and pagination
    entities = get_entities(
        session,
        YourModel,
        filters={"active": True},
        skip=0,
        limit=10,
        order_by="name",
        descending=False
    )
    
    # Update
    updated = update_entity(
        session,
        YourModel,
        "unique-id",
        {"name": "Updated Name"}
    )
    
    # Delete
    deleted = delete_entity(session, YourModel, "unique-id")
    
    # Count
    count = count_entities(
        session,
        YourModel,
        filters={"active": True}
    )
```

### Using the CRUDBase Class

The `CRUDBase` class provides an object-oriented interface for CRUD operations on a specific model:

```python
from pygovpub.core.crud import CRUDBase
from sqlmodel import Session
from pygovpub.core.database import get_engine
from your_app.models import YourModel

# Create a CRUD instance for your model
your_model_crud = CRUDBase(YourModel)

with Session(get_engine()) as session:
    # Now use the CRUD instance methods
    entity = your_model_crud.create(session, {"id": "unique-id", "name": "Test"})
    
    retrieved = your_model_crud.get(session, "unique-id")
    
    entities = your_model_crud.get_multi(
        session, 
        filters={"active": True}, 
        limit=10
    )
    
    updated = your_model_crud.update(
        session, 
        "unique-id", 
        {"name": "Updated"}
    )
    
    deleted = your_model_crud.delete(session, "unique-id")
    
    count = your_model_crud.count(session, {"active": True})
```

## PostgreSQL-Specific Features

When using PostgreSQL, PyGovPub supports additional data types and query capabilities:

### JSON Fields

```python
from sqlmodel import Field, SQLModel
from typing import Optional
from pygovpub.models.base import BaseTable

class ModelWithJSON(BaseTable, table=True):
    id: str = Field(primary_key=True)
    metadata: Optional[dict] = Field(
        default=None, 
        sa_column_kwargs={"type": "JSONB"}
    )
```

Query JSON fields using PostgreSQL operators:

```python
from sqlmodel import select

# Query by JSON property
result = session.exec(
    select(ModelWithJSON).where(
        ModelWithJSON.metadata["key"].as_string() == "value"
    )
).all()

# Test for existence of a key
result = session.exec(
    select(ModelWithJSON).where(
        ModelWithJSON.metadata.has_key("key_name")
    )
).all()
```

### Array Fields

```python
from sqlmodel import Field, SQLModel
from typing import Optional, List
from pygovpub.models.base import BaseTable

class ModelWithArray(BaseTable, table=True):
    id: str = Field(primary_key=True)
    tags: Optional[List[str]] = Field(
        default=None, 
        sa_column_kwargs={"type": "VARCHAR[]"}
    )
```

Query array fields:

```python
from sqlmodel import select

# Array contains
result = session.exec(
    select(ModelWithArray).where(
        ModelWithArray.tags.contains(["tag1", "tag2"])
    )
).all()

# Array overlap
result = session.exec(
    select(ModelWithArray).where(
        ModelWithArray.tags.overlap(["tag1", "tag3"])
    )
).all()
```

## Testing with Database Fixtures

The PyGovPub test suite includes comprehensive fixtures for database testing across SQLite and PostgreSQL backends.

### Available Test Fixtures

#### Basic Database Fixtures

```python
# SQLite test engine (fresh for each test)
def test_with_engine(test_engine):
    """Test uses a clean SQLite database."""
    SQLModel.metadata.create_all(test_engine)
    # Use engine for tests...

# SQLModel session for SQLite
def test_with_session(test_session):
    """Test uses a SQLModel session with SQLite."""
    # Use session directly
    model = MyModel(id=1, name="Test")
    test_session.add(model)
    test_session.commit()
    
    # Query using .exec() method
    result = test_session.exec(select(MyModel)).first()
```

#### Multi-Database Fixtures

```python
# Parametrize to test with both SQLite and PostgreSQL
@pytest.mark.parametrize('any_db_engine', ['sqlite', 'postgres'], indirect=True)
def test_with_multiple_dbs(any_db_engine):
    """Test runs twice - once with SQLite, once with PostgreSQL."""
    SQLModel.metadata.create_all(any_db_engine)
    # Test database operations...
    
# Use database session for either backend
@pytest.mark.parametrize('any_db_session', ['sqlite', 'postgres'], indirect=True)
def test_with_session_backends(any_db_session):
    """Test runs twice with different database backends."""
    # SQLModel session works with either
    model = MyModel(id=1, name="Test")
    any_db_session.add(model)
    any_db_session.commit()
    
    # Query using SQLModel's .exec() method
    result = any_db_session.exec(select(MyModel)).first()
```

### Creating Test Models

For test-only models, define them in your test file:

```python
class TestModel(SQLModel, table=True):
    """Model used only for testing."""
    
    __tablename__ = "test_models"
    
    id: int = Field(primary_key=True)
    name: str
    description: Optional[str] = None
    
    # To ensure the table is recreated for each test:
    __table_args__ = {"extend_existing": True}
```

### PostgreSQL-Specific Testing

For PostgreSQL-specific features (JSON, arrays), use the `postgres_available` marker:

```python
@postgres_available
def test_postgres_json_fields():
    """Test is skipped if PostgreSQL is not available."""
    # Use PostgreSQL features...
```

## Performance Considerations

### Connection Pooling

The database module is configured with connection pooling for optimal performance:

- `pool_pre_ping`: Verifies connections before checkout from the pool
- `pool_recycle`: Recycles connections after 1 hour (3600 seconds)
- `pool_size`: Default pool size of 5 connections
- `max_overflow`: Allows up to 10 additional connections

### Query Optimization

For best performance:

1. Use indexes on frequently queried fields
2. Use limit/skip for pagination rather than fetching all records
3. Only select the columns you need
4. Use bulk operations when possible
5. Keep transactions short

```python
# Efficient querying with specific columns
from sqlalchemy import select
from sqlmodel import col

with Session(get_engine()) as session:
    # Only select needed columns
    statement = select(
        col(YourModel.id),
        col(YourModel.name)
    ).where(
        YourModel.active == True
    ).limit(10)
    
    results = session.exec(statement).all()
```

## Configuration

See [Configuration Guide](/docs/configuration.md) for details on configuring the database connection.