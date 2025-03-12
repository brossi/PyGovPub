# Enhanced PyGovPub Storage Architecture Implementation Plan

## Executive Summary

This document outlines a streamlined implementation plan for expanding PyGovPub's storage architecture to support multiple database backends (PostgreSQL with pgVector, SQLite, MySQL) while enabling cloud storage solutions (Supabase, Pinecone) as optional, on-demand features. The enhanced plan addresses critical infrastructure needs including error handling, monitoring, security, and async support.

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
┌────────────────┐      ┌─────────────────┐    ┌─────────────────┐   ┌─────────────────────┐
│  PostgreSQL +  │      │     SQLite      │    │     MySQL       │   │  Optional Providers │
│   pgVector     │      │                 │    │                 │   │ (Supabase/Pinecone) │
└────────────────┘      └─────────────────┘    └─────────────────┘   └─────────────────────┘
```

### 1.2 Key Design Principles

1. **Minimal Abstraction**: Create only the necessary abstraction to support multiple databases
2. **Optional Dependencies**: Make cloud provider libraries optional and load them only when configured
3. **Feature Detection**: Identify database capabilities at runtime to enable appropriate functionality
4. **Progressive Enhancement**: Add features incrementally as database support allows
5. **Resilient Operations**: Implement structured logging, retry mechanisms, and monitoring
6. **Secure by Default**: Ensure data and credentials are protected throughout the system

## 2. Dependencies Management

### 2.1 Core Requirements

```
# Core SQLAlchemy and Database
sqlalchemy>=2.0.0  # Note: Use compatibility mode with SQLModel
alembic>=1.12.0    # Database migrations
asyncpg>=0.27.0    # PostgreSQL async support
aiosqlite>=0.19.0  # SQLite async support
psycopg>=3.1.16    # PostgreSQL support
mysqlclient>=2.2.1 # MySQL support
aiomysql>=0.2.0    # MySQL async support - to be added

# Vector Extensions
pgvector>=0.2.4    # Python bindings for pgVector extension

# Embedding Generation
sentence-transformers>=2.2.2  # Embedding models
torch>=2.1.0       # Required by sentence-transformers (CPU-only is sufficient)

# Error Handling & Monitoring
structlog>=24.0.0  # Structured logging
tenacity>=8.2.3    # Retry mechanisms
prometheus-client>=0.20.0  # Metrics collection

# Security
cryptography>=40.0.0  # For data encryption
```

### 2.2 Optional Cloud Provider Dependencies

We'll make these dependencies optional by using extras_require in setup.py:

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
        # other core dependencies
    ],
    extras_require={
        "pinecone": ["pinecone-client>=2.2.4"],
        "supabase": ["supabase>=2.0.3"],
        "cloud": ["pinecone-client>=2.2.4", "supabase>=2.0.3"],
        "llm": ["transformers>=4.36.0", "accelerate>=0.25.0"],
        "mysql": ["mysqlclient>=2.2.1", "aiomysql>=0.2.0"],
    }
)
```

## 3. Enhanced Implementation Plan

### 3.1 Storage Interface with Integrated Monitoring (Priority: High)

Create a minimal storage interface with monitoring, error tracking, and database abstraction.

```python
# pygovpub/storage/interface.py
import importlib.util
import time
from typing import Any, Dict, List, Optional, Type, TypeVar, Generic, Union

import structlog
from prometheus_client import Counter, Histogram
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from tenacity import retry, stop_after_attempt, wait_exponential

# Set up structured logging
logger = structlog.get_logger()

# Set up metrics
DB_OPERATIONS = Counter("db_operations_total", "Total database operations", ["operation", "status", "db_type"])
DB_OPERATION_DURATION = Histogram("db_operation_duration_seconds", "Database operation duration in seconds", 
                                 ["operation", "db_type"])

T = TypeVar("T")

class StorageInterface:
    """Database-agnostic storage interface with monitoring and fallbacks"""
    
    def __init__(self, connection_string: str, **config):
        self.connection_string = connection_string
        self.config = config
        self.db_type = self._determine_db_type(connection_string)
        
        # Setup sync engine
        self.engine = create_engine(
            connection_string, 
            echo=config.get("echo", False),
            pool_pre_ping=True  # Health check for connection pool
        )
        self.Session = sessionmaker(bind=self.engine)
        
        # Setup async engine if supported
        if self._supports_async():
            async_connection = self._get_async_connection_string(connection_string)
            self.async_engine = create_async_engine(
                async_connection,
                echo=config.get("echo", False),
                pool_pre_ping=True
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
        
        logger.info(
            "Storage interface initialized", 
            db_type=self.db_type, 
            features=self.features,
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
        elif "mysql" in connection_string:
            # Convert mysql:// to mysql+aiomysql://
            return connection_string.replace("mysql://", "mysql+aiomysql://")
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
        elif db_type == "mysql":
            return self._is_package_available("aiomysql")
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
        
        # MySQL detection
        elif self.db_type == "mysql":
            features['enterprise_storage'] = True
            # Check for MySQL fulltext search
            try:
                with self.engine.connect() as conn:
                    # Test if server version supports JSON features
                    result = conn.execute(text("SELECT VERSION()"))
                    version = result.scalar()
                    if version and int(version.split('.')[0]) >= 8:
                        features['json_support'] = True
                        features['full_text_search'] = True
            except Exception as e:
                logger.error("Error detecting MySQL features", error=str(e))
        
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
        
        return features
    
    def _is_package_available(self, package_name: str) -> bool:
        """Check if a Python package is installed and available"""
        return importlib.util.find_spec(package_name) is not None
        
    def supports(self, feature: str) -> bool:
        """Check if a specific feature is supported"""
        return self.features.get(feature, False)
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True
    )
    def create(self, model_class: Type[T], data: Dict[str, Any]) -> int:
        """Create a new record with monitoring and retry support"""
        start_time = time.time()
        session = self.Session()
        
        try:
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
    
    async def create_async(self, model_class: Type[T], data: Dict[str, Any]) -> int:
        """Create a new record asynchronously with monitoring"""
        if not self._supports_async():
            raise NotImplementedError(f"Async operations not supported for {self.db_type}")
            
        start_time = time.time()
        async_session = self.AsyncSession()
        
        try:
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

    # Additional CRUD methods with monitoring would be implemented similarly
    # get(), update(), delete(), query(), and their async equivalents
```

