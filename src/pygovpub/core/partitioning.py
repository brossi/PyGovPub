"""
Database partitioning utilities for PyGovPub.

This module provides tools for creating and managing PostgreSQL table partitions,
which improve query performance by dividing large tables into smaller, 
more manageable pieces based on ranges, lists, or hashes.
"""

import logging
from typing import Dict, List, Any, Optional, Union
from datetime import date

from sqlalchemy import text
from sqlalchemy.engine import Engine

from pygovpub.core.database import get_engine

# Configure logging
logger = logging.getLogger(__name__)


def create_date_partitioned_table(
    table_name: str,
    partition_column: str,
    schema: Dict[str, str],
    engine: Optional[Engine] = None,
    create_partition_column_index: bool = False
) -> None:
    """
    Create a date-range partitioned table in PostgreSQL.
    
    Args:
        table_name: Name of the partitioned table to create
        partition_column: Column to use for partitioning (must be DATE type)
        schema: Dictionary of column definitions {"column_name": "column_type"}
        engine: SQLAlchemy engine (uses default engine if None)
        create_partition_column_index: Whether to create an index on the partition column
    
    Example:
        ```python
        create_date_partitioned_table(
            "bills_by_date",
            "introduced_date",
            {
                "id": "SERIAL",
                "title": "TEXT NOT NULL",
                "introduced_date": "DATE NOT NULL",
                "status": "TEXT NOT NULL"
            },
            create_partition_column_index=True
        )
        ```
    """
    engine = engine or get_engine()
    
    # Build column definitions
    column_defs = []
    has_primary_key = False
    
    for column_name, column_def in schema.items():
        column_defs.append(f"{column_name} {column_def}")
        if "PRIMARY KEY" in column_def:
            has_primary_key = True
    
    # Join column definitions with commas
    columns_sql = ",\n    ".join(column_defs)
    
    # Create partitioned table SQL
    sql = f"""
    CREATE TABLE {table_name} (
    {columns_sql}
    )
    PARTITION BY RANGE ({partition_column});
    """
    
    # Execute statement
    with engine.connect() as conn:
        conn.execute(text(sql))
        
        # Create index on partition column if requested
        if create_partition_column_index:
            index_name = f"idx_{table_name}_{partition_column}"
            index_sql = f"""
            CREATE INDEX {index_name} ON {table_name} ({partition_column});
            """
            conn.execute(text(index_sql))
        
        conn.commit()
    
    logger.info(f"Created date-partitioned table {table_name} on {partition_column}")


def create_date_partition(
    table_name: str,
    partition_name: str,
    start_date: date,
    end_date: date,
    engine: Optional[Engine] = None
) -> None:
    """
    Create a date range partition for a partitioned table.
    
    Args:
        table_name: Name of the parent partitioned table
        partition_name: Name for the new partition
        start_date: Start date for the partition (inclusive)
        end_date: End date for the partition (exclusive)
        engine: SQLAlchemy engine (uses default engine if None)
    
    Example:
        ```python
        create_date_partition(
            "bills_by_date",
            "bills_by_date_2022",
            date(2022, 1, 1),
            date(2023, 1, 1)
        )
        ```
    """
    engine = engine or get_engine()
    
    # Format dates as strings
    start_str = start_date.isoformat()
    end_str = end_date.isoformat()
    
    # Create partition SQL
    sql = f"""
    CREATE TABLE {partition_name} PARTITION OF {table_name}
    FOR VALUES FROM ('{start_str}') TO ('{end_str}');
    """
    
    # Execute statement
    with engine.connect() as conn:
        conn.execute(text(sql))
        conn.commit()
    
    logger.info(
        f"Created partition {partition_name} for {table_name} "
        f"from {start_date} to {end_date}"
    )


