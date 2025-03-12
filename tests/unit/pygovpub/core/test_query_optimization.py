"""
Tests for query optimization module.

This module contains unit tests for the database query optimization functionality.
"""

import time
import pytest
from unittest import mock
from datetime import datetime

import sqlalchemy
from sqlalchemy import Column, Integer, String, text, select
from sqlalchemy.orm import Session, declarative_base
from sqlalchemy.sql import Select

from pygovpub.core.database import get_engine, with_transaction
from pygovpub.core.query_optimization import (
    reset_query_stats, get_query_stats, query_analyzer, with_query_analysis,
    explain_query, optimize_query_loading, create_composite_index,
    create_functional_index, create_partial_index
)

# Create a test model
Base = declarative_base()

# Note: This is a test model used only for testing, so we can 
# safely ignore the PytestCollectionWarning about it having an __init__
class TestModel(Base):
    """Simple model for testing query optimization."""
    __tablename__ = 'test_query_optimization'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    value = Column(Integer, nullable=True)


@pytest.fixture
def setup_test_table():
    """Create test table and clean up after test."""
    # Create table
    engine = get_engine()
    TestModel.__table__.create(engine, checkfirst=True)
    
    # Insert test data
    with with_transaction() as session:
        for i in range(5):
            session.add(TestModel(name=f"Test {i}", value=i*10))
    
    yield
    
    # Drop table after test
    TestModel.__table__.drop(engine, checkfirst=True)


def test_query_stats_collection(setup_test_table):
    """Test that query statistics are collected."""
    # Reset stats
    reset_query_stats()
    
    # Execute a query
    with with_transaction() as session:
        _ = session.exec(select(TestModel).where(TestModel.value > 20)).all()
    
    # Get stats
    stats = get_query_stats()
    
    # Verify stats are collected
    assert len(stats) >= 1
    
    # Verify a query contains expected stats keys
    for query, query_stats in stats.items():
        assert 'count' in query_stats
        assert 'total_time' in query_stats
        assert 'avg_time' in query_stats
        assert 'min_time' in query_stats
        assert 'max_time' in query_stats
        assert 'last_executed' in query_stats
        assert isinstance(query_stats['last_executed'], datetime)
        assert 'percentiles' in query_stats


def test_query_stats_filtering(setup_test_table):
    """Test that query statistics can be filtered."""
    # Reset stats
    reset_query_stats()
    
    # Execute multiple queries with different patterns
    with with_transaction() as session:
        # Fast query executed once
        _ = session.exec(select(TestModel).where(TestModel.id == 1)).all()
        
        # Slow query executed multiple times
        for _ in range(3):
            with mock.patch('time.time', side_effect=[0, 0.2]):  # Mock 200ms execution
                session.exec(select(TestModel).where(TestModel.value > 0)).all()
    
    # Get all stats
    all_stats = get_query_stats()
    assert len(all_stats) >= 2
    
    # Filter by min_count
    count_filtered = get_query_stats(min_count=2)
    assert len(count_filtered) < len(all_stats)
    for query, stats in count_filtered.items():
        assert stats['count'] >= 2
    
    # Filter by min_avg_time
    time_filtered = get_query_stats(min_avg_time=0.1)
    assert len(time_filtered) < len(all_stats)
    for query, stats in time_filtered.items():
        assert stats['avg_time'] >= 0.1
    
    # Apply both filters
    combined_filtered = get_query_stats(min_count=2, min_avg_time=0.1)
    assert len(combined_filtered) <= len(count_filtered)
    assert len(combined_filtered) <= len(time_filtered)
    for query, stats in combined_filtered.items():
        assert stats['count'] >= 2
        assert stats['avg_time'] >= 0.1


def test_reset_query_stats(setup_test_table):
    """Test that query statistics can be reset."""
    # Execute a query
    with with_transaction() as session:
        _ = session.exec(select(TestModel)).all()
    
    # Verify stats were collected
    assert len(get_query_stats()) >= 1
    
    # Reset stats
    reset_query_stats()
    
    # Verify stats were reset
    assert len(get_query_stats()) == 0


