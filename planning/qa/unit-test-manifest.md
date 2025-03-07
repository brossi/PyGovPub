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

## Core Test Patterns

### Validation Chain Tests
```python
class TestValidationChains:
    """Test data validation chains across components"""

    @pytest.mark.parametrize("test_data,validation_steps", [
        (
            {"id": "BILLS-118hr1234ih", "congress": 118},
            ["format", "congress", "bill_type", "number"]
        ),
        (
            {"id": "HAMDT123", "congress": 118},
            ["format", "congress", "amendment_type"]
        ),
        (
            {"id": "CREC-2023-01-03", "congress": 118},
            ["format", "date", "document_type"]
        )
    ])
    async def test_id_validation_chain(self, test_data, validation_steps):
        """Verify complete validation chain for identifiers:
        - Format validation
        - Component validation
        - Cross-reference validation
        - Historical validation
        """

    @pytest.mark.parametrize("entity_type,required_fields", [
        ("bill", ["congress", "bill_type", "number", "version"]),
        ("amendment", ["congress", "number", "chamber"]),
        ("committee", ["congress", "code", "type"])
    ])
    async def test_entity_completeness(self, entity_type, required_fields):
        """Verify entity data completeness:
        - Required field presence
        - Field type validation
        - Relationship requirements
        - Historical requirements
        """

    @pytest.mark.parametrize("date_type,validation_rules", [
        ("introduced_date", ["not_future", "not_pre_congress", "business_day"]),
        ("reported_date", ["not_future", "after_introduced", "business_day"]),
        ("enacted_date", ["not_future", "after_reported", "any_day"])
    ])
    async def test_date_validation_chain(self, date_type, validation_rules):
        """Verify date validation chains:
        - Date format validation
        - Business rules validation
        - Historical context validation
        - Cross-reference timing
        """
```

### Error Scenario Tests
```python
class TestErrorScenarios:
    """Test comprehensive error handling scenarios"""

    @pytest.mark.parametrize("error_type,recovery_steps", [
        ("missing_data", ["cache_check", "api_retry", "partial_construct"]),
        ("invalid_format", ["format_repair", "alternate_source", "manual_flag"]),
        ("version_conflict", ["timestamp_check", "merge_attempt", "force_latest"])
    ])
    async def test_error_recovery_chain(self, error_type, recovery_steps):
        """Verify error recovery chains:
        - Error detection
        - Recovery attempt sequence
        - Fallback handling
        - Error state persistence
        """

    @pytest.mark.parametrize("validation_level,expected_errors", [
        ("strict", ["format", "reference", "historical"]),
        ("normal", ["format", "reference"]),
        ("lenient", ["format"])
    ])
    async def test_validation_level_handling(self, validation_level, expected_errors):
        """Verify validation level behavior:
        - Error categorization
        - Error threshold handling
        - Warning generation
        - Error aggregation
        """
```

### Data Consistency Tests
```python
class TestDataConsistency:
    """Test data consistency across operations"""

    @pytest.mark.parametrize("operation_sequence", [
        ["create", "update", "delete"],
        ["create", "reference", "update"],
        ["create", "version", "supersede"]
    ])
    async def test_operation_atomicity(self, operation_sequence):
        """Verify operation atomicity:
        - Transaction boundaries
        - Rollback conditions
        - State preservation
        - Reference integrity
        """

    @pytest.mark.parametrize("entity_relationship", [
        ("bill", "amendment"),
        ("committee", "member"),
        ("document", "version")
    ])
    async def test_relationship_consistency(self, entity_relationship):
        """Verify relationship consistency:
        - Reference integrity
        - Cascade behavior
        - Historical preservation
        - Orphan prevention
        """
```

## Bill Tests
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

## Shared Test Components

