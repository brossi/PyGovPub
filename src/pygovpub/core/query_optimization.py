"""
Query optimization utilities for PyGovPub database operations.

This module provides tools for monitoring, analyzing, and optimizing database queries
using SQLAlchemy's capabilities and PostgreSQL-specific optimizations.
"""

import logging
import time
import functools
import statistics
from typing import Dict, List, Optional, Any, Callable, Union, TypeVar, cast
from contextlib import contextmanager
from datetime import datetime, timedelta

import sqlalchemy
from sqlalchemy import event, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, Query, selectinload, joinedload, contains_eager
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select, Executable
from sqlalchemy.sql.expression import BinaryExpression, ClauseElement

from pygovpub.core.database import get_engine

# Configure logging
logger = logging.getLogger(__name__)

# Type variables
T = TypeVar('T')
F = TypeVar('F', bound=Callable[..., Any])

# Global query statistics storage
query_stats: Dict[str, Dict[str, Any]] = {}


@event.listens_for(Engine, "before_cursor_execute")
def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    """
    SQLAlchemy event that fires before SQL query execution.
    
    Args:
        conn: Connection object
        cursor: Database cursor
        statement: SQL statement
        parameters: Query parameters
        context: Execution context
        executemany: Whether executing multiple statements
    """
    # Store execution start time in context for later retrieval
    context._query_start_time = time.time()
    
    # Log SQL with parameters for debugging (only in debug mode)
    logger.debug(f"Executing SQL: {statement}")
    logger.debug(f"With parameters: {parameters}")


@event.listens_for(Engine, "after_cursor_execute")
def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    """
    SQLAlchemy event that fires after SQL query execution.
    
    Args:
        conn: Connection object
        cursor: Database cursor
        statement: SQL statement
        parameters: Query parameters
        context: Execution context
        executemany: Whether executing multiple statements
    """
    # Calculate execution time
    execution_time = time.time() - context._query_start_time
    
    # Normalize statement by removing extra whitespace for better grouping
    normalized_stmt = ' '.join(statement.split())
    
    # Update stats for this query
    if normalized_stmt not in query_stats:
        query_stats[normalized_stmt] = {
            'count': 0,
            'total_time': 0.0,
            'min_time': float('inf'),
            'max_time': 0.0,
            'times': [],
            'last_executed': datetime.now(),
            'parameters_sample': [],
        }
    
    stats = query_stats[normalized_stmt]
    stats['count'] += 1
    stats['total_time'] += execution_time
    stats['min_time'] = min(stats['min_time'], execution_time)
    stats['max_time'] = max(stats['max_time'], execution_time)
    stats['times'].append(execution_time)
    stats['last_executed'] = datetime.now()
    
    # Keep a sample of parameters for analysis (limit to 5 samples)
    if len(stats['parameters_sample']) < 5:
        stats['parameters_sample'].append(parameters)
    
    # Log slow queries (>100ms)
    if execution_time > 0.1:
        logger.warning(f"Slow query ({execution_time:.4f}s): {normalized_stmt}")


def reset_query_stats():
    """
    Reset all collected query statistics.
    """
    global query_stats
    query_stats = {}
    logger.info("Query statistics have been reset")


def get_query_stats(min_count: int = 1, min_avg_time: float = 0.0) -> Dict[str, Dict[str, Any]]:
    """
    Get collected query statistics, optionally filtered.
    
    Args:
        min_count: Minimum execution count to include
        min_avg_time: Minimum average execution time to include (in seconds)
    
    Returns:
        Dictionary of query statistics
    """
    result = {}
    
    for stmt, stats in query_stats.items():
        avg_time = stats['total_time'] / stats['count'] if stats['count'] > 0 else 0
        
        if stats['count'] >= min_count and avg_time >= min_avg_time:
            # Calculate percentiles if we have enough data
            if len(stats['times']) >= 5:
                percentiles = {
                    'p50': statistics.median(stats['times']),
                    'p90': statistics.quantiles(stats['times'], n=10)[8],
                    'p95': statistics.quantiles(stats['times'], n=20)[18],
                    'p99': statistics.quantiles(stats['times'], n=100)[98] if len(stats['times']) >= 100 else None
                }
            else:
                percentiles = {'p50': None, 'p90': None, 'p95': None, 'p99': None}
            
            # Create result with computed metrics
            result[stmt] = {
                'count': stats['count'],
                'total_time': stats['total_time'],
                'avg_time': avg_time,
                'min_time': stats['min_time'],
                'max_time': stats['max_time'],
                'last_executed': stats['last_executed'],
                'percentiles': percentiles
            }
    
    return result


