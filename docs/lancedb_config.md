# LanceDB Provider Configuration Guide

This document provides comprehensive guidance for configuring and using the LanceDB vector database provider in PyGovPub.

## Overview

LanceDB is a high-performance embedded vector database that provides:

- Vector similarity search capabilities
- Hybrid search (vector + text) functionality
- Local, embedded database deployment
- Fast indexing and retrieval
- Seamless integration with PyArrow data types
- Connection pooling for concurrent operations

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
    db_dir="~/.pygovpub/lancedb",          # Default location if no URI provided
    use_connection_pool=True,              # Enable connection pooling
    pool_id="default",                     # Connection pool identifier
    pool_max_size=10,                      # Maximum connections in pool
    pool_min_size=2                        # Minimum connections to maintain
)
```

### Connection Pooling Configuration

Connection pooling improves performance in multi-threaded and concurrent environments:

```python
from pygovpub.storage.providers.lancedb_provider import LanceDBProvider

# Provider with advanced connection pooling settings
provider = LanceDBProvider(
    uri="/path/to/database",
    use_connection_pool=True,              # Enable connection pooling
    pool_id="bills_router",                # Router-specific pool ID
    pool_max_size=15,                      # Maximum connections in pool
    pool_min_size=3,                       # Minimum connections to maintain
    connection_timeout=30.0,               # Timeout waiting for a connection (seconds)
    idle_timeout=300.0                     # Timeout for idle connections (seconds)
)
```

#### Router-Specific Connection Pooling

For optimal performance in complex APIs with multiple router endpoints, create router-specific connection pools:

```python
# Bills router provider (lighter workload)
bills_provider = LanceDBProvider(
    uri="/path/to/database",
    use_connection_pool=True,
    pool_id="bills_router",
    pool_max_size=5
)

# Search router provider (heavy workload)
search_provider = LanceDBProvider(
    uri="/path/to/database",
    use_connection_pool=True,
    pool_id="search_router",
    pool_max_size=15
)
```

Each router gets its own isolated connection pool optimized for its specific workload, improving overall system performance.

#### Re-using Existing Pools

Connection pools are maintained as singletons by pool ID. To reuse an existing pool:

```python
from pygovpub.storage.providers.lancedb_provider import get_connection_pool

# Create or get a pool directly
pool = get_connection_pool(
    uri="/path/to/database",
    pool_id="shared_pool",
    max_size=10,
    min_size=2
)