### 3.2 Security Layer Implementation (Priority: High)

Implement a streamlined security layer for protecting API keys and sensitive metadata.

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

### 3.3 Database-Compatible Schema Migrations (Priority: High)

Create a migration system that maintains schema compatibility across different database types.

```python
# pygovpub/storage/migrations/migration_manager.py
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import structlog
import alembic
from alembic.config import Config
from alembic import command
from sqlalchemy import create_engine, text

logger = structlog.get_logger()

class MigrationManager:
    """
    Manages database schema migrations with compatibility across database types
    
    This enables developers to use SQLite locally while ensuring migrations
    will work correctly on PostgreSQL or MySQL in production environments.
    It does NOT migrate data between different database systems.
    """
    
    def __init__(self, storage_interface):
        self.storage = storage_interface
        self.db_type = storage_interface.db_type
        self.connection_string = storage_interface.connection_string
        
        # Get project root directory
        self.project_root = self._find_project_root()
        
        # Set up Alembic config
        self.alembic_cfg = Config()
        self.alembic_cfg.set_main_option("script_location", 
                                        str(Path(self.project_root) / "migrations"))
        self.alembic_cfg.set_main_option("sqlalchemy.url", self.connection_string)
        
        # Set up database-specific branches
        # This allows for different SQL syntax while maintaining schema compatibility
        if self.db_type in ["postgresql", "mysql", "sqlite"]:
            db_specific_dir = str(Path(self.project_root) / f"migrations_{self.db_type}")
            if os.path.exists(db_specific_dir):
                self.alembic_cfg.set_main_option("version_locations", db_specific_dir)
                logger.info(f"Using database-specific migrations for {self.db_type}")
    
    def _find_project_root(self) -> str:
        """Find the project root directory"""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        while current_dir != os.path.dirname(current_dir):  # Stop at filesystem root
            if os.path.exists(os.path.join(current_dir, "pyproject.toml")) or \
               os.path.exists(os.path.join(current_dir, "setup.py")):
                return current_dir
            current_dir = os.path.dirname(current_dir)
        
        # Default to current directory if not found
        return os.path.dirname(os.path.abspath(__file__))
    
    def init_migrations(self):
        """Initialize the migrations directory structure"""
        # Set up main migrations directory
        command.init(self.alembic_cfg, "migrations", template="generic")
        
        # Create database-specific directories for compatibility branches
        for db_type in ["postgresql", "mysql", "sqlite"]:
            db_dir = Path(self.project_root) / f"migrations_{db_type}"
            db_dir.mkdir(exist_ok=True)
            
            # Create documentation README
            readme = db_dir / "README.md"
            if not readme.exists():
                with open(readme, "w") as f:
                    f.write(f"# {db_type.capitalize()}-Specific Migrations\n\n")
                    f.write(f"This directory contains migrations adjusted for {db_type} syntax and features.\n")
                    f.write("These parallel migrations maintain schema compatibility across different database types.\n")
    
    def create_migration(self, message: str, autogenerate: bool = True):
        """Create a new migration with database-specific compatibility"""
        if self.db_type in ["pinecone", "supabase"]:
            logger.warning(f"Schema migrations not supported for {self.db_type}")
            return
            
        # Create primary migration first
        command.revision(self.alembic_cfg, message=message, autogenerate=autogenerate)
        
        # Create database-specific versions only when needed
        if autogenerate and self.db_type in ["postgresql", "mysql", "sqlite"]:
            self._create_db_specific_version(message)
    
    def _create_db_specific_version(self, message: str):
        """
        Create a database-specific version of the migration
        
        This handles cases where database features aren't compatible:
        - PostgreSQL: pgvector extension, GIN indexes
        - MySQL: Different JSON handling, index types
        - SQLite: Limited ALTER TABLE support, no vector types
        """
        # Find latest migration file
        versions_dir = Path(self.project_root) / "migrations" / "versions"
        migration_files = sorted(versions_dir.glob("*.py"), key=os.path.getctime)
        
        if not migration_files:
            logger.warning("No migration files found to adapt")
            return
            
        latest_migration = migration_files[-1]
        
        # Read the migration file
        with open(latest_migration, "r") as f:
            migration_content = f.read()
            
        # Create database-specific version with adjustments
        db_specific_dir = Path(self.project_root) / f"migrations_{self.db_type}"
        os.makedirs(db_specific_dir, exist_ok=True)
        
        # Add database-specific adjustments based on db_type
        if self.db_type == "postgresql":
            # PostgreSQL-specific adjustments
            adjusted_content = self._adjust_for_postgresql(migration_content)
        elif self.db_type == "mysql":
            # MySQL-specific adjustments
            adjusted_content = self._adjust_for_mysql(migration_content)
        elif self.db_type == "sqlite":
            # SQLite-specific adjustments
            adjusted_content = self._adjust_for_sqlite(migration_content)
        else:
            adjusted_content = migration_content
            
        # Write adjusted migration
        with open(db_specific_dir / latest_migration.name, "w") as f:
            f.write(adjusted_content)
            
        logger.info(f"Created {self.db_type}-specific migration: {latest_migration.name}")
    
    def _adjust_for_postgresql(self, content: str) -> str:
        """Make PostgreSQL-specific adjustments to migration"""
        # Only add vector extension setup if needed
        if "embedding" in content and self.storage.supports("vector_operations"):
            # Add CREATE EXTENSION if not exists at top of upgrade()
            pattern = r"def upgrade\(\).*?:"
            replacement = r"""def upgrade():
    # Add pgvector extension for vector operations
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')
    """
            content = re.sub(pattern, replacement, content, flags=re.DOTALL)
            
        return content
    
    def _adjust_for_mysql(self, content: str) -> str:
        """Make MySQL-specific adjustments to migration"""
        # Convert PostgreSQL-specific syntax to MySQL equivalent
        content = content.replace("JSONB", "JSON")
        content = content.replace("using='gin'", "mysql_using='btree'")
        
        # MySQL doesn't support vector types, use JSON array instead
        if "Vector(" in content:
            content = content.replace("sa.Column('embedding', Vector(768))", 
                                     "sa.Column('embedding_json', sa.JSON())")
            
        # Ensure MySQL-compatible index methods
        content = content.replace("op.create_index", 
                                 "# MySQL index creation\nop.create_index")
        
        return content
    
    def _adjust_for_sqlite(self, content: str) -> str:
        """Make SQLite-specific adjustments to migration"""
        # SQLite doesn't support ALTER TABLE for dropping columns
        if "drop_column" in content:
            logger.warning(
                "SQLite migration contains unsupported drop_column operations. "
                "These will be commented out, but schema may become inconsistent."
            )
            # Comment out drop_column operations
            content = re.sub(
                r"(op\.drop_column.*$)", 
                r"# SQLite doesn't support this: \1", 
                content, 
                flags=re.MULTILINE
            )
            
        # SQLite doesn't support vector types
        if "Vector(" in content:
            content = content.replace("sa.Column('embedding', Vector(768))", 
                                     "sa.Column('embedding_json', sa.JSON())")
            
        return content
    
    def upgrade(self, revision: str = "head"):
        """Upgrade the database to the specified revision"""
        if self.db_type in ["pinecone", "supabase"]:
            logger.warning(f"Schema migrations not supported for {self.db_type}")
            return
            
        try:
            command.upgrade(self.alembic_cfg, revision)
            logger.info(f"Database upgraded to {revision}")
        except Exception as e:
            logger.error("Failed to upgrade database", error=str(e), exc_info=True)
            raise
    
    def downgrade(self, revision: str):
        """Downgrade the database to the specified revision"""
        if self.db_type in ["pinecone", "supabase"]:
            logger.warning(f"Schema migrations not supported for {self.db_type}")
            return
            
        try:
            command.downgrade(self.alembic_cfg, revision)
            logger.info(f"Database downgraded to {revision}")
        except Exception as e:
            logger.error("Failed to downgrade database", error=str(e))
            raise
    
    def get_current_revision(self) -> Optional[str]:
        """Get the current database revision"""
        if self.db_type in ["pinecone", "supabase"]:
            logger.warning(f"Schema migrations not supported for {self.db_type}")
            return None
            
        try:
            script = alembic.script.ScriptDirectory.from_config(self.alembic_cfg)
            environment = alembic.environment.EnvironmentContext(self.alembic_cfg, script)
            connection = create_engine(self.connection_string).connect()
            
            current_rev = None
            
            def get_rev(rev, context):
                nonlocal current_rev
                current_rev = rev
                return []
                
            environment.configure(connection=connection, fn=get_rev)
            environment.run_migrations()
            
            return current_rev
        except Exception as e:
            logger.error("Failed to get current revision", error=str(e))
            return None
```

