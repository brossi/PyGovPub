# Resiliency Patterns in PyGovPub

PyGovPub implements several resiliency patterns to ensure reliable operation even in the face of system failures, network issues, or external API problems. This document outlines the key resiliency patterns used throughout the library.

## Circuit Breaker Pattern

The circuit breaker pattern prevents cascading failures by failing fast when a system component is experiencing problems.

### Implementation

PyGovPub implements a decorator-based circuit breaker that monitors failures and "opens" the circuit when a threshold is reached:

```python
@CONNECTION_CIRCUIT_BREAKER
def update(self, model_class: Type[T], id: Any, data: Dict[str, Any]) -> bool:
    """Update operation with circuit breaker protection."""
    # Database operation code here
```

### Configuration Options

The circuit breaker can be configured with:

- `max_failures`: Number of consecutive failures before opening circuit (default: 5)
- `reset_timeout`: Time in seconds before attempting to close the circuit (default: 30)

### States

1. **Closed**: Normal operation, requests go through to the database
2. **Open**: Failing fast, immediately rejecting requests
3. **Half-open**: Testing if the system has recovered, allowing a single test request

### Monitoring

Circuit breaker state is tracked through Prometheus metrics:

```python
CIRCUIT_STATE = Gauge(
    "circuit_breaker_state", 
    "Circuit breaker state (0=closed, 1=open)", 
    ["db_type"]
)
```

## Retry with Exponential Backoff

For transient errors, PyGovPub implements retry with exponential backoff to automatically recover from temporary failures.

### Implementation

Using the `tenacity` library:

```python
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=True
)
def create(self, model_class: Type[T], data: Dict[str, Any]) -> Union[int, str]:
    """Create operation with retry capabilities."""
    # Database operation code here
```

### Configuration

- `stop_after_attempt(3)`: Retry up to 3 times before giving up
- `wait_exponential`: Wait 1s, then 2s, then 4s between retries
- `reraise=True`: Re-raise the original exception if all retries fail

## In-memory Fallbacks

PyGovPub maintains in-memory caches that serve as fallbacks when database operations fail.

### Rate Limiting Fallback

The rate limiter will fall back to in-memory tracking if database operations fail:

```python
async def check_rate_limit(self, source: ApiSource) -> Tuple[bool, Optional[datetime]]:
    """Check if rate limit allows another request."""
    # Try database first
    if self._session_factory:
        try:
            # Query database for rate limit info
            # ...
        except Exception:
            # Fall back to memory tracking on database error
            pass
    
    # Use in-memory tracking
    source_limits = self._memory_limits[source]
    # ...
```

### Implementation Details

- In-memory tracking is always maintained alongside database tracking
- If database operations fail, the system continues functioning using in-memory data
- When database connections are restored, data is synchronized back to persistent storage

## Graceful Degradation

PyGovPub implements graceful degradation by offering progressively reduced functionality when components fail.

### Search Degradation Flow

1. **Vector Search**: Fastest and most accurate for semantic queries
2. **Hybrid Search**: Falls back to hybrid search if vector search fails
3. **Text-only Search**: Falls back to text search if both vector and hybrid fail

### Degradation Control

Degradation is controlled through configuration:

```python
fallback_config = FallbackConfig(
    vector_quality_threshold=0.6,
    hybrid_quality_threshold=0.5,
    text_quality_threshold=0.4,
    results_count_threshold=3,
    enable_result_merging=True
)
```

## Bulkhead Pattern

The bulkhead pattern isolates failures to prevent them from cascading across the entire system.

### Connection Pool Configuration

PyGovPub configures connection pools with isolation parameters:

```python
engine = create_engine(
    connection_string,
    pool_size=config.get("pool_size", 5),
    max_overflow=config.get("max_overflow", 10),
    pool_timeout=config.get("pool_timeout", 30),
    pool_recycle=config.get("pool_recycle", 1800)
)
```