### Common Fixtures
```python
@pytest.fixture(scope="session")
def congress_dates():
    """Provide common congressional date test data:
    - Key transition dates (1789, 1933, present)
    - Session start/end dates
    - Special session dates
    - Holiday/recess periods
    """
    return {
        "transitions": [
            (date(1789, 3, 4), 1, "first"),
            (date(1933, 3, 4), 73, "march_to_january"),
            (date(1934, 1, 3), 73, "modern")
        ],
        "sessions": {
            1: {"start": date(1789, 3, 4), "end": date(1791, 3, 3)},
            73: {"start": date(1933, 1, 3), "end": date(1935, 1, 2)}
        },
        "special": {
            "pre_constitution": date(1788, 12, 31),
            "20th_amendment": date(1933, 1, 20)
        }
    }

@pytest.fixture(scope="session")
def validation_chains():
    """Provide common validation chain configurations:
    - ID format validators
    - Field requirement sets
    - Reference validators
    - Date sequence rules
    """
    return {
        "id_formats": {
            "bill": r"^BILLS-\d+[a-z]+\d+[a-z]{2}$",
            "amendment": r"^[HS]AMDT\d+$",
            "committee": r"^[HSJ]\d+$"
        },
        "required_fields": {
            "bill": ["congress", "type", "number"],
            "amendment": ["number", "congress", "chamber"],
            "committee": ["code", "type", "congress"]
        },
        "date_rules": {
            "introduced": ["not_future", "business_day"],
            "reported": ["after_introduced", "business_day"],
            "enacted": ["after_reported"]
        }
    }

@pytest.fixture(scope="function")
def mock_responses():
    """Provide standardized mock API responses:
    - Congress.gov responses
    - GovInfo.gov responses
    - Error responses
    - Partial data responses
    """
    return {
        "congress": {
            "bill": load_json("test_data/congress/bill_response.json"),
            "member": load_json("test_data/congress/member_response.json"),
            "committee": load_json("test_data/congress/committee_response.json")
        },
        "govinfo": {
            "package": load_json("test_data/govinfo/package_response.json"),
            "metadata": load_json("test_data/govinfo/metadata_response.json"),
            "content": load_json("test_data/govinfo/content_response.json")
        },
        "errors": {
            "rate_limit": {"status": 429, "reset": 300},
            "not_found": {"status": 404, "message": "Not found"},
            "invalid_key": {"status": 401, "message": "Invalid API key"}
        }
    }

@pytest.fixture(scope="function")
def test_entities():
    """Provide common test entities with relationships:
    - Bills with amendments
    - Committees with members
    - Documents with versions
    """
    return {
        "bills": [
            {
                "id": "BILLS-118hr1234ih",
                "amendments": ["HAMDT123", "HAMDT124"],
                "committees": ["HSBA", "HSJU"]
            }
        ],
        "committees": [
            {
                "code": "HSBA",
                "members": ["B001234", "B001235"],
                "parent": None
            }
        ],
        "documents": [
            {
                "id": "CREC-2023-01-03",
                "versions": ["v1", "v2"],
                "references": ["BILLS-118hr1234ih"]
            }
        ]
    }
```

### Shared Mocks
```python
class MockAPIClient:
    """Mock API client for testing:
    - Configurable response patterns
    - Rate limit simulation
    - Error injection
    - Request validation
    """
    def __init__(self, mock_responses, settings=None):
        self.responses = mock_responses
        self.settings = settings or {}
        self.calls = []

    async def get(self, endpoint, params=None):
        """Record call and return configured response"""
        self.calls.append({"endpoint": endpoint, "params": params})
        return self._get_response(endpoint)

    def _get_response(self, endpoint):
        """Get configured response or raise error"""
        if "error_rate" in self.settings:
            if random.random() < self.settings["error_rate"]:
                return self.responses["errors"]["rate_limit"]
        return self.responses.get(endpoint, {})

class MockDatabase:
    """Mock database for testing:
    - Transaction simulation
    - Constraint checking
    - History tracking
    - Relationship validation
    """
    def __init__(self, test_entities):
        self.entities = copy.deepcopy(test_entities)
        self.transactions = []
        self.constraints = self._load_constraints()

    async def execute(self, query, params=None):
        """Execute query with constraint checking"""
        self.transactions.append({"query": query, "params": params})
        return self._validate_and_execute(query, params)

    def _validate_and_execute(self, query, params):
        """Validate constraints and simulate execution"""
        self._check_constraints(query, params)
        return self._simulate_result(query)
```

