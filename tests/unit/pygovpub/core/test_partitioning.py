"""
Tests for database partitioning functionality.

This module contains unit tests for the PostgreSQL table partitioning features.
"""

import pytest
from unittest import mock
from datetime import date, datetime, timedelta

import sqlalchemy
from sqlalchemy import text, Column, Integer, String, Date
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import Session

from pygovpub.core.database import get_engine, with_transaction

# Skip all tests if not PostgreSQL
pytestmark = pytest.mark.skipif(
    get_engine().dialect.name != 'postgresql',
    reason="Partitioning tests require PostgreSQL"
)

# Create base for declarative models
Base = declarative_base()

# These will be implemented in the partitioning module
# Import the actual functions from the module
from pygovpub.core.partitioning import (
    create_date_partitioned_table,
    create_list_partitioned_table,
    create_range_partitioned_table,
    create_date_partition,
    create_list_partition,
    create_range_partition,
    attach_partition,
    detach_partition,
    get_partition_info,
    setup_partitioning_environment,
    create_partition_maintenance_function
)


class TestDatePartitioning:
    """Test date-based table partitioning."""
    
    def test_create_date_partitioned_table(self):
        """Test creating a date-partitioned table."""
        with mock.patch('sqlalchemy.engine.Connection.execute') as mock_execute:
            mock_execute.return_value = None
            
            # Define table schema for legislative bills by year
            table_name = "test_bills_by_date"
            partition_column = "introduced_date"
            
            # Call function
            create_date_partitioned_table(
                table_name=table_name,
                partition_column=partition_column,
                schema={
                    "id": "SERIAL PRIMARY KEY",
                    "title": "TEXT NOT NULL",
                    "introduced_date": "DATE NOT NULL"
                }
            )
            
            # Verify SQL execution
            mock_execute.assert_called_once()
            sql = mock_execute.call_args[0][0].text
            assert "CREATE TABLE" in sql
            assert table_name in sql
            assert "PARTITION BY RANGE" in sql
            assert partition_column in sql
    
    def test_create_date_partitioned_table_with_index(self):
        """Test creating a date-partitioned table with index on the partition column."""
        with mock.patch('sqlalchemy.engine.Connection.execute') as mock_execute:
            mock_execute.return_value = None
            
            # Define table schema for legislative bills by year
            table_name = "test_bills_by_date"
            partition_column = "introduced_date"
            
            # Call function with index parameter
            create_date_partitioned_table(
                table_name=table_name,
                partition_column=partition_column,
                schema={
                    "id": "SERIAL PRIMARY KEY",
                    "title": "TEXT NOT NULL",
                    "introduced_date": "DATE NOT NULL"
                },
                create_partition_column_index=True
            )
            
            # Verify SQL execution was called multiple times (table creation + index)
            assert mock_execute.call_count >= 1
            
            # Check table creation
            table_create_sql = mock_execute.call_args_list[0][0][0].text
            assert "CREATE TABLE" in table_create_sql
            assert table_name in table_create_sql
            assert "PARTITION BY RANGE" in table_create_sql
            assert partition_column in table_create_sql
            
    def test_create_date_partition(self):
        """Test creating a date partition."""
        with mock.patch('sqlalchemy.engine.Connection.execute') as mock_execute:
            mock_execute.return_value = None
            
            # Define parent table and partition
            table_name = "test_bills_by_date"
            start_date = date(2022, 1, 1)
            end_date = date(2022, 12, 31)
            partition_name = f"{table_name}_y2022"
            
            # Call function
            create_date_partition(
                table_name=table_name,
                partition_name=partition_name,
                start_date=start_date,
                end_date=end_date
            )
            
            # Verify SQL execution
            mock_execute.assert_called_once()
            sql = mock_execute.call_args[0][0].text
            assert "CREATE TABLE" in sql
            assert partition_name in sql
            assert "PARTITION OF" in sql
            assert table_name in sql
            assert "FOR VALUES FROM" in sql
            assert "'2022-01-01'" in sql
            assert "'2022-12-31'" in sql
            
    def test_date_partition_integration(self):
        """
        Integration test for date partitioning.
        
        This test mocks the SQL execution but tests the full flow of creating 
        a partitioned table, creating partitions, and inserting data.
        """
        with mock.patch('sqlalchemy.engine.Connection.execute') as mock_execute:
            mock_execute.return_value = None
            
            # Setup partitioned table
            table_name = "bills_by_date"
            partition_column = "introduced_date"
            
            # 1. Create partitioned table
            create_date_partitioned_table(
                table_name=table_name,
                partition_column=partition_column,
                schema={
                    "id": "SERIAL PRIMARY KEY",
                    "title": "TEXT NOT NULL",
                    "introduced_date": "DATE NOT NULL"
                }
            )
            
            # 2. Create yearly partitions
            for year in range(2020, 2023):
                start_date = date(year, 1, 1)
                end_date = date(year, 12, 31)
                partition_name = f"{table_name}_y{year}"
                
                create_date_partition(
                    table_name=table_name,
                    partition_name=partition_name,
                    start_date=start_date,
                    end_date=end_date
                )
            
            # 3. Insert data (would be routed to appropriate partition)
            insert_sql = text(f"""
            INSERT INTO {table_name} (title, introduced_date) VALUES
            ('Bill 2020-1', '2020-03-15'),
            ('Bill 2021-1', '2021-05-20'),
            ('Bill 2022-1', '2022-01-10')
            """)
            
            with mock.patch.object(sqlalchemy.engine.Connection, 'execute') as mock_insert:
                mock_insert.return_value = None
                
                # Execute insert
                with get_engine().connect() as conn:
                    conn.execute(insert_sql)
                
                # Verify insert was called
                mock_insert.assert_called_once()
                
            # 4. Query partition information
            get_partition_info.return_value = [
                {'partition_name': f"{table_name}_y2020", 'row_count': 1},
                {'partition_name': f"{table_name}_y2021", 'row_count': 1},
                {'partition_name': f"{table_name}_y2022", 'row_count': 1}
            ]
            
            # Get partition info
            partitions = get_partition_info(table_name)
            
            # Verify result
            assert len(partitions) == 3
            assert all(p['row_count'] == 1 for p in partitions)


