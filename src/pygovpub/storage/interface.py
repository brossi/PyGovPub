"""
Database-agnostic storage interface with monitoring, circuit breaking, and feature detection.

This module provides a unified interface for storage operations across various database
backends including PostgreSQL, SQLite, and optional cloud providers like Pinecone,
Supabase, and LanceDB. It includes built-in monitoring, circuit breaking for resilience,
and runtime feature detection.
"""

import importlib.util
import time
from typing import Any, Dict, List, Optional, Type, TypeVar, Generic, Union

import structlog
from prometheus_client import Counter, Histogram, Gauge
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
DB_CONNECTIONS_ACTIVE = Gauge("db_connections_active", "Active database connections", ["db_type"])
CIRCUIT_STATE = Gauge("circuit_breaker_state", "Circuit breaker state (0=closed, 1=open)", ["db_type"])

T = TypeVar("T")

# Simple circuit breaker decorator
def circuit_breaker(max_failures=5, reset_timeout=30):
    """
    Simple circuit breaker decorator.
    
    Args:
        max_failures: Maximum number of consecutive failures before opening the circuit
        reset_timeout: Time in seconds before attempting to close the circuit
    """
    def decorator(func):
        # State for this circuit breaker
        state = {
            "failures": 0,
            "open": False,
            "last_failure_time": 0
        }
        
        def wrapper(*args, **kwargs):
            # Get db_type from first argument (self)
            db_type = args[0].db_type if args and hasattr(args[0], "db_type") else "unknown"
            
            # Check if circuit is open
            if state["open"]:
                # Check if enough time has passed to try again
                if (time.time() - state["last_failure_time"]) > reset_timeout:
                    # Reset state to half-open
                    state["open"] = False
                    state["failures"] = 0
                    CIRCUIT_STATE.labels(db_type=db_type).set(0)
                    logger.info(f"Circuit breaker for {db_type} reset to closed state")
                else:
                    logger.warning(f"Circuit breaker for {db_type} is open, rejecting request")
                    raise RuntimeError(f"Circuit breaker for {db_type} is open")
            
            # Try the operation
            try:
                result = func(*args, **kwargs)
                # Success, reset failure count
                state["failures"] = 0
                return result
            except Exception as e:
                # Increment failure count
                state["failures"] += 1
                state["last_failure_time"] = time.time()
                
                # Check if we should open the circuit
                if state["failures"] >= max_failures:
                    state["open"] = True
                    CIRCUIT_STATE.labels(db_type=db_type).set(1)
                    logger.error(f"Circuit breaker for {db_type} opened after {max_failures} failures")
                
                # Re-raise the exception
                raise
        
        return wrapper
    
    return decorator

# Define our circuit breaker for database connections
CONNECTION_CIRCUIT_BREAKER = circuit_breaker(max_failures=5, reset_timeout=30)

def _initialize_lancedb_provider(connection_string: str, **config):
    """
    Initialize a LanceDB provider instance.
    
    Args:
        connection_string: LanceDB connection string
        **config: Additional configuration options
        
    Returns:
        LanceDBProvider instance
    """
    from pygovpub.storage.providers.lancedb_provider import LanceDBProvider
    # Remove lancedb:// prefix if present
    uri = connection_string.replace("lancedb://", "")
    return LanceDBProvider(uri=uri, **config)

