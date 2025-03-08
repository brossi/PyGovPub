# PyGovPub Test Manifest

o## Test Base Classes and Utilities

### FastAPI Test Base
```python
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from typing import AsyncGenerator, Dict, Any

class TestBase:
    """Base class for all API tests leveraging FastAPI TestClient"""

    @pytest.fixture(scope="session")
    def engine(self):
        return create_engine(
            "postgresql+asyncpg://test:test@localhost:5432/test",
            echo=True,
            future=True
        )

    @pytest.fixture(autouse=True)
    async def setup_db(self, engine) -> AsyncGenerator[Session, None]:
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

        async with Session(engine) as session:
            yield session
            await session.rollback()

    @pytest.fixture
    def client(self, setup_db) -> TestClient:
        from app.main import app
        return TestClient(app)

### Pydantic Test Models
```python
from pydantic import BaseModel, Field, validator
from datetime import datetime
from typing import Optional

class TestBillRequest(BaseModel):
    """Test model for bill API requests"""
    congress: int = Field(..., ge=1, le=118)
    bill_type: str = Field(..., regex="^(hr|s|hjres|sjres)$")
    number: int = Field(..., gt=0)

    @validator("congress")
    def validate_congress_number(cls, v):
        if v < 1 or v > current_congress():
            raise ValueError("Invalid congress number")
        return v

class TestAPIResponse(BaseModel):
    """Base model for API response validation"""
    status: int
    message: str
    data: Optional[Dict[str, Any]]
    timestamp: datetime

### PostgreSQL Test Utilities
```python
class PostgresTestUtils:
    """Utilities leveraging PostgreSQL features"""

    @staticmethod
    async def verify_trigger_execution(session: Session, table: str, operation: str):
        """Verify PostgreSQL trigger execution"""
        result = await session.execute(
            text("""
                SELECT EXISTS (
                    SELECT 1 FROM pg_trigger
                    WHERE tgrelid = :table::regclass
                    AND tgname = :trigger_name
                )
            """),
            {"table": table, "trigger_name": f"{table}_{operation}_trigger"}
        )
        return result.scalar()

    @staticmethod
    async def check_index_usage(session: Session, table: str, index: str):
        """Check if index is being used"""
        return await session.execute(
            text("""
                SELECT idx_scan
                FROM pg_stat_user_indexes
                WHERE schemaname = 'public'
                AND tablename = :table
                AND indexrelname = :index
            """),
            {"table": table, "index": index}
        )
```

## Core Authentication Tests

### Client Initialization and Configuration
```python
def test_client_initialization_basic():
    """Verify client initializes with minimal required configuration (just API keys)"""

def test_client_initialization_full_config():
    """Verify client initializes with complete configuration options"""

def test_client_initialization_validation():
    """Verify validation of configuration parameters:
    - cache_enabled type checking
    - rate_limit_buffer range validation
    - retry_attempts range validation
    """

def test_client_config_defaults():
    """Verify default configuration values are correctly applied"""

def test_client_config_override():
    """Verify configuration overrides work as expected"""

def test_client_lifecycle():
    """Verify client cleanup on shutdown:
    - Database connections closed
    - Cache cleared
    - Active requests completed
    """

def test_client_async_context():
    """Verify client works as async context manager:
    - Proper initialization in __aenter__
    - Resource cleanup in __aexit__
    """

def test_connection_pool():
    """Verify connection pool management:
    - Pool size limits
    - Connection reuse
    - Pool cleanup
    """
```

### API Key Management
```python
def test_congress_key_header_formatting():
    """Verify Congress.gov API key is correctly formatted in X-API-Key header"""

def test_govinfo_key_query_param():
    """Verify GovInfo.gov API key is correctly included as query parameter"""

def test_key_validation():
    """Verify API key validation:
    - Key format checking
    - Key length validation
    - Character set validation
    """

def test_key_persistence():
    """Verify API keys are properly stored and retrieved from configuration"""

def test_key_rotation():
    """Verify API key rotation:
    - New key acceptance
    - Old key deprecation
    - Request retry with new key
    """

def test_missing_key_handling():
    """Verify handling of missing API keys:
    - Missing Congress.gov key
    - Missing GovInfo.gov key
    - Missing both keys
    """

def test_invalid_key_handling():
    """Verify handling of invalid API keys:
    - Malformed keys
    - Expired keys
    - Revoked keys
    """
```

