"""
Database connection management for PyGovPub.

This module handles database connections, session management, and transactions.
It provides both synchronous and asynchronous database interfaces with
performance optimization features including:

- Connection pooling optimization
- Transaction isolation tuning
- Bulk operation optimization 
- Query cache utilization
"""

import os
import logging
import time
import atexit
from typing import Optional, Dict, Callable, List, Any, AsyncGenerator, Generator, Union, TypeVar, Tuple
from datetime import datetime
from contextlib import contextmanager, asynccontextmanager

import sqlalchemy
from sqlalchemy import event, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlmodel import Session, SQLModel, create_engine

from pygovpub.core.db_performance import (
    DatabasePerformanceManager, 
    ConnectionPoolManager,
    TransactionManager,
    BulkOperationOptimizer,
    QueryCache
)

# Configure logging
logger = logging.getLogger(__name__)

# Global engine instance (initialized on first use)
_ENGINE = None
_ASYNC_ENGINE = None

# Global performance manager
_PERFORMANCE_MANAGER = None

# Database URL from environment variables (or use default for development)
DATABASE_URL = None

# Global query cache
_QUERY_CACHE = None


def get_connection_url() -> str:
    """
    Construct database connection URL from environment variables.
    
    Environment variables:
    - DB_TYPE: Database type (postgresql, mysql, sqlite)
    - DB_HOST: Database host
    - DB_PORT: Database port
    - DB_NAME: Database name
    - DB_USER: Database username
    - DB_PASSWORD: Database password
    
    Returns:
        str: Database connection URL
    """
    db_type = os.environ.get("DB_TYPE", "sqlite")
    db_host = os.environ.get("DB_HOST", ":memory:")
    db_port = os.environ.get("DB_PORT", "")
    db_name = os.environ.get("DB_NAME", "pygovpub")
    db_user = os.environ.get("DB_USER", "")
    db_password = os.environ.get("DB_PASSWORD", "")
    
    # Construct URL based on database type
    if db_type == "sqlite":
        if db_host == ":memory:" or not db_host:
            # Import additional modules needed for this path
            import tempfile
            import uuid
            from pathlib import Path
            
            # Use a managed directory in the project for SQLite temp files
            project_root = Path(__file__).absolute().parents[3]  # Go up 3 levels from this file
            sqlite_dir = project_root / "tmp" / "sqlite_files"
            
            # Create directory if needed
            os.makedirs(sqlite_dir, exist_ok=True)
            
            # Create a unique temp file name with timestamp to aid in debugging
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            temp_db_file = sqlite_dir / f"sqlite_temp_{timestamp}_{uuid.uuid4().hex}.db"
            
            # Ensure the file gets deleted when the process exits
            @atexit.register
            def cleanup_db_file():
                if temp_db_file.exists():
                    try:
                        temp_db_file.unlink()
                    except (PermissionError, OSError) as e:
                        # Log error but don't crash
                        logger.warning(f"Could not delete temp SQLite file {temp_db_file}: {e}")
                        # Write to cleanup list for future cleanup
                        cleanup_list = sqlite_dir / "_cleanup_list.txt"
                        try:
                            with open(cleanup_list, "a") as f:
                                f.write(f"{temp_db_file}\n")
                        except:
                            pass
                            
            # Return file-based URL but with temp file that will be cleaned up
            return f"sqlite:///{temp_db_file}"
        return f"sqlite:///{db_host}"
    
    # For PostgreSQL and MySQL, include user/password if provided
    if db_user and db_password:
        auth = f"{db_user}:{db_password}@"
    else:
        auth = ""
    
    # Include port if provided
    if db_port:
        host_port = f"{db_host}:{db_port}"
    else:
        host_port = db_host
    
    return f"{db_type}://{auth}{host_port}/{db_name}"


