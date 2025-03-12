"""
Tests for RateLimitUsage model sharding functionality.
"""

import asyncio
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, AsyncMock
import uuid
from zoneinfo import ZoneInfo

from sqlalchemy import text, create_engine
from sqlmodel import Session, SQLModel, create_engine
from sqlalchemy.pool import StaticPool

from pygovpub.auth.models import RateLimitUsage, ApiSource
from pygovpub.auth.rate_limiter import RateLimiter, ThrottleStrategy


def create_test_db():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    
    # Create tables
    SQLModel.metadata.create_all(engine)
    
    return engine


class TestRateLimitSharding:
    """Test RateLimitUsage model sharding functionality."""
    
    @pytest.fixture
    def engine(self):
        """Create a test SQLite database engine."""
        return create_test_db()
    
    @pytest.fixture
    def session(self, engine):
        """Create a test database session."""
        with Session(engine) as session:
            yield session
    
    @pytest.fixture
    def rate_limiter(self, session):
        """Create a RateLimiter with mocked session factory."""
        # Use a closure to capture the session
        def session_factory():
            return session
        
        return RateLimiter(
            session_factory=session_factory,
            strategy=ThrottleStrategy.WAIT
        )
    
    @patch("pygovpub.auth.rate_limiter.RateLimiter._ensure_partition_exists")
    @patch("pygovpub.auth.models.RateLimitUsage.get_table_name")
    async def test_track_request_with_sharding(self, mock_get_table_name, mock_ensure_partition, rate_limiter, session):
        """Test that track_request properly uses sharded tables."""
        # Mock the get_table_name method to return a fixed table name
        mock_get_table_name.return_value = "rate_limit_usage_test"
        
        # Create rate limit headers
        headers = {
            "x-ratelimit-remaining": "100",
            "x-ratelimit-reset": str(int((datetime.now(ZoneInfo("UTC")) + timedelta(hours=1)).timestamp()))
        }
        
        # Create SQL statements that would be executed
        with patch.object(session, "execute") as mock_execute:
            # Configure mock to simulate finding no existing entry
            mock_execute.return_value.first.return_value = None
            
            # Track a request
            await rate_limiter.track_request(
                source=ApiSource.CONGRESS,
                endpoint="/bills",
                status_code=200,
                rate_limit_headers=headers,
                response_time_ms=150,
                success=True
            )
            
            # Verify partition was created
            mock_ensure_partition.assert_called_once()
            
            # Verify correct SQL statements were executed
            # Extract SQL from the mock calls
            sql_statements = [
                call.args[0].text if hasattr(call.args[0], 'text') else str(call.args[0])
                for call in mock_execute.call_args_list
            ]
            
            # Check that we executed a SELECT to check for existing entry
            assert any("SELECT id FROM rate_limit_usage_test" in stmt for stmt in sql_statements)
            
            # Check that we executed an INSERT for the new entry
            assert any("INSERT INTO rate_limit_usage_test" in stmt for stmt in sql_statements)
    
    @patch("pygovpub.auth.rate_limiter.RateLimiter._ensure_partition_exists")
    @patch("pygovpub.auth.models.RateLimitUsage.get_table_name")
    async def test_check_rate_limit_with_sharding(self, mock_get_table_name, mock_ensure_partition, rate_limiter, session):
        """Test that check_rate_limit properly uses sharded tables."""
        # Mock the get_table_name method to return a fixed table name
        mock_get_table_name.return_value = "rate_limit_usage_test"
        
        # Set up the session to return results from the sharded table
        reset_time = datetime.now(ZoneInfo("UTC")) + timedelta(hours=1)
        
        with patch.object(session, "execute") as mock_execute:
            # First check if table exists
            mock_execute.return_value.first.side_effect = [
                (1,),  # Table exists
                (50, reset_time)  # Rate limit data
            ]
            
            # Check rate limit
            allowed, returned_reset_time = await rate_limiter.check_rate_limit(ApiSource.CONGRESS)
            
            # Verify correct SQL statements were executed
            # Extract SQL from the mock calls
            sql_statements = [
                call.args[0].text if hasattr(call.args[0], 'text') else str(call.args[0])
                for call in mock_execute.call_args_list
            ]
            
            # Check that we executed a SELECT to check if table exists
            assert any("SELECT 1 FROM pg_tables" in stmt for stmt in sql_statements)
            
            # Check that we executed a SELECT to get rate limit data
            assert any("SELECT remaining, reset_time" in stmt for stmt in sql_statements)
            
            # Verify results
            assert allowed is True
            assert returned_reset_time == reset_time
    
    @patch("pygovpub.auth.rate_limiter.RateLimiter._ensure_partition_exists")
    async def test_purge_old_rate_limit_data(self, mock_ensure_partition, rate_limiter, session):
        """Test purging old rate limit data."""
        with patch.object(session, "execute") as mock_execute:
            # Mock finding old tables
            mock_execute.return_value.__iter__.return_value = [
                ("rate_limit_usage_congress_2024_01",),
                ("rate_limit_usage_govinfo_2024_01",),
                ("rate_limit_usage_congress_2024_02",),
                ("rate_limit_usage_govinfo_2024_02",),
                ("rate_limit_usage_congress_2024_03",),
                ("rate_limit_usage_govinfo_2024_03",),
                ("rate_limit_usage_congress_2025_01",),
                ("rate_limit_usage_govinfo_2025_01",),
                ("rate_limit_usage_congress_2025_02",),
                ("rate_limit_usage_govinfo_2025_02",),
                ("rate_limit_usage_congress_2025_03",),
                ("rate_limit_usage_govinfo_2025_03",),
            ]
            
            # Purge data (keep last 3 months)
            await rate_limiter.purge_old_rate_limit_data(months_to_keep=3)
            
            # Extract DROP TABLE statements
            drop_statements = [
                call.args[0].text
                for call in mock_execute.call_args_list
                if hasattr(call.args[0], 'text') and "DROP TABLE" in call.args[0].text
            ]
            
            # Only tables from 2024 should be dropped (6 tables)
            expected_drop_count = 6
            assert len(drop_statements) == expected_drop_count
            
            # Verify correct tables are dropped
            assert any("DROP TABLE rate_limit_usage_congress_2024_01" in stmt for stmt in drop_statements)
            assert any("DROP TABLE rate_limit_usage_govinfo_2024_01" in stmt for stmt in drop_statements)
            assert any("DROP TABLE rate_limit_usage_congress_2024_02" in stmt for stmt in drop_statements)
            assert any("DROP TABLE rate_limit_usage_govinfo_2024_02" in stmt for stmt in drop_statements)
            assert any("DROP TABLE rate_limit_usage_congress_2024_03" in stmt for stmt in drop_statements)
            assert any("DROP TABLE rate_limit_usage_govinfo_2024_03" in stmt for stmt in drop_statements)
            
            # Verify 2025 tables are NOT dropped
            assert not any("DROP TABLE rate_limit_usage_congress_2025_01" in stmt for stmt in drop_statements)
            assert not any("DROP TABLE rate_limit_usage_govinfo_2025_01" in stmt for stmt in drop_statements)
            assert not any("DROP TABLE rate_limit_usage_congress_2025_02" in stmt for stmt in drop_statements)
            assert not any("DROP TABLE rate_limit_usage_govinfo_2025_02" in stmt for stmt in drop_statements)
            assert not any("DROP TABLE rate_limit_usage_congress_2025_03" in stmt for stmt in drop_statements)
            assert not any("DROP TABLE rate_limit_usage_govinfo_2025_03" in stmt for stmt in drop_statements)
            
    def test_get_table_name(self):
        """Test that get_table_name produces correct table names."""
        # Test for Congress API
        date1 = datetime(2025, 3, 15)
        table_name1 = RateLimitUsage.get_table_name(ApiSource.CONGRESS, date1)
        assert table_name1 == "rate_limit_usage_congress_2025_03"
        
        # Test for GovInfo API
        date2 = datetime(2024, 12, 1)
        table_name2 = RateLimitUsage.get_table_name(ApiSource.GOVINFO, date2)
        assert table_name2 == "rate_limit_usage_govinfo_2024_12"
    
    def test_create_monthly_partition(self, engine):
        """Test creating monthly partitions."""
        # Patch the engine's begin and execute methods
        with patch.object(engine, "begin") as mock_begin:
            mock_conn = MagicMock()
            mock_begin.return_value.__enter__.return_value = mock_conn
            
            # Call the method
            RateLimitUsage.create_monthly_partition(
                engine,
                ApiSource.CONGRESS,
                2025,
                3
            )
            
            # Verify execute was called on the connection
            mock_conn.execute.assert_called_once()
            
            # Extract the SQL from the call
            call_args = mock_conn.execute.call_args[0][0]
            sql_text = str(call_args).lower()
            
            # Verify the SQL contains the expected table name and partition values
            assert "rate_limit_usage_congress_2025_03" in sql_text
            assert "partition of rate_limit_usage" in sql_text
            assert "for values in ('congress')" in sql_text


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])