### 3.4 Database-Specific Implementation with Vector Support (Priority: High)

Implement database-specific operations with comprehensive support for all backends.

```python
# pygovpub/storage/models/document.py
from typing import Dict, List, Optional, Any
from datetime import datetime

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, JSON, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

# Define the base document class for all backends
class Document(Base):
    """Base document model for all storage backends"""
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True)
    content = Column(Text, nullable=False)
    source = Column(String(255), nullable=True)
    title = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    metadata = Column(JSON, nullable=True)
    is_processed = Column(Boolean, default=False)
    
    # Relationships would be defined here
    
    # Special handling for database-specific fields
    def __init__(self, **kwargs):
        # Remove embedding if present but not supported
        if 'embedding' in kwargs and not hasattr(self.__class__, 'embedding'):
            kwargs.pop('embedding')
        super().__init__(**kwargs)

# Define database-specific document models

# PostgreSQL model with pgvector support
try:
    from pgvector.sqlalchemy import Vector
    
    class PostgreSQLDocument(Document):
        """PostgreSQL-specific document model with vector support"""
        __tablename__ = None  # Use the parent tablename
        
        # Add pgvector column if available
        embedding = Column(Vector(768), nullable=True)
        
except ImportError:
    # Fallback for when pgvector is not available
    class PostgreSQLDocument(Document):
        """PostgreSQL document model without vector support"""
        __tablename__ = None  # Use the parent tablename
        
        # Embedding stored as JSON array when pgvector not available
        embedding_json = Column(JSON, nullable=True)

# MySQL model with fulltext search
class MySQLDocument(Document):
    """MySQL-specific document model"""
    __tablename__ = None  # Use the parent tablename
    
    # Add MySQL-specific columns or indexes
    # Note: MySQL doesn't have native vector support, so we'll store embeddings as JSON
    embedding_json = Column(JSON, nullable=True)
    
    # Storing a text representation for full-text search
    search_text = Column(Text, nullable=True)
    
    # MySQL would define FULLTEXT indexes in migrations

# SQLite model
class SQLiteDocument(Document):
    """SQLite-specific document model"""
    __tablename__ = None  # Use the parent tablename
    
    # SQLite doesn't have native vector support, so store as JSON
    embedding_json = Column(JSON, nullable=True)
    
    # Additional field for FTS indexing
    search_text = Column(Text, nullable=True)

# Factory function to get the appropriate document model
def get_document_model(db_type: str):
    """Get the appropriate document model for the database type"""
    if db_type == "postgresql":
        return PostgreSQLDocument
    elif db_type == "mysql":
        return MySQLDocument
    elif db_type == "sqlite":
        return SQLiteDocument
    else:
        # Default to base document for other providers
        return Document
```

