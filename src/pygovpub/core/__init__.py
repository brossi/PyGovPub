"""
Core functionality for PyGovPub SDK.

This package contains core modules that provide functionality
used across the SDK.
"""

# Import database modules for convenience
from pygovpub.core.database import (
    get_engine,
    get_session,
    with_transaction,
    get_async_session,
    with_async_transaction,
    create_tables,
    drop_tables,
    get_migration_version,
    run_migrations,
    MigrationManager
)

# Import CRUD modules for convenience
from pygovpub.core.crud import (
    CRUDBase,
    create_entity,
    get_entity,
    get_entities,
    update_entity,
    delete_entity,
    count_entities
)