### Test Extensions
```python
class ValidationMixin:
    """Common validation methods for tests"""

    def validate_id_format(self, id_str, entity_type):
        """Validate entity ID format"""
        pattern = self.validation_chains["id_formats"][entity_type]
        assert re.match(pattern, id_str)

    def validate_required_fields(self, data, entity_type):
        """Validate required fields presence"""
        required = self.validation_chains["required_fields"][entity_type]
        assert all(field in data for field in required)

    def validate_date_sequence(self, dates, rules):
        """Validate date sequence rules"""
        for rule in rules:
            assert self._check_date_rule(dates, rule)

    # New methods
    def validate_reference_integrity(self, source_entity, ref_type, ref_id):
        """Validate reference exists and is valid:
        - Reference exists in database
        - Reference type matches expected
        - Reference is not deleted/invalid
        - Historical reference is preserved
        """
        ref_entity = self._get_referenced_entity(ref_type, ref_id)
        assert ref_entity is not None, f"Referenced {ref_type} {ref_id} not found"
        assert ref_entity["status"] != "deleted", f"Referenced {ref_type} {ref_id} is deleted"
        assert self._check_reference_validity(source_entity, ref_entity)

    def validate_version_sequence(self, versions):
        """Validate version sequence integrity:
        - Version numbers are sequential
        - Timestamps are monotonic
        - Content hashes differ
        - Metadata consistency
        """
        for i in range(len(versions) - 1):
            assert versions[i]["version"] < versions[i + 1]["version"]
            assert versions[i]["timestamp"] < versions[i + 1]["timestamp"]
            assert versions[i]["hash"] != versions[i + 1]["hash"]
            assert self._check_version_metadata_consistency(versions[i], versions[i + 1])

    def validate_historical_state(self, entity, as_of_date):
        """Validate entity state at historical point:
        - Fields reflect historical values
        - References are historically valid
        - Changes after date not included
        - Deleted data preserved
        """
        historical = self._get_historical_state(entity, as_of_date)
        assert historical is not None, f"No historical state found for {as_of_date}"
        assert all(self._check_field_historical_validity(field, value, as_of_date)
                  for field, value in historical.items())

class ErrorHandlingMixin:
    """Common error handling methods for tests"""

    def verify_error_handling(self, error_type, expected_steps):
        """Verify error handling steps"""
        actual_steps = self._get_error_handling_steps(error_type)
        assert actual_steps == expected_steps

    def verify_recovery_state(self, error_type, expected_state):
        """Verify system state after error recovery"""
        actual_state = self._get_current_state()
        assert actual_state == expected_state

    # New methods
    def verify_error_propagation(self, operation, expected_error):
        """Verify error propagation chain:
        - Original error preserved
        - Stack trace maintained
        - Context added at each level
        - Final error format correct
        """
        with pytest.raises(type(expected_error)) as exc_info:
            self._execute_operation(operation)
        assert self._verify_error_chain(exc_info.value, expected_error)
        assert self._check_error_context(exc_info.value)

    def verify_partial_success(self, operation, expected_partial):
        """Verify partial success handling:
        - Successful parts committed
        - Failed parts rolled back
        - Partial state recorded
        - Recovery steps logged
        """
        result = self._execute_with_partial_failure(operation)
        assert self._verify_partial_state(result, expected_partial)
        assert self._check_recovery_logging(result)

    def verify_concurrent_error_handling(self, operations):
        """Verify concurrent error scenarios:
        - Race conditions detected
        - Deadlocks resolved
        - Priority preserved
        - System consistency maintained
        """
        results = self._execute_concurrent(operations)
        assert self._verify_concurrent_error_handling(results)
        assert self._check_system_consistency()

class TransactionMixin:
    """Common transaction testing methods"""

    def verify_transaction_boundaries(self, operations):
        """Verify transaction boundaries"""
        boundaries = self._get_transaction_boundaries(operations)
        assert self._validate_boundaries(boundaries)

    def verify_rollback_state(self, failed_operation):
        """Verify state after rollback"""
        state = self._get_state_after_rollback(failed_operation)
        assert state == self._get_initial_state()

    # New methods
    def verify_transaction_isolation(self, concurrent_ops):
        """Verify transaction isolation levels:
        - Read phenomena prevented
        - Write conflicts detected
        - Deadlock handling correct
        - Consistency preserved
        """
        results = self._execute_concurrent_transactions(concurrent_ops)
        assert self._verify_isolation_level(results)
        assert self._check_read_phenomena(results)
        assert self._verify_conflict_resolution(results)

    def verify_savepoint_handling(self, operations, savepoints):
        """Verify savepoint behavior:
        - Savepoint creation successful
        - Partial rollback works
        - State consistent at each point
        - Resources cleaned up
        """
        results = self._execute_with_savepoints(operations, savepoints)
        assert self._verify_savepoint_states(results)
        assert self._check_resource_cleanup(results)

    def verify_cross_partition_atomicity(self, operations):
        """Verify atomicity across partitions:
        - All partitions updated
        - Partial failures handled
        - Consistency maintained
        - Cleanup successful
        """
        results = self._execute_cross_partition(operations)
        assert self._verify_partition_consistency(results)
        assert self._check_partition_cleanup(results)

class CacheMixin:
    """Common cache testing methods:
    - Cache hit/miss verification
    - Invalidation checking
    - Consistency validation
    - Performance monitoring
    """
    def verify_cache_state(self, key, expected_value):
        """Verify cache entry state"""
        cached = self._get_cache_entry(key)
        assert cached == expected_value
        assert self._verify_cache_metadata(key)

    def verify_cache_invalidation(self, trigger_op):
        """Verify cache invalidation:
        - Related entries invalidated
        - Timestamps updated
        - Notifications sent
        - Cleanup completed
        """
        affected = self._execute_invalidation_trigger(trigger_op)
        assert self._verify_invalidation_cascade(affected)
        assert self._check_cleanup_completion(affected)

    def verify_cache_consistency(self, operations):
        """Verify cache consistency:
        - Multi-level cache aligned
        - Write-through successful
        - Race conditions handled
        - Staleness prevented
        """
        results = self._execute_cache_operations(operations)
        assert self._verify_cache_layers(results)
        assert self._check_cache_freshness(results)
```