### 3.5 Vector Search Service with Fallbacks (Priority: Medium)

Create a unified vector search service that handles all database types with appropriate fallbacks.

```python
# pygovpub/search/vector_search.py
from typing import Dict, List, Optional, Any, Tuple
import time
import json
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from sqlalchemy import select, text
from sentence_transformers import SentenceTransformer

logger = structlog.get_logger()

class VectorSearchService:
    """Vector search service with fallbacks across database types"""
    
    def __init__(self, storage):
        self.storage = storage
        self.db_type = storage.db_type
        
        # Load embedding model on demand
        self._embedding_model = None
        
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
        
        # Generate query embedding
        query_embedding = self.generate_embedding(query)
        
        # Perform search based on database type
        if self.db_type == "postgresql" and self.storage.supports("vector_operations"):
            results = self._vector_search_postgresql(query_embedding, limit, filter_criteria)
        elif self.db_type == "pinecone":
            from pygovpub.storage.providers import pinecone_provider
            if pinecone_provider.is_available():
                results = self._vector_search_pinecone(query_embedding, limit, filter_criteria)
            else:
                logger.warning("Pinecone support not available, falling back to keyword search")
                results = self._keyword_search(query, limit, filter_criteria)
        elif self.db_type == "supabase" and self.storage.supports("vector_operations"):
            results = self._vector_search_supabase(query_embedding, limit, filter_criteria)
        else:
            # Fall back to keyword search for other databases
            logger.info("Vector search not supported, falling back to keyword search")
            results = self._keyword_search(query, limit, filter_criteria)
        
        logger.info(
            "Search completed", 
            db_type=self.db_type, 
            query_length=len(query),
            result_count=len(results),
            duration_ms=int((time.time() - start_time) * 1000)
        )
        
        return results
    
    def _vector_search_postgresql(self, 
                                 query_embedding: List[float], 
                                 limit: int = 10,
                                 filter_criteria: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """PostgreSQL-specific vector search implementation"""
        from pgvector.sqlalchemy import cosine_distance
        from pygovpub.storage.models.document import PostgreSQLDocument
        
        session = self.storage.Session()
        
        try:
            # Build base query
            stmt = select(PostgreSQLDocument)
            
            # Add vector similarity
            stmt = stmt.order_by(cosine_distance(PostgreSQLDocument.embedding, query_embedding))
            
            # Add filters if provided
            if filter_criteria:
                for field, value in filter_criteria.items():
                    if hasattr(PostgreSQLDocument, field):
                        stmt = stmt.filter(getattr(PostgreSQLDocument, field) == value)
            
            # Apply limit
            stmt = stmt.limit(limit)
            
            # Execute query
            results = session.execute(stmt).scalars().all()
            
            # Convert to dictionaries
            return [
                {
                    "id": doc.id,
                    "content": doc.content,
                    "source": doc.source,
                    "title": doc.title,
                    "metadata": doc.metadata,
                    "created_at": doc.created_at.isoformat() if doc.created_at else None,
                }
                for doc in results
            ]
        finally:
            session.close()
    
    def _vector_search_pinecone(self, 
                              query_embedding: List[float], 
                              limit: int = 10,
                              filter_criteria: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Pinecone-specific vector search implementation"""
        from pygovpub.storage.providers import pinecone_provider
        
        # Initialize connection
        index = pinecone_provider.initialize(
            self.storage.config.get("api_key"),
            self.storage.config.get("environment"),
            self.storage.config.get("index_name")
        )
        
        # Convert filter criteria to Pinecone format if provided
        pinecone_filter = {}
        if filter_criteria:
            pinecone_filter = filter_criteria  # Simplified, would need conversion
        
        # Perform search
        search_results = index.query(
            vector=query_embedding,
            top_k=limit,
            filter=pinecone_filter if pinecone_filter else None,
            include_metadata=True
        )
        
        # Convert to standard format
        return [
            {
                "id": match.id,
                "content": match.metadata.get("content", ""),
                "source": match.metadata.get("source", ""),
                "title": match.metadata.get("title", ""),
                "metadata": match.metadata,
                "score": match.score,
            }
            for match in search_results.matches
        ]
    
    def _vector_search_supabase(self, 
                              query_embedding: List[float], 
                              limit: int = 10,
                              filter_criteria: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Supabase-specific vector search implementation"""
        from pygovpub.storage.providers import supabase_provider
        
        # Initialize connection
        client = supabase_provider.initialize(
            self.storage.config.get("url"),
            self.storage.config.get("key")
        )
        
        # Build query
        query = client.from_("documents").select("*")
        
        # Add filters if provided
        if filter_criteria:
            for field, value in filter_criteria.items():
                query = query.eq(field, value)
        
        # Order by vector similarity (simplified; actual syntax depends on Supabase setup)
        response = client.rpc(
            "match_documents", 
            {"query_embedding": query_embedding, "match_count": limit}
        ).execute()
        
        if response.error:
            logger.error("Supabase search error", error=response.error)
            return []
            
        return response.data
    
    def _keyword_search(self, 
                       query: str, 
                       limit: int = 10,
                       filter_criteria: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Keyword search fallback for databases without vector support"""
        from pygovpub.storage.models.document import get_document_model
        
        Document = get_document_model(self.db_type)
        session = self.storage.Session()
        
        try:
            # Build base query
            if self.db_type == "mysql" and self.storage.supports("full_text_search"):
                # Use MySQL MATCH AGAINST for fulltext search
                stmt = text(f"""
                    SELECT id, content, source, title, metadata, created_at
                    FROM documents
                    WHERE MATCH(search_text) AGAINST(:query IN NATURAL LANGUAGE MODE)
                    LIMIT :limit
                """)
                result = session.execute(stmt, {"query": query, "limit": limit})
                
                return [dict(row) for row in result]
                
            elif self.db_type == "sqlite" and self.storage.supports("full_text_search"):
                # Use SQLite FTS5 if available
                stmt = text(f"""
                    SELECT id, content, source, title, metadata, created_at
                    FROM documents
                    WHERE documents MATCH :query
                    LIMIT :limit
                """)
                result = session.execute(stmt, {"query": query, "limit": limit})
                
                return [dict(row) for row in result]
                
            else:
                # Simple LIKE query as last resort
                stmt = select(Document).where(
                    Document.content.like(f"%{query}%")
                )
                
                # Add filters if provided
                if filter_criteria:
                    for field, value in filter_criteria.items():
                        if hasattr(Document, field):
                            stmt = stmt.filter(getattr(Document, field) == value)
                
                # Apply limit
                stmt = stmt.limit(limit)
                
                # Execute query
                results = session.execute(stmt).scalars().all()
                
                # Convert to dictionaries
                return [
                    {
                        "id": doc.id,
                        "content": doc.content,
                        "source": doc.source,
                        "title": doc.title,
                        "metadata": doc.metadata,
                        "created_at": doc.created_at.isoformat() if doc.created_at else None,
                    }
                    for doc in results
                ]
        finally:
            session.close()
```

