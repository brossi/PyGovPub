# Authentication and Configuration

## Overview

PyGovPub requires authentication for both Congress.gov and GovInfo.gov APIs. This document details the authentication process, configuration management, and rate limit tracking.

## Models

### Core Models

```python
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from sqlmodel import SQLModel, Field, Relationship
from pydantic import validator, constr
from .base import BaseModel
from .errors import AuthError
from .logging import LogContext
from .metrics import record_metric
import asyncio

# Base Models
class ApiConfigBase(BaseModel):
    """Base model for API configuration data"""
    api_source: str = Field(
        ...,
        description="API source identifier",
        sa_column_kwargs={"check": "api_source IN ('govinfo', 'congress')"}
    )
    config_key: str = Field(
        ...,
        max_length=50,
        description="Configuration key"
    )
    config_value: Optional[str] = Field(
        None,
        description="Configuration value"
    )
    is_active: bool = Field(
        default=True,
        description="Whether configuration is active"
    )

    @validator("api_source")
    def validate_api_source(cls, v):
        if v not in {"govinfo", "congress"}:
            raise AuthError("API source must be either 'govinfo' or 'congress'")
        return v

# Database Models
class ApiConfiguration(ApiConfigBase, table=True):
    """Database model for API configuration"""
    __tablename__ = "api_configuration"

    config_id: int = Field(default=None, primary_key=True)
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column_kwargs={"onupdate": datetime.utcnow},
        description="Last update timestamp"
    )

    class Config:
        orm_mode = True

class ApiUsage(SQLModel, table=True):
    """Database model for API usage tracking"""
    __tablename__ = "api_usage"

    usage_id: int = Field(default=None, primary_key=True)
    api_source: str = Field(
        ...,
        description="API source identifier",
        sa_column_kwargs={"check": "api_source IN ('govinfo', 'congress')"}
    )
    request_time: datetime = Field(
        ...,
        description="Request timestamp"
    )
    endpoint: str = Field(..., description="API endpoint called")
    rate_limit_remaining: Optional[int] = Field(
        None,
        description="Remaining rate limit"
    )
    reset_time: Optional[datetime] = Field(
        None,
        description="Rate limit reset time"
    )
    response_time: Optional[int] = Field(
        None,
        description="Response time in milliseconds"
    )
    success: bool = Field(..., description="Request success status")
    error_message: Optional[str] = Field(None, description="Error message if any")
    created_at: datetime = Field(default_factory=datetime.utcnow)

# Error Classes
class AuthError(Exception):
    """Base class for authentication errors"""
    entity_type: str = "auth"

class AuthenticationError(AuthError):
    """Raised when authentication fails"""
    status_code: int = 401
    detail: str = "Authentication failed"

class RateLimitError(AuthError):
    """Raised when rate limit is exceeded"""
    status_code: int = 429
    retry_after: int = 3600  # 1 hour default

class ConfigurationError(AuthError):
    """Raised for configuration errors"""
    status_code: int = 400

# API Request/Response Models
class ApiConfigCreate(ApiConfigBase):
    """Model for API configuration creation requests"""
    class Config:
        schema_extra = {
            "example": {
                "api_source": "govinfo",
                "config_key": "rate_limit_buffer",
                "config_value": "100",
                "is_active": True
            }
        }

class ApiConfigUpdate(SQLModel):
    """Model for API configuration update requests"""
    config_value: Optional[str] = None
    is_active: Optional[bool] = None

    class Config:
        schema_extra = {
            "example": {
                "config_value": "200",
                "is_active": True
            }
        }

class ApiConfigResponse(ApiConfigBase):
    """Model for API configuration responses"""
    config_id: int
    updated_at: datetime

    class Config:
        orm_mode = True
        schema_extra = {
            "example": {
                "config_id": 1,
                "api_source": "govinfo",
                "config_key": "rate_limit_buffer",
                "config_value": "100",
                "is_active": True,
                "updated_at": "2023-03-01T00:00:00Z"
            }
        }

class ApiUsageResponse(SQLModel):
    """Model for API usage statistics responses"""
    api_source: str
    requests_made: int
    remaining: Optional[int]
    reset_at: Optional[datetime]

    class Config:
        schema_extra = {
            "example": {
                "api_source": "govinfo",
                "requests_made": 500,
                "remaining": 500,
                "reset_at": "2023-03-01T01:00:00Z"
            }
        }

## Service Layer

```python
from fastapi import Depends, HTTPException
from sqlmodel import select
from typing import Optional, List
from .logging import LogContext
from .metrics import record_metric
import time

