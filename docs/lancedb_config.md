# LanceDB Provider Configuration Guide

This document provides comprehensive guidance for configuring and using the LanceDB vector database provider in PyGovPub.

## Overview

LanceDB is a high-performance embedded vector database that provides:

- Vector similarity search capabilities
- Hybrid search (vector + text) functionality
- Local, embedded database deployment
- Fast indexing and retrieval
- Seamless integration with PyArrow data types

The PyGovPub LanceDB provider integrates with the storage interface to provide these capabilities with proper schema management and migration support.

## Configuration Options

### Basic Connection

The simplest configuration connects to a LanceDB database:

```python
from pygovpub.storage.interface import StorageInterface

# Connect using a LanceDB URI
storage = StorageInterface("lancedb:///path/to/database")

# Use a model class for operations
document = storage.get_with_provider("lancedb", DocumentModel, "doc-id-123")
```

### Provider Configuration

When initializing the LanceDB provider directly, several options are available:

```python
from pygovpub.storage.providers.lancedb_provider import LanceDBProvider
from pygovpub.storage.schema_registry import SchemaRegistry

# Initialize schema registry
registry = SchemaRegistry(connection_string="sqlite:///schemas.db")

# Configure LanceDB provider
provider = LanceDBProvider(
    uri="/path/to/database",               # Database location
    create_vector_index=True,              # Auto-create vector indices
    vector_dim=384,                        # Vector dimension (default=384)
    schema_registry=registry,              # Schema registry for versioning
    overwrite_tables=False,                # Don't overwrite existing tables
    db_dir="~/.pygovpub/lancedb"           # Default location if no URI provided
)
```

## Schema Management

The LanceDB provider supports schema management through integration with the SchemaRegistry:

```python
# Apply a specific schema version to a table
provider.apply_schema_version("documents", "1.2.0")

# Create a table with a specific schema version
provider._get_or_create_table("documents", schema_version="1.2.0")
```

### Schema Version Format

Schema versions in the registry should follow this format:

```json
{
  "version": "1.0.0",
  "fields": [
    {"name": "id", "type": "string"},
    {"name": "embedding", "type": "vector", "dimension": 384},
    {"name": "content", "type": "string"},
    {"name": "metadata", "type": "json"},
    {"name": "tags", "type": "string"}
  ]
}
```

Supported field types:
- string: Text data
- integer: Integer values
- float: Floating point values
- boolean: True/false values
- timestamp: DateTime values
- json: JSON objects (stored as strings)
- vector: Vector embeddings with dimension
- binary: Binary data

## Vector Search Operations

### Basic Vector Search

```python
# Perform vector search
results = provider.vector_search(
    DocumentModel,
    query_vector=[0.1, 0.2, ...],  # 384-dimensional vector
    limit=10,
    filter_criteria={"category": "legal"}
)
```

### Hybrid Search

```python
# Perform hybrid search (vector + text)
results = provider.hybrid_search(
    DocumentModel,
    query_text="federal regulations",
    query_vector=[0.1, 0.2, ...],  # Optional: provide vector for hybrid search
    limit=20,
    filter_criteria={"is_active": True}
)
```

## Implementation Notes

### Schema Migration Limitations

LanceDB has some limitations regarding schema migrations:

1. Adding fields is supported
2. Removing fields is not supported
3. Changing field types is not supported

When applying schema versions that involve unsupported operations, the system will log warnings but attempt to handle them gracefully.

### Best Practices

1. **Embedding Dimensions**: Ensure consistent vector dimensions (default: 384)
2. **Indexing**: Create vector indices for tables with significant data
3. **Schema Versions**: Use schema registry to manage evolving schemas
4. **Transactions**: LanceDB doesn't support transactions, so handle failures appropriately
5. **Performance**: For large datasets, consider using batch operations

## Monitoring

The LanceDB provider exposes the following Prometheus metrics:

- `lancedb_operations_total`: Counter for operations (create, get, search)
- `lancedb_operation_duration_seconds`: Histogram of operation durations
- `lancedb_schema_version`: Gauge tracking schema versions by table

## Troubleshooting

Common issues and solutions:

1. **Connection errors**: Verify path permissions and existence
2. **Missing PyArrow**: Install with `pip install pyarrow>=14.0.1`
3. **Schema compatibility**: Use schema adapter to verify compatibility
4. **Search performance**: Ensure vector indices are created