## API Parity Tests

### Congress.gov API Parity Tests
```python
class TestCongressGovParity:
    """Direct implementation of Congress.gov's official API test suite.
    These tests are maintained to match Congress.gov's own test implementations
    and serve as parity validation for our wrapper implementation."""

    @pytest.fixture(scope="session")
    def congress_official_responses():
        """Load official Congress.gov test responses"""
        return load_test_data("congress_official_test_data")

    @pytest.fixture(scope="session")
    def congress_our_client():
        """Initialize our client with test configuration"""
        return PyGovPubClient(test_config)

    @pytest.mark.parametrize("test_case", load_congress_test_cases())
    async def test_congress_endpoint_parity(self, test_case, congress_official_responses, congress_our_client):
        """Run official Congress.gov test cases against our implementation:
        - Uses same input data
        - Expects identical output
        - Validates all response fields
        - Checks error handling
        """
        official_response = congress_official_responses[test_case.id]
        our_response = await congress_our_client.execute_test(test_case)

        assert_responses_match(our_response, official_response)
        assert_error_handling_matches(our_response, official_response)
        assert_rate_limit_behavior_matches(our_response, official_response)

    @pytest.mark.parametrize("api_version", ["v3", "v4"])
    async def test_congress_version_compatibility(self, api_version):
        """Verify version-specific behaviors match official implementation:
        - API version differences
        - Deprecated field handling
        - New field support
        - Version-specific error cases
        """
        official_behavior = get_official_version_behavior(api_version)
        our_behavior = await get_our_version_behavior(api_version)
        assert_version_behaviors_match(our_behavior, official_behavior)

class CongressGovParityMixin:
    """Mixin for implementing Congress.gov's test patterns"""

    def verify_congress_response_format(self, response):
        """Verify response matches Congress.gov's format requirements:
        - JSON structure
        - Field naming
        - Data types
        - Null handling
        """
        assert self._validate_congress_format(response)

    def verify_congress_error_format(self, error):
        """Verify error format matches Congress.gov's requirements:
        - Error codes
        - Message format
        - Stack trace handling
        - Error categorization
        """
        assert self._validate_congress_error_format(error)

### GovInfo.gov API Parity Tests
```python
class TestGovInfoParity:
    """Direct implementation of GovInfo.gov's official API test suite.
    These tests are maintained to match GovInfo.gov's own test implementations
    and serve as parity validation for our wrapper implementation."""

    @pytest.fixture(scope="session")
    def govinfo_official_responses():
        """Load official GovInfo.gov test responses"""
        return load_test_data("govinfo_official_test_data")

    @pytest.fixture(scope="session")
    def govinfo_our_client():
        """Initialize our client with test configuration"""
        return PyGovPubClient(test_config)

    @pytest.mark.parametrize("test_case", load_govinfo_test_cases())
    async def test_govinfo_endpoint_parity(self, test_case, govinfo_official_responses, govinfo_our_client):
        """Run official GovInfo.gov test cases against our implementation:
        - Uses same input data
        - Expects identical output
        - Validates all response fields
        - Checks error handling
        """
        official_response = govinfo_official_responses[test_case.id]
        our_response = await govinfo_our_client.execute_test(test_case)

        assert_responses_match(our_response, official_response)
        assert_error_handling_matches(our_response, official_response)
        assert_bulk_download_behavior_matches(our_response, official_response)

    @pytest.mark.parametrize("collection", ["BILLS", "STATUTE", "FR", "CFR"])
    async def test_govinfo_collection_parity(self, collection):
        """Verify collection-specific behaviors match official implementation:
        - Collection metadata
        - Package structure
        - Granule handling
        - Collection-specific features
        """
        official_behavior = get_official_collection_behavior(collection)
        our_behavior = await get_our_collection_behavior(collection)
        assert_collection_behaviors_match(our_behavior, official_behavior)