class TestListPartitioning:
    """Test list-based table partitioning."""
    
    def test_create_list_partitioned_table(self):
        """Test creating a list-partitioned table."""
        with mock.patch('sqlalchemy.engine.Connection.execute') as mock_execute:
            mock_execute.return_value = None
            
            # Define table schema for bills by type
            table_name = "test_bills_by_type"
            partition_column = "bill_type"
            
            # Call function
            create_list_partitioned_table(
                table_name=table_name,
                partition_column=partition_column,
                schema={
                    "id": "SERIAL PRIMARY KEY",
                    "title": "TEXT NOT NULL",
                    "bill_type": "TEXT NOT NULL"
                }
            )
            
            # Verify SQL execution
            mock_execute.assert_called_once()
            sql = mock_execute.call_args[0][0].text
            assert "CREATE TABLE" in sql
            assert table_name in sql
            assert "PARTITION BY LIST" in sql
            assert partition_column in sql
            
    def test_create_list_partition(self):
        """Test creating a list partition."""
        with mock.patch('sqlalchemy.engine.Connection.execute') as mock_execute:
            mock_execute.return_value = None
            
            # Define parent table and partition
            table_name = "test_bills_by_type"
            values = ["HR", "HRES", "HJRES"]
            partition_name = f"{table_name}_house"
            
            # Call function
            create_list_partition(
                table_name=table_name,
                partition_name=partition_name,
                values=values
            )
            
            # Verify SQL execution
            mock_execute.assert_called_once()
            sql = mock_execute.call_args[0][0].text
            assert "CREATE TABLE" in sql
            assert partition_name in sql
            assert "PARTITION OF" in sql
            assert table_name in sql
            assert "FOR VALUES IN" in sql
            for value in values:
                assert f"'{value}'" in sql


