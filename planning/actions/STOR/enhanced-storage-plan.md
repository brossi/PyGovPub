# Enhanced PyGovPub Storage Architecture Implementation Plan

## Executive Summary

This document outlines a streamlined implementation plan for expanding PyGovPub's storage architecture to support multiple database backends (PostgreSQL with pgVector, SQLite) while enabling cloud storage solutions (Supabase, Pinecone) as optional, on-demand features. The enhanced plan addresses critical infrastructure needs including error handling, monitoring, security, and async support with clear integration paths to existing architecture.

## 1. System Architecture

### 1.1 Core Components

```
┌─────────────────┐       ┌───────────────┐       ┌────────────────┐
│  External APIs  │◄─────►│               │       │ Monitoring &   │
│ (GovInfo, etc.) │       │               │◄─────►│ Error Tracking │
└─────────────────┘       │   PyGovPub    │       └────────────────┘
                          │   Application  │
┌─────────────────┐       │               │       ┌────────────────┐
│    Billy LLM    │◄─────►│               │◄─────►│  Security &    │
└─────────────────┘       └───────┬───────┘       │ Access Control │
                                  │               └────────────────┘
                                  ▼
                          ┌───────────────┐
                          │    Storage    │
                          │   Interface   │
                          └───────┬───────┘
                                  │
           ┌──────────────────────┼────────────────────┐
           │                      │                    │
           ▼                      ▼                    ▼
┌────────────────┐      ┌─────────────────┐    ┌─────────────────────┐
│  PostgreSQL +  │      │     SQLite      │    │  Optional Providers │
│   pgVector     │      │                 │    │ (Supabase/Pinecone) │
└────────────────┘      └─────────────────┘    └─────────────────────┘
```

### 1.2 Key Design Principles

1. **Minimal Abstraction**: Create only the necessary abstraction to support multiple databases
2. **Optional Dependencies**: Make cloud provider libraries optional and load them only when configured
3. **Feature Detection**: Identify database capabilities at runtime to enable appropriate functionality
4. **Progressive Enhancement**: Add features incrementally as database support allows
5. **Resilient Operations**: Implement structured logging, circuit breakers, and monitoring
6. **Secure by Default**: Ensure data and credentials are protected throughout the system
7. **Schema Versioning**: Track schema compatibility across different database backends using <mcsymbol name="BillVersion" filename="database-schema.md"></mcsymbol> and <mcsymbol name="DocumentContent" filename="database-schema.md"></mcsymbol> models
8. **Consistent Implementation**: Enforce <mcfile name="naming-conventions.md"></mcfile> across all storage components

## 2. Dependencies Management

### 2.1 Core Requirements

```
# Core SQLAlchemy and Database
sqlalchemy>=2.0.0  # Note: Use compatibility mode with SQLModel
alembic>=1.12.0    # Database migrations
asyncpg>=0.27.0    # PostgreSQL async support
aiosqlite>=0.19.0  # SQLite async support
psycopg>=3.1.16    # PostgreSQL support

# Vector Extensions
pgvector>=0.2.4    # Python bindings for pgVector extension

# Embedding Generation
sentence-transformers>=2.2.2  # Embedding models
torch>=2.1.0       # Required by sentence-transformers (CPU-only is sufficient)

# Error Handling & Monitoring
structlog>=24.0.0  # Structured logging
tenacity>=8.2.3    # Retry mechanisms
prometheus-client>=0.20.0  # Metrics collection
circuit-breaker-python>=1.0.1  # Circuit breaking for catastrophic failures

# Security
cryptography>=40.0.0  # For data encryption
```

### 2.2 Optional Cloud Provider Dependencies

[*] We'll make these dependencies optional by using extras_require in setup.py:

```python
# In setup.py
setup(
    name="pygovpub",
    # ...other parameters...
    install_requires=[
        "fastapi>=0.95.0",
        "sqlalchemy>=2.0.0",
        "cryptography>=40.0.0",
        "structlog>=24.0.0",
        "tenacity>=8.2.3",
        "prometheus-client>=0.20.0",
        "circuit-breaker-python>=1.0.1",
        # other core dependencies
    ],
    extras_require={
        "pinecone": ["pinecone-client>=2.2.4"],
        "supabase": ["supabase>=2.0.3"],
        "cloud": ["pinecone-client>=2.2.4", "supabase>=2.0.3"],
        "llm": ["transformers>=4.36.0", "accelerate>=0.25.0"],
        "mysql": ["mysqlclient>=2.2.1", "aiomysql>=0.2.0"],
        "lancedb": ["lancedb>=0.4.1"],
    }
)
```

## 3. Enhanced Implementation Plan

### 3.1 Storage Interface with Integrated Monitoring and Circuit Breaking (Priority: High)

- Add error translation layer mapping storage exceptions to <mcsymbol name="APIError" filename="api-documentation.md"></mcsymbol> format
- Implement security event logging aligned with <mcfile name="api-documentation.md"></mcfile> standards
- Ensure vector search implementations respect <mcsymbol name="ContentHash" filename="database-schema.md"></mcsymbol> indexing constraints

Create a minimal storage interface with monitoring, error tracking, circuit breaking, and database abstraction.

