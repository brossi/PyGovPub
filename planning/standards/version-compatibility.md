# Version Compatibility Standards

## API Version Tracking

### Congress.gov API
- Track API version in requests
- Monitor for version changes in responses
- Store version information with responses
```python
CONGRESS_API_VERSION = "v3"
CONGRESS_API_MIN_SUPPORTED = "v3"
```

### GovInfo.gov API
- Track API version in requests
- Monitor for version changes in responses
- Store version information with responses
```python
GOVINFO_API_VERSION = "2023-12"
GOVINFO_API_MIN_SUPPORTED = "2023-01"
```

## Version Compatibility Checks

### Request-Time Checks
```python
def verify_api_version(response: Response) -> bool:
    """Verify API version compatibility"""
    api_version = response.headers.get("api-version")
    return is_version_compatible(api_version, MIN_SUPPORTED_VERSION)
```

### Response Processing
```python
def process_response(response: Response) -> Dict:
    """Process API response with version validation"""
    if not verify_api_version(response):
        raise VersionIncompatibilityError(
            f"API version {response.version} not supported"
        )
    return response.json()
```

## Version Storage

### Database Schema
```sql
CREATE TABLE api_versions (
    version_id SERIAL PRIMARY KEY,
    api_source VARCHAR(10) NOT NULL,
    version_string VARCHAR(20) NOT NULL,
    first_seen TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    last_seen TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    is_supported BOOLEAN DEFAULT true
);

CREATE TABLE response_versions (
    response_id SERIAL PRIMARY KEY,
    api_source VARCHAR(10) NOT NULL,
    endpoint VARCHAR(100) NOT NULL,
    version_used VARCHAR(20) NOT NULL,
    response_time TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
```

## Version Monitoring

### Active Monitoring
- Check API version on each request
- Log version changes
- Alert on version deprecation notices
- Track endpoint-specific version requirements

### Version Change Handling
1. Detect version change in response
2. Log change details
3. Verify compatibility
4. Update stored version information
5. Trigger alerts if needed

## Documentation Requirements

### Version Documentation
- Document supported API versions
- Track version-specific features
- Maintain compatibility notes
- Document version migration steps

### Version-Specific Code
```python
if api_version >= "v3":
    # Use new endpoint structure
    endpoint = f"/v3/bill/{congress}/{bill_type}/{bill_number}"
else:
    # Use legacy endpoint structure
    endpoint = f"/bill/{congress}/{bill_type}-{bill_number}"
```

## Implementation in Phase Structure

### Phase Integration
- Version checks added to AUTH-001
- Version storage added to CORE-001
- Version monitoring added to DX-004
- Version documentation added to DX-002

### Quality Gates
- Version compatibility tests must pass
- Version change handling must be tested
- Version documentation must be complete
- Version monitoring must be operational