### Rate Limit Management
```python
def test_congress_rate_limit_tracking():
    """Verify Congress.gov rate limit tracking:
    - Request counting
    - Remaining requests calculation
    - Reset time tracking
    - Buffer enforcement (100 requests)
    """

def test_govinfo_rate_limit_tracking():
    """Verify GovInfo.gov rate limit tracking:
    - Request counting
    - Remaining requests calculation
    - Reset time tracking
    - Bulk download exemption
    """

def test_rate_limit_headers_parsing():
    """Verify parsing of rate limit headers:
    - X-RateLimit-Remaining
    - X-RateLimit-Reset
    - Header format variations
    """

def test_rate_limit_persistence():
    """Verify rate limit data persistence:
    - Storage in api_usage table
    - Reset time updates
    - Historical tracking
    """

def test_rate_limit_buffer():
    """Verify rate limit buffer behavior:
    - Buffer threshold enforcement
    - Buffer configuration
    - Buffer reset handling
    """

def test_concurrent_request_limits():
    """Verify rate limiting under concurrent requests:
    - Multiple simultaneous requests
    - Queue management
    - Request prioritization
    """

def test_bulk_download_exemption():
    """Verify bulk download exemption for GovInfo.gov:
    - Bulk request identification
    - Rate limit bypass
    - Download tracking
    """
```

### Database Schema
```python
def test_schema_validation():
    """Verify database schema requirements:
    - Required tables exist
    - Column constraints enforced
    - Indexes present
    """

def test_schema_migrations():
    """Verify schema migration handling:
    - Version tracking
    - Forward migration
    - Rollback support
    """
```

### Error Handling
```python
def test_auth_error_handling():
    """Verify authentication error handling:
    - Error message formatting
    - Error logging to sync_errors
    - Error propagation
    - Retry logic
    """

def test_rate_limit_error_handling():
    """Verify rate limit error handling:
    - Wait time calculation
    - Reset time handling
    - Request queuing
    - Retry scheduling
    """

def test_network_error_handling():
    """Verify network error handling:
    - Connection timeouts
    - DNS failures
    - SSL errors
    - Retry logic
    """

def test_error_logging():
    """Verify error logging:
    - Log entry creation
    - Error detail capture
    - Timestamp accuracy
    - Source tracking
    """
```

### Usage Monitoring
```python
def test_usage_tracking():
    """Verify API usage tracking:
    - Request recording
    - Response time tracking
    - Success/failure logging
    - Error message capture
    """

def test_usage_statistics():
    """Verify usage statistics calculation:
    - Request counting
    - Rate limit tracking
    - Time window calculations
    - Source separation
    """

def test_usage_reporting():
    """Verify usage report generation:
    - Report accuracy
    - Time period filtering
    - Source filtering
    - Aggregation
    """
```

### FastAPI Integration
```python
def test_fastapi_dependency_injection():
    """Verify FastAPI dependency injection:
    - Client injection
    - Configuration handling
    - Error propagation
    """

def test_fastapi_lifecycle():
    """Verify FastAPI lifecycle management:
    - Startup initialization
    - Shutdown cleanup
    - Resource management
    """

def test_fastapi_middleware():
    """Verify FastAPI middleware integration:
    - Authentication middleware
    - Rate limit middleware
    - Error handling middleware
    """

def test_fastapi_error_handling():
    """Verify FastAPI error handling:
    - Error response formatting
    - Status code mapping
    - Error detail propagation
    """
```

## Database Integration Tests

### Usage Tracking Tests
```python
def test_api_usage_recording():
    """Verify API usage is properly recorded in database"""

def test_usage_statistics_calculation():
    """Verify accurate calculation of usage statistics"""

def test_error_logging():
    """Verify proper logging of API errors and failures"""

def test_response_time_tracking():
    """Verify accurate tracking of API response times"""
```

### Configuration Management Tests
```python
def test_config_persistence():
    """Verify configuration changes are properly persisted"""

def test_config_retrieval():
    """Verify accurate retrieval of stored configurations"""

def test_config_validation():
    """Verify validation of configuration values"""

def test_config_update_atomicity():
    """Verify atomic updates of configuration values"""
```

## Error Handling Tests

### Authentication Error Tests
```python
def test_auth_failure_handling():
    """Verify proper handling of authentication failures"""

def test_auth_error_logging():
    """Verify authentication errors are properly logged"""

def test_auth_retry_behavior():
    """Verify retry behavior for authentication failures"""
```

### Rate Limit Error Tests
```python
def test_rate_limit_exceeded_handling():
    """Verify proper handling of rate limit exceeded scenarios"""

def test_rate_limit_wait_behavior():
    """Verify proper wait behavior when rate limits are exceeded"""

def test_concurrent_request_handling():
    """Verify proper handling of concurrent requests under rate limits"""
```