```python
# pygovpub/storage/interface.py
import importlib.util
import time
from typing import Any, Dict, List, Optional, Type, TypeVar, Generic, Union

import structlog
from prometheus_client import Counter, Histogram, Gauge
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from tenacity import retry, stop_after_attempt, wait_exponential
from circuit_breaker import CircuitBreaker

# Set up structured logging
logger = structlog.get_logger()

# Set up metrics
DB_OPERATIONS = Counter("db_operations_total", "Total database operations", ["operation", "status", "db_type"])
DB_OPERATION_DURATION = Histogram("db_operation_duration_seconds", "Database operation duration in seconds",
                                 ["operation", "db_type"])
DB_CONNECTIONS_ACTIVE = Gauge("db_connections_active", "Active database connections", ["db_type"])

T = TypeVar("T")

# Circuit breaker configuration
CONNECTION_CIRCUIT_BREAKER = CircuitBreaker(
    name="database_connection",
    failure_threshold=5,
    recovery_timeout=30,
    expected_exception=Exception
)

class StorageInterface:
    """Database-agnostic storage interface with monitoring and fallbacks"""

    def __init__(self, connection_string: str, **config):
        self.connection_string = connection_string
        self.config = config
        self.db_type = self._determine_db_type(connection_string)

        # Schema version tracking
        self.schema_version = None

        # Setup sync engine with appropriate pool settings
        self.engine = create_engine(
            connection_string,
            echo=config.get("echo", False),
            pool_pre_ping=True,  # Health check for connection pool
            pool_size=config.get("pool_size", 5),
            max_overflow=config.get("max_overflow", 10),
            pool_timeout=config.get("pool_timeout", 30),
            pool_recycle=config.get("pool_recycle", 1800)  # Recycle connections after 30 min
        )
        self.Session = sessionmaker(bind=self.engine)

        # Setup async engine if supported
        if self._supports_async():
            async_connection = self._get_async_connection_string(connection_string)
            self.async_engine = create_async_engine(
                async_connection,
                echo=config.get("echo", False),
                pool_pre_ping=True,
                pool_size=config.get("pool_size", 5),
                max_overflow=config.get("max_overflow", 10),
                pool_timeout=config.get("pool_timeout", 30),
                pool_recycle=config.get("pool_recycle", 1800)
            )
            self.AsyncSession = sessionmaker(
                bind=self.async_engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
        else:
            self.async_engine = None
            self.AsyncSession = None

        # Detect features and capabilities
        self.features = self._detect_features()

        # Load schema version
        self.schema_version = self._get_schema_version()

        logger.info(
            "Storage interface initialized",
            db_type=self.db_type,
            features=self.features,
            schema_version=self.schema_version,
            async_supported=self._supports_async()
        )

    def _determine_db_type(self, connection_string: str) -> str:
        """Determine database type from connection string"""
        if "sqlite" in connection_string:
            return "sqlite"
        elif "postgresql" in connection_string:
            return "postgresql"
        elif "mysql" in connection_string:
            return "mysql"
        elif "pinecone" in connection_string:
            return "pinecone"
        elif "supabase" in connection_string:
            return "supabase"
        elif "lancedb://" in connection_string:
            return "lancedb"
        else:
            return "unknown"

    def _get_async_connection_string(self, connection_string: str) -> str:
        """Convert standard connection string to async equivalent"""
        if "sqlite" in connection_string:
            # Convert sqlite:/// to sqlite+aiosqlite:///
            return connection_string.replace("sqlite:///", "sqlite+aiosqlite:///")
        elif "postgresql" in connection_string:
            # Convert postgresql:// to postgresql+asyncpg://
            return connection_string.replace("postgresql://", "postgresql+asyncpg://")
        else:
            # Return original for non-standard backends
            return connection_string

    def _supports_async(self) -> bool:
        """Check if async operations are supported for this database"""
        db_type = self.db_type

        if db_type == "sqlite":
            return self._is_package_available("aiosqlite")
        elif db_type == "postgresql":
            return self._is_package_available("asyncpg")
        else:
            # Cloud providers use their own async patterns
            return False

    def _detect_features(self) -> Dict[str, bool]:
        """Detect database features and capabilities"""
        features = {'basic_storage': True}

        # PostgreSQL with pgVector detection
        if self.db_type == "postgresql":
            try:
                with self.engine.connect() as conn:
                    result = conn.execute(text("SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'vector')"))
                    if result.scalar():
                        features['vector_operations'] = True
                    else:
                        logger.warning("PostgreSQL detected but pgvector extension not installed")
            except Exception as e:
                logger.error("Error detecting pgVector extension", error=str(e))
                # Fallback to basic PostgreSQL
                features['fallback_basic_postgresql'] = True

        # SQLite detection
        elif self.db_type == "sqlite":
            features['local_storage'] = True
            # SQLite FTS5 for full-text search
            try:
                with self.engine.connect() as conn:
                    conn.execute(text("SELECT fts5()"))
                    features['full_text_search'] = True
            except Exception:
                logger.info("SQLite FTS5 extension not available")

        # Cloud provider feature detection
        elif self.db_type == "pinecone" and self._is_package_available('pinecone'):
            features['cloud_storage'] = True
            features['vector_operations'] = True

        elif self.db_type == "supabase" and self._is_package_available('supabase'):
            features['cloud_storage'] = True
            # Check if Supabase has pgvector enabled
            try:
                from pygovpub.storage.providers import supabase_provider
                client = supabase_provider.initialize(
                    self.config.get('url'),
                    self.config.get('key')
                )
                result = client.rpc('has_pgvector').execute()
                if result.data:
                    features['vector_operations'] = True
            except Exception as e:
                logger.error("Error checking Supabase pgvector support", error=str(e))

        # LanceDB feature detection
        elif self.db_type == "lancedb" and self._is_package_available('lancedb'):
            features['vector_operations'] = True
            features['hybrid_search'] = True
            features['full_text_search'] = True
            features['embedded_database'] = True

            # Check for optional LanceDB capabilities
            try:
                import lancedb
                from pygovpub.storage.providers import lancedb_provider

                # Initialize provider to check capabilities
                provider = lancedb_provider.LanceDBProvider(self.connection_string.replace("lancedb://", ""))

                # Check for HNSW index support
                if hasattr(lancedb, "index") and hasattr(lancedb.index, "HNSW"):
                    features['hnsw_index'] = True

                # Check for versioning support
                if hasattr(provider.db, "create_version"):
                    features['versioning'] = True

                # Record provider for later use
                self._providers["lancedb"] = provider

            except Exception as e:
                logger.error("Error during LanceDB feature detection", error=str(e))

        return features

    def _is_package_available(self, package_name: str) -> bool:
        """Check if a Python package is installed and available"""
        return importlib.util.find_spec(package_name) is not None

    def _get_schema_version(self) -> Optional[int]:
        """Get the current schema version from the database"""
        if self.db_type in ["pinecone", "supabase"]:
            return None

        try:
            with self.engine.connect() as conn:
                # Check if schema_versions table exists
                inspector = inspect(self.engine)
                if 'schema_versions' not in inspector.get_table_names():
                    logger.warning("Schema version table not found")
                    return None

                # Get current version
                result = conn.execute(text(
                    "SELECT MAX(version) FROM schema_versions WHERE db_type = :db_type"
                ), {"db_type": self.db_type})
                version = result.scalar()
                return version
        except Exception as e:
            logger.error("Failed to get schema version", error=str(e))
            return None

    def supports(self, feature: str) -> bool:
        """Check if a specific feature is supported"""
        return self.features.get(feature, False)

    def supports_schema_feature(self, feature_name: str) -> bool:
        """Check if current schema version supports a feature"""
        # Schema compatibility matrix
        SCHEMA_COMPATIBILITY = {
            "vector_search": {"postgresql": 5, "sqlite": 3},
            "advanced_partitioning": {"postgresql": 7},
            "full_text_search": {"postgresql": 3, "sqlite": 4}
        }

        if not self.schema_version:
            return False

        required = SCHEMA_COMPATIBILITY.get(feature_name, {}).get(self.db_type)
        return required is not None and self.schema_version >= required

    @CONNECTION_CIRCUIT_BREAKER
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True
    )
    def create(self, model_class: Type[T], data: Dict[str, Any]) -> int:
        """Create a new record with monitoring, retry, and circuit breaking"""
        start_time = time.time()
        session = self.Session()

        try:
            # Track active connections
            DB_CONNECTIONS_ACTIVE.labels(db_type=self.db_type).inc()

            instance = model_class(**data)
            session.add(instance)
            session.commit()

            DB_OPERATIONS.labels(operation="create", status="success", db_type=self.db_type).inc()
            DB_OPERATION_DURATION.labels(operation="create", db_type=self.db_type).observe(time.time() - start_time)

            logger.debug("Created record", model=model_class.__name__, id=instance.id)
            return instance.id

        except Exception as e:
            session.rollback()
            DB_OPERATIONS.labels(operation="create", status="error", db_type=self.db_type).inc()
            logger.error(
                "Failed to create record",
                model=model_class.__name__,
                error=str(e),
                error_type=type(e).__name__
            )
            raise
        finally:
            session.close()
            # Decrement active connection count
            DB_CONNECTIONS_ACTIVE.labels(db_type=self.db_type).dec()

    @CONNECTION_CIRCUIT_BREAKER
    async def create_async(self, model_class: Type[T], data: Dict[str, Any]) -> int:
        """Create a new record asynchronously with monitoring and circuit breaking"""
        if not self._supports_async():
            raise NotImplementedError(f"Async operations not supported for {self.db_type}")

        start_time = time.time()
        async_session = self.AsyncSession()

        try:
            # Track active connections
            DB_CONNECTIONS_ACTIVE.labels(db_type=self.db_type).inc()

            instance = model_class(**data)
            async_session.add(instance)
            await async_session.commit()

            DB_OPERATIONS.labels(operation="create_async", status="success", db_type=self.db_type).inc()
            DB_OPERATION_DURATION.labels(operation="create_async", db_type=self.db_type).observe(time.time() - start_time)

            logger.debug("Created record asynchronously", model=model_class.__name__, id=instance.id)
            return instance.id

        except Exception as e:
            await async_session.rollback()
            DB_OPERATIONS.labels(operation="create_async", status="error", db_type=self.db_type).inc()
            logger.error(
                "Failed to create record asynchronously",
                model=model_class.__name__,
                error=str(e),
                error_type=type(e).__name__
            )
            raise
        finally:
            await async_session.close()
            # Decrement active connection count
            DB_CONNECTIONS_ACTIVE.labels(db_type=self.db_type).dec()

    # Additional CRUD methods with monitoring would be implemented similarly
    # get(), update(), delete(), query(), and their async equivalents
```

