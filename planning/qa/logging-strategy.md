# PyGovPub Logging Strategy

## Technical Terms

### Log Categories
- `api`: API interaction logs
- `sync`: Data synchronization logs
- `auth`: Authentication and authorization logs
- `document`: Document processing logs
- `perf`: Performance monitoring logs
- `security`: Security-related logs
- `system`: System operation logs

### Log Levels
- `debug` (10): Detailed debugging information
- `info` (20): General operational information
- `warning` (30): Warning messages for potential issues
- `error` (40): Error conditions requiring attention
- `critical` (50): Critical conditions requiring immediate action

### Metrics Types
- `counter`: Cumulative metric that only increases
- `histogram`: Samples observations and counts them in configurable buckets
- `gauge`: Single numerical value that can go up and down

## Overview

This document outlines PyGovPub's logging architecture, designed to provide comprehensive visibility into system operations, API interactions, and data synchronization processes. The strategy focuses on structured logging, distributed tracing, and metrics collection to support operational monitoring, debugging, and compliance requirements.

## Core Components

### 1. Structured Logging

#### Log Levels and Categories
```python
class LogCategory:
    """Log category definitions for system-wide use"""
    API_INTERACTION = "api"      # API request/response tracking
    SYNC = "sync"               # Data synchronization operations
    AUTH = "auth"               # Authentication events
    DOCUMENT = "document"       # Document processing
    PERFORMANCE = "perf"        # Performance metrics
    SECURITY = "security"       # Security events
    SYSTEM = "system"          # General system operations

class LogLevel:
    """Standard log levels with numeric values"""
    DEBUG = 10    # Detailed debugging information
    INFO = 20     # General operational information
    WARNING = 30  # Warning messages
    ERROR = 40    # Error conditions
    CRITICAL = 50 # Critical failures
```

#### Log Entry Schema
```python
from datetime import datetime
from typing import Optional, Dict, Any
from sqlmodel import SQLModel, Field
from uuid import UUID
from sqlalchemy import Index, text

class SystemLogs(SQLModel, table=True):
    """System-wide logging model for structured event tracking"""
    __tablename__ = "system_logs"

    # Composite indices for common queries
    __table_args__ = (
        Index('idx_logs_level_timestamp', 'level', 'timestamp'),
        Index('idx_logs_category_timestamp', 'category', 'timestamp'),
        # Partial index for recent errors
        Index('idx_recent_errors',
              'timestamp',
              postgresql_where=text("level >= 40 AND timestamp > now() - interval '24 hours'"))
    )

    log_id: Optional[int] = Field(
        default=None,
        primary_key=True,
        description="Unique log entry identifier"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Event timestamp"
    )
    level: int = Field(
        index=True,
        description="Log level (10:DEBUG to 50:CRITICAL)"
    )
    category: str = Field(
        max_length=50,
        index=True,
        description="Log category (api, sync, auth, etc.)"
    )
    trace_id: Optional[UUID] = Field(
        index=True,
        description="Distributed tracing identifier"
    )
    span_id: Optional[UUID] = Field(
        description="Trace span identifier"
    )
    source: Dict[str, Any] = Field(
        sa_column=Column(JSONB),
        description="Event source details"
    )
    context: Optional[Dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSONB),
        description="Additional context information"
    )
    metrics: Optional[Dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSONB),
        description="Associated metrics data"
    )
    message: str = Field(description="Log message")
    data: Optional[Dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSONB),
        description="Structured event data"
    )
    retention_days: int = Field(
        default=90,
        description="Log retention period in days"
    )

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
```

### 2. Logging Infrastructure

#### Database Tables

```sql
-- Structured Logs
CREATE TABLE system_logs (
    log_id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    level INTEGER NOT NULL,
    category VARCHAR(50) NOT NULL,
    trace_id UUID,
    span_id UUID,
    source JSONB NOT NULL,
    context JSONB,
    metrics JSONB,
    message TEXT NOT NULL,
    data JSONB,
    retention_days INTEGER DEFAULT 90,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Performance Metrics
CREATE TABLE performance_metrics (
    metric_id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    metric_name VARCHAR(100) NOT NULL,
    metric_value NUMERIC NOT NULL,
    labels JSONB,
    trace_id UUID,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Audit Trail
CREATE TABLE audit_trail (
    audit_id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    actor VARCHAR(100) NOT NULL,
    action VARCHAR(100) NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    entity_id TEXT NOT NULL,
    changes JSONB,
    trace_id UUID,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
```

