# Schema Migration Workflow

This document describes the workflow for managing database schema migrations in PyGovPub.

## Overview

PyGovPub uses a versioned migration system to:

1. Track schema versions across multiple database backends
2. Ensure compatibility between database schema and application code
3. Prevent version conflicts and accidental downgrades
4. Support cross-database compatibility checks
5. Provide transaction-based migrations with rollback capability

## Schema Registry

The Schema Registry is responsible for:

- Creating and maintaining a version table in the database
- Registering new schema versions with proper sequencing
- Applying migrations with transaction support
- Verifying compatibility with models like BillVersion
- Checking cross-database feature compatibility

## Migration Workflow

### 1. Creating a Migration

To create a new migration, follow these steps:

1. Create a SQL file in the `migrations` directory with the following naming convention:
   ```
   V{major}_{minor}_{patch}__description.sql
   ```
   Example: `V1_2_0__add_bill_version_table.sql`

2. Write your SQL migration with both "up" and "down" sections:
   ```sql
   -- UP MIGRATION
   CREATE TABLE bill_version (
     version_id VARCHAR(255) PRIMARY KEY,
     bill_id VARCHAR(255) NOT NULL,
     version_code VARCHAR(50) NOT NULL,
     published_date TIMESTAMP NOT NULL,
     govinfo_package_id VARCHAR(255) NULL
   );
   
   -- DOWN MIGRATION
   DROP TABLE IF EXISTS bill_version;
   ```

### 2. Applying a Migration

Use the schema registry to apply migrations:

```python
from pygovpub.storage.schema_registry import SchemaRegistry

# Initialize registry with database connection
registry = SchemaRegistry(connection)

# Apply a migration
success = registry.apply_migration(
    version="1.2.0",
    description="Add bill version table",
    up_sql="CREATE TABLE bill_version...",
    down_sql="DROP TABLE IF EXISTS bill_version;",
    force=False  # Set to True to override some safety checks
)

if success:
    print("Migration applied successfully")
else:
    print("Migration failed")
```

### 3. Registering a Version

After a successful migration, register the new version:

```python
registry.register_version(
    version="1.2.0",
    description="Add bill version table",
    api_version="3.1.0"  # Associated API version
)
```

### 4. Checking Version History

To get the version history:

```python
version_history = registry.get_version_history()
for version in version_history:
    print(f"Version {version['version']} - {version['description']}")
    print(f"  Applied at {version['applied_at']}")
    print(f"  API Version: {version['api_version']}")
```

### 5. Verifying Model Compatibility

To verify that the current schema supports specific models:

```python
from pygovpub.models.legislative_db import BillVersion

# Check compatibility with BillVersion model
is_compatible = registry.verify_bill_version_compatibility()
if not is_compatible:
    print("Database schema not compatible with BillVersion model")
```

## Cross-Database Compatibility

The schema registry supports checking feature compatibility across different database types:

```python
# Get features that are compatible across PostgreSQL and SQLite
compatible_features = registry.get_cross_db_compatible_features(
    db_types=["postgresql", "sqlite"]
)

# Get compatibility summary for all supported database types
compatibility_summary = registry.get_db_compatibility_summary()
```

## Safety Mechanisms

The migration system includes several safety mechanisms:

### Version Conflict Detection

The system prevents:
- Gaps in version sequences (e.g., jumping from 1.0.0 to 1.2.0 without 1.1.0)
- Out-of-order version application
- Duplicate version registrations

### Schema Downgrade Prevention

Downgrading to earlier schema versions is prevented by default as it may cause data loss. To allow a downgrade:

```python
registry.register_version(
    version="1.1.0",  # Earlier version than current
    description="Rollback to previous schema",
    allow_downgrade=True  # Explicitly allow downgrade
)
```

### Transactional Migrations

All migrations run in a transaction that will be rolled back if the migration fails:

```python
try:
    success = registry.apply_migration(
        version="1.2.0",
        description="Add bill version table",
        up_sql="CREATE TABLE bill_version...",
        down_sql="DROP TABLE IF EXISTS bill_version;",
    )
except Exception as e:
    print(f"Migration failed and was rolled back: {str(e)}")
```

## Best Practices

1. **Version Sequentially**: Follow semantic versioning (MAJOR.MINOR.PATCH) and increment appropriately.

2. **Always Include Down Migration**: Every migration should include SQL to revert the changes.

3. **Test Migrations on Multiple Database Types**: Verify migrations work on all supported databases.

4. **Keep Migrations Atomic**: Each migration should represent a single logical change.

5. **Verify Model Compatibility**: Run compatibility checks to ensure models work with the schema.

6. **Document API Version Dependencies**: Track which API versions require which schema versions.

7. **Use Transactions**: Always leverage the built-in transaction support for safety.

8. **Monitor Migration Performance**: Large migrations can cause downtime; plan accordingly.