## FastAPI Integration Tests

### Dependency Injection Tests
```python
def test_client_dependency_injection():
    """Verify proper client injection in FastAPI endpoints"""

def test_client_lifecycle_in_fastapi():
    """Verify client lifecycle management in FastAPI context"""

def test_client_error_propagation():
    """Verify proper error propagation through FastAPI endpoints"""
```

### Middleware Tests
```python
def test_rate_limit_middleware():
    """Verify rate limit middleware functionality"""

def test_auth_middleware():
    """Verify authentication middleware functionality"""

def test_error_handling_middleware():
    """Verify error handling middleware functionality"""
```

## Integration Test Scenarios

### Congress.gov Integration Tests
```python
def test_congress_request_formatting():
    """Verify proper formatting of Congress.gov API requests"""

def test_congress_response_parsing():
    """Verify proper parsing of Congress.gov API responses"""

def test_congress_error_handling():
    """Verify handling of Congress.gov API errors"""
```

### GovInfo.gov Integration Tests
```python
def test_govinfo_request_formatting():
    """Verify proper formatting of GovInfo.gov API requests"""

def test_govinfo_response_parsing():
    """Verify proper parsing of GovInfo.gov API responses"""

def test_govinfo_error_handling():
    """Verify handling of GovInfo.gov API errors"""
```

## Legislative Endpoint Tests

### Bill Tests
```python
from sqlmodel import SQLModel, Field, UniqueConstraint, select

class TestBill(SQLModel, table=True):
    """SQLModel for bill test data"""
    __tablename__ = "test_bills"

    id: Optional[int] = Field(default=None, primary_key=True)
    bill_id: str = Field(index=True)
    congress: int = Field(index=True)
    version_code: str

    __table_args__ = (
        UniqueConstraint("bill_id", "version_code", name="uq_bill_version"),
    )

class TestBillOperations(TestBase):
    """Test bill operations with comprehensive validation"""

    @pytest.fixture
    async def seed_test_data(self, setup_db: Session):
        """Fixture to seed test data using SQLModel"""
        bills = [
            TestBill(bill_id="HR1234", congress=117, version_code="ih"),
            TestBill(bill_id="S2345", congress=117, version_code="is")
        ]
        setup_db.add_all(bills)
        await setup_db.commit()

    @pytest.mark.parametrize("bill_type,number_range,congress", [
        ("hr", (1, 9999), 118),
        ("s", (1, 9999), 118),
        ("hjres", (1, 999), 118)
    ])
    async def test_bill_number_validation(
        self,
        client: TestClient,
        bill_type: str,
        number_range: tuple,
        congress: int
    ):
        """Verify bill number validation"""
        request = TestBillRequest(
            congress=congress,
            bill_type=bill_type,
            number=number_range[0]
        )
        response = await client.post("/api/bills", json=request.dict())
        result = TestAPIResponse(**response.json())
        assert result.status == 201

    @pytest.mark.parametrize("version_code,requirements", [
        ("ih", ["introduced_date", "sponsor"]),
        ("rh", ["reported_date", "committee"]),
        ("eh", ["engrossed_date", "vote_record"])
    ])
    async def test_bill_version_requirements(
        self,
        setup_db: Session,
        version_code: str,
        requirements: list
    ):
        """Verify bill version requirements"""
        bill = TestBill(
            bill_id="HR1234",
            congress=117,
            version_code=version_code
        )
        setup_db.add(bill)
        await setup_db.commit()

        result = await setup_db.execute(
            select(TestBill).where(TestBill.version_code == version_code)
        )
        db_bill = result.scalar_one()
        assert all(hasattr(db_bill, req) for req in requirements)

    @pytest.mark.parametrize("action_type,validators", [
        ("introduced", ["date", "sponsor", "chamber"]),
        ("referred", ["date", "committee", "referral_type"]),
        ("reported", ["date", "committee", "report_number"])
    ])
    async def test_bill_action_validation(
        self,
        client: TestClient,
        action_type: str,
        validators: list
    ):
        """Verify bill action validation"""
        response = await client.post(
            f"/api/bills/HR1234/actions",
            json={"action_type": action_type, "data": {}}
        )
        result = TestAPIResponse(**response.json())
        assert result.status == 400  # Should fail without required validators
```