class StorageInterface:
    """Database-agnostic storage interface with monitoring and fallbacks"""

    def __init__(self, connection_string: str, **config):
        """
        Initialize storage interface with the specified connection string.
        
        Args:
            connection_string: Database connection string
            **config: Additional configuration options
                - echo: Whether to echo SQL statements (default: False)
                - pool_size: Connection pool size (default: 5)
                - max_overflow: Maximum overflow connections (default: 10)
                - pool_timeout: Pool timeout in seconds (default: 30)
                - pool_recycle: Connection recycle time in seconds (default: 1800)
        """
        self.connection_string = connection_string
        self.config = config
        self.db_type = self._determine_db_type(connection_string)
        
        # Provider storage for non-SQLAlchemy databases
        self._providers = {}

        # Schema version tracking
        self.schema_version = None

        # Initialize provider-specific instances if needed
        if self.db_type == "lancedb" and self._is_package_available("lancedb"):
            try:
                self._providers["lancedb"] = _initialize_lancedb_provider(connection_string, **config)
            except Exception as e:
                logger.error("Failed to initialize LanceDB provider", error=str(e))

        # Setup sync engine with appropriate pool settings for SQL databases
        if self.db_type in ["sqlite", "postgresql", "mysql"]:
            # SQLite doesn't support the same connection pooling options
            if self.db_type == "sqlite":
                self.engine = create_engine(
                    connection_string,
                    echo=config.get("echo", False),
                    connect_args={"check_same_thread": False}  # Allow cross-thread usage
                )
            else:
                # Full connection pooling for production databases
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
                
                # SQLite doesn't support the same connection pooling options for async
                if self.db_type == "sqlite":
                    self.async_engine = create_async_engine(
                        async_connection,
                        echo=config.get("echo", False),
                        connect_args={"check_same_thread": False}
                    )
                else:
                    # Full connection pooling for production async databases
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
        else:
            # For non-SQL databases, set these to None
            self.engine = None
            self.Session = None
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
            async_supported=self._supports_async() if self.db_type in ["sqlite", "postgresql", "mysql"] else False
        )

    def _determine_db_type(self, connection_string: str) -> str:
        """
        Determine database type from connection string.
        
        Args:
            connection_string: Database connection string
            
        Returns:
            Database type identifier (e.g., "sqlite", "postgresql", etc.)
        """
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
        """
        Convert standard connection string to async equivalent.
        
        Args:
            connection_string: Standard database connection string
            
        Returns:
            Async-compatible connection string
        """
        if "sqlite" in connection_string:
            # Convert sqlite:/// to sqlite+aiosqlite:///
            return connection_string.replace("sqlite:///", "sqlite+aiosqlite:///")
        elif "postgresql" in connection_string:
            # Convert postgresql:// to postgresql+asyncpg://
            return connection_string.replace("postgresql://", "postgresql+asyncpg://")
        elif "mysql" in connection_string:
            # Convert any mysql dialect to mysql+aiomysql
            # Handle various mysql dialects (mysql+pymysql, mysql+mysqldb, etc.)
            if "mysql+aiomysql://" in connection_string:
                # Already using aiomysql
                return connection_string
            
            # Replace any mysql dialect or default with aiomysql
            if "mysql+pymysql://" in connection_string:
                return connection_string.replace("mysql+pymysql://", "mysql+aiomysql://")
            elif "mysql+mysqldb://" in connection_string:
                return connection_string.replace("mysql+mysqldb://", "mysql+aiomysql://")
            elif "mysql+mysqlconnector://" in connection_string:
                return connection_string.replace("mysql+mysqlconnector://", "mysql+aiomysql://")
            else:
                # Default mysql:// case
                return connection_string.replace("mysql://", "mysql+aiomysql://")
        else:
            # Return original for non-standard backends
            return connection_string

    def _supports_async(self) -> bool:
        """
        Check if async operations are supported for this database.
        
        Returns:
            True if async operations are supported, False otherwise
        """
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
        """
        Detect database features and capabilities.
        
        Returns:
            Dictionary of feature flags
        """
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
                
                # Check for HNSW index support
                if hasattr(lancedb, "index") and hasattr(lancedb.index, "HNSW"):
                    features['hnsw_index'] = True
                
                # Get provider if already initialized
                provider = self._providers.get("lancedb")
                if provider and hasattr(provider.db, "create_version"):
                    features['versioning'] = True

            except Exception as e:
                logger.error("Error during LanceDB feature detection", error=str(e))

        return features

    def _is_package_available(self, package_name: str) -> bool:
        """
        Check if a Python package is installed and available.
        
        Args:
            package_name: Name of the package to check
            
        Returns:
            True if package is available, False otherwise
        """
        return importlib.util.find_spec(package_name) is not None

    def _get_schema_version(self) -> Optional[int]:
        """
        Get the current schema version from the database.
        
        Returns:
            Schema version number or None if not available
        """
        if self.db_type in ["pinecone", "supabase", "lancedb"]:
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
        """
        Check if a specific feature is supported.
        
        Args:
            feature: Feature name to check
            
        Returns:
            True if feature is supported, False otherwise
        """
        return self.features.get(feature, False)

    def supports_schema_feature(self, feature_name: str) -> bool:
        """
        Check if current schema version supports a feature.
        
        Args:
            feature_name: Feature name to check
            
        Returns:
            True if feature is supported at current schema version, False otherwise
        """
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

    def _get_provider(self, provider_type: str = None):
        """
        Get the appropriate storage provider for the current database type.
        
        Args:
            provider_type: Optional provider type to use instead of db_type
            
        Returns:
            Storage provider instance
        
        Raises:
            ValueError: If provider not available
        """
        db_type = provider_type or self.db_type
        
        if db_type not in self._providers:
            raise ValueError(f"Provider for {db_type} not initialized")
        
        return self._providers[db_type]

    @CONNECTION_CIRCUIT_BREAKER
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True
    )
    def create(self, model_class: Type[T], data: Dict[str, Any]) -> Union[int, str]:
        """
        Create a new record with monitoring, retry, and circuit breaking.
        
        Args:
            model_class: Model class to instantiate
            data: Dictionary of attribute values
            
        Returns:
            ID of the created record
        
        Raises:
            Exception: Database errors during creation
        """
        # For non-SQL databases, use provider
        if self.db_type in ["lancedb", "pinecone", "supabase"]:
            return self.create_with_provider(self.db_type, model_class, data)
        
        # SQL database path
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
    def create_with_provider(self, provider_type: str, model_class: Type[T], data: Dict[str, Any]) -> str:
        """
        Create a new record using a specific provider.
        
        Args:
            provider_type: Provider type (e.g., "lancedb")
            model_class: Model class to instantiate
            data: Dictionary of attribute values
            
        Returns:
            ID of the created record
            
        Raises:
            ValueError: If provider not available
            Exception: Database errors during creation
        """
        provider = self._get_provider(provider_type)
        
        start_time = time.time()
        try:
            # Track operations
            DB_OPERATIONS.labels(operation=f"create_{provider_type}", status="processing", db_type=provider_type).inc()
            
            # Create record using provider
            result = provider.create(model_class, data)
            
            DB_OPERATIONS.labels(operation=f"create_{provider_type}", status="success", db_type=provider_type).inc()
            DB_OPERATION_DURATION.labels(operation=f"create_{provider_type}", db_type=provider_type).observe(time.time() - start_time)
            
            return result
        except Exception as e:
            DB_OPERATIONS.labels(operation=f"create_{provider_type}", status="error", db_type=provider_type).inc()
            logger.error(f"Failed to create record with {provider_type}", error=str(e))
            raise

    @CONNECTION_CIRCUIT_BREAKER
    async def create_async(self, model_class: Type[T], data: Dict[str, Any]) -> int:
        """
        Create a new record asynchronously with monitoring and circuit breaking.
        
        Args:
            model_class: Model class to instantiate
            data: Dictionary of attribute values
            
        Returns:
            ID of the created record
            
        Raises:
            NotImplementedError: If async operations not supported
            Exception: Database errors during creation
        """
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

    def vector_search_with_provider(self, 
                                   provider_type: str, 
                                   model_class: Type[T], 
                                   query_vector: List[float], 
                                   limit: int = 10, 
                                   filter_criteria: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Perform vector search using a specific provider.
        
        Args:
            provider_type: Provider type (e.g., "lancedb")
            model_class: Model class to use for the search
            query_vector: Query embedding vector
            limit: Maximum number of results to return
            filter_criteria: Optional filtering criteria
            
        Returns:
            List of matching records
            
        Raises:
            ValueError: If provider not available
            Exception: Database errors during search
        """
        provider = self._get_provider(provider_type)
        
        start_time = time.time()
        try:
            # Track operations
            DB_OPERATIONS.labels(operation=f"vector_search_{provider_type}", status="processing", db_type=provider_type).inc()
            
            # Perform search using provider
            results = provider.vector_search(model_class, query_vector, limit=limit, filter_criteria=filter_criteria)
            
            DB_OPERATIONS.labels(operation=f"vector_search_{provider_type}", status="success", db_type=provider_type).inc()
            DB_OPERATION_DURATION.labels(operation=f"vector_search_{provider_type}", db_type=provider_type).observe(time.time() - start_time)
            
            return results
        except Exception as e:
            DB_OPERATIONS.labels(operation=f"vector_search_{provider_type}", status="error", db_type=provider_type).inc()
            logger.error(f"Failed to perform vector search with {provider_type}", error=str(e))
            raise

    def hybrid_search_with_provider(self, 
                                   provider_type: str, 
                                   model_class: Type[T], 
                                   query_text: str, 
                                   query_vector: List[float] = None, 
                                   limit: int = 10, 
                                   filter_criteria: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Perform hybrid search (vector + text) using a specific provider.
        
        Args:
            provider_type: Provider type (e.g., "lancedb")
            model_class: Model class to use for the search
            query_text: Text query
            query_vector: Optional vector query
            limit: Maximum number of results to return
            filter_criteria: Optional filtering criteria
            
        Returns:
            List of matching records
            
        Raises:
            ValueError: If provider not available or doesn't support hybrid search
            Exception: Database errors during search
        """
        provider = self._get_provider(provider_type)
        
        if not hasattr(provider, "hybrid_search"):
            raise ValueError(f"Provider {provider_type} does not support hybrid search")
        
        start_time = time.time()
        try:
            # Track operations
            DB_OPERATIONS.labels(operation=f"hybrid_search_{provider_type}", status="processing", db_type=provider_type).inc()
            
            # Perform hybrid search using provider
            results = provider.hybrid_search(
                model_class, query_text, query_vector=query_vector, limit=limit, filter_criteria=filter_criteria
            )
            
            DB_OPERATIONS.labels(operation=f"hybrid_search_{provider_type}", status="success", db_type=provider_type).inc()
            DB_OPERATION_DURATION.labels(operation=f"hybrid_search_{provider_type}", db_type=provider_type).observe(time.time() - start_time)
            
            return results
        except Exception as e:
            DB_OPERATIONS.labels(operation=f"hybrid_search_{provider_type}", status="error", db_type=provider_type).inc()
            logger.error(f"Failed to perform hybrid search with {provider_type}", error=str(e))
            raise
            
    def migrate_to_provider(self, 
                           table_name: str,
                           target_provider,
                           model_class: Type[T],
                           embedding_field: str = None,
                           embedding_generator = None,
                           content_field: str = None,
                           limit: int = None,
                           batch_size: int = 100,
                           schema_version: str = None) -> int:
        """
        Migrate data from SQL database to a different provider.
        
        Args:
            table_name: Source table name
            target_provider: Target provider instance
            model_class: Model class for the data
            embedding_field: Field to store embeddings (for vector databases)
            embedding_generator: Optional function to generate embeddings from content
            content_field: Field containing text content for embedding generation
            limit: Optional limit on number of records to migrate
            batch_size: Batch size for processing records
            schema_version: Optional schema version to apply to target
            
        Returns:
            Number of records migrated
        """
        # Validate provider-specific parameters
        if embedding_generator and not content_field:
            raise ValueError("content_field must be specified when embedding_generator is provided")
            
        if self.db_type in ["lancedb"]:
            # For non-SQL databases, use their provider's migrate method if available
            if self._providers.get(self.db_type) and hasattr(self._providers[self.db_type], "migrate_to_provider"):
                return self._providers[self.db_type].migrate_to_provider(
                    table_name,
                    target_provider,
                    model_class,
                    limit=limit,
                    batch_size=batch_size
                )
            else:
                raise ValueError(f"Provider {self.db_type} does not support migration")
        
        # For SQL databases, use SQL query to extract data
        if self.db_type not in ["sqlite", "postgresql", "mysql"]:
            raise ValueError(f"Unsupported source database type: {self.db_type}")
            
        start_time = time.time()
        
        try:
            # Track operation
            DB_OPERATIONS.labels(
                operation=f"migrate_to_{getattr(target_provider, 'db_type', 'unknown')}",
                status="processing", 
                db_type=self.db_type
            ).inc()
            
            # Get all records from source table
            connection = self._get_sql_connection()
            
            # Construct query
            query = text(f"SELECT * FROM {table_name}")
            if limit:
                query = text(f"SELECT * FROM {table_name} LIMIT {limit}")
                
            result = connection.execute(query)
            
            # Process results and generate embeddings if needed
            migrated_count = 0
            batch = []
            
            for row in result:
                # Convert to dict
                record = dict(row)
                
                # Generate embedding if needed
                if embedding_generator and content_field and content_field in record:
                    embedding = embedding_generator(record[content_field])
                    record[embedding_field] = embedding
                
                batch.append(record)
                
                # Process in batches
                if len(batch) >= batch_size:
                    # Apply schema version if provided
                    if schema_version and hasattr(target_provider, "apply_schema_version"):
                        target_provider.apply_schema_version(table_name, schema_version)
                    
                    # Process batch
                    for item in batch:
                        target_provider.create(model_class, item)
                        migrated_count += 1
                    
                    # Clear batch
                    batch = []
            
            # Process any remaining records
            if batch:
                for item in batch:
                    target_provider.create(model_class, item)
                    migrated_count += 1
            
            DB_OPERATIONS.labels(
                operation=f"migrate_to_{getattr(target_provider, 'db_type', 'unknown')}",
                status="success", 
                db_type=self.db_type
            ).inc()
            
            DB_OPERATION_DURATION.labels(
                operation=f"migrate_to_{getattr(target_provider, 'db_type', 'unknown')}",
                db_type=self.db_type
            ).observe(time.time() - start_time)
            
            logger.info(f"Migrated {migrated_count} records from {table_name} to {getattr(target_provider, 'db_type', 'unknown')}")
            return migrated_count
            
        except Exception as e:
            DB_OPERATIONS.labels(
                operation=f"migrate_to_{getattr(target_provider, 'db_type', 'unknown')}",
                status="error", 
                db_type=self.db_type
            ).inc()
            
            logger.error(f"Failed to migrate data to {getattr(target_provider, 'db_type', 'unknown')}", error=str(e))
            raise

    @CONNECTION_CIRCUIT_BREAKER
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True
    )
    def get(self, model_class: Type[T], id: Any) -> Optional[Dict[str, Any]]:
        """
        Retrieve a record by ID with monitoring, retry, and circuit breaking.
        
        Args:
            model_class: Model class to query
            id: ID of the record to retrieve
            
        Returns:
            Dictionary of attribute values or None if not found
            
        Raises:
            Exception: Database errors during retrieval
        """
        # For non-SQL databases, use provider
        if self.db_type in ["lancedb", "pinecone", "supabase"]:
            return self.get_with_provider(self.db_type, model_class, id)
        
        # SQL database path
        start_time = time.time()
        session = self.Session()
        
        try:
            # Track active connections
            DB_CONNECTIONS_ACTIVE.labels(db_type=self.db_type).inc()
            
            # Query for the record
            record = session.query(model_class).filter(model_class.id == id).first()
            
            # Record operation in metrics
            if record:
                DB_OPERATIONS.labels(operation="get", status="success", db_type=self.db_type).inc()
            else:
                DB_OPERATIONS.labels(operation="get", status="not_found", db_type=self.db_type).inc()
                
            DB_OPERATION_DURATION.labels(operation="get", db_type=self.db_type).observe(time.time() - start_time)
            
            if not record:
                return None
                
            # Convert to dictionary and remove SQLAlchemy state
            result = {k: v for k, v in record.__dict__.items() if not k.startswith('_')}
            
            logger.debug("Retrieved record", model=model_class.__name__, id=id)
            return result
            
        except Exception as e:
            DB_OPERATIONS.labels(operation="get", status="error", db_type=self.db_type).inc()
            logger.error(
                "Failed to retrieve record",
                model=model_class.__name__,
                id=id,
                error=str(e),
                error_type=type(e).__name__
            )
            raise
        finally:
            session.close()
            # Decrement active connection count
            DB_CONNECTIONS_ACTIVE.labels(db_type=self.db_type).dec()
            
    @CONNECTION_CIRCUIT_BREAKER
    def get_with_provider(self, provider_type: str, model_class: Type[T], id: Any) -> Optional[Dict[str, Any]]:
        """
        Retrieve a record by ID using a specific provider.
        
        Args:
            provider_type: Provider type (e.g., "lancedb")
            model_class: Model class to query
            id: ID of the record to retrieve
            
        Returns:
            Dictionary of attribute values or None if not found
            
        Raises:
            ValueError: If provider not available
            Exception: Database errors during retrieval
        """
        provider = self._get_provider(provider_type)
        
        start_time = time.time()
        try:
            # Track operations
            DB_OPERATIONS.labels(operation=f"get_{provider_type}", status="processing", db_type=provider_type).inc()
            
            # Retrieve record using provider
            result = provider.get(model_class, id)
            
            # Record metrics based on result
            if result:
                DB_OPERATIONS.labels(operation=f"get_{provider_type}", status="success", db_type=provider_type).inc()
            else:
                DB_OPERATIONS.labels(operation=f"get_{provider_type}", status="not_found", db_type=provider_type).inc()
                
            DB_OPERATION_DURATION.labels(operation=f"get_{provider_type}", db_type=provider_type).observe(time.time() - start_time)
            
            return result
        except Exception as e:
            DB_OPERATIONS.labels(operation=f"get_{provider_type}", status="error", db_type=provider_type).inc()
            logger.error(f"Failed to retrieve record with {provider_type}", model=model_class.__name__, id=id, error=str(e))
            raise
            
    @CONNECTION_CIRCUIT_BREAKER
    async def get_async(self, model_class: Type[T], id: Any) -> Optional[Dict[str, Any]]:
        """
        Retrieve a record by ID asynchronously with monitoring and circuit breaking.
        
        Args:
            model_class: Model class to query
            id: ID of the record to retrieve
            
        Returns:
            Dictionary of attribute values or None if not found
            
        Raises:
            NotImplementedError: If async operations not supported
            Exception: Database errors during retrieval
        """
        if not self._supports_async():
            raise NotImplementedError(f"Async operations not supported for {self.db_type}")
            
        start_time = time.time()
        async_session = self.AsyncSession()
        
        try:
            # Track active connections
            DB_CONNECTIONS_ACTIVE.labels(db_type=self.db_type).inc()
            
            # Query for the record asynchronously
            from sqlalchemy import select
            query = select(model_class).filter(model_class.id == id)
            result = await async_session.execute(query)
            record = result.scalar_one_or_none()
            
            # Record operation in metrics
            if record:
                DB_OPERATIONS.labels(operation="get_async", status="success", db_type=self.db_type).inc()
            else:
                DB_OPERATIONS.labels(operation="get_async", status="not_found", db_type=self.db_type).inc()
                
            DB_OPERATION_DURATION.labels(operation="get_async", db_type=self.db_type).observe(time.time() - start_time)
            
            if not record:
                return None
                
            # Convert to dictionary and remove SQLAlchemy state
            result_dict = {k: v for k, v in record.__dict__.items() if not k.startswith('_')}
            
            logger.debug("Retrieved record asynchronously", model=model_class.__name__, id=id)
            return result_dict
            
        except Exception as e:
            DB_OPERATIONS.labels(operation="get_async", status="error", db_type=self.db_type).inc()
            logger.error(
                "Failed to retrieve record asynchronously",
                model=model_class.__name__,
                id=id,
                error=str(e),
                error_type=type(e).__name__
            )
            raise
        finally:
            await async_session.close()
            # Decrement active connection count
            DB_CONNECTIONS_ACTIVE.labels(db_type=self.db_type).dec()
    
    @CONNECTION_CIRCUIT_BREAKER
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True
    )
    def update(self, model_class: Type[T], id: Any, data: Dict[str, Any]) -> bool:
        """
        Update an existing record with monitoring, retry, and circuit breaking.
        
        Args:
            model_class: Model class to query
            id: ID of the record to update
            data: Dictionary of attribute values to update
            
        Returns:
            True if record was updated, False if record not found
            
        Raises:
            Exception: Database errors during update
        """
        # For non-SQL databases, use provider
        if self.db_type in ["lancedb", "pinecone", "supabase"]:
            return self.update_with_provider(self.db_type, model_class, id, data)
        
        # SQL database path
        start_time = time.time()
        session = self.Session()
        
        try:
            # Track active connections
            DB_CONNECTIONS_ACTIVE.labels(db_type=self.db_type).inc()
            
            # Query for the record
            record = session.query(model_class).filter(model_class.id == id).first()
            
            if not record:
                DB_OPERATIONS.labels(operation="update", status="not_found", db_type=self.db_type).inc()
                DB_OPERATION_DURATION.labels(operation="update", db_type=self.db_type).observe(time.time() - start_time)
                return False
                
            # Update record attributes
            for key, value in data.items():
                setattr(record, key, value)
                
            # Commit changes
            session.commit()
            
            DB_OPERATIONS.labels(operation="update", status="success", db_type=self.db_type).inc()
            DB_OPERATION_DURATION.labels(operation="update", db_type=self.db_type).observe(time.time() - start_time)
            
            logger.debug("Updated record", model=model_class.__name__, id=id)
            return True
            
        except Exception as e:
            session.rollback()
            DB_OPERATIONS.labels(operation="update", status="error", db_type=self.db_type).inc()
            logger.error(
                "Failed to update record",
                model=model_class.__name__,
                id=id,
                error=str(e),
                error_type=type(e).__name__
            )
            raise
        finally:
            session.close()
            # Decrement active connection count
            DB_CONNECTIONS_ACTIVE.labels(db_type=self.db_type).dec()
            
    @CONNECTION_CIRCUIT_BREAKER
    def update_with_provider(self, provider_type: str, model_class: Type[T], id: Any, data: Dict[str, Any]) -> bool:
        """
        Update a record using a specific provider.
        
        Args:
            provider_type: Provider type (e.g., "lancedb")
            model_class: Model class to query
            id: ID of the record to update
            data: Dictionary of attribute values to update
            
        Returns:
            True if record was updated, False if record not found
            
        Raises:
            ValueError: If provider not available
            Exception: Database errors during update
        """
        provider = self._get_provider(provider_type)
        
        start_time = time.time()
        try:
            # Track operations
            DB_OPERATIONS.labels(operation=f"update_{provider_type}", status="processing", db_type=provider_type).inc()
            
            # Update record using provider
            result = provider.update(model_class, id, data)
            
            # Record metrics based on result
            if result:
                DB_OPERATIONS.labels(operation=f"update_{provider_type}", status="success", db_type=provider_type).inc()
            else:
                DB_OPERATIONS.labels(operation=f"update_{provider_type}", status="not_found", db_type=provider_type).inc()
                
            DB_OPERATION_DURATION.labels(operation=f"update_{provider_type}", db_type=provider_type).observe(time.time() - start_time)
            
            return result
        except Exception as e:
            DB_OPERATIONS.labels(operation=f"update_{provider_type}", status="error", db_type=provider_type).inc()
            logger.error(f"Failed to update record with {provider_type}", model=model_class.__name__, id=id, error=str(e))
            raise
            
    @CONNECTION_CIRCUIT_BREAKER
    async def update_async(self, model_class: Type[T], id: Any, data: Dict[str, Any]) -> bool:
        """
        Update an existing record asynchronously with monitoring and circuit breaking.
        
        Args:
            model_class: Model class to query
            id: ID of the record to update
            data: Dictionary of attribute values to update
            
        Returns:
            True if record was updated, False if record not found
            
        Raises:
            NotImplementedError: If async operations not supported
            Exception: Database errors during update
        """
        if not self._supports_async():
            raise NotImplementedError(f"Async operations not supported for {self.db_type}")
            
        start_time = time.time()
        async_session = self.AsyncSession()
        
        try:
            # Track active connections
            DB_CONNECTIONS_ACTIVE.labels(db_type=self.db_type).inc()
            
            # Query for the record asynchronously
            from sqlalchemy import select
            query = select(model_class).filter(model_class.id == id)
            result = await async_session.execute(query)
            record = result.scalar_one_or_none()
            
            if not record:
                DB_OPERATIONS.labels(operation="update_async", status="not_found", db_type=self.db_type).inc()
                DB_OPERATION_DURATION.labels(operation="update_async", db_type=self.db_type).observe(time.time() - start_time)
                return False
                
            # Update record attributes
            for key, value in data.items():
                setattr(record, key, value)
                
            # Commit changes
            await async_session.commit()
            
            DB_OPERATIONS.labels(operation="update_async", status="success", db_type=self.db_type).inc()
            DB_OPERATION_DURATION.labels(operation="update_async", db_type=self.db_type).observe(time.time() - start_time)
            
            logger.debug("Updated record asynchronously", model=model_class.__name__, id=id)
            return True
            
        except Exception as e:
            await async_session.rollback()
            DB_OPERATIONS.labels(operation="update_async", status="error", db_type=self.db_type).inc()
            logger.error(
                "Failed to update record asynchronously",
                model=model_class.__name__,
                id=id,
                error=str(e),
                error_type=type(e).__name__
            )
            raise
        finally:
            await async_session.close()
            # Decrement active connection count
            DB_CONNECTIONS_ACTIVE.labels(db_type=self.db_type).dec()
    
    @CONNECTION_CIRCUIT_BREAKER
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True
    )
    def delete(self, model_class: Type[T], id: Any) -> bool:
        """
        Delete a record with monitoring, retry, and circuit breaking.
        
        Args:
            model_class: Model class to query
            id: ID of the record to delete
            
        Returns:
            True if record was deleted, False if record not found
            
        Raises:
            Exception: Database errors during deletion
        """
        # For non-SQL databases, use provider
        if self.db_type in ["lancedb", "pinecone", "supabase"]:
            return self.delete_with_provider(self.db_type, model_class, id)
        
        # SQL database path
        start_time = time.time()
        session = self.Session()
        
        try:
            # Track active connections
            DB_CONNECTIONS_ACTIVE.labels(db_type=self.db_type).inc()
            
            # Query for the record
            record = session.query(model_class).filter(model_class.id == id).first()
            
            if not record:
                DB_OPERATIONS.labels(operation="delete", status="not_found", db_type=self.db_type).inc()
                DB_OPERATION_DURATION.labels(operation="delete", db_type=self.db_type).observe(time.time() - start_time)
                return False
                
            # Delete the record
            session.delete(record)
            session.commit()
            
            DB_OPERATIONS.labels(operation="delete", status="success", db_type=self.db_type).inc()
            DB_OPERATION_DURATION.labels(operation="delete", db_type=self.db_type).observe(time.time() - start_time)
            
            logger.debug("Deleted record", model=model_class.__name__, id=id)
            return True
            
        except Exception as e:
            session.rollback()
            DB_OPERATIONS.labels(operation="delete", status="error", db_type=self.db_type).inc()
            logger.error(
                "Failed to delete record",
                model=model_class.__name__,
                id=id,
                error=str(e),
                error_type=type(e).__name__
            )
            raise
        finally:
            session.close()
            # Decrement active connection count
            DB_CONNECTIONS_ACTIVE.labels(db_type=self.db_type).dec()
            
    @CONNECTION_CIRCUIT_BREAKER
    def delete_with_provider(self, provider_type: str, model_class: Type[T], id: Any) -> bool:
        """
        Delete a record using a specific provider.
        
        Args:
            provider_type: Provider type (e.g., "lancedb")
            model_class: Model class to query
            id: ID of the record to delete
            
        Returns:
            True if record was deleted, False if record not found
            
        Raises:
            ValueError: If provider not available
            Exception: Database errors during deletion
        """
        provider = self._get_provider(provider_type)
        
        start_time = time.time()
        try:
            # Track operations
            DB_OPERATIONS.labels(operation=f"delete_{provider_type}", status="processing", db_type=provider_type).inc()
            
            # Delete record using provider
            result = provider.delete(model_class, id)
            
            # Record metrics based on result
            if result:
                DB_OPERATIONS.labels(operation=f"delete_{provider_type}", status="success", db_type=provider_type).inc()
            else:
                DB_OPERATIONS.labels(operation=f"delete_{provider_type}", status="not_found", db_type=provider_type).inc()
                
            DB_OPERATION_DURATION.labels(operation=f"delete_{provider_type}", db_type=provider_type).observe(time.time() - start_time)
            
            return result
        except Exception as e:
            DB_OPERATIONS.labels(operation=f"delete_{provider_type}", status="error", db_type=provider_type).inc()
            logger.error(f"Failed to delete record with {provider_type}", model=model_class.__name__, id=id, error=str(e))
            raise
            
    @CONNECTION_CIRCUIT_BREAKER
    async def delete_async(self, model_class: Type[T], id: Any) -> bool:
        """
        Delete a record asynchronously with monitoring and circuit breaking.
        
        Args:
            model_class: Model class to query
            id: ID of the record to delete
            
        Returns:
            True if record was deleted, False if record not found
            
        Raises:
            NotImplementedError: If async operations not supported
            Exception: Database errors during deletion
        """
        if not self._supports_async():
            raise NotImplementedError(f"Async operations not supported for {self.db_type}")
            
        start_time = time.time()
        async_session = self.AsyncSession()
        
        try:
            # Track active connections
            DB_CONNECTIONS_ACTIVE.labels(db_type=self.db_type).inc()
            
            # Query for the record asynchronously
            from sqlalchemy import select
            query = select(model_class).filter(model_class.id == id)
            result = await async_session.execute(query)
            record = result.scalar_one_or_none()
            
            if not record:
                DB_OPERATIONS.labels(operation="delete_async", status="not_found", db_type=self.db_type).inc()
                DB_OPERATION_DURATION.labels(operation="delete_async", db_type=self.db_type).observe(time.time() - start_time)
                return False
                
            # Delete the record
            await async_session.delete(record)
            await async_session.commit()
            
            DB_OPERATIONS.labels(operation="delete_async", status="success", db_type=self.db_type).inc()
            DB_OPERATION_DURATION.labels(operation="delete_async", db_type=self.db_type).observe(time.time() - start_time)
            
            logger.debug("Deleted record asynchronously", model=model_class.__name__, id=id)
            return True
            
        except Exception as e:
            await async_session.rollback()
            DB_OPERATIONS.labels(operation="delete_async", status="error", db_type=self.db_type).inc()
            logger.error(
                "Failed to delete record asynchronously",
                model=model_class.__name__,
                id=id,
                error=str(e),
                error_type=type(e).__name__
            )
            raise
        finally:
            await async_session.close()
            # Decrement active connection count
            DB_CONNECTIONS_ACTIVE.labels(db_type=self.db_type).dec()
    
    @CONNECTION_CIRCUIT_BREAKER
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True
    )
    def query(self, model_class: Type[T], filter_criteria: Dict[str, Any], limit: Optional[int] = None, offset: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Query records with filters and pagination with monitoring, retry, and circuit breaking.
        
        Args:
            model_class: Model class to query
            filter_criteria: Dictionary of attribute-value pairs to filter on
            limit: Maximum number of records to return
            offset: Number of records to skip
            
        Returns:
            List of dictionaries containing attribute values
            
        Raises:
            Exception: Database errors during query
        """
        # For non-SQL databases, use provider
        if self.db_type in ["lancedb", "pinecone", "supabase"]:
            return self.query_with_provider(self.db_type, model_class, filter_criteria, limit, offset)
        
        # SQL database path
        start_time = time.time()
        session = self.Session()
        
        try:
            # Track active connections
            DB_CONNECTIONS_ACTIVE.labels(db_type=self.db_type).inc()
            
            # Start query
            query = session.query(model_class)
            
            # Apply filters
            for attr, value in filter_criteria.items():
                query = query.filter(getattr(model_class, attr) == value)
                
            # Apply pagination
            if offset is not None:
                query = query.offset(offset)
            if limit is not None:
                query = query.limit(limit)
                
            # Execute query
            records = query.all()
            
            # Convert to list of dictionaries
            results = []
            for record in records:
                # Convert to dictionary and remove SQLAlchemy state
                result = {k: v for k, v in record.__dict__.items() if not k.startswith('_')}
                results.append(result)
                
            DB_OPERATIONS.labels(operation="query", status="success", db_type=self.db_type).inc()
            DB_OPERATION_DURATION.labels(operation="query", db_type=self.db_type).observe(time.time() - start_time)
            
            logger.debug("Queried records", model=model_class.__name__, count=len(results))
            return results
            
        except Exception as e:
            DB_OPERATIONS.labels(operation="query", status="error", db_type=self.db_type).inc()
            logger.error(
                "Failed to query records",
                model=model_class.__name__,
                filters=str(filter_criteria),
                error=str(e),
                error_type=type(e).__name__
            )
            raise
        finally:
            session.close()
            # Decrement active connection count
            DB_CONNECTIONS_ACTIVE.labels(db_type=self.db_type).dec()
            
    @CONNECTION_CIRCUIT_BREAKER
    def query_with_provider(self, provider_type: str, model_class: Type[T], filter_criteria: Dict[str, Any], limit: Optional[int] = None, offset: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Query records using a specific provider.
        
        Args:
            provider_type: Provider type (e.g., "lancedb")
            model_class: Model class to query
            filter_criteria: Dictionary of attribute-value pairs to filter on
            limit: Maximum number of records to return
            offset: Number of records to skip
            
        Returns:
            List of dictionaries containing attribute values
            
        Raises:
            ValueError: If provider not available
            Exception: Database errors during query
        """
        provider = self._get_provider(provider_type)
        
        start_time = time.time()
        try:
            # Track operations
            DB_OPERATIONS.labels(operation=f"query_{provider_type}", status="processing", db_type=provider_type).inc()
            
            # Query records using provider
            results = provider.query(model_class, filter_criteria, limit=limit, offset=offset)
            
            DB_OPERATIONS.labels(operation=f"query_{provider_type}", status="success", db_type=provider_type).inc()
            DB_OPERATION_DURATION.labels(operation=f"query_{provider_type}", db_type=provider_type).observe(time.time() - start_time)
            
            return results
        except Exception as e:
            DB_OPERATIONS.labels(operation=f"query_{provider_type}", status="error", db_type=provider_type).inc()
            logger.error(f"Failed to query records with {provider_type}", model=model_class.__name__, filters=str(filter_criteria), error=str(e))
            raise
            
    @CONNECTION_CIRCUIT_BREAKER
    async def query_async(self, model_class: Type[T], filter_criteria: Dict[str, Any], limit: Optional[int] = None, offset: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Query records asynchronously with monitoring and circuit breaking.
        
        Args:
            model_class: Model class to query
            filter_criteria: Dictionary of attribute-value pairs to filter on
            limit: Maximum number of records to return
            offset: Number of records to skip
            
        Returns:
            List of dictionaries containing attribute values
            
        Raises:
            NotImplementedError: If async operations not supported
            Exception: Database errors during query
        """
        if not self._supports_async():
            raise NotImplementedError(f"Async operations not supported for {self.db_type}")
            
        start_time = time.time()
        async_session = self.AsyncSession()
        
        try:
            # Track active connections
            DB_CONNECTIONS_ACTIVE.labels(db_type=self.db_type).inc()
            
            # Build query asynchronously
            from sqlalchemy import select
            query = select(model_class)
            
            # Apply filters
            for attr, value in filter_criteria.items():
                query = query.filter(getattr(model_class, attr) == value)
                
            # Apply pagination
            if offset is not None:
                query = query.offset(offset)
            if limit is not None:
                query = query.limit(limit)
                
            # Execute query
            result = await async_session.execute(query)
            records = result.all()
            
            # Convert to list of dictionaries
            results = []
            for record_tuple in records:
                record = record_tuple[0] if isinstance(record_tuple, tuple) else record_tuple
                # Convert to dictionary and remove SQLAlchemy state
                result_dict = {k: v for k, v in record.__dict__.items() if not k.startswith('_')}
                results.append(result_dict)
                
            DB_OPERATIONS.labels(operation="query_async", status="success", db_type=self.db_type).inc()
            DB_OPERATION_DURATION.labels(operation="query_async", db_type=self.db_type).observe(time.time() - start_time)
            
            logger.debug("Queried records asynchronously", model=model_class.__name__, count=len(results))
            return results
            
        except Exception as e:
            DB_OPERATIONS.labels(operation="query_async", status="error", db_type=self.db_type).inc()
            logger.error(
                "Failed to query records asynchronously",
                model=model_class.__name__,
                filters=str(filter_criteria),
                error=str(e),
                error_type=type(e).__name__
            )
            raise
        finally:
            await async_session.close()
            # Decrement active connection count
            DB_CONNECTIONS_ACTIVE.labels(db_type=self.db_type).dec()