def init_db(connection_url: Optional[str] = None, echo: bool = False, 
          optimize_performance: bool = True) -> sqlalchemy.engine.Engine:
    """
    Initialize database engine with performance optimizations.
    
    Args:
        connection_url: Database connection URL (if None, uses environment variables)
        echo: Whether to echo SQL statements
        optimize_performance: Whether to apply performance optimizations
        
    Returns:
        SQLAlchemy engine instance
    """
    global DATABASE_URL, _PERFORMANCE_MANAGER, _QUERY_CACHE
    
    # Use provided URL or get from environment
    if connection_url:
        DATABASE_URL = connection_url
    else:
        DATABASE_URL = get_connection_url()
    
    logger.info(f"Initializing database with type: {DATABASE_URL.split('://')[0]}")
    
    # Check if SQLite
    is_sqlite = DATABASE_URL.startswith('sqlite')
    
    # Create engine with different settings for SQLite vs other databases
    if is_sqlite:
        # SQLite doesn't support the same connection pooling options
        engine = create_engine(
            DATABASE_URL,
            echo=echo,
            connect_args={"check_same_thread": False}  # Allow cross-thread usage
        )
    else:
        # Full connection pooling for production databases
        engine = create_engine(
            DATABASE_URL,
            echo=echo,
            pool_pre_ping=True,  # Verify connections before using from pool
            pool_recycle=3600,   # Recycle connections after 1 hour
            pool_size=5,         # Pool size
            max_overflow=10,     # Allow up to 10 additional connections in high demand
            future=True          # Use the new SQLAlchemy 2.0 future API
        )
    
    # Initialize performance manager if requested
    if optimize_performance:
        _PERFORMANCE_MANAGER = DatabasePerformanceManager(engine)
        
        # Initialize global query cache if not exists
        if _QUERY_CACHE is None:
            _QUERY_CACHE = QueryCache()
            
        # Set up event listener to track query performance
        if not is_sqlite:  # Skip for SQLite since these events can cause issues
            @event.listens_for(engine, "before_cursor_execute")
            def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
                conn.info.setdefault('query_start_time', []).append(time.time())
                
            @event.listens_for(engine, "after_cursor_execute")
            def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
                start_time = conn.info['query_start_time'].pop()
                execution_time = time.time() - start_time
                if execution_time > 0.5:  # Log slow queries (>500ms)
                    logger.warning(f"Slow query detected ({execution_time:.2f}s): {statement[:100]}...")
    
    return engine


def get_engine(force_new: bool = False) -> sqlalchemy.engine.Engine:
    """
    Get database engine (singleton pattern).
    
    Args:
        force_new: If True, creates a new engine instance instead of returning existing one
        
    Returns:
        SQLAlchemy engine instance
    """
    global _ENGINE, DATABASE_URL
    
    if _ENGINE is None or force_new:
        # Initialize URL if needed
        if DATABASE_URL is None:
            DATABASE_URL = get_connection_url()
        
        # Create engine
        _ENGINE = init_db(DATABASE_URL)
    
    return _ENGINE


def get_async_engine(force_new: bool = False) -> sqlalchemy.ext.asyncio.AsyncEngine:
    """
    Get async database engine (singleton pattern).
    
    Args:
        force_new: If True, creates a new engine instance instead of returning existing one
        
    Returns:
        AsyncEngine instance
    """
    global _ASYNC_ENGINE, DATABASE_URL
    
    if _ASYNC_ENGINE is None or force_new:
        # Initialize URL if needed
        if DATABASE_URL is None:
            DATABASE_URL = get_connection_url()
        
        # Replace sqlite:// with sqlite+aiosqlite:// for async support
        async_url = DATABASE_URL
        if async_url.startswith('sqlite://'):
            async_url = async_url.replace('sqlite://', 'sqlite+aiosqlite://', 1)
        
        # Check if SQLite
        is_sqlite = async_url.startswith('sqlite+aiosqlite')
        
        # Create async engine with different settings for SQLite vs other databases
        if is_sqlite:
            # SQLite doesn't support the same connection pooling options
            _ASYNC_ENGINE = create_async_engine(
                async_url,
                echo=False,
                connect_args={"check_same_thread": False}  # Allow cross-thread usage
            )
        else:
            # Full connection pooling for production databases
            _ASYNC_ENGINE = create_async_engine(
                async_url,
                echo=False,
                pool_pre_ping=True,
                pool_recycle=3600,
                pool_size=5,
                max_overflow=10
            )
    
    return _ASYNC_ENGINE