### 3.6 Async API Integration (Priority: Medium)

Create API endpoints that leverage the async capabilities of the storage layer.

```python
# pygovpub/api/documents.py
from typing import Dict, List, Optional, Any
from datetime import datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from pygovpub.storage.interface import StorageInterface
from pygovpub.security.storage_security import StorageSecurity
from pygovpub.search.vector_search import VectorSearchService
from pygovpub.config import get_config, create_storage_interface

logger = structlog.get_logger()

router = APIRouter()

class DocumentCreate(BaseModel):
    """Document creation model"""
    content: str
    source: Optional[str] = None
    title: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class DocumentResponse(BaseModel):
    """Document response model"""
    id: int
    content: str
    source: Optional[str] = None
    title: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

# Dependency injection for services
def get_storage():
    return create_storage_interface()

def get_security():
    return StorageSecurity(get_config().get("security"))

def get_search_service(storage: StorageInterface = Depends(get_storage)):
    return VectorSearchService(storage)

@router.post("/documents/", response_model=DocumentResponse)
async def create_document(
    document: DocumentCreate,
    storage: StorageInterface = Depends(get_storage),
    security: StorageSecurity = Depends(get_security)
):
    """Create a new document with async support"""
    from pygovpub.storage.models.document import get_document_model
    
    Document = get_document_model(storage.db_type)
    
    # Process data through security layer
    secure_data = security.process_data_for_storage(document.dict())
    
    try:
        # Use async version if supported
        if storage._supports_async():
            doc_id = await storage.create_async(Document, secure_data)
        else:
            # Fall back to sync version
            doc_id = storage.create(Document, secure_data)
            
        # Retrieve the created document
        if storage._supports_async():
            doc = await storage.get_async(Document, doc_id)
        else:
            doc = storage.get(Document, doc_id)
            
        # Process through security layer before returning
        doc_dict = {
            "id": doc.id,
            "content": doc.content,
            "source": doc.source,
            "title": doc.title,
            "metadata": doc.metadata,
            "created_at": doc.created_at,
            "updated_at": doc.updated_at
        }
        
        # Decrypt any encrypted fields
        processed_doc = security.process_data_from_storage(doc_dict)
            
        return DocumentResponse(**processed_doc)
    except Exception as e:
        logger.error("Failed to create document", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to create document: {str(e)}")

@router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: int,
    storage: StorageInterface = Depends(get_storage),
    security: StorageSecurity = Depends(get_security)
):
    """Get a document by ID with async support"""
    from pygovpub.storage.models.document import get_document_model
    
    Document = get_document_model(storage.db_type)
    
    try:
        # Use async version if supported
        if storage._supports_async():
            doc = await storage.get_async(Document, document_id)
        else:
            # Fall back to sync version
            doc = storage.get(Document, document_id)
            
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
            
        # Process through security layer before returning
        doc_dict = {
            "id": doc.id,
            "content": doc.content,
            "source": doc.source,
            "title": doc.title,
            "metadata": doc.metadata,
            "created_at": doc.created_at,
            "updated_at": doc.updated_at
        }
        
        # Decrypt any encrypted fields
        processed_doc = security.process_data_from_storage(doc_dict)
            
        return DocumentResponse(**processed_doc)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get document", error=str(e), document_id=document_id)
        raise HTTPException(status_code=500, detail=f"Failed to get document: {str(e)}")

@router.get("/search/", response_model=List[DocumentResponse])
async def search_documents(
    query: str = Query(..., min_length=1),
    limit: int = Query(10, gt=0, le=100),
    vector_search: bool = Query(True),
    storage: StorageInterface = Depends(get_storage),
    search_service: VectorSearchService = Depends(get_search_service),
    security: StorageSecurity = Depends(get_security)
):
    """Search documents with vector search support and fallbacks"""
    try:
        # Use vector search if requested and supported
        if vector_search and (
            storage.supports("vector_operations") or 
            storage.db_type in ["pinecone", "supabase"]
        ):
            results = search_service.vector_search(query, limit)
        else:
            # Fall back to keyword search
            results = search_service._keyword_search(query, limit)
            
        # Process through security layer
        processed_results = [
            security.process_data_from_storage(doc) for doc in results
        ]
            
        return [DocumentResponse(**doc) for doc in processed_results]
    except Exception as e:
        logger.error("Search error", error=str(e), query=query)
        raise HTTPException(status_code=500, detail=f"Search error: {str(e)}")
```

