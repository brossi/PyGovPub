# Schema Registry API Reference

This document provides a comprehensive reference for the Schema Registry API in PyGovPub.

## SchemaRegistry Class

The `SchemaRegistry` class is the primary interface for managing database schema versions and migrations.

### Initialization

```python
from pygovpub.storage.schema_registry import SchemaRegistry

registry = SchemaRegistry(
    connection,                      # SQLAlchemy connection object
    version_table="schema_version",  # Optional: custom table name
    db_type=None                     # Optional: specify db type explicitly
)
```

### Core Methods

#### ensure_version_table()

Creates the version table if it doesn't exist.

```python
registry.ensure_version_table()
```

#### register_version()

Registers a new schema version.

```python
success = registry.register_version(
    version="1.2.0",               # Schema version (MAJOR.MINOR.PATCH)
    description="Added indexes",   # Description of changes
    api_version="3.1.0",           # Associated API version
    allow_downgrade=False,         # Whether to allow downgrade
    strict_sequence=True           # Whether to enforce sequential versioning
)
```

Returns `True` if successful, `False` otherwise.

Raises:
- `SchemaVersionError`: If there's a version conflict
- `SchemaDowngradeError`: If attempting to downgrade without permission

#### get_current_version()

Gets the current schema version.

```python
version_info = registry.get_current_version()
```

Returns a dictionary with:
- `version`: Version string
- `description`: Description of the version
- `applied_at`: Timestamp when applied
- `api_version`: Associated API version

#### get_version_history()

Gets the history of all schema versions.

```python
history = registry.get_version_history()
```

Returns a list of version dictionaries, ordered by application time.

#### apply_migration()

Applies a schema migration with transaction support.

```python
success = registry.apply_migration(
    version="1.2.0",                     # Schema version
    description="Add bill version table", # Description
    up_sql="CREATE TABLE bill_version...", # SQL to apply
    down_sql="DROP TABLE IF EXISTS bill_version;", # SQL to rollback
    register=True,                       # Auto-register on success
    api_version="3.1.0",                 # Associated API version
    force=False                          # Override safety checks
)
```

Returns `True` if successful, `False` otherwise.

### Compatibility Methods

#### is_compatible_with_api_version()

Checks if the schema is compatible with a specific API version.

```python
compatible = registry.is_compatible_with_api_version("3.1.0")
```

Returns `True` if compatible, `False` otherwise.

#### supports_feature()

Checks if the current database supports a specific feature.

```python
has_feature = registry.supports_feature("json_column_type")
```

Returns `True` if the feature is supported, `False` otherwise.

#### get_db_type()

Gets the database type.

```python
db_type = registry.get_db_type()
```

Returns a string like "postgresql", "sqlite", "mysql", etc.

#### verify_bill_version_compatibility()

Verifies that the current schema supports the BillVersion model.

```python
is_compatible = registry.verify_bill_version_compatibility()
```

Returns `True` if compatible, `False` otherwise.

#### get_cross_db_compatible_features()

Gets features that are compatible across multiple database types.

```python
features = registry.get_cross_db_compatible_features(
    db_types=["postgresql", "sqlite", "mysql"]
)
```

Returns a list of feature strings.

#### get_db_compatibility_summary()

Gets a comprehensive summary of database compatibility.

```python
summary = registry.get_db_compatibility_summary()
```

Returns a dictionary with compatibility information for each database type.

### Utility Methods

#### _execute_sql()

Executes SQL with proper error handling.

```python
results = registry._execute_sql("SELECT version FROM schema_version")
```

Returns query results if successful.

Raises:
- `DatabaseExecutionError`: If SQL execution fails

#### _ensure_version_table()

Ensures the version table exists, creating it if needed.

```python
registry._ensure_version_table()
```

#### _get_features_for_db_type()

Gets supported features for a specific database type.

```python
features = registry._get_features_for_db_type("postgresql")
```

Returns a list of supported feature strings.

## Feature Support by Database Type

The Schema Registry tracks feature support across different database backends:

| Feature               | PostgreSQL | SQLite | MySQL | Oracle | SQL Server |
|-----------------------|------------|--------|-------|--------|------------|
| json_column_type      | ✅         | ❌     | ✅    | ❌     | ❌        |
| array_column_type     | ✅         | ❌     | ❌    | ❌     | ❌        |
| full_text_search      | ✅         | ✅     | ✅    | ✅     | ✅        |
| partitioning          | ✅         | ❌     | ✅    | ✅     | ✅        |
| concurrent_index      | ✅         | ❌     | ❌    | ❌     | ❌        |
| materialized_views    | ✅         | ❌     | ❌    | ✅     | ✅        |
| window_functions      | ✅         | ✅     | ✅    | ✅     | ✅        |
| tablespaces           | ✅         | ❌     | ✅    | ✅     | ✅        |
| schemas               | ✅         | ❌     | ✅    | ✅     | ✅        |
| foreign_keys          | ✅         | ✅     | ✅    | ✅     | ✅        |
| triggers              | ✅         | ✅     | ✅    | ✅     | ✅        |
| stored_procedures     | ✅         | ❌     | ✅    | ✅     | ✅        |
| check_constraints     | ✅         | ✅     | ✅    | ✅     | ✅        |
| cte_support           | ✅         | ✅     | ✅    | ✅     | ✅        |
| upsert                | ✅         | ✅     | ✅    | ✅     | ✅        |

## Error Handling

The Schema Registry defines several custom exception types:

### SchemaVersionError

Raised when there's a conflict with schema versions:
- Version already exists
- Version gap detected
- Invalid version format

### SchemaDowngradeError

Raised when attempting to downgrade without permission.

### DatabaseExecutionError

Raised when SQL execution fails.

### FeatureNotSupportedError

Raised when attempting to use a feature not supported by the current database.

### Example Error Handling

```python
from pygovpub.storage.schema_registry import (
    SchemaRegistry, 
    SchemaVersionError,
    SchemaDowngradeError,
    DatabaseExecutionError
)

try:
    registry.register_version("1.2.0", "New version")
except SchemaVersionError as e:
    print(f"Version conflict: {str(e)}")
except SchemaDowngradeError as e:
    print(f"Downgrade not allowed: {str(e)}")
except DatabaseExecutionError as e:
    print(f"Database error: {str(e)}")
```

## Metrics

The Schema Registry collects the following metrics:

- `SCHEMA_VERSION_REGISTRATION_TOTAL`: Counter for version registrations
- `SCHEMA_VERSION_REGISTRATION_ERRORS`: Counter for registration errors
- `SCHEMA_MIGRATION_DURATION`: Histogram for migration execution time
- `SCHEMA_COMPATIBILITY_DURATION`: Histogram for compatibility check time
- `SCHEMA_DOWNGRADE_ATTEMPTS`: Counter for attempted downgrades
- `SCHEMA_VERSION_CONFLICTS`: Counter for version conflicts

Access metrics via the Prometheus client library:

```python
from prometheus_client import REGISTRY

# Get metrics
for metric in REGISTRY.collect():
    if metric.name.startswith('pygovpub_schema_'):
        print(f"{metric.name}: {metric.samples}")
```

## Integration with Health Checks

The Schema Registry integrates with the health check system:

```python
from pygovpub.diagnostics.health import run_health_check

health_data = run_health_check()

# Check database schema status
if "database" in health_data:
    schema_version = health_data["database"].get("schema_version")
    if schema_version:
        print(f"Current schema version: {schema_version}")
```