def get_session(use_cache: bool = False, isolation_level: Optional[str] = None) -> Session:
    """
    Get a new database session with optional performance optimizations.
    
    Args:
        use_cache: Whether to enable query caching for this session
        isolation_level: Transaction isolation level to use for this session
        
    Returns:
        SQLModel Session
    """
    global _PERFORMANCE_MANAGER, _QUERY_CACHE
    
    engine = get_engine()
    
    # Use optimized session if available
    if _PERFORMANCE_MANAGER is not None:
        if use_cache:
            # Create a cached session
            session = Session(engine)
            
            # Add cache-enabled wrapper for execute
            original_execute = session.execute
            
            def execute_with_cache(statement, *args, **kwargs):
                # Only cache SELECT statements
                if not str(statement).strip().upper().startswith("SELECT"):
                    return original_execute(statement, *args, **kwargs)
                
                # Create a cache key
                params = str(args) + str(kwargs)
                cache_key = f"{str(statement)}:{params}"
                
                # Check cache
                cached_result = _QUERY_CACHE.get(cache_key)
                if cached_result is not None:
                    return cached_result
                
                # Execute query
                result = original_execute(statement, *args, **kwargs)
                
                # Cache result
                _QUERY_CACHE.set(cache_key, result)
                
                return result
            
            # Apply cache wrapper
            session.execute = execute_with_cache  # type: ignore
            
            # Set isolation level if specified
            if isolation_level is not None:
                # Check if SQLite (doesn't support SET TRANSACTION directly)
                is_sqlite = str(engine.url).startswith('sqlite')
                if not is_sqlite:
                    try:
                        session.execute(text(f"SET TRANSACTION ISOLATION LEVEL {isolation_level}"))
                    except Exception as e:
                        logger.warning(f"Could not set transaction isolation level: {e}")
                
            return session
            
        elif isolation_level is not None:
            # Create a session with custom isolation level
            session = Session(engine)
            
            # Check if SQLite (doesn't support SET TRANSACTION directly)
            is_sqlite = str(engine.url).startswith('sqlite')
            if not is_sqlite:
                try:
                    session.execute(text(f"SET TRANSACTION ISOLATION LEVEL {isolation_level}"))
                except Exception as e:
                    logger.warning(f"Could not set transaction isolation level: {e}")
            
            return session
    
    # Default session if no optimizations applied
    return Session(engine)


@contextmanager
def with_transaction(isolation_level: str = "READ COMMITTED", use_cache: bool = False) -> Generator[Session, None, None]:
    """
    Context manager for database transactions with performance optimizations.
    
    Automatically commits if no exceptions occur, or rolls back on exceptions.
    
    Args:
        isolation_level: Transaction isolation level to use
        use_cache: Whether to enable query caching
    
    Yields:
        SQLModel Session
    """
    global _PERFORMANCE_MANAGER, _QUERY_CACHE
    
    # Get engine directly to avoid circular import with get_performance_manager
    engine = get_engine()
    
    # Ensure tables exist for DBTestModel if being used in test
    if 'DBTestModel' in globals():
        inspector = sqlalchemy.inspect(engine)
        if "db_test_models" not in inspector.get_table_names():
            # Make sure to create tables now
            from sqlmodel import SQLModel
            SQLModel.metadata.create_all(engine)
    
    # Use basic transaction for tests
    session = get_session(use_cache=use_cache, isolation_level=isolation_level)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


class AsyncDatabaseSession:
    """Async database session manager."""
    
    def __init__(self):
        """Initialize with default engine."""
        self.engine = get_async_engine()
        self.session_factory = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
    
    async def __aenter__(self) -> AsyncSession:
        """Enter the context."""
        self.session = self.session_factory()
        return self.session
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit the context."""
        if exc_type:
            await self.session.rollback()
        else:
            await self.session.commit()
        await self.session.close()


@asynccontextmanager
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Get an async database session.
    
    Yields:
        AsyncSession
    """
    async with AsyncDatabaseSession() as session:
        yield session