### 3.7 Performance Monitoring and Optimization (Priority: Medium)

Implement monitoring and optimization tools for the storage layer.

```python
# pygovpub/monitoring/storage_metrics.py
import time
import functools
from typing import Dict, List, Optional, Any, Type, Callable

import structlog
from prometheus_client import Summary, Counter, Gauge, Histogram
from tenacity import retry, stop_after_attempt, wait_exponential

logger = structlog.get_logger()

# Define metrics
DB_POOL_SIZE = Gauge(
    "db_pool_size", 
    "Database connection pool size", 
    ["db_type"]
)

DB_QUERY_DURATION = Histogram(
    "db_query_duration_seconds", 
    "Database query duration in seconds",
    ["query_type", "db_type"]
)

DB_ERRORS = Counter(
    "db_errors_total", 
    "Database errors",
    ["operation", "error_type", "db_type"]
)

VECTOR_SEARCH_DURATION = Histogram(
    "vector_search_duration_seconds",
    "Vector search duration in seconds",
    ["db_type", "fallback_used"]
)

def monitor_db_operation(operation_name: str):
    """Decorator to monitor database operations"""
    def decorator(func):
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            self = args[0]  # The class instance
            db_type = getattr(self, "db_type", "unknown")
            
            try:
                result = func(*args, **kwargs)
                DB_QUERY_DURATION.labels(
                    query_type=operation_name, 
                    db_type=db_type
                ).observe(time.time() - start_time)
                return result
            except Exception as e:
                DB_ERRORS.labels(
                    operation=operation_name,
                    error_type=type(e).__name__,
                    db_type=db_type
                ).inc()
                raise
                
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            self = args[0]  # The class instance
            db_type = getattr(self, "db_type", "unknown")
            
            try:
                result = await func(*args, **kwargs)
                DB_QUERY_DURATION.labels(
                    query_type=f"{operation_name}_async", 
                    db_type=db_type
                ).observe(time.time() - start_time)
                return result
            except Exception as e:
                DB_ERRORS.labels(
                    operation=f"{operation_name}_async",
                    error_type=type(e).__name__,
                    db_type=db_type
                ).inc()
                raise
        
        # Return appropriate wrapper based on if the function is async
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator

class PerformanceOptimizer:
    """Tools for monitoring and optimizing storage performance"""
    
    def __init__(self, storage):
        self.storage = storage
        self.db_type = storage.db_type
        
        # Record initial pool size
        if hasattr(storage.engine, "pool"):
            DB_POOL_SIZE.labels(db_type=self.db_type).set(
                getattr(storage.engine.pool, "size", 0)
            )
            
        logger.info("Performance optimizer initialized", db_type=self.db_type)
    
    def monitor_connection_pool(self):
        """Update connection pool metrics"""
        if hasattr(self.storage.engine, "pool"):
            pool = self.storage.engine.pool
            DB_POOL_SIZE.labels(db_type=self.db_type).set(
                getattr(pool, "size", 0)
            )
            
            # Log warnings for high pool usage
            if hasattr(pool, "checkedin") and hasattr(pool, "checkedout"):
                total = pool.checkedin + pool.checkedout
                usage_pct = (pool.checkedout / total) * 100 if total > 0 else 0
                
                if usage_pct > 80:
                    logger.warning(
                        "High connection pool usage",
                        db_type=self.db_type,
                        usage_percent=usage_pct,
                        checked_out=pool.checkedout,
                        checked_in=pool.checkedin
                    )
    
    def analyze_query_performance(self, query_text: str) -> Dict[str, Any]:
        """Analyze performance of a specific query"""
        if self.db_type == "postgresql":
            return self._analyze_postgresql_query(query_text)
        elif self.db_type == "mysql":
            return self._analyze_mysql_query(query_text)
        else:
            logger.warning("Query analysis not supported for this database type")
            return {}
    
    def _analyze_postgresql_query(self, query_text: str) -> Dict[str, Any]:
        """Analyze PostgreSQL query performance"""
        with self.storage.engine.connect() as conn:
            # Get query plan
            explain_query = f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {query_text}"
            result = conn.execute(text(explain_query))
            plan = result.scalar()
            
            if not plan:
                return {}
                
            # Extract key metrics
            execution_time = plan[0]["Plan"]["Actual Total Time"]
            planning_time = plan[0]["Planning Time"]
            
            return {
                "execution_time_ms": execution_time,
                "planning_time_ms": planning_time,
                "full_plan": plan
            }
    
    def _analyze_mysql_query(self, query_text: str) -> Dict[str, Any]:
        """Analyze MySQL query performance"""
        with self.storage.engine.connect() as conn:
            # Get query plan
            conn.execute(text("SET profiling = 1"))
            conn.execute(text(query_text))
            result = conn.execute(text("SHOW PROFILE"))
            
            profiles = [dict(row) for row in result]
            
            # Get execution plan
            explain = conn.execute(text(f"EXPLAIN {query_text}"))
            plan = [dict(row) for row in explain]
            
            return {
                "profiles": profiles,
                "explain_plan": plan
            }
    
    def optimize_for_vector_operations(self):
        """Apply database-specific optimizations for vector operations"""
        if not self.storage.supports("vector_operations"):
            logger.info("Vector operations not supported, skipping optimizations")
            return False
            
        try:
            if self.db_type == "postgresql":
                # Create index for vector search if it doesn't exist
                with self.storage.engine.connect() as conn:
                    # Check if index exists
                    result = conn.execute(text(
                        "SELECT 1 FROM pg_indexes WHERE indexname = 'idx_documents_embedding'"
                    ))
                    
                    if not result.scalar():
                        # Create index for cosine distance
                        conn.execute(text(
                            "CREATE INDEX idx_documents_embedding ON documents USING ivfflat (embedding vector_cosine_ops)"
                        ))
                        logger.info("Created vector search index for PostgreSQL")
                        
                return True
                
            elif self.db_type == "pinecone":
                # Pinecone is already optimized for vector search
                return True
                
        except Exception as e:
            logger.error("Failed to optimize for vector operations", error=str(e))
            return False
```