class GovInfoParityMixin:
    """Mixin for implementing GovInfo.gov's test patterns"""

    def verify_govinfo_response_format(self, response):
        """Verify response matches GovInfo.gov's format requirements:
        - JSON structure
        - Field naming
        - Data types
        - Null handling
        """
        assert self._validate_govinfo_format(response)

    def verify_govinfo_package_format(self, package):
        """Verify package format matches GovInfo.gov's requirements:
        - Package ID format
        - Content organization
        - Metadata structure
        - Relationship handling
        """
        assert self._validate_govinfo_package_format(package)

### Shared Parity Test Components
```python
class APIParityTestBase:
    """Base class for API parity testing with shared utilities"""

    def compare_response_structures(self, our_response, official_response):
        """Compare response structures ensuring exact match:
        - Field presence and naming
        - Data types and formats
        - Nested structure
        - Array ordering
        """
        assert self._deep_compare_responses(our_response, official_response)

    def verify_error_parity(self, our_error, official_error):
        """Verify error handling matches official implementation:
        - Error codes
        - Message formatting
        - Status codes
        - Headers
        """
        assert self._compare_error_handling(our_error, official_error)

    def verify_rate_limit_parity(self, our_headers, official_headers):
        """Verify rate limit handling matches official implementation:
        - Header formats
        - Counter behavior
        - Reset timing
        - Quota management
        """
        assert self._compare_rate_limit_behavior(our_headers, official_headers)

@pytest.fixture(scope="session")
def api_parity_config():
    """Configuration for parity testing:
    - Test data paths
    - API versions
    - Collection mappings
    - Response templates
    """
    return {
        "congress_gov": {
            "test_data_path": "test_data/congress_official",
            "versions": ["v3", "v4"],
            "response_templates": load_congress_templates()
        },
        "govinfo": {
            "test_data_path": "test_data/govinfo_official",
            "collections": ["BILLS", "STATUTE", "FR", "CFR"],
            "response_templates": load_govinfo_templates()
        }
    }
```

### Parity Test Guidelines
1. Maintain exact copies of official test suites
2. Update test cases when official APIs update
3. Use official test data and expected responses
4. Implement version-specific test variations
5. Track API changes and deprecations
6. Monitor for behavioral differences
7. Document any intentional deviations

### Parity Test Categories
- Response Format Tests
- Error Handling Tests
- Rate Limit Tests
- Version Compatibility Tests
- Collection-Specific Tests
- Bulk Operation Tests
- Authentication Tests
- Special Case Tests

### Data Validation Tests

#### Monetary Value Tests
- **Storage Format Tests**:
  - Verify NUMERIC(20,2) precision is maintained
  - Confirm no floating-point rounding errors
  - Validate non-negative constraints
  - Check currency code constraints

```python
def test_monetary_value_precision():
    """Test monetary value storage precision and constraints"""
    # Test exact decimal arithmetic
    # Test range constraints
    # Verify currency code validation
    # Check non-negative constraints
```