### 3.2 Schema Version Registry (Priority: High)

Create a system to track schema versions across different database backends.

```python
# pygovpub/storage/schema_registry.py
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
        """Create schema_versions table if it doesn't exist"""
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
        """Get the current schema version for this database type"""
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
        """Register a new schema version after migration"""
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
        """Check if current schema version supports a feature"""
        current_version = self.get_current_version()
        if not current_version:
            return False

        required = self.compatibility_matrix.get(feature_name, {}).get(self.db_type)
        return required is not None and current_version >= required

    def get_version_history(self) -> List[Dict[str, Any]]:
        """Get the full version history for this database type"""
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
        """Get a dictionary of all features and whether they're supported"""
        if self.db_type in ["pinecone", "supabase"]:
            # Cloud providers handle compatibility differently
            return {feature: True for feature in self.compatibility_matrix if feature in self.storage.features}

        compatibility = {}
        for feature in self.compatibility_matrix:
            compatibility[feature] = self.supports_feature(feature)

        return compatibility
```

### 3.3 Security Layer Implementation (Priority: High)

Implement a security layer for protecting API keys and sensitive metadata.

```python
# pygovpub/security/storage_security.py
import os
from typing import Any, Dict, Optional, Set, Union

import structlog
from cryptography.fernet import Fernet
from pydantic_settings import BaseSettings

logger = structlog.get_logger()

class SecuritySettings(BaseSettings):
    """Validate and access security-related environment variables"""
    # Database credentials
    DB_PASSWORD: Optional[str] = None

    # External API keys
    GOVINFO_API_KEY: Optional[str] = None
    PINECONE_API_KEY: Optional[str] = None
    SUPABASE_KEY: Optional[str] = None

    # Encryption settings
    ENCRYPTION_KEY: Optional[str] = None

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

class StorageSecurity:
    """Handles targeted encryption for sensitive metadata fields"""

    def __init__(self, encryption_enabled: bool = True):
        self.settings = SecuritySettings()
        self.encryption_enabled = encryption_enabled

        # Initialize encryption only if enabled
        if encryption_enabled:
            self.cipher = self._initialize_cipher()

            # Define specific fields that should be encrypted
            # Note: These are only metadata fields, not the legislative content itself
            self.sensitive_field_names: Set[str] = {
                "api_key",           # External service credentials
                "classification",    # Document classification markings
                "restricted_note",   # Sensitive annotations
                "personal_data"      # Any fields containing personal identifiers
            }

            logger.info("Storage security initialized with encryption")
        else:
            logger.info("Storage security initialized without encryption")

    def _initialize_cipher(self) -> Fernet:
        """Initialize the encryption cipher"""
        # Use environment variable if available
        key = self.settings.ENCRYPTION_KEY

        if not key:
            # Generate a key only if one doesn't exist
            key_path = os.path.expanduser("~/.pygovpub/crypto.key")
            os.makedirs(os.path.dirname(key_path), exist_ok=True)

            if os.path.exists(key_path):
                with open(key_path, "rb") as key_file:
                    key = key_file.read().decode('utf-8')
            else:
                # Generate new key
                key = Fernet.generate_key().decode('utf-8')
                with open(key_path, "wb") as key_file:
                    key_file.write(key.encode('utf-8'))
                logger.info("Generated new encryption key")

        return Fernet(key.encode('utf-8') if isinstance(key, str) else key)

    def process_metadata(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process metadata for storage, encrypting only specific sensitive fields

        This targets only metadata annotations and classifications - not document content
        """
        if not self.encryption_enabled:
            return data

        processed = {}

        for key, value in data.items():
            # Skip None values
            if value is None:
                processed[key] = None
                continue

            # Only encrypt specific sensitive metadata fields
            if key in self.sensitive_field_names and isinstance(value, str):
                # Add encryption marker and encrypt
                encrypted_value = self.cipher.encrypt(value.encode()).decode('utf-8')
                processed[key] = f"__ENC__:{encrypted_value}"
                logger.debug(f"Encrypted metadata field {key}")
            elif isinstance(value, dict):
                # Recursively process nested dictionaries
                processed[key] = self.process_metadata(value)
            else:
                # Pass through other values
                processed[key] = value

        return processed

    def decrypt_metadata(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Decrypt only the encrypted metadata fields"""
        if not self.encryption_enabled:
            return data

        processed = {}

        for key, value in data.items():
            # Skip None values
            if value is None:
                processed[key] = None
                continue

            # Check for encryption marker
            if isinstance(value, str) and value.startswith("__ENC__:"):
                encrypted_value = value[8:]  # Remove marker
                try:
                    decrypted = self.cipher.decrypt(encrypted_value.encode()).decode('utf-8')
                    processed[key] = decrypted
                except Exception as e:
                    logger.error(f"Failed to decrypt field {key}", error=str(e))
                    processed[key] = "[DECRYPTION ERROR]"
            elif isinstance(value, dict):
                # Recursively process nested dictionaries
                processed[key] = self.decrypt_metadata(value)
            else:
                # Pass through other values
                processed[key] = value

        return processed

    def get_credentials(self, service_name: str) -> Dict[str, str]:
        """
        Get credentials for external services from environment variables

        This centralizes credential access and facilitates future enhancements
        like credential rotation or secrets management integration
        """
        if service_name == "postgres":
            return {"password": self.settings.DB_PASSWORD}
        elif service_name == "govinfo":
            return {"api_key": self.settings.GOVINFO_API_KEY}
        elif service_name == "pinecone":
            return {"api_key": self.settings.PINECONE_API_KEY}
        elif service_name == "supabase":
            return {"key": self.settings.SUPABASE_KEY}
        else:
            logger.warning(f"No credentials configured for service: {service_name}")
            return {}
```

