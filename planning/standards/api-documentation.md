# API Documentation Standards

## Overview
PyGovPub APIs must be thoroughly documented using OpenAPI (Swagger) specifications. FastAPI automatically generates OpenAPI documentation, but proper annotation is required for comprehensive and useful documentation.

## OpenAPI Documentation Requirements

### Endpoint Documentation
```python
@router.get(
    "/bills/{bill_id}",
    response_model=BillResponse,
    responses={
        404: {"description": "Bill not found"},
        429: {"description": "Rate limit exceeded"}
    },
    summary="Retrieve Bill Information",
    description="Get detailed information about a specific bill, including its current status and metadata.",
    tags=["Bills"]
)
async def get_bill(
    bill_id: str = Path(..., description="Bill identifier in format: {type}{number}-{congress}"),
    version: Optional[str] = Query(None, description="Specific bill version code (e.g., 'ih', 'eh')")
):
    """
    Retrieve comprehensive information about a legislative bill.

    Parameters:
    - **bill_id**: Unique identifier for the bill (e.g., "HR1234-117")
    - **version**: Optional bill version code to retrieve specific version

    Returns:
    - Bill information including status, text, and related documents

    Rate Limits:
    - Congress.gov: 5,000 requests/hour
    - GovInfo.gov: 1,000 requests/hour (bulk downloads exempt)
    """
```

### Model Documentation
```python
class BillResponse(SQLModel):
    """Standardized bill information response model."""

    bill_id: str = Field(
        ...,
        description="Unique bill identifier",
        example="HR1234-117"
    )
    congress_id: int = Field(
        ...,
        description="Congressional session number",
        example=117,
        ge=1
    )
    bill_type: str = Field(
        ...,
        description="Type of bill (hr, s, hjres, etc.)",
        example="hr"
    )

    class Config:
        schema_extra = {
            "example": {
                "bill_id": "HR1234-117",
                "congress_id": 117,
                "bill_type": "hr",
                "title": "Example Bill Title"
            }
        }
```

## Documentation Guidelines

### 1. Endpoint Documentation
- Clear, concise summary (one line)
- Detailed description of functionality
- All parameters documented with:
  - Data type and constraints
  - Description
  - Example values
- Response codes and their meanings
- Rate limits and quotas
- Authentication requirements

### 2. Request/Response Models
- All fields documented with descriptions
- Example values for all fields
- Clear validation rules
- Relationships to other models
- Nested object structures explained

### 3. Error Responses
```python
class APIError(BaseModel):
    """Standard error response model."""

    error: str = Field(
        ...,
        description="Error type identifier",
        example="RateLimitExceeded"
    )
    detail: str = Field(
        ...,
        description="Human-readable error description",
        example="API rate limit exceeded. Please wait 60 seconds."
    )
    entity_type: Optional[str] = Field(
        None,
        description="Type of entity related to error",
        example="bill"
    )
```

### 4. Security Schemes
```python
app = FastAPI(
    title="PyGovPub API",
    description="Unified access to U.S. Federal Government public data",
    version="1.0.0",
    openapi_tags=[
        {"name": "Bills", "description": "Operations with legislative bills"},
        {"name": "Members", "description": "Congressional member information"}
    ],
    openapi_url="/api/v1/openapi.json"
)

app.add_middleware(
    SecurityMiddleware,
    schemes=[
        {"type": "apiKey", "name": "X-API-Key", "in": "header"}
    ]
)
```

## Best Practices

### 1. Versioning
- Include API version in URL path
- Document breaking changes
- Maintain backward compatibility when possible

### 2. Examples
- Provide realistic example values
- Include multiple examples for complex endpoints
- Show both success and error scenarios

### 3. Schema Organization
- Group related endpoints with tags
- Use consistent naming patterns
- Document relationships between schemas

### 4. Testing
- Validate OpenAPI schema generation
- Ensure examples are valid
- Test documentation accuracy

## Implementation Checklist

1. Endpoint Documentation
   - [ ] Summary and description
   - [ ] Parameters fully documented
   - [ ] Response models defined
   - [ ] Error responses listed
   - [ ] Rate limits noted

2. Model Documentation
   - [ ] Field descriptions
   - [ ] Example values
   - [ ] Validation rules
   - [ ] Relationships noted

3. Security
   - [ ] Authentication methods
   - [ ] Authorization requirements
   - [ ] Rate limit documentation

4. Examples
   - [ ] Request examples
   - [ ] Response examples
   - [ ] Error examples

## Validation

The documentation should be validated:
1. Automatically during CI/CD
2. Through OpenAPI schema validation
3. By reviewing generated Swagger UI
4. Through integration tests

## Tools

### Recommended Tools
- FastAPI's built-in docs (`/docs` and `/redoc`)
- OpenAPI validators
- Documentation testing tools
- Schema generators