### Committee Tests
```python
def test_committee_basic_retrieval():
    """Verify basic committee retrieval:
    - By committee ID
    - Optional congress parameter
    - Response structure validation
    - Required field presence
    """

def test_committee_type_validation():
    """Verify committee type constraints:
    - Chamber validation (house/senate/joint)
    - Type validation (standing/select/joint/subcommittee)
    - Parent-child relationships
    - URL format
    """

def test_committee_hierarchy():
    """Verify committee hierarchy handling:
    - Parent committee relationships
    - Subcommittee listings
    - Cross-reference integrity
    - Hierarchy updates
    """

def test_committee_membership():
    """Verify committee membership:
    - Current members
    - Historical membership
    - Role assignments
    - Congress-specific membership
    """

def test_committee_activities():
    """Verify committee activities:
    - Activity types (hearing/markup/meeting/report)
    - Date tracking
    - Status updates
    - Bill relationships
    """

def test_committee_reports():
    """Verify committee reports:
    - Report metadata
    - GovInfo package integration
    - Digital signature verification
    - Report-bill relationships
    """

def test_committee_caching():
    """Verify committee caching:
    - Cache hit scenarios
    - Refresh conditions
    - Partial data caching
    - Cache invalidation
    """

def test_committee_data_persistence():
    """Verify committee data storage:
    - Basic info persistence
    - Activity recording
    - Report storage
    - Update handling
    """

def test_committee_congress_filtering():
    """Verify congress-specific filtering:
    - Activity filtering
    - Report filtering
    - Membership filtering
    - Cross-congress relationships
    """

def test_committee_error_handling():
    """Verify committee error scenarios:
    - Invalid committee IDs
    - Missing congress data
    - API failures
    - Transaction rollbacks
    """
```

### Amendment Tests
```python
def test_amendment_id_validation():
    """Verify amendment ID format requirements:
    - Format validation (e.g., HAMDT123)
    - Congress number range validation (valid congress years)
    - Rejection of malformed IDs
    """

def test_amendment_database_constraints():
    """Verify database constraints from schema:
    - Primary key enforcement (amendment_id)
    - Foreign key integrity (congress_id, bill_id)
    - Required fields (amendment_number, NOT NULL constraint)
    - Timestamp handling (created_at, updated_at)
    """

def test_amendment_transaction_atomicity():
    """Verify transaction handling in _store_amendment_data:
    - Rollback on action insert failure
    - Rollback on report insert failure
    - Proper cleanup on partial failures
    - Concurrent transaction isolation
    """

def test_amendment_committee_relationships():
    """Verify committee data integrity:
    - Action-committee relationships in amendment_actions
    - Report-committee relationships in amendment_committee_reports
    - Committee existence validation
    - Historical committee tracking
    """

def test_amendment_govinfo_integration():
    """Verify GovInfo.gov content integration:
    - Content retrieval based on bill type/number
    - Digital signature verification for reports
    - Package ID validation
    - Content format handling
    """

def test_amendment_cache_invalidation():
    """Verify specific cache invalidation rules:
    - Refresh after status changes
    - Refresh after new actions
    - Refresh after report updates
    - Cache key format (amendment_id + congress)
    """

def test_amendment_api_error_recovery():
    """Verify error recovery scenarios:
    - Congress.gov API timeout recovery
    - GovInfo.gov API failure handling
    - Partial data recovery
    - Error logging with sync_errors table
    """
```

### Member Tests
```python
def test_member_data_model():
    """Verify member data model integrity:
    - Core fields validation (first_name, last_name required)
    - Role history tracking (member_roles table)
    - Committee assignments with date ranges
    - Sponsored legislation tracking
    """

def test_member_retrieval():
    """Verify get_member() functionality:
    - Bioguide ID validation
    - Optional congress parameter handling
    - Response field completeness
    - Cache hit/miss behavior
    """

def test_member_congress_api():
    """Verify Congress.gov API integration:
    - Member endpoint response parsing
    - Sponsored bills endpoint handling
    - Rate limit compliance
    - Error propagation
    """

def test_member_transactions():
    """Verify transaction handling:
    - Atomic member data updates
    - Role history preservation
    - Committee assignment integrity
    - Sponsored bill tracking
    """
```

## Document Management Tests

### Document Service Tests
```python
def test_service_initialization():
    """Verify DocumentService initialization:
    - Client dependency injection
    - Database connection setup
    - GovInfo API client setup
    """

def test_service_configuration():
    """Verify service configuration:
    - Validation intervals
    - Retry settings
    - Storage options
    """

def test_content_type_validation():
    """Verify content type constraints:
    - Valid type enforcement (pdf/xml/html)
    - Default type handling
    - Invalid type rejection
    - Content type conversion
    """
```