- **Edge Cases**:
  - Maximum supported value (18 digits + 2 decimal places)
  - Zero values
  - Small fractional amounts (e.g. $0.01)
  - Values near maximum precision

- **API Response Format**:
  - Verify consistent decimal places in responses
  - Confirm currency code inclusion
  - Validate JSON number formatting
```

### SQLModel Integration Tests
```python
class TestSQLModelIntegration:
    """Verify SQLModel integration and type safety"""

    @pytest.mark.parametrize("model_class,required_fields", [
        (Bill, ["bill_id", "congress_id", "bill_type", "bill_number", "title"]),
        (BillVersion, ["version_id", "bill_id", "version_code"]),
        (Congress, ["congress_id", "start_date", "end_date"])
    ])
    async def test_model_field_validation(
        self,
        model_class: Type[SQLModel],
        required_fields: List[str]
    ):
        """Verify field validation and constraints"""
        # Test required fields
        with pytest.raises(ValidationError):
            model_class()  # Should fail without required fields

        # Test field constraints
        for field in required_fields:
            data = {f: "test" for f in required_fields}
            data[field] = None
            with pytest.raises(ValidationError):
                model_class(**data)

    @pytest.mark.parametrize("bill_type", [
        "hr", "s", "hjres", "sjres", "hconres", "sconres", "hres", "sres"
    ])
    async def test_bill_type_constraints(self, bill_type: str):
        """Verify bill type constraints"""
        bill = Bill(
            bill_id="TEST123",
            congress_id=117,
            bill_type=bill_type,
            bill_number=1234,
            title="Test Bill"
        )
        assert bill.bill_type == bill_type

        with pytest.raises(ValidationError):
            Bill(
                bill_id="TEST123",
                congress_id=117,
                bill_type="invalid",
                bill_number=1234,
                title="Test Bill"
            )

    async def test_relationship_loading(self, setup_db: AsyncSession):
        """Verify SQLModel relationship loading"""
        # Create test data
        bill = Bill(
            bill_id="TEST123",
            congress_id=117,
            bill_type="hr",
            bill_number=1234,
            title="Test Bill"
        )
        version = BillVersion(
            version_id="TEST123v1",
            version_code="ih",
            bill_id="TEST123"
        )
        setup_db.add(bill)
        setup_db.add(version)
        await setup_db.commit()

        # Test relationship loading
        result = await setup_db.execute(
            select(Bill)
            .where(Bill.bill_id == "TEST123")
            .options(selectinload(Bill.versions))
        )
        loaded_bill = result.scalar_one()
        assert len(loaded_bill.versions) == 1
        assert loaded_bill.versions[0].version_code == "ih"
```

### Database Connection Tests
```python
class TestDatabaseConnection:
    """Verify database connection management"""

    async def test_connection_pool_limits(self):
        """Verify connection pool limits"""
        pool = await init_db_pool()
        assert pool.get_size() <= 20  # Max connections
        assert pool.get_min_size() == 5  # Min connections

    async def test_session_lifecycle(self):
        """Verify session management"""
        async with AsyncSession(engine) as session:
            # Test transaction
            bill = Bill(
                bill_id="TEST123",
                congress_id=117,
                bill_type="hr",
                bill_number=1234,
                title="Test Bill"
            )
            session.add(bill)
            await session.commit()

            # Verify commit
            result = await session.execute(
                select(Bill).where(Bill.bill_id == "TEST123")
            )
            assert result.scalar_one().bill_id == "TEST123"

            # Test rollback
            bill.title = "Updated Title"
            await session.rollback()
            result = await session.execute(
                select(Bill).where(Bill.bill_id == "TEST123")
            )
            assert result.scalar_one().title == "Test Bill"
