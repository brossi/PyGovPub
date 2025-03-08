"""
Tests for authentication models.

This module tests the SQLModel classes for API authentication
and usage tracking.
"""

import pytest
from sqlmodel import Session, SQLModel, create_engine
from datetime import datetime

from pygovpub.auth.models import ApiConfiguration, ApiUsage, ApiSource, AuthType


# Create in-memory database for testing
@pytest.fixture
def db_session():
    """Create in-memory database session for testing."""
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_api_configuration_model(db_session):
    """Test ApiConfiguration model creation and retrieval."""
    # Create configuration
    config = ApiConfiguration(
        source=ApiSource.CONGRESS,
        base_url="https://api.congress.gov/v3",
        auth_type=AuthType.HEADER,
        auth_key_name="X-API-Key",
        key_reference="env:CONGRESS_GOV_API_KEY",
        rate_limit=5000,
        rate_limit_period=3600,
        active=True
    )
    
    # Save to database
    db_session.add(config)
    db_session.commit()
    db_session.refresh(config)
    
    # Verify ID was assigned
    assert config.id is not None
    
    # Retrieve and verify
    retrieved = db_session.get(ApiConfiguration, config.id)
    assert retrieved.source == ApiSource.CONGRESS
    assert retrieved.base_url == "https://api.congress.gov/v3"
    assert retrieved.auth_type == AuthType.HEADER
    assert retrieved.auth_key_name == "X-API-Key"
    assert retrieved.key_reference == "env:CONGRESS_GOV_API_KEY"
    assert retrieved.rate_limit == 5000
    assert retrieved.rate_limit_period == 3600
    assert retrieved.active is True
    assert isinstance(retrieved.created_at, datetime)
    assert isinstance(retrieved.updated_at, datetime)


def test_api_usage_model(db_session):
    """Test ApiUsage model creation and retrieval."""
    # Create usage record
    usage = ApiUsage(
        source=ApiSource.GOVINFO,
        endpoint="/collections",
        status_code=200,
        response_time_ms=150,
        rate_limit_remaining=999,
        rate_limit_reset=datetime.utcnow(),
        success=True
    )
    
    # Save to database
    db_session.add(usage)
    db_session.commit()
    db_session.refresh(usage)
    
    # Verify ID was assigned
    assert usage.id is not None
    
    # Retrieve and verify
    retrieved = db_session.get(ApiUsage, usage.id)
    assert retrieved.source == ApiSource.GOVINFO
    assert retrieved.endpoint == "/collections"
    assert retrieved.status_code == 200
    assert retrieved.response_time_ms == 150
    assert retrieved.rate_limit_remaining == 999
    assert isinstance(retrieved.rate_limit_reset, datetime)
    assert retrieved.success is True
    assert retrieved.error_message is None
    assert isinstance(retrieved.request_time, datetime)


def test_api_source_enum():
    """Test ApiSource enum values."""
    assert ApiSource.CONGRESS == "congress"
    assert ApiSource.GOVINFO == "govinfo"
    
    # Test conversion from string
    assert ApiSource("congress") == ApiSource.CONGRESS
    assert ApiSource("govinfo") == ApiSource.GOVINFO
    
    # Test invalid value
    with pytest.raises(ValueError):
        ApiSource("invalid")


def test_auth_type_enum():
    """Test AuthType enum values."""
    assert AuthType.HEADER == "header"
    assert AuthType.PARAMETER == "parameter"
    
    # Test conversion from string
    assert AuthType("header") == AuthType.HEADER
    assert AuthType("parameter") == AuthType.PARAMETER
    
    # Test invalid value
    with pytest.raises(ValueError):
        AuthType("invalid")