## 4. Implementation Phases

### Phase 1: Core Infrastructure (2 weeks)

1. Setup enhanced dependency structure with optional dependencies
2. Create the StorageInterface with error tracking and monitoring 
3. Implement security layer for credentials and sensitive data
4. Create database-specific models with common abstraction
5. Build cross-database migration system

**Deliverables:**
- Working storage abstraction with feature detection
- Support for all three main databases (PostgreSQL, SQLite, MySQL)
- Secure credential management and data encryption
- Robust error handling with structured logging
- Cross-database migration system
- Prometheus metrics integration

### Phase 2: Async Support and Provider Integration (2 weeks)

1. Implement proper async support for all database types
2. Create unified error handling across async/sync operations
3. Develop isolated provider modules with dynamic imports
4. Build monitoring infrastructure for all database operations
5. Implement comprehensive fallback strategies
6. Setup testing infrastructure with database-specific tests

**Deliverables:**
- Full async support for all databases
- Isolated provider modules with conditional loading
- Comprehensive error handling and monitoring
- Testing framework supporting all database types

### Phase 3: Vector Search Implementation (2 weeks)

1. Implement text and vector search for all database backends
2. Create fallback strategies when vector search isn't available
3. Add performance optimizations for vector operations
4. Implement security for embeddings and search queries
5. Create monitoring for search performance
6. Build comprehensive tests for vector operations

**Deliverables:**
- Working search across all database backends
- Vector search for PostgreSQL with pgVector
- Fallback strategies for databases without vector support
- Search performance monitoring

### Phase 4: API Integration and LLM Support (2 weeks)

1. Integrate storage with FastAPI endpoints
2. Implement Billy LLM with improved security handling
3. Create comprehensive documentation for all features
4. Implement performance optimizations for production
5. Setup monitoring dashboards for API and LLM operations

**Deliverables:**
- API endpoints with async support
- Secure Billy LLM integration
- Comprehensive documentation
- Performance-optimized deployment

## 5. Risk Mitigation Strategies

| Risk | Mitigation |
|------|------------|
| SQLModel/SQLAlchemy compatibility | Use SQLAlchemy 2.0's compatibility layer; unit test all database operations |
| Missing pgVector extension | Add clear detection and fallback to JSON array storage for embeddings |
| MySQL vector limitations | Store vectors as JSON arrays; implement efficient batch search operations |
| Scaling issues in vector search | Implement proper indexing, caching, and pagination in all search operations |
| Async complexity | Use consistent patterns across database types; include fallbacks to sync operations |
| Security considerations | Apply targeted encryption only to sensitivity metadata (API keys, document classifications), not to document content itself |
| Migration failures | Include detailed error logging; create database-specific migration branches |
| Production vs development | Allow SQLite for development while ensuring schema compatibility with production PostgreSQL |