@asynccontextmanager
async def with_async_transaction(isolation_level: str = "READ COMMITTED") -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager for async database transactions with performance optimizations.
    
    Automatically commits if no exceptions occur, or rolls back on exceptions.
    
    Args:
        isolation_level: Transaction isolation level to use
    
    Yields:
        AsyncSession
    """
    async with get_async_session() as session:
        # Set isolation level if specified
        if isolation_level:
            # Check if SQLite (doesn't support SET TRANSACTION directly)
            engine = get_async_engine()
            is_sqlite = str(engine.url).startswith('sqlite')
            if not is_sqlite:
                try:
                    await session.execute(text(f"SET TRANSACTION ISOLATION LEVEL {isolation_level}"))
                except Exception as e:
                    logger.warning(f"Could not set transaction isolation level: {e}")
        
        yield session


def create_tables() -> None:
    """
    Create all tables defined in SQLModel metadata.
    """
    engine = get_engine()
    SQLModel.metadata.create_all(engine)
    logger.info("All database tables created")


def drop_tables() -> None:
    """
    Drop all tables defined in SQLModel metadata.
    """
    engine = get_engine()
    SQLModel.metadata.drop_all(engine)
    logger.info("All database tables dropped")


class MigrationManager:
    """
    Database migration manager.
    
    Handles schema version tracking and migration application.
    """
    
    def __init__(self, engine=None):
        """
        Initialize migration manager.
        
        Args:
            engine: SQLAlchemy engine (if None, gets from get_engine())
        """
        self.engine = engine or get_engine()
        self.migrations: Dict[str, Callable[[Session], None]] = {}
        self.rollbacks: Dict[str, Callable[[Session], None]] = {}
        
        # Ensure version table exists
        self.ensure_version_table()
    
    def ensure_version_table(self) -> None:
        """Create schema_versions table if it doesn't exist."""
        with Session(self.engine) as session:
            # Check if table exists
            inspector = sqlalchemy.inspect(self.engine)
            if 'schema_versions' not in inspector.get_table_names():
                # Create the version table
                session.execute(sqlalchemy.text("""
                    CREATE TABLE schema_versions (
                        id INTEGER PRIMARY KEY,
                        version VARCHAR(50) NOT NULL,
                        applied_at TIMESTAMP NOT NULL
                    )
                """))
                session.commit()
                logger.info("Created schema_versions table")
    
    def get_current_version(self) -> Optional[str]:
        """
        Get current schema version from database.
        
        Returns:
            str: Current version or None if no version set
        """
        with Session(self.engine) as session:
            # Get latest version
            result = session.execute(sqlalchemy.text(
                "SELECT version FROM schema_versions ORDER BY id DESC LIMIT 1"
            ))
            row = result.fetchone()
            
            if row:
                return row[0]
            return None
    
    def set_version(self, version: str) -> None:
        """
        Set current schema version in database.
        
        Args:
            version: Version string to set
        """
        with Session(self.engine) as session:
            # Insert new version record
            session.execute(sqlalchemy.text(
                "INSERT INTO schema_versions (version, applied_at) VALUES (:version, :now)"
            ), {"version": version, "now": datetime.now()})
            session.commit()
            logger.info(f"Set schema version to {version}")
    
    def register_migration(self, version: str, up_func: Callable[[Session], None], 
                          down_func: Callable[[Session], None]) -> None:
        """
        Register a migration and its rollback function.
        
        Args:
            version: Version string for this migration
            up_func: Function to apply the migration (takes session as arg)
            down_func: Function to roll back the migration (takes session as arg)
        """
        self.migrations[version] = up_func
        self.rollbacks[version] = down_func
        logger.debug(f"Registered migration for version {version}")
    
    def apply_migration(self, version: str) -> None:
        """
        Apply a specific migration.
        
        Args:
            version: Version to migrate to
        
        Raises:
            KeyError: If migration for version not registered
        """
        if version not in self.migrations:
            raise KeyError(f"No migration registered for version {version}")
        
        # Apply migration
        with Session(self.engine) as session:
            migration_func = self.migrations[version]
            migration_func(session)
            session.commit()
        
        # Update version
        self.set_version(version)
        logger.info(f"Applied migration to version {version}")
    
    def rollback_migration(self, version: str) -> None:
        """
        Roll back a specific migration.
        
        Args:
            version: Version to roll back
            
        Raises:
            KeyError: If rollback for version not registered
        """
        if version not in self.rollbacks:
            raise KeyError(f"No rollback registered for version {version}")
        
        # Get previous version
        with Session(self.engine) as session:
            result = session.execute(sqlalchemy.text(
                "SELECT version FROM schema_versions WHERE version != :version ORDER BY id DESC LIMIT 1"
            ), {"version": version})
            row = result.fetchone()
            
            if not row:
                previous_version = None
            else:
                previous_version = row[0]
        
        # Apply rollback
        with Session(self.engine) as session:
            rollback_func = self.rollbacks[version]
            rollback_func(session)
            session.commit()
        
        # Set version to previous
        if previous_version:
            self.set_version(previous_version)
            logger.info(f"Rolled back migration from {version} to {previous_version}")
        else:
            # Remove version record if no previous
            with Session(self.engine) as session:
                session.execute(sqlalchemy.text(
                    "DELETE FROM schema_versions WHERE version = :version"
                ), {"version": version})
                session.commit()
                logger.info(f"Rolled back migration from {version} (no previous version)")
    
    def run_migrations(self, target_version: Optional[str] = None) -> List[str]:
        """
        Run all registered migrations up to target_version.
        
        Args:
            target_version: Version to migrate to (if None, runs all migrations)
            
        Returns:
            List of versions that were applied
        """
        current_version = self.get_current_version()
        if not current_version:
            logger.info("No current version found, starting from scratch")
        else:
            logger.info(f"Current version: {current_version}")
        
        # Get sorted list of all versions
        all_versions = sorted(self.migrations.keys())
        if not all_versions:
            logger.info("No migrations registered")
            return []
        
        # Determine which versions to apply
        if target_version:
            if target_version not in all_versions:
                raise ValueError(f"Target version {target_version} not found in registered migrations")
            
            target_idx = all_versions.index(target_version)
            if current_version:
                current_idx = all_versions.index(current_version)
                if current_idx > target_idx:
                    # Downgrade
                    versions_to_apply = [(v, False) for v in all_versions[target_idx+1:current_idx+1]]
                    versions_to_apply.reverse()  # Roll back in reverse order
                else:
                    # Upgrade
                    versions_to_apply = [(v, True) for v in all_versions[current_idx+1:target_idx+1]]
            else:
                # No current version, apply all up to target
                versions_to_apply = [(v, True) for v in all_versions[:target_idx+1]]
        else:
            # Apply all migrations after current version
            if current_version and current_version in all_versions:
                current_idx = all_versions.index(current_version)
                versions_to_apply = [(v, True) for v in all_versions[current_idx+1:]]
            else:
                # No current version, apply all
                versions_to_apply = [(v, True) for v in all_versions]
        
        # Apply migrations
        applied_versions = []
        for version, is_upgrade in versions_to_apply:
            if is_upgrade:
                logger.info(f"Applying migration to {version}")
                self.apply_migration(version)
                applied_versions.append(version)
            else:
                logger.info(f"Rolling back migration from {version}")
                self.rollback_migration(version)
                applied_versions.append(f"rollback_{version}")
        
        logger.info(f"Applied {len(applied_versions)} migrations")
        return applied_versions


