"""
Database performance optimization module for PyGovPub.

This module implements advanced performance optimizations for database operations,
including:
1. Connection pooling optimization
2. Transaction isolation level tuning
3. Bulk operation optimization
4. Query caching
"""

import logging
import time
from contextlib import contextmanager
from typing import List, Dict, Any, Optional, Tuple, Union, Callable, TypeVar, Generic, Iterator

import sqlalchemy
from sqlalchemy import create_engine, text, event
from sqlalchemy.engine import Engine, Connection
from sqlalchemy.orm import Session, Query
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, AsyncSession

# Configure logging
logger = logging.getLogger(__name__)

# Type variables for generic functions
T = TypeVar('T')


class ConnectionPoolManager:
    """
    Manages database connection pools for optimal performance.
    
    Provides functionality to:
    - Configure pool size based on workload
    - Monitor pool utilization
    - Recycle connections appropriately
    - Pre-ping connections to ensure they're valid
    """
    
    def __init__(self, engine: Engine):
        """
        Initialize with a SQLAlchemy engine.
        
        Args:
            engine: SQLAlchemy Engine to manage
        """
        self.engine = engine
        self.stats: Dict[str, int] = {
            "checkout_count": 0,
            "checkin_count": 0,
            "connections_created": 0,
            "connections_recycled": 0,
            "pool_exhausted_count": 0
        }
        
        # Set up event listeners if this is a pooled engine
        if hasattr(engine, "pool") and hasattr(engine.pool, "dispatch"):
            # Verify this is a real pool with event support, not a mock
            try:
                # Connection checkout events
                event.listen(engine.pool, "checkout", self._on_checkout)
                event.listen(engine.pool, "checkin", self._on_checkin)
                event.listen(engine.pool, "connect", self._on_connect)
                event.listen(engine.pool, "invalidate", self._on_invalidate)
            except Exception as e:
                # Log error but don't fail initialization
                logger.warning(f"Could not set up pool events: {e}")
                logger.debug("This is normal for test mocks and some database types")
    
    def _on_checkout(self, dbapi_connection, connection_record, connection_proxy):
        """
        Track connection checkouts from the pool.
        """
        self.stats["checkout_count"] += 1
    
    def _on_checkin(self, dbapi_connection, connection_record):
        """
        Track connection checkins to the pool.
        """
        self.stats["checkin_count"] += 1
    
    def _on_connect(self, dbapi_connection, connection_record):
        """
        Track new connection creation.
        """
        self.stats["connections_created"] += 1
    
    def _on_invalidate(self, dbapi_connection, connection_record, exception):
        """
        Track when connections are invalidated.
        """
        self.stats["connections_recycled"] += 1
        
    def get_stats(self) -> Dict[str, Any]:
        """
        Get pool statistics.
        
        Returns:
            Dict with pool statistics
        """
        stats = self.stats.copy()
        
        # Add current pool status if available
        if hasattr(self.engine, "pool"):
            # Different pool implementations have different APIs
            # Handle both callable and property implementations
            if hasattr(self.engine.pool, "size"):
                if callable(self.engine.pool.size):
                    stats["current_pool_size"] = self.engine.pool.size()
                else:
                    stats["current_pool_size"] = self.engine.pool.size
                
            if hasattr(self.engine.pool, "checkedout"):
                if callable(self.engine.pool.checkedout):
                    stats["current_checked_out"] = self.engine.pool.checkedout()
                else:
                    stats["current_checked_out"] = self.engine.pool.checkedout
            
        return stats
        
    def optimize_pool_size(self, target_utilization: float = 0.75) -> None:
        """
        Adjust pool size based on observed usage patterns.
        
        Args:
            target_utilization: Target pool utilization rate (0.0-1.0)
        """
        if not hasattr(self.engine, "pool") or not hasattr(self.engine.pool, "size"):
            logger.warning("Engine does not have a standard connection pool, cannot optimize")
            return
            
        # Get current stats
        current_size = self.engine.pool.size()
        current_checked_out = self.engine.pool.checkedout()
        
        # Skip if no connections have been used
        if self.stats["checkout_count"] == 0:
            logger.info("No connections used yet, skipping pool optimization")
            return
            
        # Calculate utilization
        utilization = current_checked_out / current_size if current_size > 0 else 0
        
        # Determine if we need to adjust the pool size
        if utilization > target_utilization:
            # Pool is heavily utilized, may need to increase
            new_size = min(int(current_size * 1.5), current_size + 10)
            logger.info(f"Increasing pool size from {current_size} to {new_size} (utilization: {utilization:.2f})")
            self.engine.pool._pool.maxsize = new_size
        elif utilization < target_utilization / 2 and current_size > 5:
            # Pool is underutilized, decrease size but keep minimum of 5
            new_size = max(5, int(current_size * 0.75))
            logger.info(f"Decreasing pool size from {current_size} to {new_size} (utilization: {utilization:.2f})")
            self.engine.pool._pool.maxsize = new_size