class AuthService:
    """Service layer for authentication and configuration operations"""

    def __init__(self, session: AsyncSession = Depends(get_session)):
        self.session = session
        self._setup_metrics()

    def _setup_metrics(self):
        """Initialize performance monitoring thresholds"""
        self.PERFORMANCE_THRESHOLDS = {
            "check_auth": 50,        # ms
            "track_request": 75,     # ms
            "check_rate_limit": 50,  # ms
            "update_config": 50,     # ms
            "get_usage": 100         # ms
        }

    async def check_authentication(
        self,
        api_source: str,
        api_key: str
    ) -> bool:
        """Check API authentication"""
        with LogContext(operation="check_auth") as log:
            start = time.perf_counter()
            try:
                if api_source == "govinfo":
                    response = await self.govinfo_api.test_auth(api_key)
                else:
                    response = await self.congress_api.test_auth(api_key)

                duration_ms = (time.perf_counter() - start) * 1000
                await self._record_performance(
                    "check_auth",
                    duration_ms,
                    log
                )

                if not response.ok:
                    raise AuthenticationError(
                        f"Authentication failed for {api_source}: {response.text}"
                    )

                return True

            except Exception as e:
                log.error("authentication_failed",
                    error=str(e),
                    api_source=api_source
                )
                raise

    async def track_request(
        self,
        api_source: str,
        endpoint: str,
        response: Response
    ) -> None:
        """Record API usage and update rate limit tracking"""
        with LogContext(operation="track_request") as log:
            start = time.perf_counter()
            try:
                usage = ApiUsage(
                    api_source=api_source,
                    endpoint=endpoint,
                    request_time=datetime.utcnow(),
                    rate_limit_remaining=response.headers.get('X-RateLimit-Remaining'),
                    reset_time=response.headers.get('X-RateLimit-Reset'),
                    response_time=response.elapsed.microseconds / 1000,
                    success=response.status_code == 200,
                    error_message=response.text if response.status_code != 200 else None
                )
                self.session.add(usage)
                await self.session.commit()

                duration_ms = (time.perf_counter() - start) * 1000
                await self._record_performance(
                    "track_request",
                    duration_ms,
                    log
                )

            except Exception as e:
                log.error("request_tracking_failed",
                    error=str(e),
                    api_source=api_source,
                    endpoint=endpoint
                )
                raise

    async def check_rate_limit(
        self,
        api_source: str
    ) -> bool:
        """Check if we're within rate limit bounds"""
        with LogContext(operation="check_rate_limit") as log:
            start = time.perf_counter()
            try:
                query = select(ApiUsage).where(
                    ApiUsage.api_source == api_source
                ).order_by(
                    ApiUsage.request_time.desc()
                ).limit(1)

                result = await self.session.execute(query)
                usage = result.scalar_one_or_none()

                if not usage:
                    return True

                remaining = usage.rate_limit_remaining
                reset_time = usage.reset_time

                if remaining is None:
                    return True

                buffer = await self._get_rate_limit_buffer(api_source)
                can_proceed = remaining > buffer or (
                    reset_time and reset_time < datetime.now(timezone.utc)
                )

                duration_ms = (time.perf_counter() - start) * 1000
                await self._record_performance(
                    "check_rate_limit",
                    duration_ms,
                    log
                )

                if not can_proceed:
                    raise RateLimitError(
                        f"Rate limit exceeded for {api_source}. "
                        f"Resets at {reset_time}"
                    )

                return True

            except Exception as e:
                log.error("rate_limit_check_failed",
                    error=str(e),
                    api_source=api_source
                )
                raise

    async def update_configuration(
        self,
        api_source: str,
        config_key: str,
        updates: ApiConfigUpdate
    ) -> ApiConfiguration:
        """Update API configuration"""
        with LogContext(operation="update_config") as log:
            start = time.perf_counter()
            try:
                query = select(ApiConfiguration).where(
                    ApiConfiguration.api_source == api_source,
                    ApiConfiguration.config_key == config_key
                )
                result = await self.session.execute(query)
                config = result.scalar_one_or_none()

                if not config:
                    raise ConfigurationError(
                        f"Configuration not found: {api_source}.{config_key}"
                    )

                update_data = updates.dict(exclude_unset=True)
                for key, value in update_data.items():
                    setattr(config, key, value)

                await self.session.commit()
                await self.session.refresh(config)

                duration_ms = (time.perf_counter() - start) * 1000
                await self._record_performance(
                    "update_config",
                    duration_ms,
                    log
                )
                return config

            except Exception as e:
                log.error("configuration_update_failed",
                    error=str(e),
                    api_source=api_source,
                    config_key=config_key
                )
                raise

    async def get_api_usage(self) -> Dict[str, ApiUsageResponse]:
        """Get current API usage statistics"""
        with LogContext(operation="get_usage") as log:
            start = time.perf_counter()
            try:
                usage = {}
                for source in ['govinfo', 'congress']:
                    query = select(
                        ApiUsage.api_source,
                        func.count().label('requests_made'),
                        func.min(ApiUsage.rate_limit_remaining).label('remaining'),
                        func.max(ApiUsage.reset_time).label('reset_at')
                    ).where(
                        ApiUsage.api_source == source,
                        ApiUsage.request_time > datetime.utcnow() - timedelta(hours=1)
                    ).group_by(
                        ApiUsage.api_source
                    )

                    result = await self.session.execute(query)
                    stats = result.first()

                    if stats:
                        usage[source] = ApiUsageResponse(
                            api_source=source,
                            requests_made=stats.requests_made,
                            remaining=stats.remaining,
                            reset_at=stats.reset_at
                        )

                duration_ms = (time.perf_counter() - start) * 1000
                await self._record_performance(
                    "get_usage",
                    duration_ms,
                    log
                )
                return usage

            except Exception as e:
                log.error("usage_retrieval_failed",
                    error=str(e)
                )
                raise

    async def _record_performance(
        self,
        operation: str,
        duration_ms: float,
        log: LogContext
    ):
        """Record and monitor operation performance"""
        threshold = self.PERFORMANCE_THRESHOLDS.get(operation, 100)
        if duration_ms > threshold:
            log.warning("slow_operation",
                operation=operation,
                duration_ms=duration_ms,
                threshold_ms=threshold
            )

        await record_metric(
            name="auth_operation_duration_ms",
            value=duration_ms,
            tags={"operation": operation}
        )
