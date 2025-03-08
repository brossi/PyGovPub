"""
Configuration module for PyGovPub SDK.

This module handles configuration settings, including:
- Environment setup (dev, test, prod)
- API base URLs and keys
- Mock server settings
- Rate limit configurations
"""

import os
from enum import Enum
from typing import Dict, Optional

from pydantic import BaseModel, Field


class Environment(str, Enum):
    """Environment options for the SDK."""
    
    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


class ApiConfig(BaseModel):
    """Configuration for a specific API."""
    
    base_url: str
    api_key: Optional[str] = None
    rate_limit: int
    rate_limit_period: int = 3600  # in seconds (default 1 hour)


class MockConfig(BaseModel):
    """Configuration for the mock server."""
    
    enabled: bool = False
    latency_ms: int = 0
    simulate_rate_limits: bool = False
    record_mode: bool = False
    fixtures_path: str = "fixtures"


class Config(BaseModel):
    """Main configuration for the PyGovPub SDK."""
    
    environment: Environment = Field(
        default_factory=lambda: Environment(
            os.getenv("PYGOVPUB_ENV", Environment.DEVELOPMENT)
        )
    )
    apis: Dict[str, ApiConfig] = Field(default_factory=dict)
    mock: MockConfig = Field(default_factory=MockConfig)
    
    @classmethod
    def from_env(cls) -> "Config":
        """Create config from environment variables."""
        config = cls(
            environment=Environment(
                os.getenv("PYGOVPUB_ENV", Environment.DEVELOPMENT)
            ),
            mock=MockConfig(
                enabled=os.getenv("PYGOVPUB_MOCK_ENABLED", "false").lower() == "true",
                latency_ms=int(os.getenv("PYGOVPUB_MOCK_LATENCY_MS", "0")),
                simulate_rate_limits=os.getenv(
                    "PYGOVPUB_MOCK_SIMULATE_RATE_LIMITS", "false"
                ).lower() == "true",
                record_mode=os.getenv("PYGOVPUB_MOCK_RECORD_MODE", "false").lower() == "true",
                fixtures_path=os.getenv("PYGOVPUB_MOCK_FIXTURES_PATH", "fixtures"),
            ),
        )
        
        # Congress.gov API settings
        congress_api_key = os.getenv("CONGRESS_GOV_API_KEY")
        if congress_api_key:
            config.apis["congress"] = ApiConfig(
                base_url=os.getenv(
                    "CONGRESS_GOV_API_URL", 
                    "https://api.congress.gov/v3"
                ),
                api_key=congress_api_key,
                rate_limit=int(os.getenv("CONGRESS_GOV_RATE_LIMIT", "5000")),
            )
        
        # GovInfo.gov API settings
        govinfo_api_key = os.getenv("GOVINFO_API_KEY")
        if govinfo_api_key:
            config.apis["govinfo"] = ApiConfig(
                base_url=os.getenv(
                    "GOVINFO_API_URL", 
                    "https://api.govinfo.gov"
                ),
                api_key=govinfo_api_key,
                rate_limit=int(os.getenv("GOVINFO_RATE_LIMIT", "1000")),
            )
        
        return config


# Default configuration instance
config = Config.from_env()