class TransactionManager:
    """
    Manages database transaction isolation levels for optimal performance.
    
    Provides functionality to:
    - Set appropriate isolation levels for different operations
    - Monitor transaction performance
    - Suggest isolation level improvements
    """
    
    # Standard isolation levels ordered by restrictiveness
    ISOLATION_LEVELS = [
        "READ UNCOMMITTED",  # Least restrictive, highest performance
        "READ COMMITTED",     # Default in many databases
        "REPEATABLE READ",    # More consistent reads
        "SERIALIZABLE"        # Most restrictive, lowest performance
    ]
    
    def __init__(self, engine: Engine):
        """
        Initialize with a SQLAlchemy engine.
        
        Args:
            engine: SQLAlchemy Engine to manage
        """
        self.engine = engine
        self.stats: Dict[str, Dict[str, float]] = {
            level: {"count": 0, "total_duration": 0.0, "max_duration": 0.0}
            for level in self.ISOLATION_LEVELS
        }
    
    @contextmanager
    def transaction(self, isolation_level: str = "READ COMMITTED") -> Iterator[Session]:
        """
        Execute a transaction with the specified isolation level.
        
        Args:
            isolation_level: Isolation level to use
            
        Yields:
            SQLAlchemy Session with configured isolation level
        """
        # Normalize isolation level
        isolation_level = isolation_level.upper()
        
        # Validate isolation level
        if isolation_level not in self.ISOLATION_LEVELS:
            raise ValueError(f"Invalid isolation level: {isolation_level}")
        
        # Start timing
        start_time = time.time()
        
        # Create session
        session = Session(self.engine)
        
        try:
            # Check if database supports SET TRANSACTION directly (some like SQLite don't)
            is_sqlite = str(self.engine.url).startswith('sqlite')
            
            if not is_sqlite:
                # Set isolation level for databases that support it directly
                try:
                    session.execute(text(f"SET TRANSACTION ISOLATION LEVEL {isolation_level}"))
                except Exception as e:
                    # Log but don't fail - might be a database that doesn't support this syntax
                    logger.warning(f"Could not set transaction isolation level: {e}")
            else:
                # For SQLite, can't set isolation level directly with SQL,
                # but can use it for tracking purposes
                logger.debug(f"SQLite doesn't support explicit isolation levels, using {isolation_level}")
            
            # Yield the session for use
            yield session
            
            # Commit if no exception occurred
            session.commit()
        except Exception:
            # Roll back on exception
            session.rollback()
            raise
        finally:
            # Record statistics
            duration = time.time() - start_time
            
            # Update stats
            level_stats = self.stats[isolation_level]
            level_stats["count"] += 1
            level_stats["total_duration"] += duration
            level_stats["max_duration"] = max(level_stats["max_duration"], duration)
            
            # Close session
            session.close()
    
    def get_stats(self) -> Dict[str, Dict[str, float]]:
        """
        Get transaction statistics.
        
        Returns:
            Dict with transaction statistics by isolation level
        """
        # Make a copy of stats with average duration added
        stats = {}
        for level, level_stats in self.stats.items():
            stats[level] = level_stats.copy()
            if level_stats["count"] > 0:
                stats[level]["avg_duration"] = level_stats["total_duration"] / level_stats["count"]
            else:
                stats[level]["avg_duration"] = 0.0
        
        return stats
    
    def suggest_isolation_level(self, needs_consistency: bool = False) -> str:
        """
        Suggest an appropriate isolation level based on usage patterns.
        
        Args:
            needs_consistency: Whether the operation needs strong consistency
            
        Returns:
            Suggested isolation level
        """
        if needs_consistency:
            # For operations needing strong consistency, use at least REPEATABLE READ
            return "SERIALIZABLE" if self._is_write_heavy() else "REPEATABLE READ"
        else:
            # For read-heavy operations, use less restrictive levels
            return "READ COMMITTED" if self._is_write_heavy() else "READ UNCOMMITTED"
    
    def _is_write_heavy(self) -> bool:
        """
        Determine if the workload is write-heavy.
        
        Returns:
            True if the workload seems write-heavy
        """
        # This is a placeholder implementation
        # In a real system, this would analyze query patterns
        return False
    
    @staticmethod
    def get_recommended_isolation_level(operation_type: str) -> str:
        """
        Get a recommended isolation level for a given operation type.
        
        Args:
            operation_type: Type of operation ("read", "write", "report", etc.)
            
        Returns:
            Recommended isolation level
        """
        operation_type = operation_type.lower()
        
        if operation_type == "read":
            return "READ COMMITTED"
        elif operation_type == "report" or operation_type == "analytics":
            return "READ UNCOMMITTED"
        elif operation_type == "write" or operation_type == "update":
            return "REPEATABLE READ"
        elif operation_type == "financial" or operation_type == "critical":
            return "SERIALIZABLE"
        else:
            # Default to a balanced isolation level
            return "READ COMMITTED"