@contextmanager
def query_analyzer(query_name: str = None):
    """
    Context manager for analyzing individual query performance.
    
    Args:
        query_name: Optional name for the query (defaults to caller function name)
    
    Example:
        ```python
        with query_analyzer("find_bill"):
            bill = session.query(Bill).filter(Bill.id == bill_id).first()
        ```
    """
    start_time = time.time()
    
    # Get caller function name if query_name not provided
    if query_name is None:
        import inspect
        caller_frame = inspect.currentframe().f_back
        query_name = caller_frame.f_code.co_name if caller_frame else "unknown_query"
    
    yield
    
    # Calculate execution time
    execution_time = time.time() - start_time
    
    # Log performance information
    logger.info(f"Query '{query_name}' executed in {execution_time:.4f}s")


def with_query_analysis(func: F) -> F:
    """
    Decorator to analyze query performance.
    
    Args:
        func: Function to decorate
    
    Returns:
        Decorated function with query performance analysis
    
    Example:
        ```python
        @with_query_analysis
        def get_bill_by_id(session, bill_id):
            return session.query(Bill).filter(Bill.id == bill_id).first()
        ```
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        with query_analyzer(func.__name__):
            return func(*args, **kwargs)
    
    return cast(F, wrapper)


def explain_query(session: Session, query: Union[Query, Select, str], analyze: bool = False) -> List[Dict[str, Any]]:
    """
    Get PostgreSQL EXPLAIN (and optionally ANALYZE) output for a query.
    
    Args:
        session: SQLAlchemy session
        query: Query to explain (SQLAlchemy Query, Select, or raw SQL string)
        analyze: Whether to run ANALYZE (actually executes the query)
    
    Returns:
        List of plan nodes from EXPLAIN output
    
    Example:
        ```python
        query = session.query(Bill).filter(Bill.congress == 117)
        plan = explain_query(session, query, analyze=True)
        for node in plan:
            print(f"{node['Node Type']} - Cost: {node['Total Cost']}")
        ```
    """
    # Convert query to SQL string
    if isinstance(query, Query):
        sql = str(query.statement.compile(
            dialect=session.bind.dialect,
            compile_kwargs={"literal_binds": True}
        ))
    elif isinstance(query, Select):
        sql = str(query.compile(
            dialect=session.bind.dialect,
            compile_kwargs={"literal_binds": True}
        ))
    else:
        sql = query
    
    # Build EXPLAIN command
    explain_options = ['VERBOSE', 'FORMAT JSON']
    if analyze:
        explain_options.append('ANALYZE')
    
    explain_sql = f"EXPLAIN ({', '.join(explain_options)}) {sql}"
    
    # Execute EXPLAIN
    result = session.execute(text(explain_sql))
    explain_result = result.scalar()
    
    # Parse JSON output
    if isinstance(explain_result, str):
        import json
        return json.loads(explain_result)
    
    return explain_result[0]['Plan']


def optimize_query_loading(query: Union[Query, Select], model_class: Any) -> Union[Query, Select]:
    """
    Apply loading optimizations based on model relationships.
    
    This function examines the model's relationships and applies appropriate
    loading strategies (selectinload, joinedload) to optimize query performance.
    
    Args:
        query: SQLAlchemy Query or Select object to optimize
        model_class: Model class being queried
    
    Returns:
        Optimized Query or Select object
    
    Example:
        ```python
        # Using SQLModel with Select
        stmt = select(Bill)
        optimized = optimize_query_loading(stmt, Bill)
        results = session.exec(optimized).all()
        
        # Using SQLAlchemy Query
        query = session.query(Bill)
        optimized = optimize_query_loading(query, Bill)
        results = optimized.all()
        ```
    """
    # Get model relationships
    inspector = inspect(model_class)
    relationships = inspector.relationships
    
    # Define loading options
    options = []
    
    # Determine loading strategies based on relationship cardinality
    for name, relationship in relationships.items():
        # Skip non-persistent relationships
        if not relationship.persist_selectable:
            continue
        
        # Use selectinload for one-to-many and many-to-many relationships
        # This performs a separate query to load related objects efficiently
        if relationship.uselist:
            options.append(selectinload(getattr(model_class, name)))
        
        # Use joinedload for many-to-one relationships
        # This performs a JOIN in the original query
        else:
            options.append(joinedload(getattr(model_class, name)))
    
    # Apply options based on query type
    if isinstance(query, Query):
        # SQLAlchemy Query object
        for option in options:
            query = query.options(option)
        return query
    else:
        # SQLAlchemy Select object
        for option in options:
            query = query.options(option)
        return query


def create_composite_index(table_name: str, column_names: List[str], index_name: Optional[str] = None,
                          unique: bool = False, engine: Optional[Engine] = None) -> None:
    """
    Create a composite index on specified columns.
    
    Args:
        table_name: Name of the table
        column_names: List of column names to include in index
        index_name: Optional name for the index (auto-generated if None)
        unique: Whether the index should enforce uniqueness
        engine: SQLAlchemy engine (uses default engine if None)
    
    Example:
        ```python
        create_composite_index('bills', ['congress', 'bill_type', 'bill_number'], unique=True)
        ```
    """
    engine = engine or get_engine()
    
    # Generate index name if not provided
    if index_name is None:
        index_name = f"idx_{table_name}_{'_'.join(column_names)}"
    
    # Create index SQL
    unique_clause = "UNIQUE" if unique else ""
    columns_clause = ", ".join(column_names)
    sql = f"CREATE {unique_clause} INDEX {index_name} ON {table_name} ({columns_clause})"
    
    # Execute statement
    with engine.connect() as conn:
        conn.execute(text(sql))
        conn.commit()
    
    logger.info(f"Created composite index {index_name} on {table_name}({columns_clause})")


def create_functional_index(table_name: str, expression: str, index_name: Optional[str] = None,
                           engine: Optional[Engine] = None) -> None:
    """
    Create a functional index based on an expression.
    
    Args:
        table_name: Name of the table
        expression: SQL expression for the index
        index_name: Optional name for the index (auto-generated if None)
        engine: SQLAlchemy engine (uses default engine if None)
    
    Example:
        ```python
        create_functional_index('bills', 'LOWER(title)', 'idx_bills_lower_title')
        ```
    """
    engine = engine or get_engine()
    
    # Generate index name if not provided
    if index_name is None:
        # Create a sanitized index name from the expression
        sanitized = ''.join(c if c.isalnum() else '_' for c in expression)
        index_name = f"idx_{table_name}_{sanitized[:30]}"
    
    # Create index SQL
    sql = f"CREATE INDEX {index_name} ON {table_name} ({expression})"
    
    # Execute statement
    with engine.connect() as conn:
        conn.execute(text(sql))
        conn.commit()
    
    logger.info(f"Created functional index {index_name} on {table_name}({expression})")


def create_partial_index(table_name: str, column_names: List[str], condition: str, 
                        index_name: Optional[str] = None, engine: Optional[Engine] = None) -> None:
    """
    Create a partial index that only indexes rows matching a condition.
    
    Args:
        table_name: Name of the table
        column_names: List of column names to include in index
        condition: SQL WHERE condition for the partial index
        index_name: Optional name for the index (auto-generated if None)
        engine: SQLAlchemy engine (uses default engine if None)
    
    Example:
        ```python
        create_partial_index('bills', ['introduced_date'], "status = 'INTRODUCED'")
        ```
    """
    engine = engine or get_engine()
    
    # Generate index name if not provided
    if index_name is None:
        columns_part = '_'.join(column_names)
        condition_part = condition.replace(' ', '_').replace('=', 'eq').replace('>', 'gt').replace('<', 'lt')
        index_name = f"idx_{table_name}_{columns_part}_{condition_part[:20]}"
    
    # Create index SQL
    columns_clause = ", ".join(column_names)
    sql = f"CREATE INDEX {index_name} ON {table_name} ({columns_clause}) WHERE {condition}"
    
    # Execute statement
    with engine.connect() as conn:
        conn.execute(text(sql))
        conn.commit()
    
    logger.info(f"Created partial index {index_name} on {table_name}({columns_clause}) WHERE {condition}")


def create_btree_index(table_name: str, column_names: List[str], index_name: Optional[str] = None,
                     engine: Optional[Engine] = None) -> None:
    """
    Create a B-tree index explicitly (this is the default PostgreSQL index type).
    
    Args:
        table_name: Name of the table
        column_names: List of column names to include in index
        index_name: Optional name for the index (auto-generated if None)
        engine: SQLAlchemy engine (uses default engine if None)
    
    Example:
        ```python
        create_btree_index('bills', ['introduced_date'])
        ```
    """
    engine = engine or get_engine()
    
    # Generate index name if not provided
    if index_name is None:
        index_name = f"idx_{table_name}_{'_'.join(column_names)}_btree"
    
    # Create index SQL
    columns_clause = ", ".join(column_names)
    sql = f"CREATE INDEX {index_name} ON {table_name} USING btree ({columns_clause})"
    
    # Execute statement
    with engine.connect() as conn:
        conn.execute(text(sql))
        conn.commit()
    
    logger.info(f"Created B-tree index {index_name} on {table_name}({columns_clause})")


def create_hash_index(table_name: str, column_name: str, index_name: Optional[str] = None,
                    engine: Optional[Engine] = None) -> None:
    """
    Create a hash index for equality operations on a single column.
    
    Args:
        table_name: Name of the table
        column_name: Column name to include in index (hash indexes only support one column)
        index_name: Optional name for the index (auto-generated if None)
        engine: SQLAlchemy engine (uses default engine if None)
    
    Example:
        ```python
        create_hash_index('bills', 'bill_id')
        ```
    """
    engine = engine or get_engine()
    
    # Generate index name if not provided
    if index_name is None:
        index_name = f"idx_{table_name}_{column_name}_hash"
    
    # Create index SQL
    sql = f"CREATE INDEX {index_name} ON {table_name} USING hash ({column_name})"
    
    # Execute statement
    with engine.connect() as conn:
        conn.execute(text(sql))
        conn.commit()
    
    logger.info(f"Created hash index {index_name} on {table_name}({column_name})")


def create_gin_index(table_name: str, column_name: str, index_name: Optional[str] = None,
                   index_operator_class: Optional[str] = None, engine: Optional[Engine] = None) -> None:
    """
    Create a GIN (Generalized Inverted Index) index for JSONB, arrays, or full-text search.
    
    Args:
        table_name: Name of the table
        column_name: Column name to include in index
        index_name: Optional name for the index (auto-generated if None)
        index_operator_class: Optional operator class (e.g., 'jsonb_path_ops' for JSONB)
        engine: SQLAlchemy engine (uses default engine if None)
    
    Example:
        ```python
        create_gin_index('bills', 'metadata', index_operator_class='jsonb_path_ops')
        ```
    """
    engine = engine or get_engine()
    
    # Generate index name if not provided
    if index_name is None:
        index_name = f"idx_{table_name}_{column_name}_gin"
    
    # Add operator class if provided
    if index_operator_class:
        column_spec = f"{column_name} {index_operator_class}"
    else:
        column_spec = column_name
    
    # Create index SQL
    sql = f"CREATE INDEX {index_name} ON {table_name} USING gin ({column_spec})"
    
    # Execute statement
    with engine.connect() as conn:
        conn.execute(text(sql))
        conn.commit()
    
    logger.info(f"Created GIN index {index_name} on {table_name}({column_spec})")


def create_gist_index(table_name: str, column_name: str, index_name: Optional[str] = None,
                    engine: Optional[Engine] = None) -> None:
    """
    Create a GiST (Generalized Search Tree) index for geometry, range types, or exclusion constraints.
    
    Args:
        table_name: Name of the table
        column_name: Column name to include in index
        index_name: Optional name for the index (auto-generated if None)
        engine: SQLAlchemy engine (uses default engine if None)
    
    Example:
        ```python
        create_gist_index('congressional_districts', 'geometry')
        ```
    """
    engine = engine or get_engine()
    
    # Generate index name if not provided
    if index_name is None:
        index_name = f"idx_{table_name}_{column_name}_gist"
    
    # Create index SQL
    sql = f"CREATE INDEX {index_name} ON {table_name} USING gist ({column_name})"
    
    # Execute statement
    with engine.connect() as conn:
        conn.execute(text(sql))
        conn.commit()
    
    logger.info(f"Created GiST index {index_name} on {table_name}({column_name})")


def get_index_info(table_name: str, engine: Optional[Engine] = None) -> List[Dict[str, Any]]:
    """
    Get information about indexes on a table.
    
    Args:
        table_name: Name of the table
        engine: SQLAlchemy engine (uses default engine if None)
    
    Returns:
        List of dictionaries with index information
    
    Example:
        ```python
        indexes = get_index_info('bills')
        for idx in indexes:
            print(f"{idx['index_name']}: {idx['index_type']} on {idx['column_names']}")
        ```
    """
    engine = engine or get_engine()
    
    # Query for index information
    sql = text("""
    SELECT
        i.relname AS index_name,
        a.attname AS column_name,
        idx.indisunique AS is_unique,
        idx.indisprimary AS is_primary,
        am.amname AS index_type,
        pg_get_indexdef(idx.indexrelid) AS index_definition,
        idx.indpred IS NOT NULL AS is_partial,
        pg_size_pretty(pg_relation_size(i.oid)) AS index_size
    FROM
        pg_index idx
    JOIN pg_class i ON i.oid = idx.indexrelid
    JOIN pg_class t ON t.oid = idx.indrelid
    JOIN pg_namespace n ON n.oid = t.relnamespace
    JOIN pg_am am ON am.oid = i.relam
    JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(idx.indkey)
    WHERE
        t.relname = :table_name
    ORDER BY
        i.relname, a.attnum;
    """)
    
    # Execute query
    with engine.connect() as conn:
        result = conn.execute(sql, {"table_name": table_name})
        rows = result.fetchall()
    
    # Group columns by index
    indexes = {}
    for row in rows:
        row_dict = dict(row._mapping)
        idx_name = row_dict['index_name']
        
        if idx_name not in indexes:
            indexes[idx_name] = {
                'index_name': idx_name,
                'is_unique': row_dict['is_unique'],
                'is_primary': row_dict['is_primary'],
                'index_type': row_dict['index_type'],
                'index_definition': row_dict['index_definition'],
                'is_partial': row_dict['is_partial'],
                'index_size': row_dict['index_size'],
                'column_names': []
            }
        
        indexes[idx_name]['column_names'].append(row_dict['column_name'])
    
    return list(indexes.values())


def drop_index(index_name: str, cascade: bool = False, if_exists: bool = True, 
             engine: Optional[Engine] = None) -> None:
    """
    Drop an index.
    
    Args:
        index_name: Name of the index to drop
        cascade: Whether to cascade the drop to dependent objects
        if_exists: Whether to include IF EXISTS clause
        engine: SQLAlchemy engine (uses default engine if None)
    
    Example:
        ```python
        drop_index('idx_bills_congress_bill_type_bill_number')
        ```
    """
    engine = engine or get_engine()
    
    # Build SQL
    if_exists_clause = "IF EXISTS" if if_exists else ""
    cascade_clause = "CASCADE" if cascade else ""
    sql = f"DROP INDEX {if_exists_clause} {index_name} {cascade_clause}"
    
    # Execute statement
    with engine.connect() as conn:
        conn.execute(text(sql))
        conn.commit()
    
    logger.info(f"Dropped index {index_name}")


def create_index_maintenance_function(engine: Optional[Engine] = None) -> None:
    """
    Create a function to analyze and maintain indexes.
    
    This function creates a PostgreSQL function that can be called to:
    1. Identify unused indexes
    2. Suggest indexes based on query patterns
    3. Rebuild bloated indexes
    
    Args:
        engine: SQLAlchemy engine (uses default engine if None)
    
    Example:
        ```python
        create_index_maintenance_function()
        # Later, in SQL: SELECT maintain_indexes();
        ```
    """
    engine = engine or get_engine()
    
    # Create function SQL
    sql = """
    CREATE OR REPLACE FUNCTION maintain_indexes(
        min_index_size_mb integer DEFAULT 10,
        rebuild_bloat_percentage integer DEFAULT 30
    )
    RETURNS TABLE(
        action text,
        object_name text,
        details text
    ) AS $$
    DECLARE
        index_record record;
        bloat_record record;
        unused_record record;
        usage_record record;
    BEGIN
        -- Find unused indexes (no scans)
        FOR unused_record IN
            SELECT
                idx.indexrelid::regclass AS index_name,
                idx.indrelid::regclass AS table_name,
                pg_size_pretty(pg_relation_size(idx.indexrelid)) AS index_size,
                pg_stat_get_numscans(idx.indexrelid) AS index_scans
            FROM pg_index idx
            JOIN pg_stat_user_indexes stat ON idx.indexrelid = stat.indexrelid
            WHERE idx.indisprimary = false
              AND idx.indisunique = false
              AND stat.idx_scan = 0
              AND pg_relation_size(idx.indexrelid) / (1024*1024) >= min_index_size_mb
            ORDER BY pg_relation_size(idx.indexrelid) DESC
        LOOP
            action := 'DROP_UNUSED_INDEX';
            object_name := unused_record.index_name::text;
            details := format('Table: %s, Size: %s, Scans: %s', 
                        unused_record.table_name, 
                        unused_record.index_size, 
                        unused_record.index_scans);
            RETURN NEXT;
        END LOOP;
        
        -- Find bloated indexes
        FOR bloat_record IN
            SELECT
                idx.indexrelid::regclass AS index_name,
                idx.indrelid::regclass AS table_name,
                pg_size_pretty(pg_relation_size(idx.indexrelid)) AS index_size,
                round(
                    (pgstatindex(idx.indexrelid::text)).avg_leaf_density
                ) AS density
            FROM pg_index idx
            WHERE idx.indisvalid = true
            AND pg_relation_size(idx.indexrelid) / (1024*1024) >= min_index_size_mb
            ORDER BY density ASC, pg_relation_size(idx.indexrelid) DESC
        LOOP
            -- If density is too low (high bloat)
            IF bloat_record.density < (100 - rebuild_bloat_percentage) THEN
                action := 'REBUILD_BLOATED_INDEX';
                object_name := bloat_record.index_name::text;
                details := format('Table: %s, Size: %s, Density: %s%%', 
                            bloat_record.table_name, 
                            bloat_record.index_size, 
                            bloat_record.density);
                RETURN NEXT;
            END IF;
        END LOOP;
        
        -- Find missing indexes (tables with sequential scans)
        FOR usage_record IN
            SELECT
                schemaname || '.' || relname AS table_name,
                pg_size_pretty(pg_relation_size(schemaname || '.' || relname)) AS table_size,
                seq_scan,
                idx_scan,
                n_live_tup AS row_count
            FROM pg_stat_user_tables
            WHERE seq_scan > 0
            AND seq_scan > idx_scan
            AND n_live_tup > 1000
            ORDER BY n_live_tup * seq_scan DESC
        LOOP
            action := 'CONSIDER_INDEX';
            object_name := usage_record.table_name::text;
            details := format('Size: %s, Seq scans: %s, Index scans: %s, Rows: %s', 
                        usage_record.table_size, 
                        usage_record.seq_scan, 
                        usage_record.idx_scan, 
                        usage_record.row_count);
            RETURN NEXT;
        END LOOP;
        
        RETURN;
    END;
    $$ LANGUAGE plpgsql;
    """
    
    # Execute statement
    with engine.connect() as conn:
        conn.execute(text(sql))
        conn.commit()
    
    logger.info("Created index maintenance function")


# Initialize event listeners when this module is imported
engine = get_engine()
logger.info("Query optimization module initialized with performance tracking")