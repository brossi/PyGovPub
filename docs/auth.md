# Authentication Guide

This guide explains how to configure and use authentication for the PyGovPub SDK.

## API Keys

PyGovPub integrates with two main API sources:

1. **Congress.gov API** (header-based authentication)
2. **GovInfo.gov API** (parameter-based authentication)

Both APIs require authentication using API keys.

### Setting Up API Keys

The simplest way to configure API keys is through environment variables:

```bash
# Add to your .env file
CONGRESS_GOV_API_KEY=your_congress_gov_api_key_here
GOVINFO_API_KEY=your_govinfo_api_key_here
```

You can also configure keys programmatically:

```python
from pygovpub.auth import AuthManager
from pygovpub.auth.models import ApiSource

# Create auth manager
auth_manager = AuthManager()

# Add keys
auth_manager.add_key(ApiSource.CONGRESS, "your_congress_gov_api_key")
auth_manager.add_key(ApiSource.GOVINFO, "your_govinfo_api_key")
```

## Key Security

PyGovPub uses secure encryption to protect API keys. By default, a random encryption key is generated for each session. For persistent key storage, set a fixed encryption key:

```bash
# Add to your .env file (generate with Fernet.generate_key())
PYGOVPUB_ENCRYPTION_KEY=your_encryption_key
```

The application never logs or displays API keys in plaintext.

## Rate Limit Management

Both APIs have hourly rate limits:
- Congress.gov: 5,000 requests/hour
- GovInfo.gov: 1,000 requests/hour

PyGovPub automatically tracks and enforces these limits with three strategies:

| Strategy | Behavior |
|----------|----------|
| `WAIT` (default) | Wait until capacity is available |
| `EXCEPTION` | Raise exception when limit reached |
| `QUEUE` | Queue requests when limit reached |

Configure the strategy through environment variables:

```bash
# Add to your .env file
PYGOVPUB_RATE_LIMIT_STRATEGY=wait
```

Or programmatically:

```python
from pygovpub.auth import AuthManager
from pygovpub.auth.rate_limiter import ThrottleStrategy

# Create auth manager with specific strategy
auth_manager = AuthManager(rate_limit_strategy=ThrottleStrategy.QUEUE)
```

### Advanced Rate Limit Tracking

PyGovPub uses a sophisticated system to track API rate limits:

1. **Database-backed tracking**: Rate limits are stored in partitioned database tables for high performance
2. **In-memory fallback**: If database operations fail, the system falls back to in-memory tracking
3. **Response header parsing**: Automatically parses rate limit information from API responses
4. **Per-source limit enforcement**: Each API source has its own independent rate limit tracking
5. **Monthly partitioning**: Rate limit data is automatically partitioned by month for efficient storage

Example usage of direct rate limiter access:

```python
from pygovpub.auth.rate_limiter import RateLimiter
from pygovpub.auth.models import ApiSource
import asyncio

# Create rate limiter
rate_limiter = RateLimiter()

async def main():
    # Pre-check if a request will be allowed
    allowed, reset_time = await rate_limiter.check_rate_limit(ApiSource.CONGRESS)
    
    if allowed:
        # Notify rate limiter before making request
        await rate_limiter.pre_request(ApiSource.CONGRESS)
        
        # Make your request here...
        
        # Update rate limiter with response headers
        await rate_limiter.track_request(
            source=ApiSource.CONGRESS,
            endpoint="/bills",
            status_code=200,
            rate_limit_headers={
                "x-ratelimit-remaining": "4998",
                "x-ratelimit-reset": "1617235200"
            }
        )
    else:
        print(f"Rate limited until {reset_time}")

# Purge old rate limit data (maintenance)
async def cleanup():
    # Keep only last 3 months of rate limit data
    await rate_limiter.purge_old_rate_limit_data(months_to_keep=3)

asyncio.run(main())
```

## Making Authenticated Requests

```python
import asyncio
from pygovpub.auth import AuthManager
from pygovpub.auth.models import ApiSource

async def fetch_bill():
    # Create auth manager
    auth_manager = AuthManager()
    
    # Make authenticated request
    result = await auth_manager.execute_request(
        source=ApiSource.CONGRESS,
        endpoint="/bill/117/hr/3076",
        params={"format": "json"}
    )
    
    return result

# Run the async function
bill_data = asyncio.run(fetch_bill())
```

## Version Compatibility

The AuthManager includes built-in version compatibility checks:

```python
from pygovpub.auth import AuthManager
from pygovpub.auth.models import ApiSource

# Create auth manager
auth_manager = AuthManager()

# Check version compatibility
is_compatible = auth_manager.check_version_compatibility(
    source=ApiSource.CONGRESS,
    version="3.0"
)

print(f"API version compatible: {is_compatible}")
```

## Database Integration

When using a database, PyGovPub can track API usage and rate limits:

```python
from sqlmodel import Session, create_engine
from pygovpub.auth import AuthManager

# Create database engine
engine = create_engine("sqlite:///pygovpub.db")

# Session factory function
def get_session():
    return Session(engine)

# Create auth manager with database integration
auth_manager = AuthManager(session_factory=get_session)
```

This enables persistent rate limit tracking across application restarts.

## Error Handling

```python
import asyncio
from pygovpub.auth import AuthManager
from pygovpub.auth.models import ApiSource
from pygovpub.exceptions import AuthenticationError, RateLimitExceededError

async def fetch_bill_with_error_handling():
    auth_manager = AuthManager()
    
    try:
        result = await auth_manager.execute_request(
            source=ApiSource.CONGRESS,
            endpoint="/bill/117/hr/3076"
        )
        return result
    except AuthenticationError as e:
        print(f"Authentication failed: {e}")
    except RateLimitExceededError as e:
        print(f"Rate limit exceeded: {e}")
        # Wait for rate limit reset
        if hasattr(e, 'retry_after') and e.retry_after:
            print(f"Retrying in {e.retry_after} seconds")
```