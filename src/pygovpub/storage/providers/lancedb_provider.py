"""
LanceDB vector database provider for PyGovPub.

This module implements a storage provider for LanceDB, a high-performance
embedded vector database. It provides vector search capabilities and
document storage with a simple, embedded deployment model.
"""

import os
import time
import json
import uuid
import threading
import queue
from typing import Any, Dict, List, Optional, Tuple, Type, TypeVar, Union, Callable

import structlog
import lancedb
import pyarrow as pa
import numpy as np
from prometheus_client import Counter, Histogram, Gauge

from pygovpub.storage.query_plan import (
    get_query_plan_analyzer,
    get_query_optimizer,
    measure_execution_time
)

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
LANCEDB_SCHEMA_VERSION = Gauge(
    "lancedb_schema_version",
    "LanceDB schema version for a table",
    ["table", "version"]
)
LANCEDB_POOL_CONNECTIONS = Gauge(
    "lancedb_pool_connections",
    "Total LanceDB connections in pool",
    ["pool_id", "status"]
)
LANCEDB_POOL_OPERATIONS = Counter(
    "lancedb_pool_operations",
    "Total LanceDB pool operations",
    ["operation", "status", "pool_id"]
)
LANCEDB_POOL_WAIT_TIME = Histogram(
    "lancedb_pool_wait_time_seconds",
    "LanceDB pool connection wait time in seconds",
    ["pool_id"]
)

T = TypeVar("T")