```

### Index Performance Tests
```python
class TestIndexPerformance:
    """Verify index usage and performance"""

    async def test_congress_type_index(self, setup_db: AsyncSession):
        """Verify congress_type index usage"""
        # Create test data
        bills = [
            Bill(
                bill_id=f"TEST{i}",
                congress_id=117,
                bill_type="hr",
                bill_number=i,
                title=f"Test Bill {i}"
            ) for i in range(100)
        ]
        setup_db.add_all(bills)
        await setup_db.commit()

        # Test index usage
        query = select(Bill).where(
            and_(
                Bill.congress_id == 117,
                Bill.bill_type == "hr"
            )
        )
        result = await setup_db.execute(query)
        assert len(result.scalars().all()) == 100

        # Verify plan uses index
        plan = await setup_db.execute(
            text("EXPLAIN ANALYZE " + str(query))
        )
        plan_text = "\n".join([row[0] for row in plan])
        assert "Index Scan" in plan_text
        assert "idx_bills_congress_type" in plan_text

    async def test_text_search_index(self, setup_db: AsyncSession):
        """Verify text search index usage"""
        # Test trigram search
        query = select(Bill).where(
            Bill.title.match("Test Bill")
        )
        result = await setup_db.execute(query)
        assert len(result.scalars().all()) > 0

        # Verify plan uses gin index
        plan = await setup_db.execute(
            text("EXPLAIN ANALYZE " + str(query))
        )
        plan_text = "\n".join([row[0] for row in plan])
        assert "Gin" in plan_text
        assert "idx_bills_title_trgm" in plan_text
```
```python
class TestPerformanceBaselines:
    """Core performance baseline tests with clear thresholds"""

    @pytest.mark.benchmark
    @pytest.mark.parametrize("operation,threshold_ms", [
        ("single_bill_lookup", 10),
        ("congress_bills_list", 50),
        ("text_search", 100),
        ("relationship_load", 50)
    ])
    async def test_core_operation_timing(
        self,
        operation: str,
        threshold_ms: int,
        setup_db: AsyncSession
    ):
        """Verify core operations meet performance thresholds

        Note: These are baseline tests that should fail only on significant regressions.
        Thresholds are set conservatively (3-5x typical performance).
        """
        operations = {
            "single_bill_lookup": lambda: select(Bill).where(Bill.bill_id == "TEST001"),
            "congress_bills_list": lambda: select(Bill).where(Bill.congress_id == 117),
            "text_search": lambda: select(Bill).where(Bill.title.match("Test")),
            "relationship_load": lambda: select(Bill)
                .where(Bill.bill_id == "TEST001")
                .options(selectinload(Bill.versions))
        }

        start = time.perf_counter()
        await setup_db.execute(operations[operation]())
        duration_ms = (time.perf_counter() - start) * 1000

        assert duration_ms < threshold_ms, f"{operation} exceeded {threshold_ms}ms threshold"

    @pytest.mark.benchmark
    async def test_index_effectiveness(self, setup_db: AsyncSession):
        """Verify critical indexes are being used effectively"""
        # Create test data
        await setup_db.execute(text("""
            INSERT INTO bills (bill_id, congress_id, bill_type, bill_number, title)
            SELECT
                'TEST' || i,
                117,
                'hr',
                i,
                'Test Bill ' || i
            FROM generate_series(1, 100) i
        """))
        await setup_db.commit()

        # Test queries that MUST use indexes
        critical_queries = [
            (
                select(Bill).where(Bill.congress_id == 117),
                "idx_bills_congress_type",
                "Congress lookup MUST use congress_type index"
            ),
            (
                select(Bill).where(Bill.title.match("Test")),
                "idx_bills_title_trgm",
                "Text search MUST use trigram index"
            )
        ]

        for query, expected_index, message in critical_queries:
            plan = await setup_db.execute(text("EXPLAIN " + str(query)))
            plan_text = "\n".join([row[0] for row in plan])
            assert expected_index in plan_text, message

    @pytest.mark.benchmark
    async def test_relationship_loading_efficiency(self, setup_db: AsyncSession):
        """Verify efficient relationship loading patterns"""
        # Create test data with relationships
        bills_with_versions = [
            (
                Bill(
                    bill_id=f"TEST{i}",
                    congress_id=117,
                    bill_type="hr",
                    bill_number=i,
                    title=f"Test Bill {i}"
                ),
                [BillVersion(
                    version_id=f"TEST{i}v{j}",
                    version_code="ih",
                    bill_id=f"TEST{i}"
                ) for j in range(3)]
            ) for i in range(10)
        ]

        for bill, versions in bills_with_versions:
            setup_db.add(bill)
            setup_db.add_all(versions)
        await setup_db.commit()

        # Test N+1 prevention
        query = select(Bill).options(selectinload(Bill.versions))
        start = time.perf_counter()
        result = await setup_db.execute(query)
        bills = result.scalars().all()
        duration_ms = (time.perf_counter() - start) * 1000

        # Verify single query was used (not N+1)
        assert duration_ms < 50, "Relationship loading exceeded 50ms threshold"
        assert all(len(bill.versions) == 3 for bill in bills)

    @pytest.mark.benchmark
    async def test_connection_pool_efficiency(self, setup_db: AsyncSession):
        """Verify connection pool handles load efficiently"""
        async def execute_query():
            async with AsyncSession(engine) as session:
                await session.execute(select(Bill).limit(1))

        # Test concurrent query execution
        start = time.perf_counter()
        await asyncio.gather(*[execute_query() for _ in range(10)])
        duration_ms = (time.perf_counter() - start) * 1000

        # Should handle 10 concurrent queries in under 100ms
        assert duration_ms < 100, "Connection pool concurrent query threshold exceeded"