# When creating a provider with the same pool_id, it will use the existing pool
provider = LanceDBProvider(
    uri="/path/to/database",
    use_connection_pool=True,
    pool_id="shared_pool"  # Will reuse the existing pool
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

## Performance Optimization

### Connection Pooling Benefits

Connection pooling provides several performance benefits:

1. **Reduced Connection Overhead**: Reusing connections eliminates connection creation costs
2. **Improved Concurrency**: Multiple concurrent operations can use different connections
3. **Resource Management**: Limits the maximum number of connections to avoid system overload
4. **Connection Health Checks**: Automatically detects and recreates stale or invalid connections
5. **Idle Connection Management**: Cleans up unused connections based on timeout configuration

### Connection Pool Sizing Guidelines

- **pool_min_size**: Keep this high enough to handle typical load without waiting for new connections
- **pool_max_size**: Set based on expected concurrent operations and system resources
- **For high-traffic APIs**: Use router-specific pools sized according to each endpoint's load
- **For batch processing**: Temporary larger pools might be appropriate

### Connection Lifecycle Management

The connection pool automatically handles connection lifecycle:

```python
# Create a provider with connection pooling
provider = LanceDBProvider(uri="/path/to/database", use_connection_pool=True)

def perform_operation():
    # This automatically gets a connection from the pool
    result = provider.vector_search(DocumentModel, query_vector=[...])
    # After operation completes, connection is automatically returned to the pool
    return result
```

### Load Testing Connection Pools

To verify your connection pool settings are appropriate, perform load testing:

```python
import concurrent.futures

# Create a provider with connection pooling
provider = LanceDBProvider(
    uri="/path/to/database",
    use_connection_pool=True,
    pool_max_size=10
)

# Define a test operation
def test_operation(i):
    return provider.vector_search(DocumentModel, query_vector=[...])

# Run concurrent operations
with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
    futures = [executor.submit(test_operation, i) for i in range(30)]
    results = [future.result() for future in futures]
```

## Monitoring

The LanceDB provider exposes the following Prometheus metrics:

### Operation Metrics

- `lancedb_operations_total`: Counter for operations (create, get, search)
- `lancedb_operation_duration_seconds`: Histogram of operation durations
- `lancedb_schema_version`: Gauge tracking schema versions by table

### Connection Pool Metrics

- `lancedb_pool_connections`: Gauge tracking pool connections by status ("available", "in_use")
- `lancedb_pool_operations`: Counter for pool operations (create_connection, get_connection, etc.)
- `lancedb_pool_wait_time_seconds`: Histogram of connection wait times

### Monitoring Connection Pools

You can monitor connection pool status through metrics and the pool's statistics method:

```python
# Get connection pool stats
from pygovpub.storage.providers.lancedb_provider import get_connection_pool

pool = get_connection_pool(uri="/path/to/database", pool_id="default")
stats = pool.get_stats()

print(f"Pool size: {stats['total_connections']}")
print(f"Available connections: {stats['available_connections']}")
print(f"In-use connections: {stats['in_use_connections']}")
```

### Health Checks

The connection pool performs automatic health checks:

1. Connections are validated before being returned from the pool
2. Invalid connections are automatically discarded and replaced
3. The pool maintains the minimum number of valid connections

## Troubleshooting

Common issues and solutions:

### Connection Pooling Issues

1. **Connection pool exhaustion**: 
   - Symptoms: Long wait times, timeout errors
   - Solution: Increase `pool_max_size` or add request queuing

2. **Stale connections**:
   - Symptoms: "Connection closed" errors after idle periods
   - Solution: Decrease `idle_timeout` to recycle connections more frequently

3. **High connection creation overhead**:
   - Symptoms: Performance spikes during traffic bursts
   - Solution: Increase `pool_min_size` to maintain more ready connections

### Other Common Issues

1. **Connection errors**: Verify path permissions and existence
2. **Missing PyArrow**: Install with `pip install pyarrow>=14.0.1`
3. **Schema compatibility**: Use schema adapter to verify compatibility
4. **Search performance**: Ensure vector indices are created

## Implementation Notes for STOR-04

The connection pooling in LanceDB was implemented with the following key components:

1. **`LanceDBConnectionPool` Class**:
   - Manages a pool of LanceDB connections
   - Provides thread-safe connection acquisition and release
   - Automatically validates connections before use
   - Handles connection lifecycle (creation, validation, cleanup)
   - Exposes metrics for monitoring pool health

2. **Singleton Pool Registry**:
   - Global registry of connection pools via `get_connection_pool()`
   - Enables router-specific connection pooling
   - Ensures connection reuse across different parts of the application

3. **Integration with `LanceDBProvider`**:
   - `use_connection_pool` parameter to enable/disable pooling
   - Pool configuration parameters (pool_id, max_size, min_size)
   - `_with_connection()` method for connection lifecycle management
   - Automatic connection release after operations

4. **Router-Specific Implementation**:
   - Example in `lancedb_search.py`
   - Pre-initializes connection pool for search router
   - Factory function for provider instantiation
   - Dedicated pool sizes optimized for search workload

5. **Connection Health Checks**:
   - Each connection is validated before use
   - Invalid connections are automatically discarded and replaced
   - Idle connections are cleaned up based on timeout settings

6. **Resource Cleanup**:
   - Shutdown handler in FastAPI application
   - Safely closes all connections in pools
   - Prevents connection leaks on application restart

These improvements help maintain performance under high load by:
- Reducing connection creation overhead
- Managing concurrent access to database connections
- Isolating workloads by router function
- Ensuring connections remain healthy and responsive
- Providing visibility into connection pool status