class LanceDBConnectionPool:
    """
    Connection pool for LanceDB to enable efficient connection reuse.
    
    This class manages a pool of LanceDB connections that can be shared across
    different parts of the application. It provides connection pooling with:
    - Connection health check and auto-recreation
    - Connection lifecycle management
    - Metrics tracking
    - Configurable pool size and timeout
    """
    
    def __init__(self, 
                uri: str, 
                pool_id: str = "default",
                max_size: int = 5,
                min_size: int = 1,
                connection_timeout: float = 30.0,
                idle_timeout: float = 300.0,  # 5 minutes
                **connection_args):
        """
        Initialize a new LanceDB connection pool.
        
        Args:
            uri: Path to LanceDB database
            pool_id: Unique identifier for this pool
            max_size: Maximum number of connections in pool
            min_size: Minimum number of connections to maintain
            connection_timeout: Timeout in seconds when waiting for a connection
            idle_timeout: Timeout in seconds for idle connections before cleanup
            **connection_args: Additional arguments to pass to LanceDB connect
        """
        self.uri = uri
        self.pool_id = pool_id
        self.max_size = max_size
        self.min_size = min_size
        self.connection_timeout = connection_timeout
        self.idle_timeout = idle_timeout
        self.connection_args = connection_args
        
        # Connection pool and metadata
        self._available_connections = queue.Queue()
        self._in_use_connections = {}  # conn_id -> (conn, last_used_timestamp)
        self._connection_ids = {}  # conn object -> conn_id
        self._last_connection_id = 0
        
        # Lock for thread safety
        self._lock = threading.RLock()
        
        # Create initial connections
        with self._lock:  # Make sure we create all connections atomically
            for _ in range(min_size):
                self._add_connection_to_pool()
            
            # Update metrics
            LANCEDB_POOL_CONNECTIONS.labels(
                pool_id=self.pool_id,
                status="available"
            ).set(self._available_connections.qsize())
            
            LANCEDB_POOL_CONNECTIONS.labels(
                pool_id=self.pool_id,
                status="in_use"
            ).set(0)
        
        logger.info(f"LanceDB connection pool initialized with {min_size} connections", 
                   pool_id=pool_id, 
                   uri=uri)
    
    def _generate_connection_id(self) -> str:
        """
        Generate a unique connection ID.
        
        Returns:
            Unique connection ID
        """
        with self._lock:
            self._last_connection_id += 1
            return f"{self.pool_id}_{self._last_connection_id}"
    
    def _add_connection_to_pool(self) -> None:
        """
        Create a new connection and add it to the pool.
        """
        try:
            # Create a new connection
            connection = lancedb.connect(self.uri, **self.connection_args)
            conn_id = self._generate_connection_id()
            self._connection_ids[connection] = conn_id
            
            # Add to available queue
            self._available_connections.put((connection, time.time()))
            
            # Update metrics
            LANCEDB_POOL_CONNECTIONS.labels(
                pool_id=self.pool_id,
                status="available"
            ).set(self._available_connections.qsize())
            
            LANCEDB_POOL_OPERATIONS.labels(
                operation="create_connection",
                status="success",
                pool_id=self.pool_id
            ).inc()
            
            logger.debug(f"Added new connection to pool", pool_id=self.pool_id, conn_id=conn_id)
        except Exception as e:
            # Update metrics
            LANCEDB_POOL_OPERATIONS.labels(
                operation="create_connection",
                status="error",
                pool_id=self.pool_id
            ).inc()
            
            logger.error(f"Failed to create LanceDB connection", pool_id=self.pool_id, error=str(e))
            raise
    
    def _is_connection_valid(self, connection) -> bool:
        """
        Check if a connection is still valid.
        
        Args:
            connection: LanceDB connection to check
            
        Returns:
            True if connection is valid, False otherwise
        """
        try:
            # Simple validity check - see if we can get table names
            connection.table_names()
            return True
        except Exception:
            return False
    
    def get_connection(self) -> Tuple[Any, str]:
        """
        Get a connection from the pool.
        
        Returns:
            Tuple of (connection, connection_id)
            
        Raises:
            TimeoutError: If no connection available within timeout
        """
        start_time = time.time()
        
        try:
            # Try to get an existing connection from the pool
            while True:
                # Check if we've timed out
                if time.time() - start_time > self.connection_timeout:
                    LANCEDB_POOL_OPERATIONS.labels(
                        operation="get_connection",
                        status="timeout",
                        pool_id=self.pool_id
                    ).inc()
                    
                    raise TimeoutError(f"Timed out waiting for LanceDB connection after {self.connection_timeout}s")
                
                try:
                    # Try to get a connection with a timeout
                    connection, created_time = self._available_connections.get(
                        block=True, 
                        timeout=min(1.0, self.connection_timeout)
                    )
                    
                    # Check if the connection is still valid
                    if self._is_connection_valid(connection):
                        # Connection is valid, mark as in use
                        with self._lock:
                            conn_id = self._connection_ids.get(connection)
                            if conn_id is None:
                                # This shouldn't happen, but handle it gracefully
                                conn_id = self._generate_connection_id()
                                self._connection_ids[connection] = conn_id
                                
                            self._in_use_connections[conn_id] = (connection, time.time())
                        
                        # Update metrics
                        LANCEDB_POOL_CONNECTIONS.labels(
                            pool_id=self.pool_id,
                            status="available"
                        ).set(self._available_connections.qsize())
                        
                        LANCEDB_POOL_CONNECTIONS.labels(
                            pool_id=self.pool_id,
                            status="in_use"
                        ).set(len(self._in_use_connections))
                        
                        LANCEDB_POOL_WAIT_TIME.labels(
                            pool_id=self.pool_id
                        ).observe(time.time() - start_time)
                        
                        LANCEDB_POOL_OPERATIONS.labels(
                            operation="get_connection",
                            status="success",
                            pool_id=self.pool_id
                        ).inc()
                        
                        logger.debug(f"Got connection from pool", 
                                    pool_id=self.pool_id, 
                                    conn_id=conn_id,
                                    wait_time=time.time() - start_time)
                        
                        return connection, conn_id
                    else:
                        # Connection is invalid, create a new one
                        logger.warning(f"Discarding invalid connection", 
                                     pool_id=self.pool_id, 
                                     conn_id=self._connection_ids.get(connection, "unknown"))
                        
                        LANCEDB_POOL_OPERATIONS.labels(
                            operation="discard_connection",
                            status="invalid",
                            pool_id=self.pool_id
                        ).inc()
                        
                        # Clean up connection id mapping
                        with self._lock:
                            if connection in self._connection_ids:
                                del self._connection_ids[connection]
                        
                        # Create a new connection if needed
                        if self._available_connections.qsize() + len(self._in_use_connections) < self.min_size:
                            self._add_connection_to_pool()
                except queue.Empty:
                    # No connection available, check if we can create a new one
                    with self._lock:
                        current_total = self._available_connections.qsize() + len(self._in_use_connections)
                        if current_total < self.max_size:
                            # Create a new connection
                            self._add_connection_to_pool()
                            logger.debug(f"Created new connection due to pool exhaustion", 
                                        pool_id=self.pool_id,
                                        current_size=current_total)
                        else:
                            # Pool is at max size, just wait for a connection
                            logger.debug(f"Pool at max size, waiting for connection", 
                                        pool_id=self.pool_id,
                                        max_size=self.max_size)
                            
        except Exception as e:
            if not isinstance(e, TimeoutError):
                LANCEDB_POOL_OPERATIONS.labels(
                    operation="get_connection",
                    status="error",
                    pool_id=self.pool_id
                ).inc()
                
                logger.error(f"Error getting connection from pool", 
                           pool_id=self.pool_id,
                           error=str(e))
            raise
    
    def release_connection(self, connection, conn_id: str) -> None:
        """
        Release a connection back to the pool.
        
        Args:
            connection: LanceDB connection to release
            conn_id: Connection ID
        """
        try:
            with self._lock:
                # Check if this connection is actually in use
                if conn_id in self._in_use_connections:
                    # Remove from in-use tracking
                    del self._in_use_connections[conn_id]
                    
                    # Check if connection is still valid
                    if self._is_connection_valid(connection):
                        # Return to available pool
                        self._available_connections.put((connection, time.time()))
                        
                        LANCEDB_POOL_OPERATIONS.labels(
                            operation="release_connection",
                            status="success",
                            pool_id=self.pool_id
                        ).inc()
                    else:
                        # Connection is invalid, discard it
                        logger.warning(f"Discarding invalid connection on release", 
                                     pool_id=self.pool_id,
                                     conn_id=conn_id)
                        
                        LANCEDB_POOL_OPERATIONS.labels(
                            operation="release_connection",
                            status="invalid",
                            pool_id=self.pool_id
                        ).inc()
                        
                        # Clean up connection id mapping
                        if connection in self._connection_ids:
                            del self._connection_ids[connection]
                        
                        # Create a new connection if needed
                        if self._available_connections.qsize() + len(self._in_use_connections) < self.min_size:
                            self._add_connection_to_pool()
                else:
                    # This connection wasn't tracked as in-use
                    logger.warning(f"Attempt to release untracked connection", 
                                 pool_id=self.pool_id,
                                 conn_id=conn_id)
                    
                    LANCEDB_POOL_OPERATIONS.labels(
                        operation="release_connection",
                        status="untracked",
                        pool_id=self.pool_id
                    ).inc()
            
            # Update metrics
            LANCEDB_POOL_CONNECTIONS.labels(
                pool_id=self.pool_id,
                status="available"
            ).set(self._available_connections.qsize())
            
            LANCEDB_POOL_CONNECTIONS.labels(
                pool_id=self.pool_id,
                status="in_use"
            ).set(len(self._in_use_connections))
            
        except Exception as e:
            LANCEDB_POOL_OPERATIONS.labels(
                operation="release_connection",
                status="error",
                pool_id=self.pool_id
            ).inc()
            
            logger.error(f"Error releasing connection to pool", 
                       pool_id=self.pool_id,
                       conn_id=conn_id,
                       error=str(e))
    
    def cleanup_idle_connections(self) -> int:
        """
        Clean up idle connections that have exceeded the idle timeout.
        
        Returns:
            Number of connections cleaned up
        """
        now = time.time()
        cleaned_up = 0
        
        try:
            # Check available connections
            remaining_connections = []
            while not self._available_connections.empty():
                try:
                    connection, created_time = self._available_connections.get_nowait()
                    
                    # Check if this connection has been idle too long
                    if now - created_time > self.idle_timeout:
                        # Connection is too idle, close it
                        with self._lock:
                            conn_id = self._connection_ids.get(connection)
                            if conn_id:
                                logger.debug(f"Closing idle connection", 
                                           pool_id=self.pool_id,
                                           conn_id=conn_id,
                                           idle_time=now - created_time)
                                
                                if connection in self._connection_ids:
                                    del self._connection_ids[connection]
                                
                                cleaned_up += 1
                    else:
                        # Connection is still fresh, keep it
                        remaining_connections.append((connection, created_time))
                except queue.Empty:
                    break
            
            # Put back the connections we want to keep
            for conn_tuple in remaining_connections:
                self._available_connections.put(conn_tuple)
            
            # Create new connections if we're below min_size
            current_size = self._available_connections.qsize() + len(self._in_use_connections)
            for _ in range(max(0, self.min_size - current_size)):
                self._add_connection_to_pool()
            
            # Update metrics
            LANCEDB_POOL_CONNECTIONS.labels(
                pool_id=self.pool_id,
                status="available"
            ).set(self._available_connections.qsize())
            
            if cleaned_up > 0:
                LANCEDB_POOL_OPERATIONS.labels(
                    operation="cleanup_idle",
                    status="success",
                    pool_id=self.pool_id
                ).inc(cleaned_up)
                
                logger.debug(f"Cleaned up {cleaned_up} idle connections", 
                           pool_id=self.pool_id,
                           remaining=current_size)
            
            return cleaned_up
        except Exception as e:
            LANCEDB_POOL_OPERATIONS.labels(
                operation="cleanup_idle",
                status="error",
                pool_id=self.pool_id
            ).inc()
            
            logger.error(f"Error cleaning up idle connections", 
                       pool_id=self.pool_id,
                       error=str(e))
            return 0
    
    def close_all(self) -> None:
        """
        Close all connections in the pool.
        """
        logger.info(f"Closing all connections in pool", pool_id=self.pool_id)
        
        with self._lock:
            # Empty the available queue
            while not self._available_connections.empty():
                try:
                    connection, _ = self._available_connections.get_nowait()
                    # No need to explicitly close LanceDB connections
                except queue.Empty:
                    break
            
            # Clear in-use connections (can't really close them while in use)
            self._in_use_connections.clear()
            self._connection_ids.clear()
            
            # Update metrics
            LANCEDB_POOL_CONNECTIONS.labels(
                pool_id=self.pool_id,
                status="available"
            ).set(0)
            
            LANCEDB_POOL_CONNECTIONS.labels(
                pool_id=self.pool_id,
                status="in_use"
            ).set(0)
            
            LANCEDB_POOL_OPERATIONS.labels(
                operation="close_all",
                status="success",
                pool_id=self.pool_id
            ).inc()
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the connection pool.
        
        Returns:
            Dictionary with pool statistics
        """
        with self._lock:
            stats = {
                "pool_id": self.pool_id,
                "max_size": self.max_size,
                "min_size": self.min_size,
                "available_connections": self._available_connections.qsize(),
                "in_use_connections": len(self._in_use_connections),
                "total_connections": self._available_connections.qsize() + len(self._in_use_connections),
                "connection_timeout": self.connection_timeout,
                "idle_timeout": self.idle_timeout
            }
            
            return stats


# Global registry of connection pools
_connection_pools: Dict[str, LanceDBConnectionPool] = {}
_connection_pools_lock = threading.RLock()

def get_connection_pool(uri: str, pool_id: str = "default", **kwargs) -> LanceDBConnectionPool:
    """
    Get or create a connection pool for the given URI.
    
    Args:
        uri: LanceDB URI
        pool_id: Pool identifier (useful for having multiple pools for same URI)
        **kwargs: Additional connection pool parameters
        
    Returns:
        LanceDB connection pool
    """
    pool_key = f"{uri}_{pool_id}"
    
    with _connection_pools_lock:
        if pool_key not in _connection_pools:
            # Create a new pool
            _connection_pools[pool_key] = LanceDBConnectionPool(uri, pool_id, **kwargs)
        
        return _connection_pools[pool_key]

class LanceDBProvider:
    """LanceDB storage provider implementation"""
    
    # Provider type for interface identification
    db_type = "lancedb"

    def __init__(self,
                uri: str = None,
                create_vector_index: bool = True,
                vector_dim: int = 384,
                schema_registry=None,
                use_connection_pool: bool = True,
                pool_id: str = "default",
                pool_max_size: int = 10, 
                pool_min_size: int = 2,
                **config):
        """
        Initialize LanceDB provider.
        
        Args:
            uri: Path to LanceDB database (directory)
            create_vector_index: Whether to create vector index on table creation
            vector_dim: Dimension of vector embeddings (default: 384 for all-MiniLM-L6-v2)
            schema_registry: Optional schema registry instance for schema management
            use_connection_pool: Whether to use connection pooling
            pool_id: Connection pool identifier (only used if use_connection_pool=True)
            pool_max_size: Maximum number of connections in the pool
            pool_min_size: Minimum number of connections to maintain in the pool
            **config: Additional configuration options
        """
        self.vector_dim = vector_dim
        self.create_vector_index = create_vector_index
        self.schema_registry = schema_registry
        self.schema_adapter = None
        self.use_connection_pool = use_connection_pool
        self.pool_id = pool_id
        self.current_connection = None
        self.current_connection_id = None

        # Use temporary directory if no URI provided
        if not uri:
            db_dir = config.get("db_dir", os.path.expanduser("~/.pygovpub/lancedb"))
            os.makedirs(db_dir, exist_ok=True)
            timestamp = int(time.time())
            db_id = str(uuid.uuid4())[:8]
            uri = f"{db_dir}/pygovpub_db_{timestamp}_{db_id}"
            logger.info(f"Creating LanceDB at {uri}")

        self.uri = uri
        self.config = config
        self.table_info = {}  # Cache table metadata
        
        # Initialize connection - either direct or via pool
        if self.use_connection_pool:
            # Get or create a connection pool
            self.connection_pool = get_connection_pool(
                uri=uri,
                pool_id=pool_id,
                max_size=pool_max_size,
                min_size=pool_min_size,
                **{k: v for k, v in config.items() if k in ['connection_timeout', 'idle_timeout']}
            )
            # Get an initial connection for compatibility with old code
            self.db, self.current_connection_id = self.connection_pool.get_connection()
            
            # Make sure we have additional connections to meet min_size
            current_available = self.connection_pool._available_connections.qsize()
            if current_available + 1 < pool_min_size:  # +1 because we have one connection in use
                for _ in range(pool_min_size - current_available - 1):
                    self.connection_pool._add_connection_to_pool()
                    
            logger.info("LanceDB provider initialized with connection pool", 
                      uri=uri, 
                      pool_id=pool_id, 
                      max_size=pool_max_size, 
                      min_size=pool_min_size)
        else:
            # Create a direct connection (old behavior)
            self.db = lancedb.connect(uri)
            self.connection_pool = None
            logger.info("LanceDB provider initialized with direct connection", uri=uri)

        # Initialize schema adapter if registry provided
        if self.schema_registry:
            try:
                from pygovpub.storage.providers.lancedb_schema import LanceDBSchemaAdapter
                self.schema_adapter = LanceDBSchemaAdapter(self, self.schema_registry)
                logger.info("LanceDB schema adapter initialized")
            except ImportError as e:
                logger.warning(f"Could not initialize LanceDB schema adapter: {str(e)}")
    
    def _get_connection(self):
        """
        Get a LanceDB connection - either from the pool or the direct connection.
        
        Returns:
            Tuple of (connection, connection_id)
        """
        if self.use_connection_pool:
            return self.connection_pool.get_connection()
        else:
            return self.db, None
    
    def _release_connection(self, connection, connection_id):
        """
        Release a connection back to the pool if using connection pooling.
        
        Args:
            connection: LanceDB connection
            connection_id: Connection ID
        """
        if self.use_connection_pool and connection_id:
            # Don't release the initial connection, as it's kept for compatibility
            if connection_id != self.current_connection_id:
                self.connection_pool.release_connection(connection, connection_id)
    
    def _with_connection(self, func):
        """
        Execute a function with a connection, properly managing the connection lifecycle.
        
        Args:
            func: Function that takes a connection as its argument
            
        Returns:
            Result of the function
        """
        connection, connection_id = self._get_connection()
        try:
            return func(connection)
        finally:
            self._release_connection(connection, connection_id)

    def _model_to_dict(self, model_obj: Any) -> Dict[str, Any]:
        """
        Convert model object to dictionary for LanceDB storage.
        
        Args:
            model_obj: Model object (Pydantic, SQLAlchemy, or dict)
            
        Returns:
            Dictionary representation of the model
        """
        if hasattr(model_obj, "model_dump"):
            # Use Pydantic's model_dump() for Pydantic v2 compatibility
            return model_obj.model_dump()
        elif hasattr(model_obj, "__dict__"):
            # Handle SQLAlchemy models or other objects
            return {
                key: value for key, value in model_obj.__dict__.items()
                if not key.startswith("_")
            }
        else:
            # Already a dict or something else
            return model_obj

    def _get_or_create_table(self, table_name: str, schema: Optional[pa.Schema] = None, schema_version: Optional[str] = None):
        """
        Get or create a LanceDB table with appropriate schema.
        
        Args:
            table_name: Table name
            schema: Optional Arrow schema for new table
            schema_version: Optional schema version to apply from registry
            
        Returns:
            LanceDB table
        """
        start_time = time.time()

        # Define the function to run with a connection
        def get_or_create_table_with_connection(connection):
            try:
                # Check if table exists
                if table_name in connection.table_names():
                    table = connection.open_table(table_name)
                    logger.debug(f"Opened existing table {table_name}")
                    
                    # Apply schema version if provided and adapter available
                    if schema_version and self.schema_adapter:
                        self.schema_adapter.apply_schema_version(table_name, schema_version)
                        # Update metrics
                        LANCEDB_SCHEMA_VERSION.labels(
                            table=table_name,
                            version=schema_version
                        ).set(1)
                else:
                    # If schema version is provided and adapter available, use that schema
                    local_schema = schema
                    if schema_version and self.schema_adapter:
                        # Get schema from registry
                        registry_schema = self.schema_registry.get_schema_version(schema_version)
                        if registry_schema:
                            local_schema = self.schema_adapter._convert_schema_version_to_arrow(registry_schema)
                            logger.info(f"Using schema version {schema_version} for table {table_name}")
                            # Update metrics
                            LANCEDB_SCHEMA_VERSION.labels(
                                table=table_name,
                                version=schema_version
                            ).set(1)
                    
                    # Use default schema if none provided
                    if local_schema is None:
                        # Create a minimal initial schema if none provided
                        local_schema = pa.schema([
                            ("id", pa.string()),
                            ("embedding", pa.list_(pa.float32(), self.vector_dim)),
                            ("metadata", pa.string()),  # JSON-serialized metadata
                            ("content", pa.string()),   # Document content
                            ("title", pa.string()),     # Document title
                            ("created_at", pa.timestamp("us")),
                            ("updated_at", pa.timestamp("us")),
                        ])

                    # Create empty table with schema
                    empty_data = pa.Table.from_pydict(
                        {field.name: [] for field in local_schema}, schema=local_schema
                    )

                    # Create table
                    mode = "overwrite" if self.config.get("overwrite_tables", False) else "create"
                    table = connection.create_table(
                        table_name,
                        data=empty_data,
                        mode=mode
                    )

                    # Create vector index if specified
                    if self.create_vector_index:
                        try:
                            # Simple index creation without extra parameters
                            # This will use default settings which should work across LanceDB versions
                            table.create_index("embedding", replace=True)
                        except Exception as e:
                            logger.warning(f"Could not create vector index: {str(e)}")
                            # We'll continue without an index

                    logger.info(f"Created new table {table_name} with vector index")

                # Cache table info
                self.table_info[table_name] = {
                    "has_vector_index": self._check_table_has_vector_index(table),
                    "schema": table.schema,
                    "version": schema_version
                }

                return table

            except Exception as e:
                LANCEDB_OPERATIONS.labels(
                    operation="get_or_create_table",
                    status="error",
                    table=table_name
                ).inc()

                logger.error(f"Error getting/creating table {table_name}", error=str(e))
                raise

        try:
            # Execute with connection pooling
            table = self._with_connection(get_or_create_table_with_connection)
            
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

            logger.error(f"Error in _get_or_create_table for {table_name}", error=str(e))
            raise

    def _check_table_has_vector_index(self, table) -> bool:
        """
        Check if table has a vector index.
        
        Args:
            table: LanceDB table
            
        Returns:
            True if table has vector index, False otherwise
        """
        try:
            # Check for index metadata
            indices = table.describe_indices()
            return len(indices) > 0 and any("embedding" in idx.get("column_names", []) for idx in indices)
        except Exception as e:
            logger.warning(f"Could not check vector index: {str(e)}")
            return False

    def _convert_model_to_arrow(self, model_class: Type[T], data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert model data to arrow-compatible format for LanceDB.
        
        Args:
            model_class: Model class
            data: Model data
            
        Returns:
            Arrow-compatible dictionary
        """
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
        """
        Create a new record in LanceDB.
        
        Args:
            model_class: Model class
            data: Model data
            
        Returns:
            ID of created record
        """
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
        """
        Retrieve a record by ID.
        
        Args:
            model_class: Model class
            id: Record ID
            
        Returns:
            Record data or None if not found
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
                    filter_criteria: Optional[Dict[str, Any]] = None,
                    analyze_query: bool = True) -> List[Dict[str, Any]]:
        """
        Perform vector similarity search.
        
        Args:
            model_class: Model class
            query_vector: Query vector
            limit: Maximum number of results
            filter_criteria: Optional filtering criteria
            analyze_query: Whether to analyze and optimize the query
            
        Returns:
            List of matching records
        """
        start_time = time.time()

        # Get table name from model class
        if hasattr(model_class, "__tablename__"):
            table_name = model_class.__tablename__
        else:
            table_name = model_class.__name__.lower()

        try:
            # Generate query plan if requested
            plan = None
            if analyze_query:
                # Get analyzer and optimizer
                analyzer = get_query_plan_analyzer()
                optimizer = get_query_optimizer()
                
                # Create and optimize plan
                plan = analyzer.analyze_vector_search(
                    provider=self,
                    model_class=model_class,
                    query_vector=query_vector,
                    filter_criteria=filter_criteria,
                    limit=limit
                )
                plan = optimizer.optimize(plan)
                
                # Log plan information
                logger.debug(
                    "Vector search query plan",
                    table=table_name,
                    estimated_cost=plan.estimated_cost,
                    estimated_time_ms=plan.estimated_time_ms,
                    optimizations=len(plan.optimizations)
                )
                
                # Apply optimizations
                for opt in plan.optimizations:
                    logger.debug(f"Suggested optimization: {opt['description']}")

            # Get table
            table = self._get_or_create_table(table_name)

            # Define the search execution function
            def execute_search():
                # Start query
                search = table.search(query_vector, vector_column_name="embedding")

                # Apply filters if provided
                if filter_criteria:
                    # Handle special text filter
                    text_filter = None
                    filter_criteria_copy = filter_criteria.copy()
                    if "__text_filter" in filter_criteria_copy:
                        text_value = filter_criteria_copy.pop("__text_filter")
                        text_filter = f"(content LIKE '%{text_value}%' OR title LIKE '%{text_value}%')"
                    
                    # Process regular filters
                    if filter_criteria_copy:
                        regular_filters = " AND ".join([
                            f"{key} = '{value}'" if isinstance(value, str) else f"{key} = {value}"
                            for key, value in filter_criteria_copy.items()
                        ])
                        
                        if text_filter:
                            filter_expr = f"({regular_filters}) AND {text_filter}"
                        else:
                            filter_expr = regular_filters
                            
                        search = search.where(filter_expr)
                    elif text_filter:
                        # Only text filter
                        search = search.where(text_filter)

                # Execute search
                result = search.limit(limit).to_pandas()

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
                    
                    # Normalize distance score (higher is better, 1.0 is perfect match)
                    if "_distance" in record:
                        # LanceDB distances are L2 norm distances (lower is better)
                        # Convert to a similarity score (1.0 - normalized distance)
                        distance = float(record["_distance"])
                        max_theoretical_distance = self.vector_dim * 2  # Maximum possible L2 distance
                        normalized_distance = min(1.0, distance / max_theoretical_distance)
                        record["score"] = 1.0 - normalized_distance
                        del record["_distance"]  # Remove original distance

                    records.append(record)
                
                return records

            # Execute search with timing measurement if we have a plan
            if plan:
                records = measure_execution_time(plan, execute_search)
            else:
                records = execute_search()

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
                    filter_criteria: Optional[Dict[str, Any]] = None,
                    analyze_query: bool = True) -> List[Dict[str, Any]]:
        """
        Perform hybrid search (full-text + vector) if text is provided.
        Will automatically generate embeddings if only text is provided.
        
        Args:
            model_class: Model class
            query_text: Text query
            query_vector: Optional vector query (for hybrid search)
            limit: Maximum number of results
            filter_criteria: Optional filtering criteria
            analyze_query: Whether to analyze and optimize the query
            
        Returns:
            List of matching records
        """
        start_time = time.time()

        # Get table name from model class
        if hasattr(model_class, "__tablename__"):
            table_name = model_class.__tablename__
        else:
            table_name = model_class.__name__.lower()

        try:
            # Generate query plan if requested
            plan = None
            if analyze_query:
                # Get analyzer and optimizer
                analyzer = get_query_plan_analyzer()
                optimizer = get_query_optimizer()
                
                # Create and optimize plan
                plan = analyzer.analyze_hybrid_search(
                    provider=self,
                    model_class=model_class,
                    query_text=query_text,
                    query_vector=query_vector,
                    filter_criteria=filter_criteria,
                    limit=limit
                )
                plan = optimizer.optimize(plan)
                
                # Log plan information
                logger.debug(
                    "Hybrid search query plan",
                    table=table_name,
                    text_length=plan.text_query_length,
                    estimated_cost=plan.estimated_cost,
                    estimated_time_ms=plan.estimated_time_ms,
                    optimizations=len(plan.optimizations)
                )
                
                # Apply optimizations
                for opt in plan.optimizations:
                    logger.debug(f"Suggested optimization: {opt['description']}")

            # Get table
            table = self._get_or_create_table(table_name)

            # Define the search execution function
            def execute_search():
                # Start hybrid query
                try:
                    if query_vector is not None:
                        # Try hybrid search with vector and text components
                        search = table.search(query_vector, query_text=query_text)
                    else:
                        # Try full-text search only
                        search = table.search(query_text=query_text)
                except TypeError:
                    # Fallback for older LanceDB versions
                    logger.warning(f"Using fallback text search for LanceDB, query_text not supported")
                    search = table.search(query_vector or np.zeros(self.vector_dim).tolist())
                    # Apply text filter manually
                    if query_text:
                        content_filter = f"content LIKE '%{query_text}%' OR title LIKE '%{query_text}%'"
                        search = search.where(content_filter)

                # Apply filters if provided
                if filter_criteria:
                    # Handle special text filter
                    text_filter = None
                    filter_criteria_copy = filter_criteria.copy()
                    if "__text_filter" in filter_criteria_copy:
                        text_value = filter_criteria_copy.pop("__text_filter")
                        text_filter = f"(content LIKE '%{text_value}%' OR title LIKE '%{text_value}%')"
                    
                    # Process regular filters
                    if filter_criteria_copy:
                        regular_filters = " AND ".join([
                            f"{key} = '{value}'" if isinstance(value, str) else f"{key} = {value}"
                            for key, value in filter_criteria_copy.items()
                        ])
                        
                        if text_filter:
                            filter_expr = f"({regular_filters}) AND {text_filter}"
                        else:
                            filter_expr = regular_filters
                            
                        search = search.where(filter_expr)
                    elif text_filter:
                        # Only text filter
                        search = search.where(text_filter)

                # Execute search
                result = search.limit(limit).to_pandas()

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
                    
                    # Normalize distance and text relevance scores
                    # For hybrid search, LanceDB may return both _distance and _relevance scores
                    distance_score = 0.0
                    text_score = 0.0
                    
                    if "_distance" in record:
                        # Convert distance to similarity score
                        distance = float(record["_distance"])
                        max_theoretical_distance = self.vector_dim * 2
                        normalized_distance = min(1.0, distance / max_theoretical_distance)
                        distance_score = 1.0 - normalized_distance
                        del record["_distance"]
                    
                    if "_relevance" in record:
                        # LanceDB text relevance is already normalized (higher is better)
                        text_score = float(record["_relevance"])
                        del record["_relevance"]
                    
                    # Combined score - if both scores are present, average them
                    # Otherwise use whichever is available
                    if distance_score > 0 and text_score > 0:
                        record["score"] = (distance_score + text_score) / 2
                    elif distance_score > 0:
                        record["score"] = distance_score
                    elif text_score > 0:
                        record["score"] = text_score

                    records.append(record)
                
                return records

            # Execute search with timing measurement if we have a plan
            if plan:
                records = measure_execution_time(plan, execute_search)
            else:
                records = execute_search()

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
            
    def text_search(self,
                   model_class: Type[T],
                   query_text: str,
                   limit: int = 10,
                   filter_criteria: Optional[Dict[str, Any]] = None,
                   analyze_query: bool = True) -> List[Dict[str, Any]]:
        """
        Perform text-only search. This is used as a fallback when vector search is not available
        or fails.
        
        Args:
            model_class: Model class
            query_text: Text query
            limit: Maximum number of results
            filter_criteria: Optional filtering criteria
            analyze_query: Whether to analyze and optimize the query
            
        Returns:
            List of matching records
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

            # Define the search execution function
            def execute_search():
                # Start text query
                try:
                    # Try to use query_text parameter
                    search = table.search(query_text=query_text)
                except TypeError:
                    # Fallback for older LanceDB versions
                    logger.warning(f"Using fallback text search for LanceDB, query_text not supported")
                    # Create a dummy vector search and filter by text
                    search = table.search(np.zeros(self.vector_dim).tolist())
                    content_filter = f"content LIKE '%{query_text}%' OR title LIKE '%{query_text}%'"
                    search = search.where(content_filter)

                # Apply filters if provided
                if filter_criteria:
                    # Handle special text filter
                    text_filter = None
                    filter_criteria_copy = filter_criteria.copy()
                    if "__text_filter" in filter_criteria_copy:
                        text_value = filter_criteria_copy.pop("__text_filter")
                        text_filter = f"(content LIKE '%{text_value}%' OR title LIKE '%{text_value}%')"
                    
                    # Process regular filters
                    if filter_criteria_copy:
                        regular_filters = " AND ".join([
                            f"{key} = '{value}'" if isinstance(value, str) else f"{key} = {value}"
                            for key, value in filter_criteria_copy.items()
                        ])
                        
                        if text_filter:
                            filter_expr = f"({regular_filters}) AND {text_filter}"
                        else:
                            filter_expr = regular_filters
                            
                        search = search.where(filter_expr)
                    elif text_filter:
                        # Only text filter
                        search = search.where(text_filter)

                # Execute search
                result = search.limit(limit).to_pandas()

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
                    
                    # Process text relevance score
                    if "_relevance" in record:
                        # LanceDB text relevance is already normalized (higher is better)
                        record["score"] = float(record["_relevance"])
                        del record["_relevance"]
                    else:
                        # Default score if not provided
                        record["score"] = 0.5

                    records.append(record)
                
                return records

            # Execute search
            records = execute_search()

            LANCEDB_OPERATIONS.labels(
                operation="text_search",
                status="success",
                table=table_name
            ).inc()

            LANCEDB_OPERATION_DURATION.labels(
                operation="text_search",
                table=table_name
            ).observe(time.time() - start_time)

            return records

        except Exception as e:
            LANCEDB_OPERATIONS.labels(
                operation="text_search",
                status="error",
                table=table_name
            ).inc()

            logger.error(f"Error performing text search in {table_name}", error=str(e))
            raise
            
    def apply_schema_version(self, table_name: str, version: str) -> bool:
        """
        Apply a schema version from the registry to a table.
        
        Args:
            table_name: Name of the table
            version: Schema version to apply
            
        Returns:
            True if successful, False otherwise
        """
        if not self.schema_adapter:
            logger.error("Schema adapter not initialized, cannot apply schema version")
            return False
        
        try:
            start_time = time.time()
            
            # Apply schema version
            result = self.schema_adapter.apply_schema_version(table_name, version)
            
            if result:
                # Update metrics
                LANCEDB_SCHEMA_VERSION.labels(
                    table=table_name,
                    version=version
                ).set(1)
                
                # Update table info cache
                if table_name in self.table_info:
                    self.table_info[table_name]["version"] = version
                
                logger.info(f"Applied schema version {version} to table {table_name}")
            
            LANCEDB_OPERATION_DURATION.labels(
                operation="apply_schema_version",
                table=table_name
            ).observe(time.time() - start_time)
            
            LANCEDB_OPERATIONS.labels(
                operation="apply_schema_version",
                status="success" if result else "failure",
                table=table_name
            ).inc()
            
            return result
            
        except Exception as e:
            LANCEDB_OPERATIONS.labels(
                operation="apply_schema_version",
                status="error",
                table=table_name
            ).inc()
            
            logger.error(f"Error applying schema version {version} to table {table_name}", error=str(e))
            return False
            
    def apply_score_threshold(self, results: List[Dict[str, Any]], threshold: float) -> List[Dict[str, Any]]:
        """
        Filter search results by score threshold.
        
        Args:
            results: List of search results
            threshold: Minimum score threshold to keep
            
        Returns:
            Filtered list of search results
        """
        return [r for r in results if r.get("score", 0) >= threshold]
        
    def verify_ann_consistency(self, 
                             results1: List[Dict[str, Any]], 
                             results2: List[Dict[str, Any]], 
                             top_k: int = None,
                             jaccard_threshold: float = 0.7) -> Dict[str, Any]:
        """
        Verify consistency between two sets of vector search results.
        
        Args:
            results1: First set of search results
            results2: Second set of search results
            top_k: Number of top results to compare (default: all)
            jaccard_threshold: Threshold for Jaccard similarity (0-1)
            
        Returns:
            Dictionary with consistency metrics
        """
        if not results1 or not results2:
            return {
                "consistent": False,
                "reason": "Empty results",
                "jaccard_similarity": 0.0,
                "rank_correlation": 0.0
            }
        
        # Limit to top_k if specified
        if top_k:
            results1 = results1[:top_k]
            results2 = results2[:top_k]
        
        # Extract IDs
        ids1 = [r.get("id") for r in results1]
        ids2 = [r.get("id") for r in results2]
        
        # Calculate Jaccard similarity (intersection over union)
        intersection = len(set(ids1).intersection(set(ids2)))
        union = len(set(ids1).union(set(ids2)))
        jaccard_similarity = intersection / union if union > 0 else 0.0
        
        # Calculate rank correlation for common items
        common_ids = set(ids1).intersection(set(ids2))
        rank_correlation = 0.0
        
        if common_ids:
            # Get ranks
            ranks1 = {id: idx for idx, id in enumerate(ids1) if id in common_ids}
            ranks2 = {id: idx for idx, id in enumerate(ids2) if id in common_ids}
            
            # Calculate rank differences
            n = len(common_ids)
            rank_diffs_squared = sum((ranks1[id] - ranks2[id])**2 for id in common_ids)
            
            # Spearman's rank correlation coefficient
            max_possible_diff = n * (n**2 - 1) / 6  # Maximum possible sum of squared differences
            if max_possible_diff > 0:
                rank_correlation = 1 - (rank_diffs_squared / max_possible_diff)
        
        # Determine if results are consistent
        is_consistent = jaccard_similarity >= jaccard_threshold
        
        return {
            "consistent": is_consistent,
            "reason": "Results consistent" if is_consistent else "Jaccard similarity below threshold",
            "jaccard_similarity": jaccard_similarity,
            "rank_correlation": rank_correlation,
            "common_items": len(common_ids),
            "total_items": max(len(ids1), len(ids2))
        }
        
    def migrate_to_provider(self, table_name: str, target_provider, model_class, 
                          limit: int = None, batch_size: int = 100) -> int:
        """
        Migrate data from this LanceDB instance to another provider.
        
        Args:
            table_name: Source table name
            target_provider: Target provider instance
            model_class: Model class for the data
            limit: Optional limit on number of records to migrate
            batch_size: Batch size for processing records
            
        Returns:
            Number of records migrated
        """
        try:
            # Get table
            table = self._get_or_create_table(table_name)
            
            # Start query
            query = table.search()
            
            # Apply limit if provided
            if limit:
                query = query.limit(limit)
            
            # Execute query
            result = query.to_pandas()
            
            # Process results
            records = []
            for _, row in result.iterrows():
                record = row.to_dict()
                
                # Parse metadata from JSON
                if "metadata" in record and isinstance(record["metadata"], str):
                    try:
                        record["metadata"] = json.loads(record["metadata"])
                    except json.JSONDecodeError:
                        logger.warning(f"Could not parse metadata JSON for record {record.get('id', 'unknown')}")
                
                records.append(record)
            
            # Create records in target provider in batches
            migrated_count = 0
            for i in range(0, len(records), batch_size):
                batch = records[i:i+batch_size]
                
                for record in batch:
                    # Create record in target provider
                    target_provider.create(model_class, record)
                    migrated_count += 1
            
            logger.info(f"Migrated {migrated_count} records from {table_name}")
            return migrated_count
            
        except Exception as e:
            logger.error(f"Error migrating data from {table_name}", error=str(e))
            raise