def create_list_partitioned_table(
    table_name: str,
    partition_column: str,
    schema: Dict[str, str],
    engine: Optional[Engine] = None
) -> None:
    """
    Create a list-partitioned table in PostgreSQL.
    
    Args:
        table_name: Name of the partitioned table to create
        partition_column: Column to use for partitioning
        schema: Dictionary of column definitions {"column_name": "column_type"}
        engine: SQLAlchemy engine (uses default engine if None)
    
    Example:
        ```python
        create_list_partitioned_table(
            "bills_by_type",
            "bill_type",
            {
                "id": "SERIAL",
                "title": "TEXT NOT NULL",
                "bill_type": "TEXT NOT NULL",
                "status": "TEXT NOT NULL"
            }
        )
        ```
    """
    engine = engine or get_engine()
    
    # Build column definitions
    column_defs = []
    has_primary_key = False
    
    for column_name, column_def in schema.items():
        column_defs.append(f"{column_name} {column_def}")
        if "PRIMARY KEY" in column_def:
            has_primary_key = True
    
    # Join column definitions with commas
    columns_sql = ",\n    ".join(column_defs)
    
    # Create partitioned table SQL
    sql = f"""
    CREATE TABLE {table_name} (
    {columns_sql}
    )
    PARTITION BY LIST ({partition_column});
    """
    
    # Execute statement
    with engine.connect() as conn:
        conn.execute(text(sql))
        conn.commit()
    
    logger.info(f"Created list-partitioned table {table_name} on {partition_column}")


def create_list_partition(
    table_name: str,
    partition_name: str,
    values: List[str],
    engine: Optional[Engine] = None
) -> None:
    """
    Create a list partition for a partitioned table.
    
    Args:
        table_name: Name of the parent partitioned table
        partition_name: Name for the new partition
        values: List of values for this partition
        engine: SQLAlchemy engine (uses default engine if None)
    
    Example:
        ```python
        create_list_partition(
            "bills_by_type",
            "bills_by_type_house",
            ["HR", "HRES", "HJRES"]
        )
        ```
    """
    engine = engine or get_engine()
    
    # Format values as comma-separated quoted strings
    values_sql = ", ".join(f"'{value}'" for value in values)
    
    # Create partition SQL
    sql = f"""
    CREATE TABLE {partition_name} PARTITION OF {table_name}
    FOR VALUES IN ({values_sql});
    """
    
    # Execute statement
    with engine.connect() as conn:
        conn.execute(text(sql))
        conn.commit()
    
    logger.info(
        f"Created partition {partition_name} for {table_name} "
        f"with values {values}"
    )


def create_range_partitioned_table(
    table_name: str,
    partition_column: str,
    schema: Dict[str, str],
    engine: Optional[Engine] = None
) -> None:
    """
    Create a range-partitioned table in PostgreSQL.
    
    Args:
        table_name: Name of the partitioned table to create
        partition_column: Column to use for partitioning
        schema: Dictionary of column definitions {"column_name": "column_type"}
        engine: SQLAlchemy engine (uses default engine if None)
    
    Example:
        ```python
        create_range_partitioned_table(
            "bills_by_congress",
            "congress",
            {
                "id": "SERIAL",
                "title": "TEXT NOT NULL",
                "congress": "INTEGER NOT NULL",
                "status": "TEXT NOT NULL"
            }
        )
        ```
    """
    engine = engine or get_engine()
    
    # Build column definitions
    column_defs = []
    has_primary_key = False
    
    for column_name, column_def in schema.items():
        column_defs.append(f"{column_name} {column_def}")
        if "PRIMARY KEY" in column_def:
            has_primary_key = True
    
    # Join column definitions with commas
    columns_sql = ",\n    ".join(column_defs)
    
    # Create partitioned table SQL
    sql = f"""
    CREATE TABLE {table_name} (
    {columns_sql}
    )
    PARTITION BY RANGE ({partition_column});
    """
    
    # Execute statement
    with engine.connect() as conn:
        conn.execute(text(sql))
        conn.commit()
    
    logger.info(f"Created range-partitioned table {table_name} on {partition_column}")