### 3. Logging Implementation

#### FastAPI Integration
```python
from fastapi import FastAPI, Request, Response
from fastapi.middleware.base import BaseHTTPMiddleware
from contextlib import asynccontextmanager
from sqlmodel import Session, select
from typing import AsyncGenerator
import structlog
import time

logger = structlog.get_logger()

class LoggingMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: FastAPI, db: Database):
        super().__init__(app)
        self.db = db

    async def dispatch(self, request: Request, call_next) -> Response:
        trace_id = UUID(request.headers.get("X-Trace-ID", str(uuid.uuid4())))

        # Structured context binding
        log = logger.bind(
            trace_id=trace_id,
            path=request.url.path,
            method=request.method
        )

        # Request timing with async context manager
        async with self.log_request_timing(log) as metrics:
            try:
                response = await call_next(request)

                # Async log entry creation
                await self.db.execute(
                    insert(SystemLogs).values(
                        level=LogLevel.INFO,
                        category=LogCategory.API_INTERACTION,
                        trace_id=trace_id,
                        context={
                            "path": request.url.path,
                            "method": request.method,
                            "status_code": response.status_code,
                            "client_ip": request.client.host,
                            "user_agent": request.headers.get("user-agent")
                        },
                        metrics=metrics,
                        message=f"{request.method} {request.url.path} completed"
                    )
                )

                return response

            except Exception as e:
                log.error("request_failed", error=str(e), exc_info=True)
                raise

    @asynccontextmanager
    async def log_request_timing(self, log) -> AsyncGenerator[dict, None]:
        start_time = time.perf_counter()
        try:
            yield {}
        finally:
            duration = time.perf_counter() - start_time
            log.info("request_completed", duration=duration)
```

### 4. Analysis and Monitoring

#### Metrics Collection
```python
from prometheus_client import Counter, Histogram
from functools import wraps

request_duration = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'path']
)

error_counter = Counter(
    'error_total',
    'Total number of errors',
    ['category', 'level']
)

def track_metrics(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        try:
            result = await func(*args, **kwargs)
            return result
        finally:
            duration = time.perf_counter() - start_time
            request_duration.labels(
                method=kwargs.get('method'),
                path=kwargs.get('path')
            ).observe(duration)
```

#### Query Interface
```python
class LogAnalyzer:
    async def get_error_distribution(
        self,
        start_time: datetime,
        end_time: datetime,
        category: Optional[str] = None
    ):
        """Analyze error distribution by category and time"""

    async def get_performance_metrics(
        self,
        metric_name: str,
        aggregation: str = "avg",
        interval: str = "5m"
    ):
        """Retrieve aggregated performance metrics"""

    async def get_audit_trail(
        self,
        entity_type: str,
        entity_id: str
    ):
        """Retrieve audit trail for specific entity"""
```

## Retention and Archival

### Retention Policy
1. System Logs: 90 days active retention
2. Performance Metrics: 30 days at full resolution, 90 days aggregated
3. Audit Trail: 7 years for compliance
4. Error Logs: 180 days

### Archival Strategy
```sql
-- Archive partitioning
CREATE TABLE system_logs_archive (
    LIKE system_logs INCLUDING ALL
) PARTITION BY RANGE (timestamp);

-- Create monthly partitions
CREATE TABLE system_logs_archive_y2024m01
    PARTITION OF system_logs_archive
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
```

## Monitoring and Alerting

### Alert Conditions
1. Error Rate Thresholds
   - Critical: >5% error rate over 5 minutes
   - Warning: >2% error rate over 15 minutes

2. Performance Thresholds
   - Response Time: >2s p95 over 5 minutes
   - Memory Usage: >85% of allocated
   - CPU Usage: >80% sustained for 5 minutes