def get_migration_version() -> Optional[str]:
    """
    Get current schema version.
    
    Returns:
        str: Current version or None if no version set
    """
    manager = MigrationManager()
    return manager.get_current_version()


def run_migrations(target_version: Optional[str] = None) -> List[str]:
    """
    Run all pending migrations.
    
    Args:
        target_version: Version to migrate to (if None, runs all migrations)
        
    Returns:
        List of versions that were applied
    """
    manager = MigrationManager()
    # Pass kwargs explicitly to match the test's expectations
    return manager.run_migrations(target_version=target_version)


# Database Performance Functions

def get_performance_manager() -> Optional[DatabasePerformanceManager]:
    """
    Get the global performance manager.
    
    Returns:
        DatabasePerformanceManager instance or None if not initialized
    """
    global _PERFORMANCE_MANAGER
    
    # Initialize if not already done
    if _PERFORMANCE_MANAGER is None:
        engine = get_engine()
        _PERFORMANCE_MANAGER = DatabasePerformanceManager(engine)
        
    return _PERFORMANCE_MANAGER
    

def bulk_insert(table: str, data: List[Dict[str, Any]], batch_size: Optional[int] = None) -> int:
    """
    Perform a bulk insert operation with performance optimization.
    
    Args:
        table: Table name
        data: List of dictionaries with column values
        batch_size: Batch size (optional)
        
    Returns:
        Number of rows inserted
    """
    manager = get_performance_manager()
    
    if manager and hasattr(manager, 'bulk_optimizer') and manager.bulk_optimizer is not None:
        return manager.bulk_optimizer.bulk_insert(table, data, batch_size)
    else:
        # Fallback to manual bulk insert
        if not data:
            return 0
            
        # Use default batch size
        if batch_size is None:
            batch_size = 1000
            
        # Get column names
        columns = list(data[0].keys())
        
        # Prepare insert statement
        insert_stmt = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({', '.join([f':{col}' for col in columns])})"
        
        # Execute in batches
        rows_inserted = 0
        with Session(get_engine()) as session:
            for i in range(0, len(data), batch_size):
                batch = data[i:i+batch_size]
                session.execute(text(insert_stmt), batch)
                rows_inserted += len(batch)
            
            session.commit()
            
        return rows_inserted