```
```python
class TestErrorHandling:
    """Verify standardized error handling"""

    @pytest.mark.parametrize("error_case", [
        ("integrity_error", IntegrityError, 400),
        ("not_found_error", BillNotFoundError, 404),
        ("rate_limit_error", ApiRateLimitError, 429),
        ("operational_error", OperationalError, 503)
    ])
    async def test_error_response_format(
        self,
        error_case: tuple,
        client: TestClient
    ):
        """Verify error responses follow standard format"""
        error_type, error_class, expected_status = error_case

        with pytest.raises(error_class):
            # Trigger error condition
            response = await client.get("/api/bills/invalid")

        assert response.status_code == expected_status
        error_response = APIError(**response.json())
        assert error_response.error == error_class.__name__
        assert error_response.trace_id is not None
        assert isinstance(error_response.detail, str)

class TestPerformanceThresholds:
    """Verify consistent performance thresholds"""

    THRESHOLDS = {
        "single_query": 10,    # ms
        "batch_query": 50,     # ms
        "search_query": 100,   # ms
        "relationship_load": 50 # ms
    }

    @pytest.mark.parametrize("operation,threshold", THRESHOLDS.items())
    async def test_operation_performance(
        self,
        operation: str,
        threshold: int,
        setup_db: AsyncSession
    ):
        """Verify operations meet performance thresholds"""
        start = time.perf_counter()

        if operation == "single_query":
            await setup_db.execute(
                select(Bill).where(Bill.bill_id == "TEST001")
            )
        elif operation == "batch_query":
            await setup_db.execute(
                select(Bill).where(Bill.congress_id == 117)
            )
        elif operation == "search_query":
            await setup_db.execute(
                select(Bill).where(Bill.title.match("Test"))
            )
        elif operation == "relationship_load":
            await setup_db.execute(
                select(Bill)
                .where(Bill.bill_id == "TEST001")
                .options(selectinload(Bill.versions))
            )

        duration_ms = (time.perf_counter() - start) * 1000
        assert duration_ms < threshold, f"{operation} exceeded {threshold}ms threshold"

class TestLoggingIntegration:
    """Verify logging adheres to defined schema"""

    async def test_structured_logging(self, setup_db: AsyncSession):
        """Verify log entries follow schema"""
        with LogCapture() as logs:
            await setup_db.execute(
                select(Bill).where(Bill.bill_id == "TEST001")
            )

        log_entry = logs.records[-1]
        assert "trace_id" in log_entry.__dict__
        assert "timestamp" in log_entry.__dict__
        assert log_entry.levelno in (10, 20, 30, 40, 50)  # Valid log levels
        assert isinstance(log_entry.msg, str)

    async def test_error_logging(self, setup_db: AsyncSession):
        """Verify error logging format"""
        with LogCapture() as logs:
            with pytest.raises(BillNotFoundError):
                await setup_db.execute(
                    select(Bill).where(Bill.bill_id == "INVALID")
                )

        error_log = logs.records[-1]
        assert error_log.levelno == 40  # ERROR
        assert "trace_id" in error_log.__dict__
        assert "error_type" in error_log.__dict__
        assert error_log.error_type == "BillNotFoundError"
```