def create_range_partition(
    table_name: str,
    partition_name: str,
    start_value: Union[int, str, float],
    end_value: Union[int, str, float],
    engine: Optional[Engine] = None
) -> None:
    """
    Create a range partition for a partitioned table.
    
    Args:
        table_name: Name of the parent partitioned table
        partition_name: Name for the new partition
        start_value: Start value for the partition (inclusive)
        end_value: End value for the partition (exclusive)
        engine: SQLAlchemy engine (uses default engine if None)
    
    Example:
        ```python
        create_range_partition(
            "bills_by_congress",
            "bills_by_congress_116",
            116,
            117
        )
        ```
    """
    engine = engine or get_engine()
    
    # Format values based on type
    if isinstance(start_value, str):
        start_str = f"'{start_value}'"
    else:
        start_str = str(start_value)
    
    if isinstance(end_value, str):
        end_str = f"'{end_value}'"
    else:
        end_str = str(end_value)
    
    # Create partition SQL
    sql = f"""
    CREATE TABLE {partition_name} PARTITION OF {table_name}
    FOR VALUES FROM ({start_str}) TO ({end_str});
    """
    
    # Execute statement
    with engine.connect() as conn:
        conn.execute(text(sql))
        conn.commit()
    
    logger.info(
        f"Created partition {partition_name} for {table_name} "
        f"from {start_value} to {end_value}"
    )


def attach_partition(
    table_name: str,
    partition_table: str,
    for_values: str,
    engine: Optional[Engine] = None
) -> None:
    """
    Attach an existing table as a partition to a partitioned table.
    
    Args:
        table_name: Name of the parent partitioned table
        partition_table: Name of the table to attach as a partition
        for_values: Partition bounds expression (e.g., "FOR VALUES FROM (1) TO (10)")
        engine: SQLAlchemy engine (uses default engine if None)
    
    Example:
        ```python
        attach_partition(
            "bills_by_date",
            "old_bills_2019",
            "FOR VALUES FROM ('2019-01-01') TO ('2020-01-01')"
        )
        ```
    """
    engine = engine or get_engine()
    
    # Attach partition SQL
    sql = f"""
    ALTER TABLE {table_name} ATTACH PARTITION {partition_table} {for_values};
    """
    
    # Execute statement
    with engine.connect() as conn:
        conn.execute(text(sql))
        conn.commit()
    
    logger.info(f"Attached {partition_table} as partition of {table_name}")


def detach_partition(
    table_name: str,
    partition_table: str,
    engine: Optional[Engine] = None
) -> None:
    """
    Detach a partition from a partitioned table.
    
    Args:
        table_name: Name of the parent partitioned table
        partition_table: Name of the partition to detach
        engine: SQLAlchemy engine (uses default engine if None)
    
    Example:
        ```python
        detach_partition(
            "bills_by_date",
            "bills_by_date_2019"
        )
        ```
    """
    engine = engine or get_engine()
    
    # Detach partition SQL
    sql = f"""
    ALTER TABLE {table_name} DETACH PARTITION {partition_table};
    """
    
    # Execute statement
    with engine.connect() as conn:
        conn.execute(text(sql))
        conn.commit()
    
    logger.info(f"Detached {partition_table} from {table_name}")


def get_partition_info(
    table_name: str,
    engine: Optional[Engine] = None
) -> List[Dict[str, Any]]:
    """
    Get information about partitions for a partitioned table.
    
    Args:
        table_name: Name of the partitioned table
        engine: SQLAlchemy engine (uses default engine if None)
    
    Returns:
        List of dictionaries with partition information
    
    Example:
        ```python
        partitions = get_partition_info("bills_by_date")
        for p in partitions:
            print(f"{p['partition_name']}: {p['row_count']} rows")
        ```
    """
    engine = engine or get_engine()
    
    # Query for partition information
    sql = text("""
    SELECT
        child.relname AS partition_name,
        pg_catalog.pg_get_expr(child.relpartbound, child.oid, true) AS partition_expression,
        pg_catalog.obj_description(child.oid, 'pg_class') AS partition_description,
        child.reltuples::bigint AS row_estimate,
        pg_catalog.pg_size_pretty(pg_catalog.pg_table_size(child.oid)) AS partition_size,
        pg_catalog.pg_size_pretty(pg_catalog.pg_indexes_size(child.oid)) AS index_size
    FROM pg_catalog.pg_inherits
    JOIN pg_catalog.pg_class parent ON pg_inherits.inhparent = parent.oid
    JOIN pg_catalog.pg_class child ON pg_inherits.inhrelid = child.oid
    JOIN pg_catalog.pg_namespace nmsp_parent ON nmsp_parent.oid = parent.relnamespace
    JOIN pg_catalog.pg_namespace nmsp_child ON nmsp_child.oid = child.relnamespace
    WHERE parent.relname = :table_name
    ORDER BY child.relname;
    """)
    
    # Execute query
    with engine.connect() as conn:
        result = conn.execute(sql, {"table_name": table_name})
        partitions = [dict(row) for row in result]
    
    # Get actual row counts for each partition
    for partition in partitions:
        count_sql = text(f"SELECT COUNT(*) FROM {partition['partition_name']}")
        with engine.connect() as conn:
            count_result = conn.execute(count_sql)
            row_count = count_result.scalar()
            partition['row_count'] = row_count
    
    return partitions