def bulk_update(table: str, data: List[Dict[str, Any]], id_column: str, 
               batch_size: Optional[int] = None) -> int:
    """
    Perform a bulk update operation with performance optimization.
    
    Args:
        table: Table name
        data: List of dictionaries with column values
        id_column: Column name for ID/primary key
        batch_size: Batch size (optional)
        
    Returns:
        Number of rows updated
    """
    manager = get_performance_manager()
    
    if manager and hasattr(manager, 'bulk_optimizer') and manager.bulk_optimizer is not None:
        return manager.bulk_optimizer.bulk_update(table, data, id_column, batch_size)
    else:
        # Fallback implementation
        if not data:
            return 0
            
        # Use default batch size
        if batch_size is None:
            batch_size = 1000
            
        # Get update columns
        update_columns = [col for col in data[0].keys() if col != id_column]
        
        # Prepare update statement
        set_clause = ", ".join([f"{col} = :{col}" for col in update_columns])
        update_stmt = f"UPDATE {table} SET {set_clause} WHERE {id_column} = :{id_column}"
        
        # Execute in batches
        rows_updated = 0
        with Session(get_engine()) as session:
            for i in range(0, len(data), batch_size):
                batch = data[i:i+batch_size]
                for row in batch:
                    session.execute(text(update_stmt), row)
                    rows_updated += 1
                session.flush()
            
            session.commit()
            
        return rows_updated


def optimize_connection_pool(target_utilization: float = 0.75) -> bool:
    """
    Optimize the connection pool size based on usage patterns.
    
    Args:
        target_utilization: Target pool utilization (0.0-1.0)
        
    Returns:
        True if optimization was performed, False otherwise
    """
    manager = get_performance_manager()
    
    if manager and hasattr(manager, 'connection_pool') and manager.connection_pool is not None:
        manager.connection_pool.optimize_pool_size(target_utilization)
        return True
    
    return False


def get_recommended_isolation_level(operation_type: str) -> str:
    """
    Get a recommended isolation level for the given operation type.
    
    Args:
        operation_type: Type of operation ("read", "write", "report", etc.)
        
    Returns:
        Recommended isolation level
    """
    # Use the static method from TransactionManager
    return TransactionManager.get_recommended_isolation_level(operation_type)


def get_database_performance_stats() -> Dict[str, Any]:
    """
    Get comprehensive database performance statistics.
    
    Returns:
        Dictionary with performance stats from all components
    """
    manager = get_performance_manager()
    
    if manager:
        return manager.get_performance_stats()
    else:
        return {
            "status": "Performance monitoring not enabled",
            "enabled": False
        }