## 6. Testing Strategy

Create a comprehensive testing framework that supports all database types:

```python
# tests/conftest.py
import pytest
import os
from typing import Dict, Any, Generator

import sqlalchemy
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from pygovpub.storage.interface import StorageInterface
from pygovpub.storage.models.document import Base, get_document_model
from pygovpub.security.storage_security import StorageSecurity

# Test against real database backends
@pytest.fixture(params=["sqlite", "postgresql", "mysql"])
def db_type(request):
    """Parametrize tests across database types"""
    return request.param

@pytest.fixture
def connection_string(db_type: str) -> str:
    """Get appropriate connection string for the database type"""
    if db_type == "sqlite":
        return "sqlite:///./test.db"
    elif db_type == "postgresql":
        # Use test database from environment or default
        return os.environ.get(
            "TEST_POSTGRESQL_URL", 
            "postgresql://postgres:postgres@localhost:5432/pygovpub_test"
        )
    elif db_type == "mysql":
        # Use test database from environment or default
        return os.environ.get(
            "TEST_MYSQL_URL",
            "mysql://root:password@localhost:3306/pygovpub_test"
        )
    else:
        raise ValueError(f"Unknown database type: {db_type}")

@pytest.fixture
def storage(connection_string: str) -> Generator[StorageInterface, None, None]:
    """Create a test storage interface"""
    test_engine = create_engine(connection_string)
    
    # Create tables
    Base.metadata.create_all(test_engine)
    
    # Create storage interface
    storage_interface = StorageInterface(connection_string)
    
    yield storage_interface
    
    # Clean up
    Base.metadata.drop_all(test_engine)

@pytest.fixture
def security() -> StorageSecurity:
    """Create test security instance"""
    return StorageSecurity({"master_password": "test_password"})

@pytest.fixture
def test_document() -> Dict[str, Any]:
    """Create a test document"""
    return {
        "content": "This is a test document",
        "source": "test_source",
        "title": "Test Document",
        "metadata": {"author": "Test Author"}
    }

# Conditional test skipping
def requires_vector_ops(storage_interface):
    """Decorator to skip tests if vector operations not supported"""
    return pytest.mark.skipif(
        not storage_interface.supports("vector_operations"),
        reason="Vector operations not supported by this database"
    )

def requires_package(package_name):
    """Decorator to skip tests if a package is not available"""
    import importlib.util
    return pytest.mark.skipif(
        importlib.util.find_spec(package_name) is None,
        reason=f"Package {package_name} not installed"
    )
```

Example vector search test:

```python
# tests/test_vector_search.py
import pytest
from pygovpub.search.vector_search import VectorSearchService
from pygovpub.storage.models.document import get_document_model

def test_basic_search(storage, test_document):
    """Test basic search functionality works across all DB types"""
    Document = get_document_model(storage.db_type)
    
    # Create test document
    doc_id = storage.create(Document, test_document)
    
    # Create search service
    search_service = VectorSearchService(storage)
    
    # Search for document
    results = search_service._keyword_search("test document")
    
    # Verify results
    assert len(results) == 1
    assert results[0]["id"] == doc_id
    assert results[0]["content"] == test_document["content"]

@pytest.mark.parametrize("query", ["test", "document"])
def test_keyword_search_variations(storage, test_document, query):
    """Test keyword search with different queries"""
    Document = get_document_model(storage.db_type)
    
    # Create test document
    storage.create(Document, test_document)
    
    # Create search service
    search_service = VectorSearchService(storage)
    
    # Search for document
    results = search_service._keyword_search(query)
    
    # Verify results
    assert len(results) > 0
    assert results[0]["content"] == test_document["content"]

@requires_vector_ops
def test_vector_search(storage, test_document):
    """Test vector search functionality"""
    Document = get_document_model(storage.db_type)
    
    # Create test document
    doc_id = storage.create(Document, test_document)
    
    # Create search service
    search_service = VectorSearchService(storage)
    
    # Generate embedding
    embedding = search_service.generate_embedding(test_document["content"])
    
    # Update document with embedding
    if storage.db_type == "postgresql":
        with storage.engine.connect() as conn:
            conn.execute(
                f"UPDATE documents SET embedding = '[{','.join(map(str, embedding))}]' WHERE id = {doc_id}"
            )
    
    # Search for document using vector search
    results = search_service.vector_search("test document")
    
    # Verify results
    assert len(results) == 1
    assert results[0]["id"] == doc_id
```

## 7. Conclusion

This enhanced implementation plan addresses all the critical gaps in the original proposal, including:

1. **MySQL Support**: Complete implementation with appropriate abstractions and fallbacks
2. **Error Handling & Monitoring**: Integrated structured logging, retry mechanisms, and metrics collection
3. **Comprehensive Async Support**: Unified async implementation across all database types
4. **Security Implementation**: Encryption for sensitive data and proper credential management
5. **Schema Migration Strategy**: Cross-database migration system with database-specific customizations

The plan also addresses potential future issues with SQLModel compatibility, database extension requirements, testing complexity, and performance at scale.

By implementing this enhanced architecture, PyGovPub will have a robust, scalable, and secure storage layer that supports multiple database backends while remaining flexible for future extensions.