### Document Retrieval Tests
```python
def test_document_basic_retrieval():
    """Verify basic document retrieval:
    - Package ID validation
    - Document type validation
    - Content type handling
    - Response structure
    """

def test_document_metadata():
    """Verify document metadata handling:
    - Title extraction
    - Published date
    - Last modified date
    - Collection code
    - Branch information
    - Page count
    """

def test_content_type_handling():
    """Verify content type handling:
    - PDF retrieval and parsing
    - XML retrieval and validation
    - HTML content processing
    - Content size validation
    """

def test_document_versioning():
    """Verify document version management:
    - Version tracking
    - Last modified detection
    - Version history
    - Update handling
    """

def test_package_relationships():
    """Verify package relationship handling:
    - Congress references
    - Collection associations
    - Related document linking
    """

def test_validation_timing_logic():
    """Verify document validation timing:
    - Validation interval checks
    - Forced revalidation conditions
    - Signature expiration handling
    """

def test_partial_content_handling():
    """Verify partial document content scenarios:
    - Metadata-only retrieval
    - Lazy content loading
    - Missing content fields
    """
```

### Document Authentication Tests
```python
def test_signature_verification():
    """Verify digital signature processing:
    - Signature extraction
    - Cryptographic verification
    - Public key handling
    - Verification status tracking
    """

def test_authentication_workflow():
    """Verify authentication workflow:
    - Signature extraction
    - Verification process
    - Status updates
    - History tracking
    """

def test_verification_history():
    """Verify verification history tracking:
    - History recording
    - Status changes
    - Method tracking
    - Error handling
    """

def test_official_content_validation():
    """Verify official content validation:
    - Official status tracking
    - Content hash verification
    - Timestamp validation
    - Chain of custody
    """
```

### Document Storage Tests
```python
def test_document_persistence():
    """Verify document storage:
    - Package data persistence
    - Content storage
    - Metadata preservation
    - Relationship maintenance
    """

def test_content_hash_validation():
    """Verify content integrity:
    - Hash calculation
    - Hash verification
    - Content validation
    - Size verification
    """

def test_storage_optimization():
    """Verify storage optimization:
    - Content deduplication
    - Storage efficiency
    - Cleanup processes
    """

def test_concurrent_access():
    """Verify concurrent document access:
    - Read consistency
    - Write locking
    - Version conflicts
    - Transaction isolation
    """

def test_transaction_management():
    """Verify transaction handling:
    - Atomic operations
    - Rollback scenarios
    - Deadlock handling
    - Transaction isolation levels
    """

def test_collection_management():
    """Verify collection handling:
    - Collection code validation
    - Branch association
    - Collection metadata
    - Cross-collection references
    """
```

### Document Cache Tests
```python
def test_cache_strategy():
    """Verify caching strategy:
    - Cache key generation
    - TTL handling
    - Cache invalidation rules
    - Memory management
    """

def test_cache_validation():
    """Verify cache validation:
    - Freshness checking
    - Revalidation triggers
    - Staleness handling
    - Validation timing
    """

def test_cache_headers():
    """Verify cache header handling:
    - ETag processing
    - Last-Modified handling
    - Cache-Control directives
    - Conditional requests
    """

def test_cache_consistency():
    """Verify cache consistency:
    - Multi-node synchronization
    - Race condition handling
    - Partial update handling
    - Revalidation queuing
    """
```

### Error Handling Tests
```python
def test_retrieval_errors():
    """Verify retrieval error handling:
    - Missing documents
    - Invalid package IDs
    - Network failures
    - Timeout handling
    """

def test_authentication_errors():
    """Verify authentication error handling:
    - Invalid signatures
    - Missing keys
    - Verification failures
    - Protocol errors
    """

def test_storage_errors():
    """Verify storage error handling:
    - Write failures
    - Constraint violations
    - Disk space issues
    - Transaction failures
    """

def test_cache_errors():
    """Verify cache error handling:
    - Cache miss handling
    - Invalidation errors
    - Consistency errors
    - Resource exhaustion
    """
```

## Regulatory Content Tests

### Federal Register Tests
```python
def test_fr_document_retrieval():
    """Verify Federal Register document retrieval"""

def test_fr_publication_tracking():
    """Verify FR publication date tracking"""

def test_fr_agency_handling():
    """Verify agency information processing"""

def test_fr_effective_date():
    """Verify effective date tracking"""
```

### CFR Tests
```python
def test_cfr_part_retrieval():
    """Verify CFR part retrieval"""

def test_cfr_structure_handling():
    """Verify CFR title/chapter/part structure"""

def test_cfr_effective_date():
    """Verify CFR effective date tracking"""

def test_cfr_relationship_mapping():
    """Verify CFR relationships with FR docs"""
```