### 3.4 Vector Search Service with Fallbacks (Priority: Medium)

Create a vector search service with appropriate benchmarking and fallbacks.

```python
# pygovpub/search/vector_search.py
from typing import Dict, List, Optional, Any, Tuple
import time
import json
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from sqlalchemy import select, text
from sentence_transformers import SentenceTransformer
from prometheus_client import Histogram, Counter

logger = structlog.get_logger()

# Metrics
VECTOR_SEARCH_DURATION = Histogram(
    "vector_search_duration_seconds",
    "Vector search duration in seconds",
    ["db_type", "strategy", "success"]
)

VECTOR_SEARCH_REQUESTS = Counter(
    "vector_search_requests_total",
    "Vector search requests",
    ["db_type", "strategy"]
)

class VectorSearchService:
    """Vector search service with fallbacks across database types"""

    def __init__(self, storage):
        self.storage = storage
        self.db_type = storage.db_type

        # Load embedding model on demand
        self._embedding_model = None

        # Track benchmark results
        self.benchmark_results = {}

        logger.info("Vector search service initialized", db_type=self.db_type)

    @property
    def embedding_model(self):
        """Lazy-load the embedding model when needed"""
        if self._embedding_model is None:
            try:
                self._embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
                logger.info("Embedding model loaded")
            except Exception as e:
                logger.error("Failed to load embedding model", error=str(e))
                raise
        return self._embedding_model

    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text"""
        if not text:
            raise ValueError("Text cannot be empty")

        try:
            embedding = self.embedding_model.encode(text)
            return embedding.tolist()
        except Exception as e:
            logger.error("Failed to generate embedding", error=str(e))
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True
    )
    def vector_search(self,
                     query: str,
                     limit: int = 10,
                     filter_criteria: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Perform vector search with appropriate implementation for database type
        Falls back to keyword search if vector search not available
        """
        start_time = time.time()
        search_strategy = "unknown"

        try:
            # Generate query embedding
            query_embedding = self.generate_embedding(query)

            # Perform search based on database type
            if self.db_type == "postgresql" and self.storage.supports("vector_operations"):
                VECTOR_SEARCH_REQUESTS.labels(db_type=self.db_type, strategy="pgvector").inc()
                search_strategy = "pgvector"
                results = self._vector_search_postgresql(query_embedding, limit, filter_criteria)
            elif self.db_type == "pinecone":
                from pygovpub.storage.providers import pinecone_provider
                if pinecone_provider.is_available():
                    VECTOR_SEARCH_REQUESTS.labels(db_type=self.db_type, strategy="pinecone").inc()
                    search_strategy = "pinecone"
                    results = self._vector_search_pinecone(query_embedding, limit, filter_criteria)
                else:
                    logger.warning("Pinecone support not available, falling back to keyword search")
                    VECTOR_SEARCH_REQUESTS.labels(db_type=self.db_type, strategy="keyword_fallback").inc()
                    search_strategy = "keyword_fallback"
                    results = self._keyword_search(query, limit, filter_criteria)
            elif self.db_type == "supabase" and self.storage.supports("vector_operations"):
                VECTOR_SEARCH_REQUESTS.labels(db_type=self.db_type, strategy="supabase_pgvector").inc()
                search_strategy = "supabase_pgvector"
                results = self._vector_search_supabase(query_embedding, limit, filter_criteria)
            else:
                # Fall back to keyword search for other databases
                logger.info("Vector search not supported, falling back to keyword search")
                VECTOR_SEARCH_REQUESTS.labels(db_type=self.db_type, strategy="keyword_fallback").inc()
                search_strategy = "keyword_fallback"
                results = self._keyword_search(query, limit, filter_criteria)

            search_duration = time.time() - start_time
            VECTOR_SEARCH_DURATION.labels(
                db_type=self.db_type,
                strategy=search_strategy,
                success="true"
            ).observe(search_duration)

            # Record for benchmarking
            if search_strategy not in self.benchmark_results:
                self.benchmark_results[search_strategy] = []

            self.benchmark_results[search_strategy].append({
                "query_length": len(query),
                "result_count": len(results),
                "duration_ms": int(search_duration * 1000),
                "timestamp": time.time()
            })

            # Keep only last 100 entries for benchmarking
            if len(self.benchmark_results[search_strategy]) > 100:
                self.benchmark_results[search_strategy] = self.benchmark_results[search_strategy][-100:]

            logger.info(
                "Search completed",
                db_type=self.db_type,
                strategy=search_strategy,
                query_length=len(query),
                result_count=len(results),
                duration_ms=int(search_duration * 1000)
            )

            return results

        except Exception as e:
            search_duration = time.time() - start_time
            VECTOR_SEARCH_DURATION.labels(
                db_type=self.db_type,
                strategy=search_strategy,
                success="false"
            ).observe(search_duration)

            logger.error(
                "Search failed",
                db_type=self.db_type,
                error=str(e),
                error_type=type(e).__name__,
                duration_ms=int(search_duration * 1000)
            )
            raise
```

## 4. LanceDB Integration

### 4.1 LanceDB Provider Implementation (Priority: High)

LanceDB offers significant advantages as an embedded vector database compared to SQLite+VSS or external solutions like ChromaDB. This section outlines the implementation of LanceDB within our enhanced storage architecture.