class BulkOperationOptimizer:
    """
    Optimizes bulk database operations for maximum performance.
    
    Provides functionality to:
    - Batch inserts and updates for better performance
    - Use optimal batch sizes
    - Monitor performance of bulk operations
    """
    
    def __init__(self, engine: Engine, default_batch_size: int = 1000):
        """
        Initialize with a SQLAlchemy engine.
        
        Args:
            engine: SQLAlchemy Engine to use
            default_batch_size: Default batch size for bulk operations
        """
        self.engine = engine
        self.default_batch_size = default_batch_size
        self.stats: Dict[str, Dict[str, float]] = {
            "insert": {"count": 0, "rows": 0, "total_duration": 0.0},
            "update": {"count": 0, "rows": 0, "total_duration": 0.0},
            "delete": {"count": 0, "rows": 0, "total_duration": 0.0}
        }
    
    def bulk_insert(self, table: str, data: List[Dict[str, Any]], 
                   batch_size: Optional[int] = None) -> int:
        """
        Perform a bulk insert operation.
        
        Args:
            table: Table name
            data: List of dictionaries with column values
            batch_size: Batch size (if None, uses default_batch_size)
            
        Returns:
            Number of rows inserted
        """
        if not data:
            return 0
            
        # Use default batch size if not specified
        if batch_size is None:
            batch_size = self.default_batch_size
            
        # Start timing
        start_time = time.time()
        
        # Get column names from first data item
        columns = list(data[0].keys())
        
        # Prepare the insert statement
        insert_stmt = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({', '.join([f':{col}' for col in columns])})"
        
        # Execute in batches
        rows_inserted = 0
        with Session(self.engine) as session:
            for i in range(0, len(data), batch_size):
                batch = data[i:i+batch_size]
                session.execute(text(insert_stmt), batch)
                rows_inserted += len(batch)
            
            # Commit the transaction
            session.commit()
            
        # Record statistics
        duration = time.time() - start_time
        self.stats["insert"]["count"] += 1
        self.stats["insert"]["rows"] += rows_inserted
        self.stats["insert"]["total_duration"] += duration
        
        return rows_inserted
    
    def bulk_update(self, table: str, data: List[Dict[str, Any]], id_column: str,
                   batch_size: Optional[int] = None) -> int:
        """
        Perform a bulk update operation.
        
        Args:
            table: Table name
            data: List of dictionaries with column values
            id_column: Column name for the ID/primary key
            batch_size: Batch size (if None, uses default_batch_size)
            
        Returns:
            Number of rows updated
        """
        if not data:
            return 0
            
        # Use default batch size if not specified
        if batch_size is None:
            batch_size = self.default_batch_size
            
        # Start timing
        start_time = time.time()
        
        # Get update columns from first data item (excluding ID column)
        update_columns = [col for col in data[0].keys() if col != id_column]
        
        # Prepare the update statement
        set_clause = ", ".join([f"{col} = :{col}" for col in update_columns])
        update_stmt = f"UPDATE {table} SET {set_clause} WHERE {id_column} = :{id_column}"
        
        # Execute in batches
        rows_updated = 0
        with Session(self.engine) as session:
            for i in range(0, len(data), batch_size):
                batch = data[i:i+batch_size]
                for row in batch:
                    session.execute(text(update_stmt), row)
                    rows_updated += 1
                session.flush()  # Flush after each batch
            
            # Commit the transaction
            session.commit()
            
        # Record statistics
        duration = time.time() - start_time
        self.stats["update"]["count"] += 1
        self.stats["update"]["rows"] += rows_updated
        self.stats["update"]["total_duration"] += duration
        
        return rows_updated
    
    def bulk_delete(self, table: str, id_values: List[Any], id_column: str = "id",
                   batch_size: Optional[int] = None) -> int:
        """
        Perform a bulk delete operation.
        
        Args:
            table: Table name
            id_values: List of ID values to delete
            id_column: Column name for the ID/primary key
            batch_size: Batch size (if None, uses default_batch_size)
            
        Returns:
            Number of rows deleted
        """
        if not id_values:
            return 0
            
        # Use default batch size if not specified
        if batch_size is None:
            batch_size = self.default_batch_size
            
        # Start timing
        start_time = time.time()
        
        # Execute in batches
        rows_deleted = 0
        with Session(self.engine) as session:
            for i in range(0, len(id_values), batch_size):
                batch = id_values[i:i+batch_size]
                
                # Use IN clause for better performance
                placeholders = ", ".join(["?"] * len(batch))
                delete_stmt = f"DELETE FROM {table} WHERE {id_column} IN ({placeholders})"
                
                # Execute the statement
                session.execute(text(delete_stmt), batch)
                rows_deleted += len(batch)
                
                session.flush()  # Flush after each batch
            
            # Commit the transaction
            session.commit()
            
        # Record statistics
        duration = time.time() - start_time
        self.stats["delete"]["count"] += 1
        self.stats["delete"]["rows"] += rows_deleted
        self.stats["delete"]["total_duration"] += duration
        
        return rows_deleted
    
    def get_stats(self) -> Dict[str, Dict[str, float]]:
        """
        Get operation statistics.
        
        Returns:
            Dict with operation statistics
        """
        # Make a copy of stats with average duration and rows per second added
        stats = {}
        for op, op_stats in self.stats.items():
            stats[op] = op_stats.copy()
            
            if op_stats["count"] > 0:
                stats[op]["avg_duration"] = op_stats["total_duration"] / op_stats["count"]
                stats[op]["avg_rows_per_op"] = op_stats["rows"] / op_stats["count"]
                
                if op_stats["total_duration"] > 0:
                    stats[op]["rows_per_second"] = op_stats["rows"] / op_stats["total_duration"]
                else:
                    stats[op]["rows_per_second"] = 0
            else:
                stats[op]["avg_duration"] = 0
                stats[op]["avg_rows_per_op"] = 0
                stats[op]["rows_per_second"] = 0
                
        return stats