def create_partition_maintenance_function(
    table_name: str,
    partition_type: str = "date",
    interval: str = "month",
    retention_periods: int = 24,
    engine: Optional[Engine] = None
) -> None:
    """
    Create a stored function to automatically maintain partitions.
    
    Args:
        table_name: Name of the partitioned table
        partition_type: Type of partitioning ('date', 'range', 'list')
        interval: Interval for date partitions ('month', 'year', 'day')
        retention_periods: Number of periods to retain (older partitions are detached)
        engine: SQLAlchemy engine (uses default engine if None)
    
    Example:
        ```python
        create_partition_maintenance_function(
            "bills_by_date",
            partition_type="date",
            interval="month",
            retention_periods=36  # Keep 3 years of data
        )
        ```
    """
    engine = engine or get_engine()
    
    function_name = f"maintain_{table_name}_partitions"
    
    # Create function SQL
    sql = f"""
    CREATE OR REPLACE FUNCTION {function_name}()
    RETURNS void AS $$
    DECLARE
        partition_name text;
        start_date date;
        end_date date;
        current_date date := CURRENT_DATE;
        retention_date date;
        interval_type text := '{interval}';
        oldest_to_keep date;
    BEGIN
        -- Create future partitions
        FOR i IN 0..3 LOOP  -- Create 3 future partitions
            IF interval_type = 'month' THEN
                start_date := date_trunc('month', current_date) + (i || ' month')::interval;
                end_date := date_trunc('month', start_date) + '1 month'::interval;
            ELSIF interval_type = 'year' THEN
                start_date := date_trunc('year', current_date) + (i || ' year')::interval;
                end_date := date_trunc('year', start_date) + '1 year'::interval;
            ELSIF interval_type = 'day' THEN
                start_date := date_trunc('day', current_date) + (i || ' day')::interval;
                end_date := date_trunc('day', start_date) + '1 day'::interval;
            END IF;
            
            -- Format partition name based on interval
            IF interval_type = 'month' THEN
                partition_name := '{table_name}_' || to_char(start_date, 'YYYY_MM');
            ELSIF interval_type = 'year' THEN
                partition_name := '{table_name}_' || to_char(start_date, 'YYYY');
            ELSIF interval_type = 'day' THEN
                partition_name := '{table_name}_' || to_char(start_date, 'YYYY_MM_DD');
            END IF;
            
            -- Check if partition exists
            PERFORM 1
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE c.relname = partition_name
              AND n.nspname = current_schema();
            
            -- Create if it doesn't exist
            IF NOT FOUND THEN
                EXECUTE 'CREATE TABLE ' || partition_name || ' PARTITION OF {table_name}
                          FOR VALUES FROM (''' || start_date || ''') TO (''' || end_date || ''')';
                RAISE NOTICE 'Created partition %', partition_name;
            END IF;
        END LOOP;
        
        -- Calculate retention date
        IF interval_type = 'month' THEN
            retention_date := date_trunc('month', current_date) - ({retention_periods} || ' month')::interval;
        ELSIF interval_type = 'year' THEN
            retention_date := date_trunc('year', current_date) - ({retention_periods} || ' year')::interval;
        ELSIF interval_type = 'day' THEN
            retention_date := date_trunc('day', current_date) - ({retention_periods} || ' day')::interval;
        END IF;
        
        -- Find and detach old partitions
        FOR partition_name IN
            SELECT c.relname
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            JOIN pg_inherits i ON i.inhrelid = c.oid
            JOIN pg_class parent ON parent.oid = i.inhparent
            WHERE parent.relname = '{table_name}'
              AND n.nspname = current_schema()
              AND pg_get_expr(c.relpartbound, c.oid) < 'FOR VALUES FROM (''' || retention_date || ''')'
        LOOP
            EXECUTE 'ALTER TABLE {table_name} DETACH PARTITION ' || partition_name;
            RAISE NOTICE 'Detached old partition %', partition_name;
        END LOOP;
    END;
    $$ LANGUAGE plpgsql;
    """
    
    # Execute statement
    with engine.connect() as conn:
        conn.execute(text(sql))
        conn.commit()
    
    logger.info(f"Created partition maintenance function for {table_name}")
    
    # Create scheduling trigger (runs once per day)
    trigger_sql = f"""
    CREATE OR REPLACE FUNCTION trigger_{function_name}()
    RETURNS trigger AS $$
    BEGIN
        PERFORM {function_name}();
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    
    DROP TRIGGER IF EXISTS {table_name}_partition_maintenance ON {table_name};
    CREATE TRIGGER {table_name}_partition_maintenance
    AFTER INSERT ON {table_name}
    FOR EACH STATEMENT
    WHEN ((current_setting('cron.partition_maintenance_enabled', true) = 'on'))
    EXECUTE FUNCTION trigger_{function_name}();
    """
    
    with engine.connect() as conn:
        conn.execute(text(trigger_sql))
        conn.commit()
    
    logger.info(f"Created partition maintenance trigger for {table_name}")