```

## FastAPI Endpoints

```python
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from typing import Dict, Optional

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post(
    "/test",
    response_model=Dict[str, bool],
    responses={
        401: {"description": "Authentication failed"}
    }
)
async def test_authentication(
    api_source: str = Query(
        ...,
        description="API source (govinfo/congress)"
    ),
    api_key: str = Query(
        ...,
        description="API key to test"
    ),
    service: AuthService = Depends()
) -> Dict[str, bool]:
    """Test API authentication"""
    is_valid = await service.check_authentication(api_source, api_key)
    return {"authenticated": is_valid}

@router.get(
    "/usage",
    response_model=Dict[str, ApiUsageResponse]
)
async def get_api_usage(
    service: AuthService = Depends()
) -> Dict[str, ApiUsageResponse]:
    """Get current API usage statistics"""
    return await service.get_api_usage()

@router.patch(
    "/config/{api_source}/{config_key}",
    response_model=ApiConfigResponse,
    responses={
        400: {"description": "Configuration error"},
        404: {"description": "Configuration not found"}
    }
)
async def update_configuration(
    api_source: str = Path(
        ...,
        description="API source (govinfo/congress)"
    ),
    config_key: str = Path(
        ...,
        description="Configuration key to update"
    ),
    updates: ApiConfigUpdate = None,
    service: AuthService = Depends()
) -> ApiConfigResponse:
    """Update API configuration"""
    return await service.update_configuration(
        api_source,
        config_key,
        updates
    )