## Test Fixtures and Utilities

### Mock API Responses
```python
@pytest.fixture
def mock_congress_api():
    """Provide mock Congress.gov API responses"""

@pytest.fixture
def mock_govinfo_api():
    """Provide mock GovInfo.gov API responses"""

@pytest.fixture
def mock_rate_limit_headers():
    """Provide mock rate limit response headers"""
```

### Database Fixtures
```python
@pytest.fixture
def test_database():
    """Provide clean test database instance"""

@pytest.fixture
def sample_api_usage_data():
    """Provide sample API usage data"""

@pytest.fixture
def sample_configuration_data():
    """Provide sample configuration data"""
```

## Test Categories and Tags

### Test Categories
- Unit Tests: `pytest -m unit`
- Integration Tests: `pytest -m integration`
- API Tests: `pytest -m api`
- Database Tests: `pytest -m db`
- Authentication Tests: `pytest -m auth`
- Rate Limit Tests: `pytest -m ratelimit`

### Test Environment Variables
```bash
# Required for running tests
PYGOVPUB_TEST_CONGRESS_KEY=test_key
PYGOVPUB_TEST_GOVINFO_KEY=test_key
PYGOVPUB_TEST_DB_URL=postgresql://test:test@localhost:5432/pygovpub_test
```

## Test Coverage Requirements

### Minimum Coverage Requirements
- Overall Coverage: 90%
- Core Components: 95%
- API Integration: 90%
- Database Layer: 90%
- Error Handling: 95%

### Critical Test Paths
1. Authentication Flow
2. Rate Limit Management
3. Error Handling
4. Database Operations
5. API Integration

## Test Implementation Guidelines

1. Use appropriate mocking for external API calls
2. Implement proper database transaction handling
3. Include both positive and negative test cases
4. Test edge cases and error conditions
5. Verify proper cleanup in teardown
6. Use parameterized tests for similar scenarios
7. Include timing assertions for rate limit tests
8. Verify proper error message formatting

## Real-time Update Tests

### Webhook Tests
```python
def test_webhook_url_validation():
    """Verify webhook URL validation:
    - HTTPS requirement
    - URL format validation
    - Domain resolution
    - Port restrictions
    """

def test_webhook_registration():
    """Verify webhook registration process:
    - Subscription creation
    - Secret key generation
    - Event type association
    - Filter storage
    """

def test_webhook_signature():
    """Verify webhook signature generation:
    - HMAC-SHA256 implementation
    - Key handling
    - Payload canonicalization
    - Signature verification
    """

def test_webhook_delivery():
    """Verify webhook delivery process:
    - Payload formatting
    - Header inclusion
    - Response handling
    - Delivery recording
    """

def test_webhook_retry():
    """Verify webhook retry mechanism:
    - Retry scheduling
    - Backoff strategy
    - Error tracking
    - Maximum attempts
    """

def test_webhook_filters():
    """Verify webhook filter processing:
    - Filter validation
    - Filter application
    - Complex conditions
    - Filter updates
    """

def test_webhook_security():
    """Verify webhook security measures:
    - Secret rotation
    - TLS verification
    - IP allowlisting
    - Rate limiting
    """

def test_webhook_management():
    """Verify webhook management:
    - Subscription updates
    - Deactivation/reactivation
    - Health monitoring
    - Cleanup processes
    """
```

### Event Processing Tests
```python
def test_event_type_validation():
    """Verify event type handling:
    - Valid type enforcement
    - Source validation
    - Type registration
    - Type relationships
    """

def test_event_payload_processing():
    """Verify event payload handling:
    - Payload validation
    - Data transformation
    - Size limits
    - Content filtering
    """

def test_event_routing():
    """Verify event routing logic:
    - Subscriber matching
    - Filter evaluation
    - Priority handling
    - Load balancing
    """

def test_event_persistence():
    """Verify event storage:
    - Delivery tracking
    - Status updates
    - History retention
    - Cleanup policies
    """
```

### Subscription Management Tests
```python
def test_subscription_lifecycle():
    """Verify subscription lifecycle:
    - Creation flow
    - Update handling
    - Suspension rules
    - Deletion process
    """

def test_subscription_validation():
    """Verify subscription validation:
    - Event type constraints
    - Filter validation
    - URL verification
    - Quota enforcement
    """

def test_subscription_monitoring():
    """Verify subscription monitoring:
    - Health checks
    - Error tracking
    - Performance metrics
    - Alert triggers
    """

def test_subscription_scaling():
    """Verify subscription scaling:
    - High volume handling
    - Connection pooling
    - Resource limits
    - Load distribution
    """
```

