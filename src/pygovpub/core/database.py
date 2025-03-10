"""
Database connection management for PyGovPub.

This module handles database connections, session management, and transactions.
It provides both synchronous and asynchronous database interfaces.
"""

import os
import logging
from typing import Optional, Dict, Callable, List, Any, AsyncGenerator, Generator, Union
from datetime import datetime
from contextlib import contextmanager, asynccontextmanager

import sqlalchemy
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlmodel import Session, SQLModel, create_engine

# Configure logging
logger = logging.getLogger(__name__)

# Global engine instance (initialized on first use)
_ENGINE = None
_ASYNC_ENGINE = None

# Database URL from environment variables (or use default for development)
DATABASE_URL = None


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
            return "sqlite:///:memory:"
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


def init_db(connection_url: Optional[str] = None, echo: bool = False) -> sqlalchemy.engine.Engine:
    """
    Initialize database engine.
    
    Args:
        connection_url: Database connection URL (if None, uses environment variables)
        echo: Whether to echo SQL statements
        
    Returns:
        SQLAlchemy engine instance
    """
    global DATABASE_URL
    
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
            max_overflow=10      # Allow up to 10 additional connections in high demand
        )
    
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


def get_session() -> Session:
    """
    Get a new database session.
    
    Returns:
        SQLModel Session
    """
    engine = get_engine()
    return Session(engine)


@contextmanager
def with_transaction() -> Generator[Session, None, None]:
    """
    Context manager for database transactions.
    
    Automatically commits if no exceptions occur, or rolls back on exceptions.
    
    Yields:
        SQLModel Session
    """
    session = get_session()
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
async def with_async_transaction() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager for async database transactions.
    
    Automatically commits if no exceptions occur, or rolls back on exceptions.
    
    Yields:
        AsyncSession
    """
    async with get_async_session() as session:
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