class TestRangePartitioning:
    """Test range-based table partitioning."""
    
    def test_create_range_partitioned_table(self):
        """Test creating a range-partitioned table."""
        with mock.patch('sqlalchemy.engine.Connection.execute') as mock_execute:
            mock_execute.return_value = None
            
            # Define table schema for bills by congress
            table_name = "test_bills_by_congress"
            partition_column = "congress"
            
            # Call function
            create_range_partitioned_table(
                table_name=table_name,
                partition_column=partition_column,
                schema={
                    "id": "SERIAL PRIMARY KEY",
                    "title": "TEXT NOT NULL",
                    "congress": "INTEGER NOT NULL"
                }
            )
            
            # Verify SQL execution
            mock_execute.assert_called_once()
            sql = mock_execute.call_args[0][0].text
            assert "CREATE TABLE" in sql
            assert table_name in sql
            assert "PARTITION BY RANGE" in sql
            assert partition_column in sql
            
    def test_create_range_partition(self):
        """Test creating a range partition."""
        with mock.patch('sqlalchemy.engine.Connection.execute') as mock_execute:
            mock_execute.return_value = None
            
            # Define parent table and partition
            table_name = "test_bills_by_congress"
            start_value = 116
            end_value = 117
            partition_name = f"{table_name}_116"
            
            # Call function
            create_range_partition(
                table_name=table_name,
                partition_name=partition_name,
                start_value=start_value,
                end_value=end_value
            )
            
            # Verify SQL execution
            mock_execute.assert_called_once()
            sql = mock_execute.call_args[0][0].text
            assert "CREATE TABLE" in sql
            assert partition_name in sql
            assert "PARTITION OF" in sql
            assert table_name in sql
            assert "FOR VALUES FROM" in sql
            assert f"({start_value})" in sql
            assert f"({end_value})" in sql


def test_attach_partition():
    """Test attaching a partition to a partitioned table."""
    with mock.patch('sqlalchemy.engine.Connection.execute') as mock_execute:
        mock_execute.return_value = None
        
        # Define parent table and partition
        table_name = "test_bills_by_date"
        partition_table = "test_bills_2023"
        start_date = date(2023, 1, 1)
        end_date = date(2023, 12, 31)
        
        # Call function
        attach_partition(
            table_name=table_name,
            partition_table=partition_table,
            for_values=f"FROM ('{start_date}') TO ('{end_date}')"
        )
        
        # Verify SQL execution
        mock_execute.assert_called_once()
        sql = mock_execute.call_args[0][0].text
        assert "ALTER TABLE" in sql
        assert table_name in sql
        assert "ATTACH PARTITION" in sql
        assert partition_table in sql
        assert "FOR VALUES" in sql
        assert str(start_date) in sql
        assert str(end_date) in sql


def test_detach_partition():
    """Test detaching a partition from a partitioned table."""
    with mock.patch('sqlalchemy.engine.Connection.execute') as mock_execute:
        mock_execute.return_value = None
        
        # Define parent table and partition
        table_name = "test_bills_by_date"
        partition_table = "test_bills_2019"
        
        # Call function
        detach_partition(
            table_name=table_name,
            partition_table=partition_table
        )
        
        # Verify SQL execution
        mock_execute.assert_called_once()
        sql = mock_execute.call_args[0][0].text
        assert "ALTER TABLE" in sql
        assert table_name in sql
        assert "DETACH PARTITION" in sql
        assert partition_table in sql


def test_setup_partitioning_environment():
    """Test setting up the partitioning environment."""
    with mock.patch('sqlalchemy.engine.Connection.execute') as mock_execute:
        mock_execute.return_value = None
        
        # Call function
        setup_partitioning_environment()
        
        # Verify SQL execution
        mock_execute.assert_called_once()
        sql = mock_execute.call_args[0][0].text
        assert "cron.partition_maintenance_enabled" in sql
        assert "toggle_partition_maintenance" in sql
        assert "move_partition_to_archive" in sql
        assert "partition_performance_stats" in sql


def test_partitioning_performance_monitoring():
    """Test partition performance statistics view."""
    with mock.patch('sqlalchemy.engine.Connection.execute') as mock_execute:
        # Create a mock result for the view query
        mock_result = mock.MagicMock()
        mock_rows = [
            {"partition_name": "bills_by_date_2022", "row_count": 1000, "total_size": "100 MB"},
            {"partition_name": "bills_by_date_2023", "row_count": 2000, "total_size": "200 MB"}
        ]
        mock_result.__iter__.return_value = [mock.MagicMock(**row) for row in mock_rows]
        mock_execute.return_value = mock_result
        
        # Call setup to ensure view is created
        setup_partitioning_environment()
        
        # Mock query execution for the view
        view_query = text("SELECT * FROM partition_performance_stats")
        with get_engine().connect() as conn:
            result = conn.execute(view_query)
            stats = [dict(row) for row in result]
        
        # Verify results
        assert len(stats) == 2
        assert stats[0]["partition_name"] == "bills_by_date_2022"
        assert stats[0]["row_count"] == 1000
        assert stats[0]["total_size"] == "100 MB"
        assert stats[1]["partition_name"] == "bills_by_date_2023"
        assert stats[1]["row_count"] == 2000
        assert stats[1]["total_size"] == "200 MB"