```python
# pygovpub/storage/providers/lancedb_provider.py
from typing import Any, Dict, List, Optional, Tuple, Type, TypeVar
import os
import time
import json
import uuid
from pathlib import Path

import structlog
import lancedb
import pyarrow as pa
from pydantic import BaseModel
import numpy as np
from prometheus_client import Counter, Histogram

from pygovpub.storage.interface import StorageInterface
from pygovpub.models.base import BaseDocument, BaseMetadata

logger = structlog.get_logger()

# Metrics
LANCEDB_OPERATIONS = Counter(
    "lancedb_operations_total",
    "Total LanceDB operations",
    ["operation", "status", "table"]
)
LANCEDB_OPERATION_DURATION = Histogram(
    "lancedb_operation_duration_seconds",
    "LanceDB operation duration in seconds",
    ["operation", "table"]
)

T = TypeVar("T")

class LanceDBProvider:
    """LanceDB storage provider implementation"""

    def __init__(self,
                uri: str = None,
                create_vector_index: bool = True,
                vector_dim: int = 384,
                **config):
        """
        Initialize LanceDB provider

        Args:
            uri: Path to LanceDB database (directory)
            create_vector_index: Whether to create vector index on table creation
            vector_dim: Dimension of vector embeddings (default: 384 for all-MiniLM-L6-v2)
        """
        self.vector_dim = vector_dim
        self.create_vector_index = create_vector_index

        # Use temporary directory if no URI provided
        if not uri:
            db_dir = config.get("db_dir", os.path.expanduser("~/.pygovpub/lancedb"))
            os.makedirs(db_dir, exist_ok=True)
            timestamp = int(time.time())
            db_id = str(uuid.uuid4())[:8]
            uri = f"{db_dir}/pygovpub_db_{timestamp}_{db_id}"
            logger.info(f"Creating temporary LanceDB at {uri}")

        self.uri = uri
        self.db = lancedb.connect(uri)
        self.config = config
        self.table_info = {}  # Cache table metadata

        logger.info("LanceDB provider initialized", uri=uri)

    def _model_to_dict(self, model_obj: Any) -> Dict[str, Any]:
        """Convert model object to dictionary for LanceDB storage"""
        if isinstance(model_obj, BaseModel):
            # Use Pydantic's model_dump() for Pydantic v2 compatibility
            if hasattr(model_obj, "model_dump"):
                return model_obj.model_dump()
            else:
                # Fallback for Pydantic v1
                return model_obj.dict()
        elif hasattr(model_obj, "__dict__"):
            # Handle SQLAlchemy models or other objects
            return {
                key: value for key, value in model_obj.__dict__.items()
                if not key.startswith("_")
            }
        else:
            # Already a dict or something else
            return model_obj

    def _get_or_create_table(self, table_name: str, schema: Optional[pa.Schema] = None):
        """Get or create a LanceDB table with appropriate schema"""
        start_time = time.time()

        try:
            if table_name in self.db.table_names():
                table = self.db.open_table(table_name)
                logger.debug(f"Opened existing table {table_name}")
            else:
                if schema is None:
                    # Create a minimal initial schema if none provided
                    schema = pa.schema([
                        ("id", pa.string()),
                        ("embedding", pa.list_(pa.float32(), self.vector_dim)),
                        ("metadata", pa.string()),  # JSON-serialized metadata
                        ("content", pa.string()),   # Document content
                        ("created_at", pa.timestamp("us")),
                        ("updated_at", pa.timestamp("us")),
                    ])

                # Create empty table with schema
                empty_data = pa.Table.from_pydict(
                    {field.name: [] for field in schema}, schema=schema
                )

                # Create table
                table = self.db.create_table(
                    table_name,
                    data=empty_data,
                    mode="overwrite" if self.config.get("overwrite_tables", False) else "error"
                )

                # Create vector index if specified
                if self.create_vector_index:
                    table.create_index(
                        ["embedding"],
                        index_type="IVF_PQ",
                        metric_type="L2",
                        replace=True
                    )

                logger.info(f"Created new table {table_name} with vector index")

            # Cache table info
            self.table_info[table_name] = {
                "has_vector_index": self._check_table_has_vector_index(table),
                "schema": table.schema
            }

            LANCEDB_OPERATION_DURATION.labels(
                operation="get_or_create_table",
                table=table_name
            ).observe(time.time() - start_time)

            return table

        except Exception as e:
            LANCEDB_OPERATIONS.labels(
                operation="get_or_create_table",
                status="error",
                table=table_name
            ).inc()

            logger.error(f"Error getting/creating table {table_name}", error=str(e))
            raise

    def _check_table_has_vector_index(self, table) -> bool:
        """Check if table has a vector index"""
        try:
            # Check for index metadata
            indices = table.describe_indices()
            return len(indices) > 0 and any("embedding" in idx.get("column_names", []) for idx in indices)
        except Exception as e:
            logger.warning(f"Could not check vector index: {str(e)}")
            return False

    def _convert_model_to_arrow(self, model_class: Type[T], data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert model data to arrow-compatible format for LanceDB"""
        arrow_data = {}

        # Ensure we have basic required fields
        arrow_data["id"] = data.get("id", str(uuid.uuid4()))

        # Handle embedding vector
        if "embedding" in data:
            embedding = data["embedding"]
            # Ensure embedding is a list with correct dimensions
            if isinstance(embedding, np.ndarray):
                embedding = embedding.tolist()
            elif isinstance(embedding, str):
                # Handle case where embedding might be JSON string
                try:
                    embedding = json.loads(embedding)
                except:
                    logger.warning(f"Could not parse embedding from string: {embedding[:20]}...")
                    # Use zero vector as fallback
                    embedding = [0.0] * self.vector_dim

            # Validate vector dimension
            if len(embedding) != self.vector_dim:
                logger.warning(
                    f"Embedding dimension mismatch: got {len(embedding)}, expected {self.vector_dim}. Padding/truncating."
                )
                if len(embedding) < self.vector_dim:
                    # Pad with zeros
                    embedding = embedding + [0.0] * (self.vector_dim - len(embedding))
                else:
                    # Truncate
                    embedding = embedding[:self.vector_dim]

            arrow_data["embedding"] = embedding
        else:
            # Default empty embedding if none provided
            arrow_data["embedding"] = [0.0] * self.vector_dim

        # Handle metadata - serialize to JSON string
        metadata = data.get("metadata", {})
        if isinstance(metadata, dict):
            arrow_data["metadata"] = json.dumps(metadata)
        else:
            # Handle case where metadata might be an object
            arrow_data["metadata"] = json.dumps(self._model_to_dict(metadata))

        # Handle content
        arrow_data["content"] = data.get("content", "")

        # Handle timestamps
        current_time = pa.scalar(time.time_ns() // 1000).cast(pa.timestamp("us"))
        arrow_data["created_at"] = data.get("created_at", current_time)
        arrow_data["updated_at"] = data.get("updated_at", current_time)

        # Add all other fields as-is
        for key, value in data.items():
            if key not in arrow_data and key not in ["metadata", "embedding", "content"]:
                arrow_data[key] = value

        return arrow_data

    def create(self, model_class: Type[T], data: Dict[str, Any]) -> str:
        """Create a new record in LanceDB"""
        start_time = time.time()

        # Get table name from model class
        if hasattr(model_class, "__tablename__"):
            table_name = model_class.__tablename__
        else:
            table_name = model_class.__name__.lower()

        # Process data for LanceDB
        processed_data = self._convert_model_to_arrow(model_class, data)

        try:
            # Get or create table
            table = self._get_or_create_table(table_name)

            # Add record to table
            table.add([processed_data])

            LANCEDB_OPERATIONS.labels(
                operation="create",
                status="success",
                table=table_name
            ).inc()

            LANCEDB_OPERATION_DURATION.labels(
                operation="create",
                table=table_name
            ).observe(time.time() - start_time)

            logger.debug(f"Created record in {table_name}", id=processed_data["id"])
            return processed_data["id"]

        except Exception as e:
            LANCEDB_OPERATIONS.labels(
                operation="create",
                status="error",
                table=table_name
            ).inc()

            logger.error(f"Error creating record in {table_name}", error=str(e))
            raise

    def get(self, model_class: Type[T], id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a record by ID"""
        start_time = time.time()

        # Get table name from model class
        if hasattr(model_class, "__tablename__"):
            table_name = model_class.__tablename__
        else:
            table_name = model_class.__name__.lower()

        try:
            # Get table
            table = self._get_or_create_table(table_name)

            # Query record by ID
            result = table.search().where(f"id = '{id}'").limit(1).to_pandas()

            if len(result) == 0:
                logger.debug(f"Record {id} not found in {table_name}")
                return None

            # Convert from pandas row to dict
            record = result.iloc[0].to_dict()

            # Parse metadata from JSON
            if "metadata" in record and isinstance(record["metadata"], str):
                try:
                    record["metadata"] = json.loads(record["metadata"])
                except json.JSONDecodeError:
                    logger.warning(f"Could not parse metadata JSON for record {id}")

            LANCEDB_OPERATIONS.labels(
                operation="get",
                status="success",
                table=table_name
            ).inc()

            LANCEDB_OPERATION_DURATION.labels(
                operation="get",
                table=table_name
            ).observe(time.time() - start_time)

            return record

        except Exception as e:
            LANCEDB_OPERATIONS.labels(
                operation="get",
                status="error",
                table=table_name
            ).inc()

            logger.error(f"Error retrieving record {id} from {table_name}", error=str(e))
            raise

    def vector_search(self,
                     model_class: Type[T],
                     query_vector: List[float],
                     limit: int = 10,
                     filter_criteria: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Perform vector similarity search"""
        start_time = time.time()

        # Get table name from model class
        if hasattr(model_class, "__tablename__"):
            table_name = model_class.__tablename__
        else:
            table_name = model_class.__name__.lower()

        try:
            # Get table
            table = self._get_or_create_table(table_name)

            # Start query
            query = table.search(query_vector, vector_column_name="embedding")

            # Apply filters if provided
            if filter_criteria:
                filter_expr = " AND ".join([
                    f"{key} = '{value}'" if isinstance(value, str) else f"{key} = {value}"
                    for key, value in filter_criteria.items()
                ])
                query = query.where(filter_expr)

            # Execute search
            result = query.limit(limit).to_pandas()

            # Process results
            records = []
            for _, row in result.iterrows():
                record = row.to_dict()

                # Parse metadata from JSON
                if "metadata" in record and isinstance(record["metadata"], str):
                    try:
                        record["metadata"] = json.loads(record["metadata"])
                    except json.JSONDecodeError:
                        logger.warning(f"Could not parse metadata JSON")

                records.append(record)

            LANCEDB_OPERATIONS.labels(
                operation="vector_search",
                status="success",
                table=table_name
            ).inc()

            LANCEDB_OPERATION_DURATION.labels(
                operation="vector_search",
                table=table_name
            ).observe(time.time() - start_time)

            return records

        except Exception as e:
            LANCEDB_OPERATIONS.labels(
                operation="vector_search",
                status="error",
                table=table_name
            ).inc()

            logger.error(f"Error performing vector search in {table_name}", error=str(e))
            raise

    def hybrid_search(self,
                     model_class: Type[T],
                     query_text: str,
                     query_vector: List[float] = None,
                     limit: int = 10,
                     filter_criteria: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Perform hybrid search (full-text + vector) if text is provided.
        Will automatically generate embeddings if only text is provided.
        """
        start_time = time.time()

        # Get table name from model class
        if hasattr(model_class, "__tablename__"):
            table_name = model_class.__tablename__
        else:
            table_name = model_class.__name__.lower()

        try:
            # Get table
            table = self._get_or_create_table(table_name)

            # Start hybrid query
            if query_vector is not None:
                # True hybrid search with vector and text components
                query = table.search(query_vector, query_text=query_text)
            else:
                # Full-text search only
                query = table.search(query_text=query_text)

            # Apply filters if provided
            if filter_criteria:
                filter_expr = " AND ".join([
                    f"{key} = '{value}'" if isinstance(value, str) else f"{key} = {value}"
                    for key, value in filter_criteria.items()
                ])
                query = query.where(filter_expr)

            # Execute search
            result = query.limit(limit).to_pandas()

            # Process results
            records = []
            for _, row in result.iterrows():
                record = row.to_dict()

                # Parse metadata from JSON
                if "metadata" in record and isinstance(record["metadata"], str):
                    try:
                        record["metadata"] = json.loads(record["metadata"])
                    except json.JSONDecodeError:
                        logger.warning(f"Could not parse metadata JSON")

                records.append(record)

            LANCEDB_OPERATIONS.labels(
                operation="hybrid_search",
                status="success",
                table=table_name
            ).inc()

            LANCEDB_OPERATION_DURATION.labels(
                operation="hybrid_search",
                table=table_name
            ).observe(time.time() - start_time)

            return records

        except Exception as e:
            LANCEDB_OPERATIONS.labels(
                operation="hybrid_search",
                status="error",
                table=table_name
            ).inc()

            logger.error(f"Error performing hybrid search in {table_name}", error=str(e))
            raise
```