### Update Processing Tests
```python
def test_update_queue_processing():
    """Verify update queue processing"""

def test_update_order_preservation():
    """Verify update order is preserved"""

def test_update_deduplication():
    """Verify duplicate update handling"""

def test_update_notification():
    """Verify subscriber notification process"""
```

### Update Subscription Tests
```python
def test_subscription_management():
    """Verify subscription creation and management"""

def test_subscription_filtering():
    """Verify subscription filter processing"""

def test_subscription_delivery():
    """Verify update delivery to subscribers"""

def test_subscription_error_handling():
    """Verify subscription error handling"""
```

## Regulatory Content Tests
```python
def test_document_retrieval():
    """Verify document retrieval by type:
    - FR citation parsing (volume/page)
    - CFR citation parsing (title/part/section)
    - Version date handling for CFR/ECFR
    - Invalid type rejection
    """

def test_document_versioning():
    """Verify CFR/ECFR version management:
    - Version tracking by date
    - Change type recording
    - Content hash validation
    - Version supersession
    """

def test_document_authentication():
    """Verify document authentication:
    - Digital signature extraction
    - Signature verification
    - Verification date tracking
    - Verification status persistence
    """

def test_agency_handling():
    """Verify agency information management:
    - Agency hierarchy (parent/child relationships)
    - CFR title authority validation
    - Agency assignment to documents
    - Historical agency tracking
    """

def test_legislative_references():
    """Verify reference tracking:
    - Reference extraction and categorization
    - Entity relationship mapping
    - Citation text preservation
    - Duplicate prevention
    """

def test_regulatory_transactions():
    """Verify transaction integrity:
    - Multi-table atomic updates
    - Version conflict handling
    - Reference consistency
    - Rollback scenarios
    """
```

### Authentication Configuration Tests
```python
def test_config_validation_comprehensive():
    """Verify configuration validation:
    - Required key presence
    - Type validation for all fields
    - Range validation for numeric values
    - Boolean parameter handling
    - Invalid config rejection
    """

def test_config_inheritance():
    """Verify configuration inheritance:
    - Default value application
    - Override behavior
    - Environment variable integration
    - Configuration persistence
    """
```

### Committee Tests
```python
def test_committee_activity_type_validation():
    """Verify committee activity type constraints:
    - Valid type enforcement
    - Activity metadata requirements
    - Type-specific field validation
    - Invalid type handling
    """

def test_committee_activity_relationships():
    """Verify activity relationships:
    - Bill associations
    - Member participation
    - Document linkages
    - Historical tracking
    """
```

### Regulatory Document Tests
```python
def test_document_relationships():
    """Verify regulatory document relationships:
    - Cross-reference integrity
    - Bidirectional relationship tracking
    - Reference type validation
    - Citation format verification
    """

def test_reference_management():
    """Verify reference management:
    - Reference extraction accuracy
    - Entity type validation
    - Citation text preservation
    - Reference update handling
    """
```

### Committee Assignment Tests
```python
def test_committee_assignment_dates():
    """Verify committee assignment date handling:
    - Date range validation
    - Overlap detection
    - Gap analysis
    - Historical preservation
    """
```

### Amendment Committee Tests
```python
def test_amendment_committee_report_tracking():
    """Verify amendment committee report handling:
    - Report association
    - Committee jurisdiction
    - Report versioning
    - Historical preservation
    """
```

## Core Unit Tests

### Congressional Date Tests
```python
class TestCongressionalDates:
    """Test congressional date calculations and transitions"""

    @pytest.mark.parametrize("test_date,expected_congress", [
        (date(1789, 3, 3), 1),    # Day before First Congress
        (date(1789, 3, 4), 1),    # First day of First Congress
        (date(1933, 3, 3), 72),   # Last March transition
        (date(1933, 3, 4), 73),   # Last Congress with March start
        (date(1933, 1, 3), 72),   # Pre-20th Amendment
        (date(1934, 1, 3), 73),   # Post-20th Amendment
        (date(2023, 1, 2), 117),  # Modern transition day before
        (date(2023, 1, 3), 118),  # Modern transition day
    ])
    def test_congress_number_calculation(self, test_date, expected_congress):
        """Test congress number calculation across historical transitions"""
        assert calculate_congress_number(test_date) == expected_congress

    @pytest.mark.parametrize("congress,expected", [
        (1, ("March", 4)),     # First Congress
        (72, ("March", 4)),    # Last March transition
        (73, ("January", 3)),  # First January transition
        (118, ("January", 3))  # Current Congress
    ])
    def test_session_start_dates(self, congress, expected):
        """Test session start date determination"""
        month, day = get_congress_transition_month(congress)
        assert (month, day) == expected

    @pytest.mark.parametrize("year,expected_pattern", [
        (1789, "1st Congress (March 1789-1791)"),
        (1801, "6th Congress (1799-March 1801) & 7th Congress (March 1801-1803)"),
        (1933, "72nd Congress (1931-March 1933) & 73rd Congress (January 1933-1935)"),
        (2023, "117th Congress (2021-January 2023) & 118th Congress (January 2023-2025)")
    ])
    def test_congress_period_formatting(self, year, expected_pattern):
        """Test congress period string formatting"""
        assert format_congress_info(year) == expected_pattern

    def test_invalid_dates(self):
        """Test handling of invalid dates"""
        with pytest.raises(ValueError):
            calculate_congress_number(date(1788, 12, 31))  # Pre-First Congress
        with pytest.raises(ValueError):
            calculate_congress_number(date.today() + timedelta(days=365*10))  # Far future
```

