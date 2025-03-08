"""
Tests for the configuration module.
"""

import os
from unittest import mock

import pytest

from pygovpub.config import Config, Environment


def test_config_default_values():
    """Test default configuration values."""
    config = Config()
    
    assert config.environment == Environment.DEVELOPMENT
    assert not config.mock.enabled
    assert config.mock.latency_ms == 0
    assert config.mock.simulate_rate_limits is False
    assert config.mock.record_mode is False
    assert config.mock.fixtures_path == "fixtures"
    assert config.apis == {}


def test_config_from_env_mock_settings():
    """Test loading mock settings from environment variables."""
    with mock.patch.dict(
        os.environ, 
        {
            "PYGOVPUB_ENV": "test",
            "PYGOVPUB_MOCK_ENABLED": "true",
            "PYGOVPUB_MOCK_LATENCY_MS": "200",
            "PYGOVPUB_MOCK_SIMULATE_RATE_LIMITS": "true",
            "PYGOVPUB_MOCK_RECORD_MODE": "true",
            "PYGOVPUB_MOCK_FIXTURES_PATH": "test_fixtures"
        }
    ):
        config = Config.from_env()
        
        assert config.environment == Environment.TEST
        assert config.mock.enabled is True
        assert config.mock.latency_ms == 200
        assert config.mock.simulate_rate_limits is True
        assert config.mock.record_mode is True
        assert config.mock.fixtures_path == "test_fixtures"


def test_config_from_env_api_settings():
    """Test loading API settings from environment variables."""
    with mock.patch.dict(
        os.environ, 
        {
            "CONGRESS_GOV_API_KEY": "congress_test_key",
            "CONGRESS_GOV_API_URL": "https://test.congress.gov/v3",
            "CONGRESS_GOV_RATE_LIMIT": "3000",
            "GOVINFO_API_KEY": "govinfo_test_key",
            "GOVINFO_API_URL": "https://test.govinfo.gov",
            "GOVINFO_RATE_LIMIT": "500"
        }
    ):
        config = Config.from_env()
        
        assert "congress" in config.apis
        assert config.apis["congress"].api_key == "congress_test_key"
        assert config.apis["congress"].base_url == "https://test.congress.gov/v3"
        assert config.apis["congress"].rate_limit == 3000
        
        assert "govinfo" in config.apis
        assert config.apis["govinfo"].api_key == "govinfo_test_key"
        assert config.apis["govinfo"].base_url == "https://test.govinfo.gov"
        assert config.apis["govinfo"].rate_limit == 500


def test_config_from_env_missing_api_keys():
    """Test configuration with missing API keys."""
    # Ensure environment variables don't exist
    with mock.patch.dict(os.environ, {}, clear=True):
        config = Config.from_env()
        
        assert "congress" not in config.apis
        assert "govinfo" not in config.apis


def test_config_from_env_partial_api_settings():
    """Test configuration with only one API configured."""
    with mock.patch.dict(
        os.environ, 
        {
            "CONGRESS_GOV_API_KEY": "congress_test_key",
        }
    ):
        config = Config.from_env()
        
        assert "congress" in config.apis
        assert config.apis["congress"].api_key == "congress_test_key"
        assert config.apis["congress"].base_url == "https://api.congress.gov/v3"
        assert config.apis["congress"].rate_limit == 5000
        
        assert "govinfo" not in config.apis