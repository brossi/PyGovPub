# Resiliency Configuration

This document describes how to configure and use the resiliency features in PyGovPub, including circuit breakers, retries, and fallbacks.

## Circuit Breakers

Circuit breakers are used to prevent cascading failures by stopping requests to services that have repeatedly failed. They have three states:

- **Closed**: Normal operation, all requests proceed.
- **Open**: Service has failed repeatedly, requests are blocked.
- **Half-Open**: Testing if service has recovered after failure.

### Configuration

You can configure circuit breakers through the `CircuitBreakerRegistry`:

```python
from pygovpub.recovery import CircuitBreakerRegistry

# Get the registry
registry = CircuitBreakerRegistry()

# Configure a circuit breaker
circuit_breaker = registry.get_circuit_breaker(
    name="api_client",
    failure_threshold=5,        # Number of failures before opening
    recovery_timeout=30,        # Seconds before testing if service recovered
    excluded_exceptions=[       # Exceptions that don't count as failures
        ResourceNotFoundError
    ]
)
```

### Usage with Async Functions

```python
async def fetch_data(api_client, query):
    # Get circuit breaker
    registry = CircuitBreakerRegistry()
    circuit_breaker = registry.get_circuit_breaker("api_client")
    
    # Execute with circuit breaker protection
    try:
        result = await circuit_breaker.execute(
            api_client.fetch, query=query
        )
        return result
    except PyGovPubException as e:
        # Handle circuit open or service failure
        logger.error(f"Service unavailable: {str(e)}")
        return None
```

### Monitoring Circuit Breakers

To check the status of all circuit breakers:

```python
from pygovpub.diagnostics.health import check_circuit_breakers

# Get circuit breaker status
circuit_status = check_circuit_breakers()

# Check if any circuits are open
critical_circuits = circuit_status["critical_circuits"]
if critical_circuits:
    print(f"Warning: {len(critical_circuits)} circuits in critical state")
    for circuit in critical_circuits:
        print(f"- {circuit['name']} in {circuit['state']} state")
```

## Retry Strategies

PyGovPub provides several retry decorators for common scenarios:

### Exponential Backoff

For general transient errors:

```python
from pygovpub.recovery import with_backoff_retry

@with_backoff_retry(
    max_attempts=3,
    max_delay=30.0,
    multiplier=2.0,
    jitter=0.1
)
async def fetch_document(document_id):
    # Function will retry up to 3 times with exponential backoff
    response = await api_client.get_document(document_id)
    return response
```

### Rate Limit Handling

For rate limit exceeded errors:

```python
from pygovpub.recovery import with_rate_limit_retry

@with_rate_limit_retry(max_attempts=5, max_delay=60.0)
async def search_bills(query):
    # Will retry when rate limits are hit, respecting retry-after headers
    response = await api_client.search(query)
    return response
```

### API-Specific Retries

For specific API error codes:

```python
from pygovpub.recovery import with_api_retry

@with_api_retry(
    max_attempts=3,
    retry_status_codes={500, 502, 503, 504}
)
async def get_bill_status(bill_id):
    # Will retry on server errors
    response = await api_client.get_bill(bill_id)
    return response
```

## Fallback Mechanisms

For providing alternative data sources when primary sources fail:

```python
from pygovpub.recovery import Fallback

async def get_bill_data(bill_id):
    fallback = Fallback()
    
    # Define primary and fallback functions
    async def from_api():
        return await api_client.get_bill(bill_id)
    
    async def from_cache():
        return cache.get(f"bill:{bill_id}")
    
    async def from_database():
        return await db.query(f"SELECT * FROM bills WHERE id = '{bill_id}'")
    
    # Try primary first, then fallbacks in order
    result = await fallback.execute_with_fallbacks(
        from_api,
        [from_cache, from_database],
        # Any additional args would be passed to all functions
    )
    
    return result
```

## Health Check Integration

PyGovPub automatically integrates circuit breaker status with health checks:

```python
from pygovpub.diagnostics.health import run_health_check

# Run health check
health_status = run_health_check()

# Get overall system status
status = health_status["status"]  # "healthy", "degraded", "unhealthy", or "critical"

# Get circuit breaker details
circuit_breakers = health_status["circuit_breakers"]
```

The health check will report:
- **Healthy**: All systems operational
- **Degraded**: At least one circuit breaker in half-open state or fewer than 50% open
- **Unhealthy**: More than 50% of circuit breakers are open
- **Critical**: All APIs are unreachable

## Configuration Best Practices

1. **Customize Per Service**: Configure different thresholds for different services based on their importance and reliability.

2. **Exclude Non-Critical Errors**: Use `excluded_exceptions` to prevent non-critical errors from triggering circuit breakers.

3. **Monitor Recovery Time**: Set `recovery_timeout` based on how long the service typically takes to recover.

4. **Add Jitter to Retries**: Always use jitter with retries to prevent thundering herd effects.

5. **Set Appropriate Retry Limits**: Be cautious with max retry attempts to avoid overwhelming services.

6. **Use Health Checks**: Regularly run health checks to monitor circuit breaker status.