### Cross-database Type Isolation

Each database provider operates independently, ensuring that failures in one don't affect others:

```python
# Operations on different database types are isolated
sql_result = storage.get(Model, id)  # SQL operation

# Even if this fails, SQL operations continue to work
vector_result = storage.vector_search_with_provider("lancedb", Model, vector)
```

## Timeouts

Proper timeout handling prevents resources being tied up indefinitely.

### Implementation

```python
# Request timeout for API calls
response = await session.get(url, timeout=aiohttp.ClientTimeout(total=10))

# Database query timeout
with engine.connect().execution_options(timeout=30) as conn:
    result = conn.execute(query)
```

## Health Checks

PyGovPub includes health check mechanisms to proactively detect issues.

### Ping Database

```python
def check_database_health(self) -> Dict[str, Any]:
    """Check database connectivity and health."""
    start_time = time.time()
    try:
        with self.engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            return {
                "status": "healthy",
                "response_time_ms": int((time.time() - start_time) * 1000)
            }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "response_time_ms": int((time.time() - start_time) * 1000)
        }
```

## Connection Pool Management

Proper connection pool management ensures efficient use of database resources.

### Implementation

```python
# Track active connections
DB_CONNECTIONS_ACTIVE = Gauge(
    "db_connections_active", 
    "Active database connections", 
    ["db_type"]
)

# Increment counter before operation
DB_CONNECTIONS_ACTIVE.labels(db_type=self.db_type).inc()

# Always decrement counter after operation
finally:
    session.close()
    DB_CONNECTIONS_ACTIVE.labels(db_type=self.db_type).dec()
```

## Session Handling

Proper session handling ensures resources are released even when operations fail.

### Implementation

```python
try:
    # Database operations
    session.add(instance)
    session.commit()
    return result
except Exception as e:
    # Error handling
    session.rollback()
    raise
finally:
    # Always close session
    session.close()
```

## Best Practices for Using Resiliency Patterns

1. **Combine Patterns**: Use multiple patterns together for comprehensive resilience
2. **Configure Timeouts**: Set appropriate timeouts for all external operations
3. **Measure Everything**: Monitor all failures and recovery attempts
4. **Test Failures**: Regularly test how your system behaves under failure conditions
5. **Avoid Cascading Timeouts**: Ensure downstream timeouts don't exceed upstream timeouts

## Example: Complete Resilient Database Operation

```python
@CONNECTION_CIRCUIT_BREAKER
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=True
)
def create(self, model_class: Type[T], data: Dict[str, Any]) -> Union[int, str]:
    """Create a new record with full resiliency protection."""
    start_time = time.time()
    session = self.Session()

    try:
        # Track active connections
        DB_CONNECTIONS_ACTIVE.labels(db_type=self.db_type).inc()

        # Execute operation with timeout
        with session.connection().execution_options(timeout=30):
            instance = model_class(**data)
            session.add(instance)
            session.commit()

        # Track successful operation
        DB_OPERATIONS.labels(
            operation="create", 
            status="success", 
            db_type=self.db_type
        ).inc()
        
        # Track operation duration
        DB_OPERATION_DURATION.labels(
            operation="create", 
            db_type=self.db_type
        ).observe(time.time() - start_time)

        return instance.id

    except Exception as e:
        # Rollback transaction
        session.rollback()
        
        # Track failed operation
        DB_OPERATIONS.labels(
            operation="create", 
            status="error", 
            db_type=self.db_type
        ).inc()
        
        # Log error
        logger.error(
            "Failed to create record",
            model=model_class.__name__,
            error=str(e),
            error_type=type(e).__name__
        )
        
        # Re-raise for circuit breaker and retry handling
        raise
        
    finally:
        # Always clean up resources
        session.close()
        
        # Decrement active connection count
        DB_CONNECTIONS_ACTIVE.labels(db_type=self.db_type).dec()
```