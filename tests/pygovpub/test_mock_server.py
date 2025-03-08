"""
Tests for the mock server implementation.
"""

import asyncio
import json
import os
from pathlib import Path
from unittest import mock

import httpx
import pytest
from fastapi.testclient import TestClient

from pygovpub.config import Config
from pygovpub.mock.server import MockServer, create_app


@pytest.fixture
def mock_server():
    """Create a mock server instance for testing."""
    # Create temporary fixtures directory
    fixtures_dir = "test_fixtures"
    os.makedirs(os.path.join(fixtures_dir, "defaults"), exist_ok=True)
    
    # Create a sample fixture file
    sample_fixture = {
        "bill": {
            "congress": 117,
            "type": "hr",
            "number": "1234",
            "title": "Test Bill"
        }
    }
    
    os.makedirs(os.path.join(fixtures_dir, "congress", "bill"), exist_ok=True)
    with open(os.path.join(fixtures_dir, "defaults", "congress_bill.json"), "w") as f:
        json.dump(sample_fixture, f)
    
    # Create server instance
    server = MockServer(fixtures_path=fixtures_dir)
    
    yield server
    
    # Clean up temporary fixtures
    import shutil
    shutil.rmtree(fixtures_dir, ignore_errors=True)


@pytest.fixture
def client(mock_server):
    """Create a TestClient for the mock server."""
    mock_server._setup_routes()
    return TestClient(mock_server.app)


def test_health_check(client):
    """Test the health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "congress" in data["apis"]
    assert "govinfo" in data["apis"]


def test_congress_bill_endpoint(client):
    """Test the Congress.gov bill endpoint."""
    # Set API key in header
    response = client.get(
        "/congress/v3/bill/117/hr/1234",
        headers={"X-API-Key": "test_key"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["bill"]["congress"] == 117
    assert data["bill"]["type"] == "hr"
    assert data["bill"]["number"] == "1234"


def test_congress_bill_endpoint_missing_auth(client):
    """Test the Congress.gov bill endpoint with missing auth."""
    response = client.get("/congress/v3/bill/117/hr/1234")
    assert response.status_code == 401
    assert "Missing API key" in response.json()["detail"]


def test_govinfo_collections_endpoint(client):
    """Test the GovInfo.gov collections endpoint."""
    # Create a sample fixture file for collections
    fixtures_dir = "test_fixtures"
    os.makedirs(os.path.join(fixtures_dir, "govinfo"), exist_ok=True)
    sample_collections = {
        "collections": [
            {
                "collectionCode": "BILLS",
                "collectionName": "Congressional Bills"
            }
        ]
    }
    with open(os.path.join(fixtures_dir, "defaults", "govinfo_collections.json"), "w") as f:
        json.dump(sample_collections, f)
    
    # Set API key in query param
    response = client.get("/collections", params={"api_key": "test_key"})
    assert response.status_code == 200
    data = response.json()
    assert "collections" in data
    assert len(data["collections"]) > 0
    assert data["collections"][0]["collectionCode"] == "BILLS"


def test_govinfo_collections_endpoint_missing_auth(client):
    """Test the GovInfo.gov collections endpoint with missing auth."""
    response = client.get("/collections")
    assert response.status_code == 401
    assert "Missing API key" in response.json()["detail"]
    assert "query parameter" in response.json()["detail"]


def test_load_fixture_fallback(mock_server):
    """Test the fixture loading fallback behavior."""
    # Test loading a non-existent fixture
    fixture_data = mock_server._load_fixture(
        Path("test_fixtures/non_existent.json")
    )
    assert fixture_data["mock"] is True
    assert "No specific fixture found" in fixture_data["message"]
    
    # Test bill fallback
    fixture_data = mock_server._load_fixture(
        Path("test_fixtures/bill_non_existent.json")
    )
    assert "bill" in fixture_data
    assert fixture_data["bill"]["congress"] == 117
    assert fixture_data["bill"]["type"] == "hr"


@pytest.mark.asyncio
async def test_simulate_latency():
    """Test the latency simulation."""
    server = MockServer()
    server.latency_ms = 100
    
    # Measure the time taken
    start_time = asyncio.get_event_loop().time()
    await server._simulate_latency()
    end_time = asyncio.get_event_loop().time()
    
    # Should be close to 100ms
    elapsed_ms = (end_time - start_time) * 1000
    assert 90 <= elapsed_ms <= 150  # Allow some margin for timing variations


def test_rate_limit_simulation(mock_server):
    """Test the rate limit simulation."""
    mock_server.simulate_rate_limits = True
    mock_server.rate_limits["congress"]["remaining"] = 1
    
    # First request should work
    mock_server._check_auth("congress", "test_key")
    assert mock_server.rate_limits["congress"]["remaining"] == 0
    
    # Second request should raise 429
    with pytest.raises(Exception) as exc_info:
        mock_server._check_auth("congress", "test_key")
    
    assert "429" in str(exc_info.value)
    assert "Rate limit exceeded" in str(exc_info.value)