3. API Health
   - Rate Limit: <10% remaining
   - Authentication Failures: >3 in 5 minutes
   - Sync Delays: >30 minutes behind

### Alert Channels
1. Critical: PagerDuty + Slack
2. Warning: Slack + Email
3. Info: Dashboard Updates

## Implementation Priorities

### Phase 1: Core Logging
1. Structured logging implementation
2. Database schema deployment
3. Basic FastAPI integration

### Phase 2: Monitoring
1. Metrics collection
2. Alert configuration
3. Dashboard setup

### Phase 3: Analysis
1. Log analysis tools
2. Retention implementation
3. Archival system

### Phase 4: Advanced Features
1. Distributed tracing
2. Performance profiling
3. Custom analytics

## Best Practices

1. **Log Entry Guidelines**
   - Use structured logging consistently
   - Include relevant context
   - Maintain appropriate log levels
   - Add trace IDs for all operations

2. **Performance Considerations**
   - Async logging operations
   - Batch metric collection
   - Efficient log rotation
   - Index optimization

3. **Security**
   - Sanitize sensitive data
   - Encrypt audit trails
   - Access control for log data
   - Compliance validation

async def cleanup_old_logs(db: Database):
    """Efficient batch deletion of old logs"""
    async with db.transaction():
        await db.execute(
            text("""
                WITH old_logs AS (
                    SELECT log_id
                    FROM system_logs
                    WHERE timestamp < NOW() - (retention_days || ' days')::INTERVAL
                    LIMIT 10000
                    FOR UPDATE SKIP LOCKED
                )
                DELETE FROM system_logs
                WHERE log_id IN (SELECT log_id FROM old_logs)
            """)
        )

import pytest
from httpx import AsyncClient
from sqlmodel import Session
from typing import AsyncGenerator

@pytest.fixture
async def test_log_db(test_engine) -> AsyncGenerator[Session, None]:
    async with Session(test_engine) as session:
        yield session
        # Cleanup after tests
        await session.execute(delete(SystemLogs))
        await session.commit()

@pytest.mark.asyncio
async def test_request_logging(
    test_app: FastAPI,
    test_log_db: Session,
    test_client: AsyncClient
):
    # Arrange
    test_trace_id = uuid.uuid4()

    # Act
    response = await test_client.get(
        "/api/test",
        headers={"X-Trace-ID": str(test_trace_id)}
    )

    # Assert
    logs = await test_log_db.execute(
        select(SystemLogs).where(SystemLogs.trace_id == test_trace_id)
    )
    log_entry = logs.first()

    assert log_entry is not None
    assert log_entry.level == LogLevel.INFO
    assert log_entry.category == LogCategory.API_INTERACTION
    assert "duration_ms" in log_entry.metrics

@pytest.mark.parametrize("error_scenario", [
    ("database_timeout", DatabaseTimeout, 503),
    ("validation_error", ValidationError, 422),
    ("not_found", NotFoundError, 404)
])
async def test_error_logging(
    error_scenario: tuple,
    test_app: FastAPI,
    test_log_db: Session
):
    # Test error handling and logging
    error_name, error_class, expected_status = error_scenario
    # ... implement error scenario testing

class LogManager:
    def __init__(self, db: Database):
        self.db = db
        self._queue: asyncio.Queue[LogEntry] = asyncio.Queue(maxsize=1000)
        self._worker_task: Optional[asyncio.Task] = None

    async def start(self):
        self._worker_task = asyncio.create_task(self._process_queue())

    async def log(self, entry: LogEntry):
        await self._queue.put(entry)

    async def _process_queue(self):
        while True:
            batch = []
            try:
                while len(batch) < 100:
                    try:
                        entry = await asyncio.wait_for(
                            self._queue.get(),
                            timeout=0.1
                        )
                        batch.append(entry)
                    except asyncio.TimeoutError:
                        break

                if batch:
                    await self.db.execute(
                        insert(SystemLogs).values(batch)
                    )
            except Exception as e:
                logger.error("batch_processing_failed", error=str(e))
