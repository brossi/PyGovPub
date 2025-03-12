"""
Schema versioning system for tracking database versions across different backends.

This module provides a registry for managing schema versions, migrations, and feature
compatibility across different database backends. It helps ensure that schema-dependent
features are only enabled when the database schema supports them.
"""

import json
from datetime import datetime
from typing import Dict, List, Optional, Any

import structlog
from sqlalchemy import text, inspect
from prometheus_client import Counter, Gauge

logger = structlog.get_logger()

# Schema metrics
SCHEMA_VERSION = Gauge(
    "schema_version",
    "Database schema version",
    ["db_type"]
)
SCHEMA_UPGRADES = Counter(
    "schema_upgrades_total",
    "Total schema upgrades",
    ["db_type", "status"]
)

class SchemaRegistry:
    """Manages schema versioning across different database backends"""

    def __init__(self, storage_interface):
        """
        Initialize the schema registry.
        
        Args:
            storage_interface: Storage interface instance
        """
        self.storage = storage_interface
        self.db_type = storage_interface.db_type

        # Initialize schema_versions table if it doesn't exist
        self._ensure_version_table()

        # Compatibility matrix maps features to required schema versions for each DB type
        self.compatibility_matrix = {
            "vector_search": {"postgresql": 5, "sqlite": 3},
            "advanced_partitioning": {"postgresql": 7},
            "full_text_search": {"postgresql": 3, "sqlite": 4},
            "database_events": {"postgresql": 4},
            "document_versioning": {"postgresql": 6, "sqlite": 5},
        }

    def _ensure_version_table(self):
        """Create schema_versions table if it doesn't exist."""
        if self.db_type in ["pinecone", "supabase"]:
            return

        try:
            with self.storage.engine.connect() as conn:
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS schema_versions (
                        version INTEGER PRIMARY KEY,
                        applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        description TEXT,
                        components JSON,
                        db_type VARCHAR(50)
                    )
                """))
        except Exception as e:
            logger.error("Failed to create schema version table", error=str(e))

    def get_current_version(self) -> Optional[int]:
        """
        Get the current schema version for this database type.
        
        Returns:
            Current schema version or None if not set
        """
        if self.db_type in ["pinecone", "supabase"]:
            return None

        try:
            with self.storage.engine.connect() as conn:
                # First check if the table exists
                inspector = inspect(self.storage.engine)
                if 'schema_versions' not in inspector.get_table_names():
                    logger.warning("Schema version table not found")
                    return None

                result = conn.execute(text("""
                    SELECT MAX(version) FROM schema_versions
                    WHERE db_type = :db_type
                """), {"db_type": self.db_type})

                version = result.scalar()
                if version is not None:
                    # Update the metric for monitoring
                    SCHEMA_VERSION.labels(db_type=self.db_type).set(version)

                return version
        except Exception as e:
            logger.error("Failed to get schema version", error=str(e))
            return None

    def register_version(self, version: int, description: str, components: List[str]) -> bool:
        """
        Register a new schema version after migration.
        
        Args:
            version: Version number
            description: Description of the changes
            components: List of components affected
            
        Returns:
            True if registration successful, False otherwise
        """
        if self.db_type in ["pinecone", "supabase"]:
            return False

        try:
            with self.storage.engine.connect() as conn:
                conn.execute(text("""
                    INSERT INTO schema_versions (version, description, components, db_type)
                    VALUES (:version, :description, :components, :db_type)
                """), {
                    "version": version,
                    "description": description,
                    "components": json.dumps(components),
                    "db_type": self.db_type
                })

                # Update the schema version metric
                SCHEMA_VERSION.labels(db_type=self.db_type).set(version)

                # Record successful upgrade
                SCHEMA_UPGRADES.labels(db_type=self.db_type, status="success").inc()

                logger.info(
                    "Registered schema version",
                    version=version,
                    description=description,
                    db_type=self.db_type
                )
                return True
        except Exception as e:
            # Record failed upgrade
            SCHEMA_UPGRADES.labels(db_type=self.db_type, status="error").inc()

            logger.error("Failed to register schema version", error=str(e), version=version)
            return False

    def supports_feature(self, feature_name: str) -> bool:
        """
        Check if current schema version supports a feature.
        
        Args:
            feature_name: Feature name to check
            
        Returns:
            True if feature is supported, False otherwise
        """
        current_version = self.get_current_version()
        if not current_version:
            return False

        required = self.compatibility_matrix.get(feature_name, {}).get(self.db_type)
        return required is not None and current_version >= required

    def get_version_history(self) -> List[Dict[str, Any]]:
        """
        Get the full version history for this database type.
        
        Returns:
            List of version records
        """
        if self.db_type in ["pinecone", "supabase"]:
            return []

        try:
            with self.storage.engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT version, applied_at, description, components
                    FROM schema_versions
                    WHERE db_type = :db_type
                    ORDER BY version
                """), {"db_type": self.db_type})

                return [
                    {
                        "version": row[0],
                        "applied_at": row[1],
                        "description": row[2],
                        "components": json.loads(row[3]) if row[3] else []
                    }
                    for row in result
                ]
        except Exception as e:
            logger.error("Failed to get version history", error=str(e))
            return []

    def get_feature_compatibility(self) -> Dict[str, bool]:
        """
        Get a dictionary of all features and whether they're supported.
        
        Returns:
            Dictionary mapping feature names to support status
        """
        if self.db_type in ["pinecone", "supabase"]:
            # Cloud providers handle compatibility differently
            return {feature: feature in self.storage.features for feature in self.compatibility_matrix}

        compatibility = {}
        for feature in self.compatibility_matrix:
            compatibility[feature] = self.supports_feature(feature)

        return compatibility