### 4.2 Storage Interface Integration with LanceDB (Priority: High)

Update the StorageInterface to detect and use LanceDB when available.

```python
# Add to pygovpub/storage/interface.py

class StorageInterface:
    # ... existing code ...

    def _detect_features(self) -> Dict[str, bool]:
        """Detect database features and capabilities"""
        features = {'basic_storage': True}

        # ... existing code ...

        # LanceDB feature detection
        elif self.db_type == "lancedb" and self._is_package_available('lancedb'):
            features['vector_operations'] = True
            features['hybrid_search'] = True
            features['full_text_search'] = True
            features['embedded_database'] = True

            # Check for optional LanceDB capabilities
            try:
                import lancedb
                from pygovpub.storage.providers import lancedb_provider

                # Initialize provider to check capabilities
                provider = lancedb_provider.LanceDBProvider(self.connection_string.replace("lancedb://", ""))

                # Check for HNSW index support
                if hasattr(lancedb, "index") and hasattr(lancedb.index, "HNSW"):
                    features['hnsw_index'] = True

                # Check for versioning support
                if hasattr(provider.db, "create_version"):
                    features['versioning'] = True

                # Record provider for later use
                self._providers["lancedb"] = provider

            except Exception as e:
                logger.error("Error during LanceDB feature detection", error=str(e))

        return features
```

### 4.3 LanceDB Schema Migration Utilities (Priority: Medium)

Create utilities to help migrate from existing SQLite schemas to LanceDB tables.

