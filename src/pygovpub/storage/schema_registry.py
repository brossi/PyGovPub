"""
Schema versioning system for tracking database versions across different backends.

This module provides a registry for managing schema versions, migrations, and feature
compatibility across different database backends. It helps ensure that schema-dependent
features are only enabled when the database schema supports them.
"""

import json
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple, Set

import structlog
from sqlalchemy import text, inspect, Connection, Engine
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
SCHEMA_COMPATIBILITY_CHECKS = Counter(
    "schema_compatibility_checks_total",
    "Total schema compatibility checks",
    ["db_type", "feature", "result"]
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
            "vector_search": {"postgresql": 5, "sqlite": 3, "mysql": 3},
            "advanced_partitioning": {"postgresql": 7, "mysql": 5},
            "full_text_search": {"postgresql": 3, "sqlite": 4, "mysql": 4},
            "database_events": {"postgresql": 4, "mysql": 4},
            "document_versioning": {"postgresql": 6, "sqlite": 5, "mysql": 5},
            "hybrid_search": {"lancedb": 1},
            "vector_operations": {"lancedb": 1, "postgresql": 5}
        }
        
        logger.info(
            "Schema registry initialized",
            db_type=self.db_type,
            current_version=self.get_current_version()
        )

    def _ensure_version_table(self):
        """Create schema_versions table if it doesn't exist."""
        if self.db_type in ["pinecone", "supabase"]:
            return

        try:
            with self.storage.engine.connect() as conn:
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS schema_versions (
                        version INTEGER NOT NULL,
                        applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        description TEXT,
                        components JSON,
                        db_type VARCHAR(50) NOT NULL,
                        api_version VARCHAR(50),
                        applied_by VARCHAR(255),
                        checksum VARCHAR(64),
                        PRIMARY KEY (version, db_type)
                    )
                """))
                conn.commit()
                
            # Check if the table was created successfully
            with self.storage.engine.connect() as conn:
                inspector = inspect(self.storage.engine)
                if 'schema_versions' in inspector.get_table_names():
                    logger.info("Schema version table verified", db_type=self.db_type)
                else:
                    logger.warning("Failed to verify schema version table", db_type=self.db_type)
        except Exception as e:
            logger.error("Failed to create schema version table", error=str(e), db_type=self.db_type)

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
            logger.error("Failed to get schema version", error=str(e), db_type=self.db_type)
            return None

    def register_version(self, 
                        version: int, 
                        description: str, 
                        components: List[str],
                        api_version: Optional[str] = None,
                        applied_by: Optional[str] = None,
                        checksum: Optional[str] = None) -> bool:
        """
        Register a new schema version after migration.
        
        Args:
            version: Version number
            description: Description of the changes
            components: List of components affected
            api_version: Optional API version this schema supports
            applied_by: Optional username or process that applied the migration
            checksum: Optional checksum of migration script for verification
            
        Returns:
            True if registration successful, False otherwise
        """
        if self.db_type in ["pinecone", "supabase"]:
            return False
            
        # Verify the version is sequential
        current_version = self.get_current_version()
        if current_version is not None and version <= current_version:
            logger.error(
                "Cannot register non-sequential version",
                current=current_version,
                attempted=version,
                db_type=self.db_type
            )
            SCHEMA_UPGRADES.labels(db_type=self.db_type, status="error_sequence").inc()
            return False

        try:
            with self.storage.engine.connect() as conn:
                conn.execute(text("""
                    INSERT INTO schema_versions 
                    (version, description, components, db_type, api_version, applied_by, checksum)
                    VALUES (:version, :description, :components, :db_type, :api_version, :applied_by, :checksum)
                """), {
                    "version": version,
                    "description": description,
                    "components": json.dumps(components),
                    "db_type": self.db_type,
                    "api_version": api_version,
                    "applied_by": applied_by,
                    "checksum": checksum
                })
                conn.commit()

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

            logger.error("Failed to register schema version", error=str(e), version=version, db_type=self.db_type)
            return False

    def supports_feature(self, feature_name: str) -> bool:
        """
        Check if current schema version supports a feature.
        
        Args:
            feature_name: Feature name to check
            
        Returns:
            True if feature is supported, False otherwise
        """
        # Special handling for cloud providers - they either have the feature or not
        if self.db_type in ["pinecone", "supabase", "lancedb"]:
            result = feature_name in self.storage.features
            SCHEMA_COMPATIBILITY_CHECKS.labels(
                db_type=self.db_type, 
                feature=feature_name,
                result="supported" if result else "unsupported"
            ).inc()
            return result
            
        # Get current schema version
        current_version = self.get_current_version()
        if not current_version:
            SCHEMA_COMPATIBILITY_CHECKS.labels(
                db_type=self.db_type, 
                feature=feature_name,
                result="no_schema"
            ).inc()
            return False

        required = self.compatibility_matrix.get(feature_name, {}).get(self.db_type)
        result = required is not None and current_version >= required
        
        # Record metric
        SCHEMA_COMPATIBILITY_CHECKS.labels(
            db_type=self.db_type, 
            feature=feature_name,
            result="supported" if result else "unsupported"
        ).inc()
        
        return result

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
                    SELECT version, applied_at, description, components, api_version, applied_by
                    FROM schema_versions
                    WHERE db_type = :db_type
                    ORDER BY version
                """), {"db_type": self.db_type})

                return [
                    {
                        "version": row[0],
                        "applied_at": row[1],
                        "description": row[2],
                        "components": json.loads(row[3]) if row[3] else [],
                        "api_version": row[4],
                        "applied_by": row[5]
                    }
                    for row in result
                ]
        except Exception as e:
            logger.error("Failed to get version history", error=str(e), db_type=self.db_type)
            return []

    def get_feature_compatibility(self) -> Dict[str, bool]:
        """
        Get a dictionary of all features and whether they're supported.
        
        Returns:
            Dictionary mapping feature names to support status
        """
        if self.db_type in ["pinecone", "supabase", "lancedb"]:
            # Cloud providers handle compatibility differently
            return {
                feature: feature in self.storage.features 
                for feature in self.compatibility_matrix
            }

        compatibility = {}
        for feature in self.compatibility_matrix:
            compatibility[feature] = self.supports_feature(feature)

        return compatibility
        
    def is_compatible_with_api_version(self, api_version: str) -> bool:
        """
        Check if the current schema is compatible with a specific API version.
        
        Args:
            api_version: API version string (e.g., "1.0.0")
            
        Returns:
            True if compatible, False otherwise
        """
        if self.db_type in ["pinecone", "supabase", "lancedb"]:
            # Cloud providers are version-independent
            return True
            
        try:
            with self.storage.engine.connect() as conn:
                # Find the most recent schema version that supports this API version
                result = conn.execute(text("""
                    SELECT MAX(version) FROM schema_versions
                    WHERE db_type = :db_type AND api_version = :api_version
                """), {
                    "db_type": self.db_type,
                    "api_version": api_version
                })
                
                required_version = result.scalar()
                current_version = self.get_current_version()
                
                if not required_version or not current_version:
                    return False
                    
                return current_version >= required_version
        except Exception as e:
            logger.error(
                "Failed to check API compatibility", 
                error=str(e), 
                api_version=api_version,
                db_type=self.db_type
            )
            return False
    
    def get_required_features(self, api_version: str) -> Set[str]:
        """
        Get the set of features required for a specific API version.
        
        Args:
            api_version: API version string (e.g., "1.0.0")
            
        Returns:
            Set of feature names required by the API version
        """
        if self.db_type in ["pinecone", "supabase", "lancedb"]:
            # For cloud providers, return empty set as features are handled differently
            return set()
            
        try:
            # Get all version records that match this API version
            with self.storage.engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT components FROM schema_versions
                    WHERE db_type = :db_type AND api_version = :api_version
                """), {
                    "db_type": self.db_type,
                    "api_version": api_version
                })
                
                # Combine all features from matching versions
                required_features = set()
                for row in result:
                    components = json.loads(row[0]) if row[0] else []
                    for component in components:
                        # Extract feature from component notation (e.g., "feature:vector_search")
                        if ":" in component:
                            feature = component.split(":", 1)[1]
                            required_features.add(feature)
                
                return required_features
        except Exception as e:
            logger.error(
                "Failed to get required features", 
                error=str(e), 
                api_version=api_version,
                db_type=self.db_type
            )
            return set()
    
    def verify_migrations(self) -> Tuple[bool, List[Dict[str, Any]]]:
        """
        Verify that schema migrations are sequential and have valid checksums.
        
        Returns:
            Tuple containing:
            - Boolean indicating if all migrations are valid
            - List of problem migrations
        """
        if self.db_type in ["pinecone", "supabase", "lancedb"]:
            # Cloud providers don't use migrations
            return (True, [])
            
        problems = []
        
        try:
            with self.storage.engine.connect() as conn:
                # Get all migrations in order
                result = conn.execute(text("""
                    SELECT version, applied_at, description, checksum
                    FROM schema_versions
                    WHERE db_type = :db_type
                    ORDER BY version
                """), {"db_type": self.db_type})
                
                versions = [row[0] for row in result]
                
                # Check for gaps in the sequence
                for i, version in enumerate(versions):
                    expected = i + 1  # Versions should start at 1 and increment
                    if version != expected:
                        problems.append({
                            "version": version,
                            "issue": f"Sequence gap: expected {expected}",
                            "severity": "high"
                        })
                
                # Additional checks can be added here (e.g., checksum verification)
                
                return (len(problems) == 0, problems)
        except Exception as e:
            logger.error("Failed to verify migrations", error=str(e), db_type=self.db_type)
            problems.append({
                "version": None,
                "issue": f"Query error: {str(e)}",
                "severity": "critical"
            })
            return (False, problems)