def setup_partitioning_environment(engine: Optional[Engine] = None) -> None:
    """
    Set up the database environment for partitioning.
    
    Ensures necessary extensions and configurations are in place.
    
    Args:
        engine: SQLAlchemy engine (uses default engine if None)
    """
    engine = engine or get_engine()
    
    # Create custom settings for partition maintenance
    setup_sql = """
    -- Create custom setting to control partition maintenance
    SELECT set_config('cron.partition_maintenance_enabled', 'off', false);
    
    -- Create function to toggle setting
    CREATE OR REPLACE FUNCTION toggle_partition_maintenance(enabled boolean)
    RETURNS void AS $$
    BEGIN
        IF enabled THEN
            PERFORM set_config('cron.partition_maintenance_enabled', 'on', false);
        ELSE
            PERFORM set_config('cron.partition_maintenance_enabled', 'off', false);
        END IF;
    END;
    $$ LANGUAGE plpgsql;
    
    -- Create utility function to move old partitions to separate tablespace
    CREATE OR REPLACE FUNCTION move_partition_to_archive(
        partition_table text,
        archive_tablespace text DEFAULT 'pg_default'
    )
    RETURNS void AS $$
    BEGIN
        EXECUTE format('ALTER TABLE %I SET TABLESPACE %I', partition_table, archive_tablespace);
        RAISE NOTICE 'Moved partition % to archive tablespace %', partition_table, archive_tablespace;
    END;
    $$ LANGUAGE plpgsql;
    
    -- Create partition performance statistics view
    CREATE OR REPLACE VIEW partition_performance_stats AS
    SELECT
        schemaname,
        relname AS partition_name,
        n_live_tup AS row_count,
        pg_size_pretty(pg_total_relation_size(schemaname || '.' || relname)) AS total_size,
        pg_size_pretty(pg_relation_size(schemaname || '.' || relname)) AS table_size,
        pg_size_pretty(pg_indexes_size(schemaname || '.' || relname)) AS index_size,
        pg_stat_get_numscans(relid) AS scan_count,
        pg_stat_get_tuples_inserted(relid) AS inserts,
        pg_stat_get_tuples_updated(relid) AS updates,
        pg_stat_get_tuples_deleted(relid) AS deletes
    FROM pg_stat_user_tables
    WHERE relname ~ '_[0-9]+'  -- Naming pattern for partitions
    ORDER BY relname;
    """
    
    try:
        with engine.connect() as conn:
            conn.execute(text(setup_sql))
            conn.commit()
        logger.info("Set up partitioning environment")
    except Exception as e:
        logger.error(f"Failed to set up partitioning environment: {e}")
        logger.info("Basic partitioning functionality will still be available")


# Initialize partitioning environment when this module is imported
engine = get_engine()
try:
    if engine.dialect.name == 'postgresql':
        setup_partitioning_environment(engine)
except Exception as e:
    logger.error(f"Failed to initialize partitioning environment: {e}")
    logger.info("Basic partitioning functionality will still be available")