class QueryCache:
    """
    Query cache for improving performance of repeated queries.
    
    Provides functionality to:
    - Cache query results
    - Set cache TTL (time-to-live)
    - Invalidate cache entries
    - Monitor cache hit/miss rates
    """
    
    def __init__(self, ttl_seconds: int = 60):
        """
        Initialize query cache.
        
        Args:
            ttl_seconds: Default TTL for cache entries in seconds
        """
        self.ttl_seconds = ttl_seconds
        self.cache: Dict[str, Tuple[Any, float]] = {}  # (result, expiry_timestamp)
        self.stats = {
            "hits": 0,
            "misses": 0,
            "invalidations": 0,
            "expirations": 0
        }
    
    def get(self, query_key: str) -> Optional[Any]:
        """
        Get a result from the cache.
        
        Args:
            query_key: Cache key for the query
            
        Returns:
            Cached result or None if not in cache or expired
        """
        # Check if in cache
        if query_key not in self.cache:
            self.stats["misses"] += 1
            return None
        
        # Get cached entry
        result, expiry = self.cache[query_key]
        
        # Check if expired
        if time.time() > expiry:
            # Remove from cache
            del self.cache[query_key]
            self.stats["expirations"] += 1
            self.stats["misses"] += 1
            return None
        
        # Cache hit
        self.stats["hits"] += 1
        return result
    
    def set(self, query_key: str, result: Any, ttl_seconds: Optional[int] = None) -> None:
        """
        Store a result in the cache.
        
        Args:
            query_key: Cache key for the query
            result: Result to cache
            ttl_seconds: TTL for this entry (if None, uses default)
        """
        # Use default TTL if not specified
        if ttl_seconds is None:
            ttl_seconds = self.ttl_seconds
        
        # Calculate expiry timestamp
        expiry = time.time() + ttl_seconds
        
        # Store in cache
        self.cache[query_key] = (result, expiry)
    
    def invalidate(self, query_key: str) -> bool:
        """
        Invalidate a specific cache entry.
        
        Args:
            query_key: Cache key to invalidate
            
        Returns:
            True if entry was in cache and removed, False otherwise
        """
        if query_key in self.cache:
            del self.cache[query_key]
            self.stats["invalidations"] += 1
            return True
        return False
    
    def invalidate_all(self) -> int:
        """
        Invalidate all cache entries.
        
        Returns:
            Number of entries invalidated
        """
        count = len(self.cache)
        self.cache.clear()
        self.stats["invalidations"] += count
        return count
    
    def cleanup_expired(self) -> int:
        """
        Remove expired entries from the cache.
        
        Returns:
            Number of entries removed
        """
        now = time.time()
        expired_keys = [k for k, (_, expiry) in self.cache.items() if now > expiry]
        
        for key in expired_keys:
            del self.cache[key]
        
        self.stats["expirations"] += len(expired_keys)
        return len(expired_keys)
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dict with cache statistics
        """
        stats = self.stats.copy()
        
        # Add additional stats
        total_requests = stats["hits"] + stats["misses"]
        stats["hit_rate"] = stats["hits"] / total_requests if total_requests > 0 else 0
        stats["cache_size"] = len(self.cache)
        
        return stats
    
    @contextmanager
    def cached_session(self, engine: Engine, ttl_seconds: Optional[int] = None) -> Iterator[Session]:
        """
        Get a session with query caching enabled.
        
        Args:
            engine: SQLAlchemy engine to use
            ttl_seconds: TTL for cached queries (if None, uses default)
            
        Yields:
            Caching-enabled session
        """
        # Create a regular session
        session = Session(engine)
        
        # Store original session.execute method
        original_execute = session.execute
        
        # Define a new execute method with caching
        def execute_with_cache(statement, *args, **kwargs):
            # Only cache SELECT statements
            if not str(statement).strip().upper().startswith("SELECT"):
                return original_execute(statement, *args, **kwargs)
            
            # Create a cache key from the statement and parameters
            params = str(args) + str(kwargs)
            cache_key = f"{str(statement)}:{params}"
            
            # Check cache
            cached_result = self.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Execute the query
            result = original_execute(statement, *args, **kwargs)
            
            # Cache the result
            self.set(cache_key, result, ttl_seconds)
            
            return result
        
        # Replace the session.execute method
        session.execute = execute_with_cache  # type: ignore
        
        try:
            # Yield session for use
            yield session
        finally:
            # Restore original execute method
            session.execute = original_execute
            session.close()


class DatabasePerformanceManager:
    """
    Main interface for database performance optimizations.
    
    Provides a unified interface to all performance optimization components.
    """
    
    def __init__(self, engine: Optional[Engine] = None):
        """
        Initialize performance manager with an engine.
        
        Args:
            engine: SQLAlchemy engine (if None, no engine-specific optimizations)
        """
        self.engine = engine
        
        # Initialize components if engine is provided
        if engine is not None:
            self.connection_pool = ConnectionPoolManager(engine)
            self.transaction_manager = TransactionManager(engine)
            self.bulk_optimizer = BulkOperationOptimizer(engine)
        else:
            self.connection_pool = None
            self.transaction_manager = None
            self.bulk_optimizer = None
            
        # Query cache doesn't require an engine
        self.query_cache = QueryCache()
    
    def optimize_connection_pool(self, target_utilization: float = 0.75) -> None:
        """
        Optimize connection pool size.
        
        Args:
            target_utilization: Target pool utilization (0.0-1.0)
        """
        if self.connection_pool is not None:
            self.connection_pool.optimize_pool_size(target_utilization)
        else:
            logger.warning("No engine provided, cannot optimize connection pool")
    
    @contextmanager
    def transaction(self, isolation_level: str = "READ COMMITTED") -> Iterator[Session]:
        """
        Get a session with specified isolation level.
        
        Args:
            isolation_level: Transaction isolation level
            
        Yields:
            SQLAlchemy Session
        """
        if self.transaction_manager is not None:
            with self.transaction_manager.transaction(isolation_level) as session:
                yield session
        else:
            raise ValueError("No engine provided, cannot create transaction")
    
    def bulk_insert(self, table: str, data: List[Dict[str, Any]], 
                   batch_size: Optional[int] = None) -> int:
        """
        Perform optimized bulk insert.
        
        Args:
            table: Table name
            data: Data to insert
            batch_size: Batch size
            
        Returns:
            Number of rows inserted
        """
        if self.bulk_optimizer is not None:
            return self.bulk_optimizer.bulk_insert(table, data, batch_size)
        else:
            raise ValueError("No engine provided, cannot perform bulk insert")
    
    def bulk_update(self, table: str, data: List[Dict[str, Any]], id_column: str,
                   batch_size: Optional[int] = None) -> int:
        """
        Perform optimized bulk update.
        
        Args:
            table: Table name
            data: Data to update
            id_column: ID column name
            batch_size: Batch size
            
        Returns:
            Number of rows updated
        """
        if self.bulk_optimizer is not None:
            return self.bulk_optimizer.bulk_update(table, data, id_column, batch_size)
        else:
            raise ValueError("No engine provided, cannot perform bulk update")
    
    def bulk_delete(self, table: str, id_values: List[Any], id_column: str = "id",
                   batch_size: Optional[int] = None) -> int:
        """
        Perform optimized bulk delete.
        
        Args:
            table: Table name
            id_values: IDs to delete
            id_column: ID column name
            batch_size: Batch size
            
        Returns:
            Number of rows deleted
        """
        if self.bulk_optimizer is not None:
            return self.bulk_optimizer.bulk_delete(table, id_values, id_column, batch_size)
        else:
            raise ValueError("No engine provided, cannot perform bulk delete")
    
    @contextmanager
    def cached_session(self, ttl_seconds: Optional[int] = None) -> Iterator[Session]:
        """
        Get a session with query caching enabled.
        
        Args:
            ttl_seconds: Cache TTL
            
        Yields:
            Caching-enabled session
        """
        if self.engine is not None:
            with self.query_cache.cached_session(self.engine, ttl_seconds) as session:
                yield session
        else:
            raise ValueError("No engine provided, cannot create cached session")
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive performance statistics.
        
        Returns:
            Dict with performance statistics from all components
        """
        stats = {}
        
        # Query cache stats (always available)
        stats["query_cache"] = self.query_cache.get_stats()
        
        # Add engine-dependent stats if available
        if self.connection_pool is not None:
            stats["connection_pool"] = self.connection_pool.get_stats()
            
        if self.transaction_manager is not None:
            stats["transactions"] = self.transaction_manager.get_stats()
            
        if self.bulk_optimizer is not None:
            stats["bulk_operations"] = self.bulk_optimizer.get_stats()
            
        return stats
    
    def get_optimization_recommendations(self) -> List[str]:
        """
        Get recommendations for performance optimizations.
        
        Returns:
            List of recommendation strings
        """
        recommendations = []
        
        # Query cache recommendations
        if self.query_cache:
            cache_stats = self.query_cache.get_stats()
            if cache_stats["hit_rate"] < 0.3 and cache_stats["hit_rate"] > 0:
                recommendations.append(
                    "Low query cache hit rate. Consider adjusting cache TTL or "
                    "reviewing query patterns."
                )
                
        # Connection pool recommendations
        if self.connection_pool:
            pool_stats = self.connection_pool.get_stats()
            if "current_pool_size" in pool_stats and "current_checked_out" in pool_stats:
                if pool_stats["current_checked_out"] >= pool_stats["current_pool_size"] * 0.9:
                    recommendations.append(
                        "Connection pool is nearly exhausted. Consider increasing pool size "
                        "or reviewing connection handling code for leaks."
                    )
                    
        # Bulk operation recommendations
        if self.bulk_optimizer:
            bulk_stats = self.bulk_optimizer.get_stats()
            for op_type, op_stats in bulk_stats.items():
                if op_stats.get("avg_rows_per_op", 0) < 10 and op_stats.get("count", 0) > 5:
                    recommendations.append(
                        f"Low row count in {op_type} bulk operations. Consider batching "
                        f"more rows for better performance."
                    )
                    
        return recommendations