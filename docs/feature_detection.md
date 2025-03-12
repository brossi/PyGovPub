# Feature Detection Matrix

The PyGovPub library includes a sophisticated feature detection system that automatically identifies available database features and capabilities at runtime. This ensures that the library can adapt to different environments and take advantage of provider-specific features when available.

## Available Features

| Feature | PostgreSQL | SQLite | MySQL | LanceDB | Description |
|---------|------------|--------|-------|---------|-------------|
| `basic_storage` | ✅ | ✅ | ✅ | ✅ | Basic CRUD operations |
| `vector_operations` | ✅ (with pgvector) | ❌ | ❌ | ✅ | Vector similarity search and operations |
| `hybrid_search` | ❌ | ❌ | ❌ | ✅ | Combined vector and text search |
| `full_text_search` | ✅ | ✅ (with FTS5) | ✅ | ✅ | Full-text search capabilities |
| `local_storage` | ✅ | ✅ | ✅ | ✅ | Storage on local filesystem |
| `cloud_storage` | ✅ (with Supabase) | ❌ | ❌ | ✅ | Cloud storage options |
| `embedded_database` | ❌ | ✅ | ❌ | ✅ | Runs embedded in application |
| `hnsw_index` | ✅ (with pgvector) | ❌ | ❌ | ✅ | Hierarchical Navigable Small World indexing |
| `versioning` | ✅ | ❌ | ❌ | ✅ | Data/schema versioning support |
| `async_support` | ✅ (asyncpg) | ✅ (aiosqlite) | ✅ (aiomysql) | ❌ | Asynchronous database operations |
| `partitioning` | ✅ | ❌ | ✅ | ✅ | Table partitioning capabilities |
| `fallback_basic_postgresql` | ✅ | ❌ | ❌ | ❌ | Fallback mode for PostgreSQL without extensions |

## Detection Methods

The feature detection system uses a multi-layered approach to identify available features:

1. **Connection string analysis**: Determines the basic database type based on the connection string format
2. **Extension detection**: Attempts to detect optional database extensions (e.g., pgvector, FTS5)
3. **Module availability**: Checks if required Python packages are installed (e.g., asyncpg, lancedb)
4. **Runtime capability probing**: Executes test queries to confirm feature availability

## Usage in Code

You can check for feature availability using the `supports()` method on the storage interface:

```python
from pygovpub.storage.interface import StorageInterface

# Create storage interface
storage = StorageInterface("postgresql://user:password@localhost/db")

# Check for vector operations support
if storage.supports("vector_operations"):
    # Use vector operations
    results = storage.vector_search_with_provider(
        provider_type="postgresql",
        model_class=Document,
        query_vector=[0.1, 0.2, 0.3, ...],
        limit=10
    )
else:
    # Fall back to text search
    results = storage.query(
        Document,
        {"title__contains": "search term"},
        limit=10
    )
```

## Schema Version Features

In addition to database provider features, the system also tracks schema version capabilities:

```python
# Check if current schema version supports advanced partitioning
if storage.supports_schema_feature("advanced_partitioning"):
    # Use advanced partitioning features
    pass
```

| Feature | PostgreSQL Min Version | SQLite Min Version | Description |
|---------|------------------------|-------------------|-------------|
| `vector_search` | 5 | 3 | Vector similarity search |
| `advanced_partitioning` | 7 | N/A | Advanced table partitioning |
| `full_text_search` | 3 | 4 | Full-text search capabilities |

## Extending Feature Detection

You can extend the feature detection system by adding new checks to the `_detect_features()` method in the `StorageInterface` class:

```python
def _detect_features(self) -> Dict[str, bool]:
    """Detect database features and capabilities."""
    features = {'basic_storage': True}
    
    # Add custom feature detection
    if self.db_type == "custom_db":
        try:
            # Attempt to detect custom feature
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT my_custom_feature()"))
                if result.scalar():
                    features['custom_feature'] = True
        except Exception as e:
            logger.warning(f"Error detecting custom feature: {str(e)}")
    
    return features
```

## Feature Compatibility Matrix

When developing applications that need to work across different database providers, use this matrix to determine which features are universally available:

| Application Requirement | PostgreSQL | SQLite | MySQL | LanceDB | Compatible Across All |
|-------------------------|------------|--------|-------|---------|----------------------|
| Basic CRUD | ✅ | ✅ | ✅ | ✅ | ✅ |
| Text Search | ✅ | ✅ | ✅ | ✅ | ✅ |
| Vector Search | ✅* | ❌ | ❌ | ✅ | ❌ |
| Hybrid Search | ❌ | ❌ | ❌ | ✅ | ❌ |
| Partitioning | ✅ | ❌ | ✅ | ✅ | ❌ |
| Async Support | ✅ | ✅ | ✅ | ❌ | ❌ |

*Requires pgvector extension

## Runtime Detection Code

The feature detection process is triggered automatically when a `StorageInterface` is instantiated. Here's how it works:

```python
# This happens internally when you create a StorageInterface
storage = StorageInterface("postgresql://user:password@localhost/db")

# Feature detection is automatically performed
features = storage.features  # Dictionary of detected features

# Features are logged for visibility
logger.info(
    "Storage interface initialized",
    db_type=storage.db_type,
    features=features,
    schema_version=storage.schema_version,
    async_supported=storage._supports_async()
)
```