def test_query_analyzer_context_manager(setup_test_table):
    """Test the query_analyzer context manager."""
    with mock.patch('pygovpub.core.query_optimization.logger') as mock_logger:
        # Use context manager
        with query_analyzer("test_query"):
            with with_transaction() as session:
                _ = session.exec(select(TestModel)).all()
        
        # Verify logging
        mock_logger.info.assert_called_once()
        log_message = mock_logger.info.call_args[0][0]
        assert "test_query" in log_message
        assert "executed in" in log_message


def test_query_analyzer_context_manager_auto_name(setup_test_table):
    """Test the query_analyzer context manager with auto-naming."""
    with mock.patch('pygovpub.core.query_optimization.logger') as mock_logger:
        # Use context manager without explicit name
        def test_function():
            with query_analyzer():
                with with_transaction() as session:
                    _ = session.exec(select(TestModel)).all()
        
        # Call the function
        test_function()
        
        # Verify logging
        mock_logger.info.assert_called_once()
        log_message = mock_logger.info.call_args[0][0]
        assert "test_function" in log_message  # Should detect caller function name
        assert "executed in" in log_message


def test_with_query_analysis_decorator(setup_test_table):
    """Test the with_query_analysis decorator."""
    with mock.patch('pygovpub.core.query_optimization.logger') as mock_logger:
        @with_query_analysis
        def test_function():
            with with_transaction() as session:
                return session.exec(select(TestModel)).all()
        
        # Call decorated function
        result = test_function()
        
        # Verify function returned correct result
        assert len(result) == 5
        
        # Verify logging
        mock_logger.info.assert_called_once()
        log_message = mock_logger.info.call_args[0][0]
        assert "test_function" in log_message
        assert "executed in" in log_message


@pytest.mark.skipif(
    get_engine().dialect.name != 'postgresql', 
    reason="explain_query requires PostgreSQL"
)
def test_explain_query(setup_test_table):
    """Test explain_query function (PostgreSQL only)."""
    with with_transaction() as session:
        query = select(TestModel).where(TestModel.value > 20)
        
        # Mock session.execute to avoid actually running EXPLAIN
        with mock.patch.object(session, 'execute') as mock_execute:
            mock_execute.return_value.scalar.return_value = [{
                "Plan": {"Node Type": "Seq Scan", "Total Cost": 1.0}
            }]
            
            # Call explain_query
            result = explain_query(session, query, analyze=False)
            
            # Verify result
            assert isinstance(result, dict)
            assert "Node Type" in result
            
            # Verify EXPLAIN was called
            mock_execute.assert_called_once()
            sql = mock_execute.call_args[0][0].text
            assert sql.startswith("EXPLAIN")


@pytest.mark.skipif(
    get_engine().dialect.name != 'postgresql', 
    reason="explain_query requires PostgreSQL"
)
def test_explain_query_with_analyze(setup_test_table):
    """Test explain_query function with ANALYZE option."""
    with with_transaction() as session:
        query = select(TestModel).where(TestModel.value > 20)
        
        # Mock session.execute to avoid actually running EXPLAIN ANALYZE
        with mock.patch.object(session, 'execute') as mock_execute:
            mock_execute.return_value.scalar.return_value = [{
                "Plan": {"Node Type": "Seq Scan", "Total Cost": 1.0, "Actual Time": 0.1}
            }]
            
            # Call explain_query with analyze=True
            result = explain_query(session, query, analyze=True)
            
            # Verify result
            assert isinstance(result, dict)
            assert "Node Type" in result
            
            # Verify EXPLAIN ANALYZE was called
            mock_execute.assert_called_once()
            sql = mock_execute.call_args[0][0].text
            assert "EXPLAIN" in sql
            assert "ANALYZE" in sql