```python
# pygovpub/storage/migration/sqlite_to_lancedb.py
import os
import time
import json
import sqlite3
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path

import structlog
import lancedb
import pyarrow as pa
import pandas as pd

logger = structlog.get_logger()

class SQLiteToLanceDBMigrator:
    """Utility to migrate data from SQLite to LanceDB"""

    def __init__(self,
                sqlite_path: str,
                lancedb_uri: str,
                vector_dim: int = 384,
                batch_size: int = 1000):
        """
        Initialize migrator

        Args:
            sqlite_path: Path to SQLite database
            lancedb_uri: URI for LanceDB
            vector_dim: Dimension of vector embeddings
            batch_size: Number of records per batch for migration
        """
        self.sqlite_path = sqlite_path
        self.lancedb_uri = lancedb_uri
        self.vector_dim = vector_dim
        self.batch_size = batch_size

        # Connect to source and target
        self.sqlite_conn = sqlite3.connect(sqlite_path)
        self.lancedb = lancedb.connect(lancedb_uri)

        # Set sqlite to return rows as dictionaries
        self.sqlite_conn.row_factory = sqlite3.Row

        logger.info("SQLite to LanceDB migrator initialized",
                   sqlite_path=sqlite_path,
                   lancedb_uri=lancedb_uri)

    def get_sqlite_tables(self) -> List[str]:
        """Get list of tables in SQLite database"""
        cursor = self.sqlite_conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        return [row[0] for row in cursor.fetchall()]

    def get_sqlite_table_schema(self, table_name: str) -> Dict[str, str]:
        """Get schema of SQLite table"""
        cursor = self.sqlite_conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name});")
        return {row[1]: row[2] for row in cursor.fetchall()}

    def map_sqlite_to_arrow_type(self, sqlite_type: str) -> pa.DataType:
        """Map SQLite type to Arrow type"""
        sqlite_type = sqlite_type.lower()

        if "int" in sqlite_type:
            return pa.int64()
        elif "real" in sqlite_type or "float" in sqlite_type or "double" in sqlite_type:
            return pa.float64()
        elif "text" in sqlite_type or "char" in sqlite_type or "clob" in sqlite_type:
            return pa.string()
        elif "blob" in sqlite_type:
            return pa.binary()
        elif "bool" in sqlite_type:
            return pa.bool_()
        elif "date" in sqlite_type or "time" in sqlite_type:
            return pa.timestamp("us")
        else:
            # Default to string for unknown types
            logger.warning(f"Unknown SQLite type: {sqlite_type}, defaulting to string")
            return pa.string()

    def create_arrow_schema(self, table_name: str) -> pa.Schema:
        """Create Arrow schema from SQLite table schema"""
        sqlite_schema = self.get_sqlite_table_schema(table_name)

        fields = []
        for column, sqlite_type in sqlite_schema.items():
            arrow_type = self.map_sqlite_to_arrow_type(sqlite_type)
            fields.append(pa.field(column, arrow_type))

        # Ensure embedding field exists
        if "embedding" not in sqlite_schema:
            fields.append(pa.field("embedding", pa.list_(pa.float32(), self.vector_dim)))

        # Ensure metadata field exists
        if "metadata" not in sqlite_schema:
            fields.append(pa.field("metadata", pa.string()))

        # Ensure content field exists
        if "content" not in sqlite_schema:
            fields.append(pa.field("content", pa.string()))

        return pa.schema(fields)

    def migrate_table(self, table_name: str,
                     create_vector_index: bool = True,
                     embedding_column: str = "embedding") -> Tuple[int, int]:
        """
        Migrate a single table from SQLite to LanceDB

        Returns:
            Tuple[int, int]: (total_records, migrated_records)
        """
        logger.info(f"Starting migration of table {table_name}")

        # Get total count
        cursor = self.sqlite_conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        total_records = cursor.fetchone()[0]

        if total_records == 0:
            logger.info(f"Table {table_name} is empty, skipping")
            return (0, 0)

        # Create Arrow schema
        schema = self.create_arrow_schema(table_name)

        # Create target table in LanceDB
        empty_data = pa.Table.from_pydict(
            {field.name: [] for field in schema}, schema=schema
        )

        lancedb_table = self.lancedb.create_table(
            table_name,
            data=empty_data,
            mode="overwrite"
        )

        # Process in batches
        migrated_records = 0
        offset = 0

        while offset < total_records:
            # Fetch batch
            cursor.execute(f"SELECT * FROM {table_name} LIMIT {self.batch_size} OFFSET {offset}")
            rows = cursor.fetchall()

            # Convert to list of dicts
            records = [dict(row) for row in rows]

            # Process embedding if present
            for record in records:
                # Handle embedding field
                if embedding_column in record and record[embedding_column]:
                    # Parse JSON embedding if stored as string
                    if isinstance(record[embedding_column], str):
                        try:
                            record["embedding"] = json.loads(record[embedding_column])
                        except json.JSONDecodeError:
                            logger.warning(f"Could not parse embedding JSON in table {table_name}")
                            record["embedding"] = [0.0] * self.vector_dim
                    # Convert numpy array to list if needed
                    elif hasattr(record[embedding_column], 'tolist'):
                        record["embedding"] = record[embedding_column].tolist()
                else:
                    # Create empty embedding
                    record["embedding"] = [0.0] * self.vector_dim

                # Handle metadata - ensure it's a JSON string
                if "metadata" in record and record["metadata"]:
                    if not isinstance(record["metadata"], str):
                        record["metadata"] = json.dumps(record["metadata"])
                else:
                    record["metadata"] = "{}"

            # Add batch to LanceDB
            try:
                lancedb_table.add(records)
                migrated_records += len(records)
                logger.info(f"Migrated {migrated_records}/{total_records} records from {table_name}")
            except Exception as e:
                logger.error(f"Error migrating batch from {table_name}", error=str(e))

            # Move to next batch
            offset += self.batch_size

        # Create vector index
        if create_vector_index:
            try:
                lancedb_table.create_index(
                    ["embedding"],
                    index_type="IVF_PQ",
                    metric_type="L2",
                    replace=True
                )
                logger.info(f"Created vector index for {table_name}")
            except Exception as e:
                logger.error(f"Error creating vector index for {table_name}", error=str(e))

        return (total_records, migrated_records)

    def migrate_all_tables(self,
                          exclude_tables: List[str] = None,
                          create_vector_indices: bool = True) -> Dict[str, Tuple[int, int]]:
        """
        Migrate all tables from SQLite to LanceDB

        Args:
            exclude_tables: List of tables to exclude
            create_vector_indices: Whether to create vector indices

        Returns:
            Dict mapping table names to (total_records, migrated_records) tuples
        """
        exclude_tables = exclude_tables or []
        results = {}

        # Get all tables
        tables = self.get_sqlite_tables()

        # Filter out excluded tables
        tables = [t for t in tables if t not in exclude_tables]

        # Migrate each table
        start_time = time.time()
        for table in tables:
            results[table] = self.migrate_table(table, create_vector_indices)

        total_duration = time.time() - start_time
        total_migrated = sum(migrated for _, migrated in results.values())

        logger.info(
            "Migration completed",
            tables=len(tables),
            total_records=sum(total for total, _ in results.values()),
            migrated_records=total_migrated,
            duration_seconds=total_duration
        )

        return results

    def close(self):
        """Close connections"""
        self.sqlite_conn.close()
```

### 4.4 LanceDB Bulk Data Loading with Progress Monitoring (Priority: Medium)

Create utilities for bulk loading of data into LanceDB with progress monitoring.