# Test Stub and Coverage Projection Strategy

## Overview

PyGovPub implements a test stub strategy that enables:
1. Early documentation of test requirements before implementation
2. Accurate projection of future code coverage
3. Clear visibility into testing gaps
4. Protection from failing but incomplete tests

## Test Stub Implementation

Test stubs are implemented in two parts:

### 1. Collection Hook (conftest.py)

The pytest collection hook in `conftest.py` automatically identifies and excludes test stubs:

```python
def pytest_collection_modifyitems(config, items):
    """Exclude stubs and work-in-progress tests from test runs."""
    selected_items = []
    
    for item in items:
        is_stub = False
        
        # Check function name
        if "stub" in item.name.lower():
            is_stub = True
        
        # Check source code for stub markers
        import inspect
        try:
            source = inspect.getsource(item.function)
            if "# STUB:" in source or "# WIP:" in source:
                is_stub = True
        except Exception:
            pass
            
        # Only include non-stub tests
        if not is_stub:
            selected_items.append(item)
    
    # Replace items with filtered list
    items[:] = selected_items
```

### 2. Coverage Projection Tool

The `projected_coverage.py` tool analyzes stubs to project future coverage:

```python
class CoverageAnalyzer:
    """Analyzes current coverage and test stubs to project future coverage."""
    
    def __init__(self, package, stub_dirs):
        self.package = package
        self.stub_dirs = stub_dirs
        self.current_coverage = {}
        self.missing_lines = defaultdict(set)
        self.stub_coverage = defaultdict(set)
    
    def get_current_coverage(self):
        """Run coverage and parse results."""
        # Run pytest with coverage and parse missing lines
        
    def analyze_test_stubs(self):
        """Extract line coverage comments from stubs."""
        # Find comments like "# STUB: This tests lines 45-60"
        
    def calculate_projected_coverage(self):
        """Calculate coverage after stubs are implemented."""
        # Combine current coverage with projected stub coverage
```

## Test Stub Patterns

Test stubs are identified by:

1. Function name containing "stub":
   ```python
   def test_stub_api_validation(): ...
   ```

2. STUB comment in function:
   ```python
   def test_rate_limiter():
       # STUB: This tests lines 45-60 in rate_limiter.py
   ```

3. WIP comment in function:
   ```python
   def test_complex_feature():
       # WIP: Will implement when feature is complete
   ```

## Coverage Documentation Standards

Each test stub should document which lines it will cover:

```python
def test_stub_auth_token_validation():
    # STUB: This tests lines 75-82 in auth_manager.py
    """
    Tests that authentication tokens are properly validated.
    
    This test will verify:
    1. Expired tokens are rejected
    2. Invalid signatures are rejected
    3. Tokens with incorrect format are rejected
    4. Valid tokens are accepted
    """
    # Implement this test after the token validation is complete
    pass
```

## Integration with CI/CD

The coverage projection system integrates with CI/CD to:

1. Monitor coverage trends over time
2. Alert when actual coverage diverges from projected coverage
3. Track implementation progress against stub plans
4. Identify newly added code without corresponding test stubs

## Implementation Workflow

1. Write code with at least 1 stub test for each function
2. Document which lines each stub will test
3. Run projected_coverage.py to confirm 100% projected coverage
4. Implement stubs in order of priority or complexity
5. Verify actual coverage matches or exceeds projections

## Benefits

- Ensures test coverage is considered during implementation
- Provides visibility into future test coverage
- Prevents test failures from incomplete tests
- Documents testing strategy within the codebase
- Eliminates the "we'll test it later" trap