@pytest.mark.skipif(
    get_engine().dialect.name != 'postgresql', 
    reason="explain_query requires PostgreSQL"
)
def test_explain_query_with_raw_sql(setup_test_table):
    """Test explain_query function with raw SQL string."""
    with with_transaction() as session:
        raw_sql = "SELECT * FROM test_query_optimization WHERE value > 20"
        
        # Mock session.execute to avoid actually running EXPLAIN
        with mock.patch.object(session, 'execute') as mock_execute:
            mock_execute.return_value.scalar.return_value = [{
                "Plan": {"Node Type": "Seq Scan", "Total Cost": 1.0}
            }]
            
            # Call explain_query with raw SQL
            result = explain_query(session, raw_sql)
            
            # Verify result
            assert isinstance(result, dict)
            assert "Node Type" in result
            
            # Verify EXPLAIN was called with the raw SQL
            mock_execute.assert_called_once()
            sql = mock_execute.call_args[0][0].text
            assert "EXPLAIN" in sql
            assert "SELECT * FROM test_query_optimization" in sql


def test_optimize_query_loading():
    """Test optimize_query_loading function with Select statement."""
    # Create a test query
    with with_transaction() as session:
        query = select(TestModel)
        
        # Call optimize_query_loading
        optimized_query = optimize_query_loading(query, TestModel)
        
        # Verify it returns a statement
        assert isinstance(optimized_query, sqlalchemy.sql.Select)


class TestRelationshipModel(Base):
    """Model with relationships for testing query optimization."""
    __tablename__ = 'test_relationship_model'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    parent_id = Column(Integer, nullable=True)
    
    # Add a relationship that can be detected by inspect()
    @property
    def children(self):
        """Test relationship property."""
        return []
    
    @property
    def parent(self):
        """Test parent relationship property."""
        return None


@pytest.fixture
def setup_relationship_models():
    """Create models with relationships for testing."""
    def mock_inspect(*args, **kwargs):
        """Mock inspector that returns fake relationships."""
        class MockRelationship:
            def __init__(self, name, uselist, parent=True):
                self.name = name
                self.uselist = uselist
                self.parent = parent
                self.persist_selectable = True
        
        class MockInspector:
            def __init__(self):
                self.relationships = {
                    "children": MockRelationship("children", True),
                    "parent": MockRelationship("parent", False)
                }
        
        return MockInspector()
    
    # Patch inspect to return mock relationships
    with mock.patch('sqlalchemy.inspect', side_effect=mock_inspect):
        yield


def test_optimize_query_loading_with_relationships(setup_relationship_models):
    """Test optimize_query_loading with relationship detection."""
    # Test with a SQLAlchemy Select
    select_query = select(TestRelationshipModel)
    optimized_select = optimize_query_loading(select_query, TestRelationshipModel)
    assert isinstance(optimized_select, sqlalchemy.sql.Select)
    
    # Test with a SQLAlchemy Query
    with with_transaction() as session:
        query = session.query(TestRelationshipModel)
        with mock.patch('sqlalchemy.orm.Query.options') as mock_options:
            mock_options.return_value = query
            optimized_query = optimize_query_loading(query, TestRelationshipModel)
            
            # Should apply options twice (once for each relationship)
            assert mock_options.call_count == 2


def test_optimize_query_loading_with_no_relationships():
    """Test optimize_query_loading when model has no relationships."""
    # Create test query
    query = select(TestModel)
    
    # Patch inspect to return no relationships
    with mock.patch('sqlalchemy.inspect') as mock_inspect:
        mock_inspect.return_value.relationships = {}
        
        # Call optimize_query_loading
        optimized_query = optimize_query_loading(query, TestModel)
        
        # Should still return a query
        assert isinstance(optimized_query, sqlalchemy.sql.Select)