### Quality Checks
```python
from fastapi.openapi.utils import get_openapi

def validate_openapi_docs(app: FastAPI):
    """Validate OpenAPI documentation completeness."""
    schema = get_openapi(
        title=app.title,
        version=app.version,
        routes=app.routes
    )

    # Validate all routes have documentation
    for route in app.routes:
        assert route.description, f"Route {route.path} missing description"
        assert route.response_model, f"Route {route.path} missing response model"

```

## PyGovPub Endpoint Examples

### 1. Bill Status Endpoint
```python
@router.get(
    "/bills/{bill_id}/status",
    response_model=BillStatusResponse,
    responses={
        404: {"description": "Bill not found"},
        429: {"description": "Rate limit exceeded"},
        503: {"description": "Source API unavailable"}
    },
    summary="Get Bill Status Information",
    description="""
    Retrieve current status and history of a legislative bill.
    Automatically selects between Congress.gov (for recent updates) and GovInfo.gov (for authenticated history).
    """,
    tags=["Bills"]
)
async def get_bill_status(
    bill_id: str = Path(
        ...,
        description="Bill identifier in format: {type}{number}-{congress}",
        example="HR1234-117"
    ),
    include_history: bool = Query(
        False,
        description="Include full status history"
    ),
    source: Optional[str] = Query(
        None,
        description="Force specific source (congress/govinfo). Default: auto-select"
    )
) -> BillStatusResponse:
    """
    Get comprehensive bill status information.

    This endpoint provides real-time bill status data by intelligently routing requests
    between Congress.gov and GovInfo.gov based on data freshness and availability.

    Parameters:
    - **bill_id**: Unique identifier for the bill (e.g., "HR1234-117")
    - **include_history**: Whether to include full status history
    - **source**: Optional override for data source selection

    Returns:
    - Current bill status
    - Latest action information
    - Committee referrals
    - If requested, full status history

    Rate Limits:
    - Congress.gov: 5,000 requests/hour
    - GovInfo.gov: 1,000 requests/hour (bulk downloads exempt)

    Notes:
    - Recent bills (current congress) default to Congress.gov
    - Historical bills default to GovInfo.gov
    - Digital signatures are verified for GovInfo.gov responses
    """
```

### 2. Committee Information Endpoint
```python
@router.get(
    "/committees/{committee_id}/members",
    response_model=CommitteeMemberList,
    responses={
        404: {"description": "Committee not found"},
        429: {"description": "Rate limit exceeded"}
    },
    summary="Get Committee Membership",
    description="Retrieve current membership information for a congressional committee.",
    tags=["Committees"]
)
async def get_committee_members(
    committee_id: str = Path(
        ...,
        description="Committee identifier (e.g., HSAG for House Agriculture)",
        example="HSAG"
    ),
    congress: Optional[int] = Query(
        None,
        description="Specific congress number (default: current)",
        ge=93
    ),
    role: Optional[str] = Query(
        None,
        description="Filter by member role (chair, ranking-member, member)"
    )
) -> CommitteeMemberList:
    """
    Get committee membership information.

    Provides detailed information about committee members, including leadership roles,
    subcommittee assignments, and service periods.

    Parameters:
    - **committee_id**: Official committee identifier code
    - **congress**: Optional congress number (defaults to current)
    - **role**: Optional filter for specific member roles

    Returns:
    - List of committee members with roles and service information
    - Committee leadership structure
    - Subcommittee assignments

    Source Attribution:
    - Member data from Congress.gov
    - Historical data from GovInfo.gov
    """
```

### 3. Document Authentication Endpoint
```python
@router.get(
    "/documents/{package_id}/verify",
    response_model=DocumentVerification,
    responses={
        404: {"description": "Document not found"},
        422: {"description": "Invalid package ID format"},
        429: {"description": "Rate limit exceeded"}
    },
    summary="Verify Document Authentication",
    description="""
    Verify the authenticity of a government document using digital signatures.
    Supports documents from GovInfo.gov with PKI signatures.
    """,
    tags=["Documents"]
)
async def verify_document(
    package_id: str = Path(
        ...,
        description="GovInfo.gov package identifier",
        example="BILLS-117hr1234ih"
    ),
    check_timestamp: bool = Query(
        True,
        description="Verify signature timestamp validity"
    )
) -> DocumentVerification:
    """
    Verify document authenticity using digital signatures.

    This endpoint verifies the authenticity of official government documents
    by validating their digital signatures against the GPO's PKI infrastructure.

    Parameters:
    - **package_id**: GovInfo.gov package identifier
    - **check_timestamp**: Whether to verify signature timestamps

    Returns:
    - Verification status
    - Signature details
    - Timestamp validation
    - Chain of custody information

    Security Notes:
    - Uses GPO's public key infrastructure
    - Validates against Certificate Revocation Lists
    - Checks signature timestamps when requested
    """
```