```python
# pygovpub/storage/loaders/lancedb_loader.py
import os
import time
import json
import threading
from typing import Dict, List, Optional, Any, Callable, Generic, TypeVar, Type, Union
from pathlib import Path

import structlog
import lancedb
import pyarrow as pa
import pandas as pd
from tqdm.auto import tqdm
from concurrent.futures import ThreadPoolExecutor

from pygovpub.models.base import BaseDocument, BaseMetadata

logger = structlog.get_logger()

T = TypeVar("T")

class LanceDBBulkLoader(Generic[T]):
    """Utility for bulk loading data into LanceDB with progress tracking"""

    def __init__(self,
                db_uri: str,
                model_class: Type[T] = None,
                schema: Optional[pa.Schema] = None,
                vector_dim: int = 384,
                batch_size: int = 1000,
                overwrite: bool = False,
                create_vector_index: bool = True,
                progress_callback: Optional[Callable[[int, int], None]] = None):
        """
        Initialize bulk loader

        Args:
            db_uri: Path to LanceDB database
            model_class: Optional model class for schema inference
            schema: Optional Arrow schema (required if model_class not provided)
            vector_dim: Dimension of vector embeddings
            batch_size: Number of records per batch for loading
            overwrite: Whether to overwrite existing table
            create_vector_index: Whether to create vector index
            progress_callback: Optional callback for progress updates
        """
        self.db_uri = db_uri
        self.model_class = model_class
        self.vector_dim = vector_dim
        self.batch_size = batch_size
        self.overwrite = overwrite
        self.create_vector_index = create_vector_index
        self.progress_callback = progress_callback

        # Connect to LanceDB
        self.db = lancedb.connect(db_uri)

        # Get table name from model class
        if model_class and hasattr(model_class, "__tablename__"):
            self.table_name = model_class.__tablename__
        elif model_class:
            self.table_name = model_class.__name__.lower()
        else:
            self.table_name = "documents"

        # Set up schema
        self.schema = schema or self._infer_schema_from_model()

        logger.info("LanceDB bulk loader initialized",
                   db_uri=db_uri,
                   table_name=self.table_name)

    def _infer_schema_from_model(self) -> pa.Schema:
        """Infer Arrow schema from model class"""
        if not self.model_class:
            raise ValueError("Either model_class or schema must be provided")

        # Basic fields for all document tables
        fields = [
            pa.field("id", pa.string()),
            pa.field("embedding", pa.list_(pa.float32(), self.vector_dim)),
            pa.field("metadata", pa.string()),  # JSON-serialized metadata
            pa.field("content", pa.string()),   # Document content
            pa.field("created_at", pa.timestamp("us")),
            pa.field("updated_at", pa.timestamp("us")),
        ]

        # Try to infer additional fields from model annotations or Pydantic model
        if hasattr(self.model_class, "__annotations__"):
            for name, type_hint in self.model_class.__annotations__.items():
                # Skip already handled fields
                if name in ["id", "embedding", "metadata", "content", "created_at", "updated_at"]:
                    continue

                # Map Python type to Arrow type
                arrow_type = None
                type_name = str(type_hint)

                if "str" in type_name:
                    arrow_type = pa.string()
                elif "int" in type_name:
                    arrow_type = pa.int64()
                elif "float" in type_name:
                    arrow_type = pa.float64()
                elif "bool" in type_name:
                    arrow_type = pa.bool_()
                elif "datetime" in type_name:
                    arrow_type = pa.timestamp("us")

                if arrow_type:
                    fields.append(pa.field(name, arrow_type))

        return pa.schema(fields)

    def _preprocess_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Preprocess record for storage in LanceDB"""
        processed = {}

        # Handle ID field
        processed["id"] = record.get("id", str(record.get("_id", "")))

        # Handle embedding
        if "embedding" in record:
            embedding = record["embedding"]
            # Convert numpy array to list if needed
            if hasattr(embedding, 'tolist'):
                embedding = embedding.tolist()
            # Parse JSON if it's a string
            elif isinstance(embedding, str):
                try:
                    embedding = json.loads(embedding)
                except json.JSONDecodeError:
                    logger.warning(f"Could not parse embedding JSON, using zeros")
                    embedding = [0.0] * self.vector_dim
            processed["embedding"] = embedding
        else:
            # Default empty embedding
            processed["embedding"] = [0.0] * self.vector_dim

        # Handle metadata
        if "metadata" in record:
            metadata = record["metadata"]
            if isinstance(metadata, dict):
                processed["metadata"] = json.dumps(metadata)
            elif isinstance(metadata, str):
                # Verify it's valid JSON
                try:
                    json.loads(metadata)
                    processed["metadata"] = metadata
                except json.JSONDecodeError:
                    processed["metadata"] = json.dumps({"raw": metadata})
            else:
                processed["metadata"] = json.dumps({"value": str(metadata)})
        else:
            processed["metadata"] = "{}"

        # Handle content
        processed["content"] = str(record.get("content", ""))

        # Handle timestamps
        now = pd.Timestamp.now()
        processed["created_at"] = record.get("created_at", now)
        processed["updated_at"] = record.get("updated_at", now)

        # Copy other fields
        for key, value in record.items():
            if key not in processed and key not in ["_id"]:
                processed[key] = value

        return processed

    def create_table(self) -> Any:
        """Create or open LanceDB table"""
        if self.table_name in self.db.table_names() and not self.overwrite:
            logger.info(f"Opening existing table {self.table_name}")
            return self.db.open_table(self.table_name)
        else:
            # Create empty table with schema
            empty_data = pa.Table.from_pydict(
                {field.name: [] for field in self.schema}, schema=self.schema
            )

            logger.info(f"Creating new table {self.table_name}")
            return self.db.create_table(
                self.table_name,
                data=empty_data,
                mode="overwrite" if self.overwrite else "error"
            )

    def load_data(self,
                 data: Union[List[Dict[str, Any]], pd.DataFrame, pa.Table],
                 create_vector_index: bool = None) -> int:
        """
        Load data into LanceDB table

        Args:
            data: List of records, Pandas DataFrame or PyArrow Table
            create_vector_index: Whether to create vector index (defaults to constructor setting)

        Returns:
            Number of records loaded
        """
        start_time = time.time()

        # Convert data to list of dicts if needed
        if isinstance(data, pd.DataFrame):
            records = data.to_dict("records")
        elif isinstance(data, pa.Table):
            records = data.to_pylist()
        else:
            records = data

        # Create table
        table = self.create_table()

        # Process and load in batches
        total_records = len(records)
        loaded_records = 0

        # Set up progress bar
        pbar = tqdm(total=total_records, desc=f"Loading data into {self.table_name}")

        for i in range(0, total_records, self.batch_size):
            batch = records[i:i+self.batch_size]

            # Preprocess batch
            processed_batch = [self._preprocess_record(record) for record in batch]

            # Add batch to table
            try:
                table.add(processed_batch)
                loaded_records += len(processed_batch)

                # Update progress
                pbar.update(len(processed_batch))
                if self.progress_callback:
                    self.progress_callback(loaded_records, total_records)

            except Exception as e:
                logger.error(f"Error loading batch into {self.table_name}", error=str(e))

        pbar