@pytest.mark.skipif(
    get_engine().dialect.name != 'postgresql', 
    reason="Index creation tests require PostgreSQL"
)
class TestIndexCreation:
    """Tests for index creation functions."""
    
    def test_create_composite_index(self, setup_test_table):
        """Test create_composite_index function."""
        with mock.patch('pygovpub.core.query_optimization.logger') as mock_logger:
            with mock.patch('sqlalchemy.engine.Connection.execute') as mock_execute:
                mock_execute.return_value = None
                
                # Call create_composite_index
                create_composite_index(
                    'test_query_optimization', 
                    ['name', 'value'], 
                    'idx_test_composite'
                )
                
                # Verify SQL was executed
                mock_execute.assert_called_once()
                sql = mock_execute.call_args[0][0].text
                assert "CREATE" in sql
                assert "INDEX" in sql
                assert "idx_test_composite" in sql
                assert "test_query_optimization" in sql
                assert "name, value" in sql
                
                # Verify logging
                mock_logger.info.assert_called_once()
    
    def test_create_composite_index_auto_name(self, setup_test_table):
        """Test create_composite_index with auto-generated name."""
        with mock.patch('pygovpub.core.query_optimization.logger') as mock_logger:
            with mock.patch('sqlalchemy.engine.Connection.execute') as mock_execute:
                mock_execute.return_value = None
                
                # Call create_composite_index without index_name
                create_composite_index(
                    'test_query_optimization', 
                    ['name', 'value']
                )
                
                # Verify SQL was executed
                mock_execute.assert_called_once()
                sql = mock_execute.call_args[0][0].text
                assert "CREATE" in sql
                assert "INDEX" in sql
                assert "idx_test_query_optimization_name_value" in sql
                assert "test_query_optimization" in sql
                assert "name, value" in sql
    
    def test_create_unique_composite_index(self, setup_test_table):
        """Test create_composite_index with unique constraint."""
        with mock.patch('pygovpub.core.query_optimization.logger') as mock_logger:
            with mock.patch('sqlalchemy.engine.Connection.execute') as mock_execute:
                mock_execute.return_value = None
                
                # Call create_composite_index with unique=True
                create_composite_index(
                    'test_query_optimization', 
                    ['name', 'value'],
                    unique=True
                )
                
                # Verify SQL was executed
                mock_execute.assert_called_once()
                sql = mock_execute.call_args[0][0].text
                assert "CREATE UNIQUE INDEX" in sql
                assert "test_query_optimization" in sql
                assert "name, value" in sql
    
    def test_create_functional_index(self, setup_test_table):
        """Test create_functional_index function."""
        with mock.patch('pygovpub.core.query_optimization.logger') as mock_logger:
            with mock.patch('sqlalchemy.engine.Connection.execute') as mock_execute:
                mock_execute.return_value = None
                
                # Call create_functional_index
                create_functional_index(
                    'test_query_optimization', 
                    'LOWER(name)', 
                    'idx_test_functional'
                )
                
                # Verify SQL was executed
                mock_execute.assert_called_once()
                sql = mock_execute.call_args[0][0].text
                assert "CREATE INDEX" in sql
                assert "idx_test_functional" in sql
                assert "test_query_optimization" in sql
                assert "LOWER(name)" in sql
                
                # Verify logging
                mock_logger.info.assert_called_once()
    
    def test_create_partial_index(self, setup_test_table):
        """Test create_partial_index function."""
        with mock.patch('pygovpub.core.query_optimization.logger') as mock_logger:
            with mock.patch('sqlalchemy.engine.Connection.execute') as mock_execute:
                mock_execute.return_value = None
                
                # Call create_partial_index
                create_partial_index(
                    'test_query_optimization', 
                    ['value'], 
                    "value > 0", 
                    'idx_test_partial'
                )
                
                # Verify SQL was executed
                mock_execute.assert_called_once()
                sql = mock_execute.call_args[0][0].text
                assert "CREATE INDEX" in sql
                assert "idx_test_partial" in sql
                assert "test_query_optimization" in sql
                assert "value" in sql
                assert "WHERE value > 0" in sql
                
                # Verify logging
                mock_logger.info.assert_called_once()