```

## Testing

```python
from .test_utils import IntegrationTestBase, LogCapture
from .errors import AuthError, AuthenticationError, RateLimitError

class TestAuthEndpoints(IntegrationTestBase):
    """Integration tests for authentication endpoints"""

    async def test_authentication(
        self,
        client: TestClient,
        setup_db: AsyncSession
    ):
        """Test API authentication"""
        # Test valid authentication
        response = await client.post(
            "/api/auth/test",
            params={
                "api_source": "govinfo",
                "api_key": "valid_key"
            }
        )
        assert response.status_code == 200
        assert response.json()["data"]["authenticated"] is True

        # Test invalid authentication
        response = await client.post(
            "/api/auth/test",
            params={
                "api_source": "govinfo",
                "api_key": "invalid_key"
            }
        )
        assert response.status_code == 401
        error = AuthError(**response.json())
        assert error.error == "AuthenticationError"

    async def test_rate_limiting(
        self,
        client: TestClient,
        setup_db: AsyncSession
    ):
        """Test rate limit handling"""
        # Create usage records to trigger rate limit
        for _ in range(900):  # Near GovInfo limit
            await client.post(
                "/api/auth/test",
                params={
                    "api_source": "govinfo",
                    "api_key": "test_key"
                }
            )

        # Verify rate limit error
        response = await client.post(
            "/api/auth/test",
            params={
                "api_source": "govinfo",
                "api_key": "test_key"
            }
        )
        assert response.status_code == 429
        error = AuthError(**response.json())
        assert error.error == "RateLimitError"
        assert error.retry_after is not None

    async def test_configuration(
        self,
        client: TestClient,
        setup_db: AsyncSession
    ):
        """Test configuration management"""
        # Create configuration
        config_data = {
            "api_source": "govinfo",
            "config_key": "rate_limit_buffer",
            "config_value": "100"
        }
        response = await client.post(
            "/api/auth/config",
            json=config_data
        )
        assert response.status_code == 201
        config_id = response.json()["data"]["config_id"]

        # Update configuration
        update_data = {
            "config_value": "200"
        }
        response = await client.patch(
            f"/api/auth/config/govinfo/rate_limit_buffer",
            json=update_data
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["config_value"] == update_data["config_value"]

    async def test_usage_statistics(
        self,
        client: TestClient,
        setup_db: AsyncSession
    ):
        """Test usage statistics retrieval"""
        # Create some usage records
        for _ in range(10):
            await client.post(
                "/api/auth/test",
                params={
                    "api_source": "govinfo",
                    "api_key": "test_key"
                }
            )

        # Get usage statistics
        response = await client.get("/api/auth/usage")
        assert response.status_code == 200
        data = response.json()["data"]
        assert "govinfo" in data
        assert data["govinfo"]["requests_made"] == 10

    async def test_performance_monitoring(
        self,
        client: TestClient,
        setup_db: AsyncSession
    ):
        """Test performance monitoring"""
        with LogCapture() as logs:
            # Make multiple authentication requests
            for _ in range(10):
                await client.post(
                    "/api/auth/test",
                    params={
                        "api_source": "govinfo",
                        "api_key": "test_key"
                    }
                )

        # Check for slow operation warnings
        slow_ops = [
            log for log in logs.records
            if log.msg == "slow_operation"
        ]
        assert len(slow_ops) > 0
```
