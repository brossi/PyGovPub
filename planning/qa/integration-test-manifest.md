# PyGovPub Integration Test Manifest

## Overview

This manifest defines integration testing strategies and scenarios for PyGovPub, focusing on:
- Cross-component interactions
- System boundaries
- Data flow verification
- End-to-end workflows
- Infrastructure integration

## Test Environment Setup

### Base Environment Configuration
```python
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from typing import AsyncGenerator, Dict, Any
import pytest
import asyncio
import docker

class IntegrationTestBase:
    """Base class for integration tests"""

    @pytest.fixture(scope="session")
    async def docker_services(self):
        """Provide containerized services for testing"""
        async with docker.DockerClient() as client:
            # Start PostgreSQL
            postgres = await client.containers.run(
                "postgres:14",
                environment={
                    "POSTGRES_DB": "test",
                    "POSTGRES_USER": "test",
                    "POSTGRES_PASSWORD": "test"
                },
                ports={'5432/tcp': None},
                detach=True
            )

            # Start Redis
            redis = await client.containers.run(
                "redis:6",
                ports={'6379/tcp': None},
                detach=True
            )

            yield {
                "postgres": postgres,
                "redis": redis
            }

            # Cleanup
            await postgres.stop()
            await redis.stop()

    @pytest.fixture(scope="session")
    def engine(self, docker_services):
        """Create SQLModel engine"""
        postgres = docker_services["postgres"]
        port = postgres.ports['5432/tcp'][0]

        return create_engine(
            f"postgresql+asyncpg://test:test@localhost:{port}/test",
            echo=True,
            future=True
        )

    @pytest.fixture(autouse=True)
    async def setup_db(self, engine) -> AsyncGenerator[Session, None]:
        """Setup test database with SQLModel"""
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

        async with Session(engine) as session:
            yield session
            await session.rollback()

    @pytest.fixture
    def test_app(self, setup_db):
        """Create FastAPI test application"""
        from app.main import app

        async def override_get_db():
            yield setup_db

        app.dependency_overrides[get_db] = override_get_db
        return app

    @pytest.fixture
    def client(self, test_app) -> TestClient:
        """Create FastAPI test client"""
        return TestClient(test_app)

### Test Data Models
```python
class IntegrationTestBill(SQLModel, table=True):
    """Bill model for integration testing"""
    __tablename__ = "integration_test_bills"

    id: Optional[int] = Field(default=None, primary_key=True)
    bill_id: str = Field(index=True)
    congress: int = Field(index=True)
    content: Dict[str, Any] = Field(default={}, sa_column=Column(JSONB))

    __table_args__ = (
        UniqueConstraint("bill_id", "congress", name="uq_bill_congress"),
    )

class IntegrationTestEvent(SQLModel, table=True):
    """Event model for integration testing"""
    __tablename__ = "integration_test_events"

    id: Optional[int] = Field(default=None, primary_key=True)
    event_type: str = Field(index=True)
    entity_id: str = Field(index=True)
    payload: Dict[str, Any] = Field(sa_column=Column(JSONB))
    processed: bool = Field(default=False)

    __table_args__ = (
        Index("idx_unprocessed_events", "processed", "event_type",
              postgresql_where=text("processed = false")),
    )

@pytest.fixture
async def seed_integration_data(setup_db: Session):
    """Seed data for integration tests"""
    bills = [
        IntegrationTestBill(
            bill_id="HR1234",
            congress=117,
            content={"version": "ih", "title": "Test Bill"}
        ),
        IntegrationTestBill(
            bill_id="S2345",
            congress=117,
            content={"version": "is", "title": "Another Test Bill"}
        )
    ]

    events = [
        IntegrationTestEvent(
            event_type="bill_introduced",
            entity_id="HR1234",
            payload={"action": "introduced", "date": "2023-01-03"}
        ),
        IntegrationTestEvent(
            event_type="bill_referred",
            entity_id="HR1234",
            payload={"committee": "HSBA", "date": "2023-01-04"}
        )
    ]

    setup_db.add_all(bills + events)
    await setup_db.commit()
```

## Core Integration Flows

### Legislative Data Flow
```python
class TestLegislativeIntegration(IntegrationTestBase):
    """Verify legislative data integration workflows"""

    async def test_bill_lifecycle(
        self,
        client: TestClient,
        setup_db: Session,
        seed_integration_data: None
    ):
        """Verify complete bill tracking workflow"""
        # Test bill creation
        bill_request = {
            "congress": 117,
            "bill_type": "hr",
            "number": 5678,
            "title": "New Test Bill"
        }
        response = await client.post("/api/bills", json=bill_request)
        assert response.status_code == 201
        bill_id = response.json()["data"]["bill_id"]

        # Test status update
        status_update = {
            "action": "introduced",
            "date": "2023-02-01",
            "sponsor": "B001234"
        }
        response = await client.post(f"/api/bills/{bill_id}/status", json=status_update)
        assert response.status_code == 200

        # Verify database state
        result = await setup_db.execute(
            select(IntegrationTestBill)
            .where(IntegrationTestBill.bill_id == bill_id)
        )
        db_bill = result.scalar_one()
        assert db_bill.content["status"] == "introduced"

        # Verify event creation
        result = await setup_db.execute(
            select(IntegrationTestEvent)
            .where(IntegrationTestEvent.entity_id == bill_id)
            .where(IntegrationTestEvent.event_type == "bill_introduced")
        )
        event = result.scalar_one()
        assert event.payload["date"] == "2023-02-01"

    async def test_committee_workflow(
        self,
        client: TestClient,
        setup_db: Session,
        seed_integration_data: None
    ):
        """Verify committee activity integration"""
        # Test committee referral
        referral = {
            "committee_id": "HSBA",
            "date": "2023-02-02",
            "type": "primary"
        }
        response = await client.post("/api/bills/HR1234/referrals", json=referral)
        assert response.status_code == 200

        # Verify event creation
        result = await setup_db.execute(
            select(IntegrationTestEvent)
            .where(IntegrationTestEvent.entity_id == "HR1234")
            .where(IntegrationTestEvent.event_type == "bill_referred")
            .order_by(IntegrationTestEvent.id.desc())
        )
        event = result.scalar_one()
        assert event.payload["committee"] == "HSBA"

        # Test report filing
        report = {
            "report_number": "118-123",
            "committee_id": "HSBA",
            "date": "2023-02-15"
        }
        response = await client.post("/api/bills/HR1234/reports", json=report)
        assert response.status_code == 200

    async def test_member_integration(
        self,
        client: TestClient,
        setup_db: Session
    ):
        """Verify member data integration"""
        # Test member creation
        member = {
            "bioguide_id": "B001234",
            "first_name": "Test",
            "last_name": "Member",
            "state": "CA"
        }
        response = await client.post("/api/members", json=member)
        assert response.status_code == 201

        # Test sponsorship
        sponsor = {
            "bill_id": "HR1234",
            "member_id": "B001234",
            "type": "sponsor",
            "date": "2023-02-01"
        }
        response = await client.post("/api/bills/HR1234/sponsors", json=sponsor)
        assert response.status_code == 200

        # Verify relationship
        result = await setup_db.execute(
            select(IntegrationTestBill)
            .where(IntegrationTestBill.bill_id == "HR1234")
        )
        bill = result.scalar_one()
        assert bill.content["sponsor"] == "B001234"

    async def test_bill_version_authentication(
        self,
        client: TestClient,
        setup_db: Session
    ):
        """Verify bill version authentication workflow"""
        # Test version creation
        version = {
            "bill_id": "HR1234",
            "version_code": "ih",
            "content": "Test content",
            "signature": "test_signature"
        }
        response = await client.post("/api/bills/HR1234/versions", json=version)
        assert response.status_code == 201

        # Test signature verification
        response = await client.post("/api/bills/HR1234/versions/ih/verify")
        assert response.status_code == 200
        assert response.json()["data"]["verified"] == True

        # Verify database state
        result = await setup_db.execute(
            select(IntegrationTestBill)
            .where(IntegrationTestBill.bill_id == "HR1234")
        )
        bill = result.scalar_one()
        assert bill.content["versions"]["ih"]["verified"] == True

    async def test_amendment_committee_flow(
        self,
        client: TestClient,
        setup_db: Session
    ):
        """Verify amendment-committee integration"""
        # Test amendment creation
        amendment = {
            "bill_id": "HR1234",
            "number": "123",
            "sponsor": "B001234"
        }
        response = await client.post("/api/amendments", json=amendment)
        assert response.status_code == 201
        amendment_id = response.json()["data"]["amendment_id"]

        # Test committee referral
        referral = {
            "committee_id": "HSBA",
            "date": "2023-02-03"
        }
        response = await client.post(
            f"/api/amendments/{amendment_id}/referrals",
            json=referral
        )
        assert response.status_code == 200

        # Verify event creation
        result = await setup_db.execute(
            select(IntegrationTestEvent)
            .where(IntegrationTestEvent.entity_id == amendment_id)
            .where(IntegrationTestEvent.event_type == "amendment_referred")
        )
        event = result.scalar_one()
        assert event.payload["committee"] == "HSBA"
```

### Document Processing Flow
```python
from sqlmodel import SQLModel, Field, Column, JSON
from typing import Dict, Any, Optional
from datetime import datetime

class IntegrationTestDocument(SQLModel, table=True):
    """Document model for integration testing"""
    __tablename__ = "integration_test_documents"

    id: Optional[int] = Field(default=None, primary_key=True)
    package_id: str = Field(index=True)
    document_type: str = Field(index=True)
    content: Dict[str, Any] = Field(default={}, sa_column=Column(JSON))
    signature_verified: bool = Field(default=False)
    last_verified_at: datetime = Field(default_factory=datetime.utcnow)

class TestDocumentIntegration(IntegrationTestBase):
    """Verify document processing workflows"""

    @pytest.fixture
    async def test_document(self, setup_db: Session):
        """Provide test document data"""
        doc = IntegrationTestDocument(
            package_id="BILLS-117hr1234ih",
            document_type="bill",
            content={
                "title": "Test Bill",
                "version": "ih",
                "congress": 117
            }
        )
        setup_db.add(doc)
        await setup_db.commit()
        return doc

    async def test_document_lifecycle(
        self,
        client: TestClient,
        setup_db: Session,
        test_document: IntegrationTestDocument
    ):
        """Verify complete document workflow"""
        # Test document retrieval
        response = await client.get(f"/api/documents/{test_document.package_id}")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["package_id"] == test_document.package_id

        # Test content update
        content_update = {
            "version": "enr",
            "title": "Updated Test Bill"
        }
        response = await client.put(
            f"/api/documents/{test_document.package_id}/content",
            json=content_update
        )
        assert response.status_code == 200

        # Verify database state
        result = await setup_db.execute(
            select(IntegrationTestDocument)
            .where(IntegrationTestDocument.package_id == test_document.package_id)
        )
        updated_doc = result.scalar_one()
        assert updated_doc.content["version"] == "enr"

    async def test_authentication_chain(
        self,
        client: TestClient,
        setup_db: Session,
        test_document: IntegrationTestDocument
    ):
        """Verify authentication workflow"""
        # Test signature verification
        signature_data = {
            "signature": "test_signature",
            "algorithm": "sha256",
            "timestamp": datetime.utcnow().isoformat()
        }
        response = await client.post(
            f"/api/documents/{test_document.package_id}/verify",
            json=signature_data
        )
        assert response.status_code == 200

        # Verify database state
        result = await setup_db.execute(
            select(IntegrationTestDocument)
            .where(IntegrationTestDocument.package_id == test_document.package_id)
        )
        verified_doc = result.scalar_one()
        assert verified_doc.signature_verified
        assert verified_doc.last_verified_at is not None

    async def test_content_delivery(
        self,
        client: TestClient,
        setup_db: Session,
        test_document: IntegrationTestDocument
    ):
        """Verify content delivery pipeline"""
        # Test PDF retrieval
        response = await client.get(
            f"/api/documents/{test_document.package_id}/content",
            params={"format": "pdf"}
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"

        # Test XML retrieval
        response = await client.get(
            f"/api/documents/{test_document.package_id}/content",
            params={"format": "xml"}
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/xml"

    async def test_regulatory_document_flow(
        self,
        client: TestClient,
        setup_db: Session
    ):
        """Verify regulatory document workflow"""
        # Test FR document creation
        fr_doc = {
            "citation": "86 FR 12345",
            "agency": "EPA",
            "document_type": "rule"
        }
        response = await client.post("/api/documents/fr", json=fr_doc)
        assert response.status_code == 201
        doc_id = response.json()["data"]["package_id"]

        # Verify database state
        result = await setup_db.execute(
            select(IntegrationTestDocument)
            .where(IntegrationTestDocument.package_id == doc_id)
        )
        db_doc = result.scalar_one()
        assert db_doc.document_type == "fr"
        assert db_doc.content["citation"] == "86 FR 12345"

    async def test_document_version_management(
        self,
        client: TestClient,
        setup_db: Session,
        test_document: IntegrationTestDocument
    ):
        """Verify version management workflow"""
        # Test version creation
        version_data = {
            "version_code": "enr",
            "content": "Updated content",
            "timestamp": datetime.utcnow().isoformat()
        }
        response = await client.post(
            f"/api/documents/{test_document.package_id}/versions",
            json=version_data
        )
        assert response.status_code == 201

        # Verify version history
        response = await client.get(
            f"/api/documents/{test_document.package_id}/versions"
        )
        assert response.status_code == 200
        versions = response.json()["data"]
        assert len(versions) == 2  # Original + new version
```

### Event System Flow
```python
from sqlmodel import SQLModel, Field, Column, JSON
from typing import Dict, Any, Optional
from datetime import datetime

class IntegrationTestWebhook(SQLModel, table=True):
    """Webhook configuration for integration testing"""
    __tablename__ = "integration_test_webhooks"

    id: Optional[int] = Field(default=None, primary_key=True)
    url: str = Field(index=True)
    secret: str
    event_types: list[str] = Field(default=[])
    active: bool = Field(default=True)
    last_delivery_at: Optional[datetime] = None

class TestEventIntegration(IntegrationTestBase):
    """Verify event system workflows"""

    @pytest.fixture
    async def test_webhook(self, setup_db: Session):
        """Provide test webhook configuration"""
        webhook = IntegrationTestWebhook(
            url="https://test.example.com/webhook",
            secret="test_secret_123",
            event_types=["bill.introduced", "bill.reported"]
        )
        setup_db.add(webhook)
        await setup_db.commit()
        return webhook

    async def test_event_pipeline(
        self,
        client: TestClient,
        setup_db: Session,
        test_webhook: IntegrationTestWebhook
    ):
        """Verify complete event workflow"""
        # Create test event
        event_data = {
            "type": "bill.introduced",
            "data": {
                "bill_id": "HR1234",
                "congress": 117,
                "action_date": "2023-03-01"
            }
        }
        response = await client.post("/api/events", json=event_data)
        assert response.status_code == 201
        event_id = response.json()["data"]["event_id"]

        # Verify event processing
        response = await client.get(f"/api/events/{event_id}")
        assert response.status_code == 200
        assert response.json()["data"]["processed"] == True

        # Verify webhook delivery
        result = await setup_db.execute(
            select(IntegrationTestEvent)
            .where(IntegrationTestEvent.id == event_id)
        )
        event = result.scalar_one()
        assert event.processed
        assert "delivery_attempts" in event.payload

    async def test_subscription_workflow(
        self,
        client: TestClient,
        setup_db: Session
    ):
        """Verify subscription lifecycle"""
        # Create subscription
        subscription = {
            "url": "https://test.example.com/webhook2",
            "secret": "test_secret_456",
            "event_types": ["committee.*"],
            "filters": {
                "congress": 117,
                "chamber": "house"
            }
        }
        response = await client.post("/api/webhooks", json=subscription)
        assert response.status_code == 201
        webhook_id = response.json()["data"]["webhook_id"]

        # Test filter update
        filter_update = {
            "filters": {
                "congress": 117,
                "chamber": ["house", "senate"]
            }
        }
        response = await client.patch(
            f"/api/webhooks/{webhook_id}",
            json=filter_update
        )
        assert response.status_code == 200

        # Verify database state
        result = await setup_db.execute(
            select(IntegrationTestWebhook)
            .where(IntegrationTestWebhook.id == webhook_id)
        )
        webhook = result.scalar_one()
        assert "house" in webhook.content["filters"]["chamber"]
        assert "senate" in webhook.content["filters"]["chamber"]

    async def test_delivery_reliability(
        self,
        client: TestClient,
        setup_db: Session,
        test_webhook: IntegrationTestWebhook
    ):
        """Verify reliable delivery"""
        # Create test event
        event_data = {
            "type": "bill.introduced",
            "data": {"bill_id": "HR1234"}
        }

        # Simulate failed delivery
        with patch("app.services.webhook.deliver_event") as mock_deliver:
            mock_deliver.side_effect = [
                ConnectionError("Network error"),
                ConnectionError("Timeout"),
                None  # Success on third try
            ]

            response = await client.post("/api/events", json=event_data)
            assert response.status_code == 201
            event_id = response.json()["data"]["event_id"]

        # Verify retry behavior
        result = await setup_db.execute(
            select(IntegrationTestEvent)
            .where(IntegrationTestEvent.id == event_id)
        )
        event = result.scalar_one()
        assert event.processed
        assert len(event.payload["delivery_attempts"]) == 3
        assert event.payload["delivery_attempts"][-1]["success"]

    async def test_webhook_security(
        self,
        client: TestClient,
        setup_db: Session,
        test_webhook: IntegrationTestWebhook
    ):
        """Verify webhook security measures"""
        # Test signature verification
        event_data = {
            "type": "bill.introduced",
            "data": {"bill_id": "HR1234"}
        }

        # Generate valid signature
        signature = hmac.new(
            test_webhook.secret.encode(),
            json.dumps(event_data).encode(),
            hashlib.sha256
        ).hexdigest()

        # Test with valid signature
        response = await client.post(
            "/api/events",
            json=event_data,
            headers={"X-Webhook-Signature": signature}
        )
        assert response.status_code == 201

        # Test with invalid signature
        response = await client.post(
            "/api/events",
            json=event_data,
            headers={"X-Webhook-Signature": "invalid"}
        )
        assert response.status_code == 401

    async def test_event_filter_processing(
        self,
        client: TestClient,
        setup_db: Session,
        test_webhook: IntegrationTestWebhook
    ):
        """Verify event filter processing"""
        # Create filtered webhook
        webhook_data = {
            "url": "https://test.example.com/webhook3",
            "secret": "test_secret_789",
            "event_types": ["bill.*"],
            "filters": {
                "congress": 117,
                "bill_type": ["hr", "s"],
                "committee": "HSBA"
            }
        }
        response = await client.post("/api/webhooks", json=webhook_data)
        assert response.status_code == 201

        # Test matching event
        matching_event = {
            "type": "bill.reported",
            "data": {
                "bill_id": "HR1234",
                "congress": 117,
                "committee": "HSBA"
            }
        }
        response = await client.post("/api/events", json=matching_event)
        assert response.status_code == 201

        # Test non-matching event
        non_matching_event = {
            "type": "bill.reported",
            "data": {
                "bill_id": "HR1234",
                "congress": 118,  # Different congress
                "committee": "HSBA"
            }
        }
        response = await client.post("/api/events", json=non_matching_event)
        assert response.status_code == 201

        # Verify delivery filtering
        result = await setup_db.execute(
            select(IntegrationTestEvent)
            .where(IntegrationTestEvent.event_type == "bill.reported")
            .order_by(IntegrationTestEvent.id.desc())
            .limit(2)
        )
        events = result.scalars().all()

        assert events[0].payload["delivery_status"] == "filtered"
        assert events[1].payload["delivery_status"] == "delivered"
```

## System Boundary Tests

### External API Integration
```python
from sqlmodel import SQLModel, Field, Column, JSON
from datetime import datetime
from typing import Optional, Dict, Any, List

class APIResponse(SQLModel, table=True):
    """Model for tracking API responses"""
    __tablename__ = "integration_test_api_responses"

    id: Optional[int] = Field(default=None, primary_key=True)
    service: str = Field(index=True)  # congress.gov or govinfo.gov
    endpoint: str = Field(index=True)
    response_time: float
    status_code: int
    headers: Dict[str, Any] = Field(default={}, sa_column=Column(JSON))
    rate_limit_remaining: Optional[int] = None
    rate_limit_reset: Optional[datetime] = None

class TestAPIBoundaries(IntegrationTestBase):
    """Verify external API integration"""

    @pytest.fixture
    async def test_api_response(self, setup_db: Session) -> APIResponse:
        """Provide test API response data"""
        response = APIResponse(
            service="congress.gov",
            endpoint="/bill/117/hr/1234",
            response_time=0.234,
            status_code=200,
            headers={
                "X-RateLimit-Remaining": "95",
                "X-RateLimit-Reset": "1623456789"
            },
            rate_limit_remaining=95
        )
        setup_db.add(response)
        await setup_db.commit()
        return response

    async def test_congress_api_integration(
        self,
        client: TestClient,
        setup_db: Session,
        test_api_response: APIResponse
    ):
        """Verify Congress.gov API integration"""
        # Test request formatting
        response = await client.get(
            "/api/proxy/congress/bill/117/hr/1234",
            headers={"X-API-Key": "test_key"}
        )
        assert response.status_code == 200

        # Verify response handling
        result = await setup_db.execute(
            select(APIResponse)
            .where(APIResponse.endpoint == "/bill/117/hr/1234")
            .order_by(APIResponse.id.desc())
        )
        latest_response = result.scalar_one()
        assert latest_response.status_code == 200
        assert latest_response.rate_limit_remaining is not None

    async def test_govinfo_api_integration(
        self,
        client: TestClient,
        setup_db: Session
    ):
        """Verify GovInfo.gov API integration"""
        # Test package retrieval
        response = await client.get(
            "/api/proxy/govinfo/BILLS-117hr1234ih/pdf",
            params={"api_key": "test_key"}
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"

        # Verify response tracking
        result = await setup_db.execute(
            select(APIResponse)
            .where(APIResponse.service == "govinfo.gov")
            .order_by(APIResponse.id.desc())
        )
        latest_response = result.scalar_one()
        assert latest_response.endpoint.endswith("/pdf")

    async def test_rate_limit_coordination(
        self,
        client: TestClient,
        setup_db: Session
    ):
        """Verify rate limit coordination"""
        # Create test responses with rate limits
        responses = [
            APIResponse(
                service="congress.gov",
                endpoint=f"/test/endpoint/{i}",
                response_time=0.1,
                status_code=200,
                rate_limit_remaining=100-i
            ) for i in range(5)
        ]
        setup_db.add_all(responses)
        await setup_db.commit()

        # Test rate limit tracking
        result = await setup_db.execute(
            select(func.min(APIResponse.rate_limit_remaining))
            .where(APIResponse.service == "congress.gov")
        )
        min_remaining = result.scalar_one()
        assert min_remaining == 96  # 100 - 4

    async def test_api_version_compatibility(
        self,
        client: TestClient,
        setup_db: Session
    ):
        """Verify API version compatibility"""
        # Test Congress.gov v3 endpoint
        response = await client.get(
            "/api/proxy/congress/v3/bill/117/hr/1234",
            headers={"X-API-Key": "test_key"}
        )
        assert response.status_code == 200

        # Verify response schema evolution
        result = await setup_db.execute(
            select(APIResponse)
            .where(APIResponse.endpoint.like("%/v3/%"))
        )
        v3_response = result.scalar_one()
        assert "v3" in v3_response.endpoint
```

### Database Integration
```python
from sqlmodel import SQLModel, Field, Column, JSON, text
from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy.dialects.postgresql import JSONB

class PartitionTest(SQLModel, table=True):
    """Model for testing partitioned tables"""
    __tablename__ = "integration_test_partitions"

    id: Optional[int] = Field(default=None, primary_key=True)
    congress: int = Field(index=True)
    document_type: str = Field(index=True)
    content: Dict[str, Any] = Field(default={}, sa_column=Column(JSONB))
    created_at: datetime = Field(default_factory=datetime.utcnow)

    __table_args__ = (
        text('PARTITION BY RANGE (congress)'),
    )

class TestDatabaseBoundaries(IntegrationTestBase):
    """Verify database integration"""

    @pytest.fixture
    async def setup_partitions(self, setup_db: Session):
        """Create test partitions"""
        await setup_db.execute(text("""
            CREATE TABLE IF NOT EXISTS integration_test_partitions_117
            PARTITION OF integration_test_partitions
            FOR VALUES FROM (117) TO (118)
        """))
        await setup_db.execute(text("""
            CREATE TABLE IF NOT EXISTS integration_test_partitions_118
            PARTITION OF integration_test_partitions
            FOR VALUES FROM (118) TO (119)
        """))
        await setup_db.commit()

    async def test_transaction_boundaries(
        self,
        setup_db: Session
    ):
        """Verify transaction management"""
        # Test atomic operations
        async with setup_db.begin():
            test_doc = PartitionTest(
                congress=117,
                document_type="bill",
                content={"status": "introduced"}
            )
            setup_db.add(test_doc)

        # Verify commit
        result = await setup_db.execute(
            select(PartitionTest)
            .where(PartitionTest.congress == 117)
        )
        saved_doc = result.scalar_one()
        assert saved_doc.content["status"] == "introduced"

        # Test rollback
        async with setup_db.begin() as tx:
            test_doc.content["status"] = "reported"
            await setup_db.flush()
            await tx.rollback()

        # Verify rollback
        result = await setup_db.execute(
            select(PartitionTest)
            .where(PartitionTest.congress == 117)
        )
        current_doc = result.scalar_one()
        assert current_doc.content["status"] == "introduced"

    async def test_partition_management(
        self,
        setup_db: Session,
        setup_partitions: None
    ):
        """Verify partition operations"""
        # Test data distribution
        docs = [
            PartitionTest(
                congress=117,
                document_type="bill",
                content={"number": i}
            ) for i in range(5)
        ] + [
            PartitionTest(
                congress=118,
                document_type="bill",
                content={"number": i}
            ) for i in range(5)
        ]
        setup_db.add_all(docs)
        await setup_db.commit()

        # Verify partition distribution
        result = await setup_db.execute(text("""
            SELECT tableoid::regclass::text as partition_name, count(*)
            FROM integration_test_partitions
            GROUP BY tableoid
        """))
        partition_counts = {row[0]: row[1] for row in result}
        assert partition_counts["integration_test_partitions_117"] == 5
        assert partition_counts["integration_test_partitions_118"] == 5

    async def test_congress_partitioning(
        self,
        setup_db: Session,
        setup_partitions: None
    ):
        """Verify congress-based partitioning"""
        # Test cross-partition query
        result = await setup_db.execute(
            select(PartitionTest)
            .where(PartitionTest.document_type == "bill")
            .order_by(PartitionTest.congress)
        )
        docs = result.scalars().all()
        assert len(docs) == 10
        assert [doc.congress for doc in docs[:5]] == [117] * 5
        assert [doc.congress for doc in docs[5:]] == [118] * 5

    async def test_relationship_integrity(
        self,
        setup_db: Session
    ):
        """Verify relationship integrity"""
        # Test relationship constraints
        bill = PartitionTest(
            congress=117,
            document_type="bill",
            content={
                "number": "1234",
                "type": "hr",
                "related_docs": []
            }
        )
        amendment = PartitionTest(
            congress=117,
            document_type="amendment",
            content={
                "number": "123",
                "bill_reference": "117hr1234"
            }
        )
        setup_db.add_all([bill, amendment])
        await setup_db.commit()

        # Update relationships
        bill.content["related_docs"].append({
            "type": "amendment",
            "number": "123"
        })
        await setup_db.commit()

        # Verify relationship
        result = await setup_db.execute(
            select(PartitionTest)
            .where(PartitionTest.congress == 117)
            .where(PartitionTest.document_type == "bill")
        )
        updated_bill = result.scalar_one()
        assert len(updated_bill.content["related_docs"]) == 1
        assert updated_bill.content["related_docs"][0]["number"] == "123"
```

### Cache Integration
```python
from sqlmodel import SQLModel, Field, Column, JSON
from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy.dialects.postgresql import JSONB

class CacheEntry(SQLModel, table=True):
    """Model for tracking cache entries"""
    __tablename__ = "integration_test_cache_entries"

    id: Optional[int] = Field(default=None, primary_key=True)
    key: str = Field(index=True)
    value: Dict[str, Any] = Field(sa_column=Column(JSONB))
    content_hash: str = Field(index=True)
    last_accessed: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    invalidated: bool = Field(default=False)

class TestCacheBoundaries(IntegrationTestBase):
    """Verify cache system integration"""

    @pytest.fixture
    async def test_cache_entry(self, setup_db: Session) -> CacheEntry:
        """Provide test cache entry"""
        entry = CacheEntry(
            key="test_bill_117_hr_1234",
            value={
                "bill_id": "HR1234",
                "congress": 117,
                "title": "Test Bill"
            },
            content_hash="abc123",
            expires_at=datetime.utcnow() + timedelta(hours=1)
        )
        setup_db.add(entry)
        await setup_db.commit()
        return entry

    async def test_cache_coordination(
        self,
        client: TestClient,
        setup_db: Session,
        test_cache_entry: CacheEntry
    ):
        """Verify cache operations"""
        # Test cache hit
        response = await client.get(
            "/api/bills/117/hr/1234",
            headers={"Cache-Control": "max-age=3600"}
        )
        assert response.status_code == 200
        assert response.headers["X-Cache"] == "HIT"

        # Verify cache access update
        result = await setup_db.execute(
            select(CacheEntry)
            .where(CacheEntry.key == "test_bill_117_hr_1234")
        )
        updated_entry = result.scalar_one()
        assert updated_entry.last_accessed > test_cache_entry.last_accessed

    async def test_cache_consistency(
        self,
        client: TestClient,
        setup_db: Session,
        test_cache_entry: CacheEntry
    ):
        """Verify cache consistency"""
        # Test write-through
        update_data = {
            "title": "Updated Test Bill"
        }
        response = await client.patch(
            "/api/bills/117/hr/1234",
            json=update_data
        )
        assert response.status_code == 200

        # Verify cache invalidation
        result = await setup_db.execute(
            select(CacheEntry)
            .where(CacheEntry.key == "test_bill_117_hr_1234")
        )
        updated_entry = result.scalar_one()
        assert updated_entry.invalidated == True

        # Test cache revalidation
        response = await client.get("/api/bills/117/hr/1234")
        assert response.status_code == 200
        assert response.headers["X-Cache"] == "REVALIDATED"

        # Verify new cache entry
        result = await setup_db.execute(
            select(CacheEntry)
            .where(CacheEntry.key == "test_bill_117_hr_1234")
            .where(CacheEntry.invalidated == False)
            .order_by(CacheEntry.id.desc())
        )
        new_entry = result.scalar_one()
        assert new_entry.value["title"] == "Updated Test Bill"
        assert new_entry.content_hash != test_cache_entry.content_hash

    async def test_cache_invalidation_cascade(
        self,
        client: TestClient,
        setup_db: Session
    ):
        """Verify cache invalidation cascade"""
        # Create related cache entries
        entries = [
            CacheEntry(
                key=f"test_bill_117_hr_1234_{suffix}",
                value={"type": suffix},
                content_hash=f"hash_{suffix}"
            )
            for suffix in ["summary", "text", "actions"]
        ]
        setup_db.add_all(entries)
        await setup_db.commit()

        # Trigger invalidation
        response = await client.post(
            "/api/bills/117/hr/1234/invalidate",
            json={"cascade": True}
        )
        assert response.status_code == 200

        # Verify cascade invalidation
        result = await setup_db.execute(
            select(CacheEntry)
            .where(CacheEntry.key.like("test_bill_117_hr_1234%"))
        )
        invalidated_entries = result.scalars().all()
        assert all(entry.invalidated for entry in invalidated_entries)
        assert len(invalidated_entries) == 3

### Authentication Integration
```python
from sqlmodel import SQLModel, Field, Column, JSON
from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy.dialects.postgresql import JSONB
import hmac
import hashlib

class APIKey(SQLModel, table=True):
    """Model for API key management"""
    __tablename__ = "integration_test_api_keys"

    id: Optional[int] = Field(default=None, primary_key=True)
    key_id: str = Field(index=True)
    key_hash: str = Field(unique=True)
    permissions: List[str] = Field(default=[])
    rate_limit: int = Field(default=1000)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    revoked: bool = Field(default=False)

class DocumentSignature(SQLModel, table=True):
    """Model for document signatures"""
    __tablename__ = "integration_test_document_signatures"

    id: Optional[int] = Field(default=None, primary_key=True)
    document_id: str = Field(index=True)
    signature: str
    public_key_id: str = Field(index=True)
    verified_at: Optional[datetime] = None
    verification_status: str = Field(default="pending")
    verification_history: List[Dict[str, Any]] = Field(default=[])

class TestAuthenticationBoundaries(IntegrationTestBase):
    """Verify authentication integration"""

    @pytest.fixture
    async def test_api_key(self, setup_db: Session) -> APIKey:
        """Provide test API key"""
        key_secret = "test_secret_123"
        key = APIKey(
            key_id="TEST_KEY_1",
            key_hash=hashlib.sha256(key_secret.encode()).hexdigest(),
            permissions=["read:bills", "write:bills"],
            rate_limit=100
        )
        setup_db.add(key)
        await setup_db.commit()
        return key, key_secret

    @pytest.fixture
    async def test_document_signature(self, setup_db: Session) -> DocumentSignature:
        """Provide test document signature"""
        signature = DocumentSignature(
            document_id="BILLS-117hr1234ih",
            signature="test_signature_data",
            public_key_id="GPO_KEY_1",
            verification_history=[{
                "timestamp": datetime.utcnow().isoformat(),
                "status": "pending",
                "message": "Initial signature registration"
            }]
        )
        setup_db.add(signature)
        await setup_db.commit()
        return signature

    async def test_api_key_management(
        self,
        client: TestClient,
        setup_db: Session,
        test_api_key: tuple[APIKey, str]
    ):
        """Verify API key handling"""
        key, secret = test_api_key

        # Test key validation
        response = await client.get(
            "/api/bills/117/hr/1234",
            headers={"X-API-Key": secret}
        )
        assert response.status_code == 200

        # Test invalid key
        response = await client.get(
            "/api/bills/117/hr/1234",
            headers={"X-API-Key": "invalid_key"}
        )
        assert response.status_code == 401

        # Test key rotation
        new_key_data = {
            "permissions": ["read:bills"],
            "rate_limit": 200
        }
        response = await client.post(
            f"/api/keys/{key.key_id}/rotate",
            json=new_key_data
        )
        assert response.status_code == 200
        new_secret = response.json()["data"]["key"]

        # Verify old key is revoked
        result = await setup_db.execute(
            select(APIKey)
            .where(APIKey.key_id == key.key_id)
            .where(APIKey.revoked == True)
        )
        old_key = result.scalar_one()
        assert old_key.revoked

        # Verify new key works
        response = await client.get(
            "/api/bills/117/hr/1234",
            headers={"X-API-Key": new_secret}
        )
        assert response.status_code == 200

    async def test_document_signature_verification(
        self,
        client: TestClient,
        setup_db: Session,
        test_document_signature: DocumentSignature
    ):
        """Verify document signature workflow"""
        # Test signature verification
        verification_data = {
            "public_key": "test_public_key",
            "algorithm": "sha256",
            "timestamp": datetime.utcnow().isoformat()
        }
        response = await client.post(
            f"/api/documents/{test_document_signature.document_id}/verify",
            json=verification_data
        )
        assert response.status_code == 200

        # Verify signature status update
        result = await setup_db.execute(
            select(DocumentSignature)
            .where(DocumentSignature.document_id == test_document_signature.document_id)
        )
        updated_sig = result.scalar_one()
        assert updated_sig.verification_status == "verified"
        assert updated_sig.verified_at is not None
        assert len(updated_sig.verification_history) == 2

    async def test_permission_enforcement(
        self,
        client: TestClient,
        setup_db: Session,
        test_api_key: tuple[APIKey, str]
    ):
        """Verify permission enforcement"""
        key, secret = test_api_key

        # Test allowed operation
        response = await client.get(
            "/api/bills/117/hr/1234",
            headers={"X-API-Key": secret}
        )
        assert response.status_code == 200

        # Test forbidden operation
        response = await client.post(
            "/api/amendments",
            headers={"X-API-Key": secret},
            json={"bill_id": "hr1234"}
        )
        assert response.status_code == 403

        # Update permissions
        key.permissions.append("write:amendments")
        await setup_db.commit()

        # Verify updated permissions
        response = await client.post(
            "/api/amendments",
            headers={"X-API-Key": secret},
            json={"bill_id": "hr1234"}
        )
        assert response.status_code == 201
```

## Infrastructure Integration

### Load Balancing
```python
from sqlmodel import SQLModel, Field, Column, JSON
from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy.dialects.postgresql import JSONB

class RequestMetric(SQLModel, table=True):
    """Model for tracking request metrics"""
    __tablename__ = "integration_test_request_metrics"

    id: Optional[int] = Field(default=None, primary_key=True)
    endpoint: str = Field(index=True)
    method: str = Field(index=True)
    response_time: float
    status_code: int
    server_id: str = Field(index=True)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    client_ip: Optional[str] = None
    user_agent: Optional[str] = None

class TestLoadBalancing(IntegrationTestBase):
    """Verify load distribution"""

    @pytest.fixture
    async def test_request_metrics(self, setup_db: Session) -> List[RequestMetric]:
        """Provide test request metrics"""
        metrics = [
            RequestMetric(
                endpoint="/api/bills/117/hr/1234",
                method="GET",
                response_time=0.123,
                status_code=200,
                server_id=f"server_{i}",
                client_ip="127.0.0.1",
                user_agent="test-client/1.0"
            ) for i in range(3)
        ]
        setup_db.add_all(metrics)
        await setup_db.commit()
        return metrics

    async def test_request_distribution(
        self,
        client: TestClient,
        setup_db: Session,
        test_request_metrics: List[RequestMetric]
    ):
        """Verify request handling"""
        # Test load distribution
        responses = await asyncio.gather(*[
            client.get("/api/bills/117/hr/1234")
            for _ in range(5)
        ])
        assert all(r.status_code == 200 for r in responses)

        # Verify server distribution
        result = await setup_db.execute(
            select(RequestMetric.server_id, func.count())
            .group_by(RequestMetric.server_id)
        )
        server_counts = {row[0]: row[1] for row in result}
        assert len(server_counts) >= 2  # Requests distributed across servers

### Monitoring Integration
```python
class MetricSample(SQLModel, table=True):
    """Model for system metrics"""
    __tablename__ = "integration_test_metric_samples"

    id: Optional[int] = Field(default=None, primary_key=True)
    metric_name: str = Field(index=True)
    value: float
    labels: Dict[str, str] = Field(default={}, sa_column=Column(JSONB))
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class TestMonitoringIntegration(IntegrationTestBase):
    """Verify monitoring system"""

    @pytest.fixture
    async def test_metrics(self, setup_db: Session) -> List[MetricSample]:
        """Provide test metrics"""
        metrics = [
            MetricSample(
                metric_name="http_request_duration_seconds",
                value=0.123,
                labels={
                    "method": "GET",
                    "path": "/api/bills",
                    "status": "200"
                }
            ),
            MetricSample(
                metric_name="http_requests_total",
                value=1.0,
                labels={
                    "method": "GET",
                    "path": "/api/bills",
                    "status": "200"
                }
            ),
            MetricSample(
                metric_name="system_memory_bytes",
                value=1024 * 1024 * 100,  # 100MB
                labels={"type": "used"}
            )
        ]
        setup_db.add_all(metrics)
        await setup_db.commit()
        return metrics

    async def test_metric_collection(
        self,
        client: TestClient,
        setup_db: Session,
        test_metrics: List[MetricSample]
    ):
        """Verify metrics pipeline"""
        # Test metrics endpoint
        response = await client.get("/metrics")
        assert response.status_code == 200
        assert "http_request_duration_seconds" in response.text
        assert "http_requests_total" in response.text

        # Test metric recording
        response = await client.get("/api/bills/117/hr/1234")
        assert response.status_code == 200

        # Verify metric storage
        result = await setup_db.execute(
            select(MetricSample)
            .where(MetricSample.metric_name == "http_requests_total")
            .order_by(MetricSample.timestamp.desc())
        )
        latest_metric = result.scalar_one()
        assert latest_metric.labels["path"] == "/api/bills"
        assert latest_metric.labels["status"] == "200"

    async def test_alert_conditions(
        self,
        client: TestClient,
        setup_db: Session
    ):
        """Verify alert condition monitoring"""
        # Create error metrics
        error_metrics = [
            MetricSample(
                metric_name="http_requests_total",
                value=1.0,
                labels={
                    "method": "GET",
                    "path": "/api/bills",
                    "status": "500"
                }
            ) for _ in range(5)
        ]
        setup_db.add_all(error_metrics)
        await setup_db.commit()

        # Test alert endpoint
        response = await client.get("/api/alerts")
        assert response.status_code == 200
        alerts = response.json()["data"]
        assert any(
            alert["metric"] == "http_requests_total" and
            alert["severity"] == "critical"
            for alert in alerts
        )

    async def test_metric_aggregation(
        self,
        client: TestClient,
        setup_db: Session,
        test_metrics: List[MetricSample]
    ):
        """Verify metric aggregation"""
        # Test aggregation endpoint
        response = await client.get(
            "/api/metrics/aggregate",
            params={
                "metric": "http_request_duration_seconds",
                "window": "5m"
            }
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert "avg" in data
        assert "p95" in data
        assert "p99" in data
```

## Recovery Scenarios

### Failure Recovery
```python
from sqlmodel import SQLModel, Field, Column, JSON
from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy.dialects.postgresql import JSONB

class FailureEvent(SQLModel, table=True):
    """Model for tracking system failures"""
    __tablename__ = "integration_test_failures"

    id: Optional[int] = Field(default=None, primary_key=True)
    failure_type: str = Field(index=True)
    component: str = Field(index=True)
    error_message: str
    stack_trace: Optional[str] = None
    recovery_attempts: int = Field(default=0)
    recovered: bool = Field(default=False)
    metadata: Dict[str, Any] = Field(default={}, sa_column=Column(JSONB))
    occurred_at: datetime = Field(default_factory=datetime.utcnow)
    recovered_at: Optional[datetime] = None

class TestFailureRecovery(IntegrationTestBase):
    """Verify system recovery"""

    @pytest.fixture
    async def test_failure_event(self, setup_db: Session) -> FailureEvent:
        """Provide test failure event"""
        event = FailureEvent(
            failure_type="api_timeout",
            component="congress_api",
            error_message="Connection timeout",
            metadata={
                "endpoint": "/bill/117/hr/1234",
                "attempt": 1
            }
        )
        setup_db.add(event)
        await setup_db.commit()
        return event

    async def test_api_failure_recovery(
        self,
        client: TestClient,
        setup_db: Session,
        test_failure_event: FailureEvent
    ):
        """Verify API failure handling"""
        # Simulate API failure
        with patch("app.services.congress.get_bill") as mock_get_bill:
            mock_get_bill.side_effect = [
                TimeoutError("Connection timeout"),
                TimeoutError("Connection timeout"),
                {"bill_id": "hr1234", "congress": 117}  # Success on third try
            ]

            response = await client.get("/api/bills/117/hr/1234")
            assert response.status_code == 200

        # Verify recovery tracking
        result = await setup_db.execute(
            select(FailureEvent)
            .where(FailureEvent.failure_type == "api_timeout")
            .where(FailureEvent.component == "congress_api")
            .order_by(FailureEvent.occurred_at.desc())
        )
        latest_failure = result.scalar_one()
        assert latest_failure.recovery_attempts == 3
        assert latest_failure.recovered
        assert latest_failure.recovered_at is not None

    async def test_storage_failure_recovery(
        self,
        client: TestClient,
        setup_db: Session
    ):
        """Verify storage failure handling"""
        # Create test document
        doc_data = {
            "bill_id": "hr1234",
            "congress": 117,
            "content": "Test content"
        }

        # Simulate storage failure
        with patch("app.services.storage.store_document") as mock_store:
            mock_store.side_effect = [
                IOError("Storage error"),
                None  # Success on second try
            ]

            response = await client.post(
                "/api/documents",
                json=doc_data
            )
            assert response.status_code == 201

        # Verify failure tracking
        result = await setup_db.execute(
            select(FailureEvent)
            .where(FailureEvent.failure_type == "storage_error")
            .where(FailureEvent.component == "document_storage")
            .order_by(FailureEvent.occurred_at.desc())
        )
        failure = result.scalar_one()
        assert failure.recovery_attempts == 2
        assert failure.recovered

### Data Consistency Recovery
```python
class VersionConflict(SQLModel, table=True):
    """Model for tracking version conflicts"""
    __tablename__ = "integration_test_version_conflicts"

    id: Optional[int] = Field(default=None, primary_key=True)
    document_id: str = Field(index=True)
    version_a: str
    version_b: str
    conflict_type: str = Field(index=True)
    resolution: Optional[str] = None
    resolved: bool = Field(default=False)
    metadata: Dict[str, Any] = Field(default={}, sa_column=Column(JSONB))
    detected_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None

class TestConsistencyRecovery(IntegrationTestBase):
    """Verify data consistency recovery"""

    @pytest.fixture
    async def test_version_conflict(self, setup_db: Session) -> VersionConflict:
        """Provide test version conflict"""
        conflict = VersionConflict(
            document_id="BILLS-117hr1234ih",
            version_a="v1",
            version_b="v2",
            conflict_type="content_mismatch",
            metadata={
                "hash_a": "abc123",
                "hash_b": "def456"
            }
        )
        setup_db.add(conflict)
        await setup_db.commit()
        return conflict

    async def test_version_conflict_resolution(
        self,
        client: TestClient,
        setup_db: Session,
        test_version_conflict: VersionConflict
    ):
        """Verify version conflict handling"""
        # Test conflict resolution
        resolution_data = {
            "resolution": "use_version_b",
            "reason": "newer_timestamp"
        }
        response = await client.post(
            f"/api/documents/{test_version_conflict.document_id}/resolve",
            json=resolution_data
        )
        assert response.status_code == 200

        # Verify conflict resolution
        result = await setup_db.execute(
            select(VersionConflict)
            .where(VersionConflict.document_id == test_version_conflict.document_id)
        )
        resolved_conflict = result.scalar_one()
        assert resolved_conflict.resolved
        assert resolved_conflict.resolution == "use_version_b"
        assert resolved_conflict.resolved_at is not None

    async def test_relationship_repair(
        self,
        client: TestClient,
        setup_db: Session
    ):
        """Verify relationship repair"""
        # Create test relationships
        bill_data = {
            "bill_id": "hr1234",
            "congress": 117,
            "related_docs": ["amdt123", "rpt456"]
        }
        response = await client.post(
            "/api/bills",
            json=bill_data
        )
        assert response.status_code == 201

        # Simulate relationship corruption
        await setup_db.execute(
            text("""
                UPDATE bills
                SET related_docs = '["invalid_ref"]'::jsonb
                WHERE bill_id = :bill_id
            """),
            {"bill_id": "hr1234"}
        )
        await setup_db.commit()

        # Test relationship repair
        response = await client.post("/api/repair/relationships")
        assert response.status_code == 200

        # Verify repair
        result = await setup_db.execute(
            select(Bill)
            .where(Bill.bill_id == "hr1234")
        )
        repaired_bill = result.scalar_one()
        assert "amdt123" in repaired_bill.related_docs
        assert "rpt456" in repaired_bill.related_docs
```

### SQLModel Integration Flow
```python
class TestSQLModelIntegrationFlow(IntegrationTestBase):
    """Verify SQLModel integration across system boundaries"""

    async def test_model_persistence_flow(
        self,
        client: TestClient,
        setup_db: AsyncSession
    ):
        """Verify complete model persistence flow"""
        # Create test bill
        bill_data = {
            "bill_id": "HR1234-117",
            "congress_id": 117,
            "bill_type": "hr",
            "bill_number": 1234,
            "title": "Test Bill"
        }
        response = await client.post("/api/bills", json=bill_data)
        assert response.status_code == 201
        bill_id = response.json()["data"]["bill_id"]

        # Add version
        version_data = {
            "version_id": f"{bill_id}-v1",
            "bill_id": bill_id,
            "version_code": "ih"
        }
        response = await client.post(
            f"/api/bills/{bill_id}/versions",
            json=version_data
        )
        assert response.status_code == 201

        # Verify relationships
        response = await client.get(
            f"/api/bills/{bill_id}/full"
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert len(data["versions"]) == 1
        assert data["versions"][0]["version_code"] == "ih"

    async def test_query_optimization_flow(
        self,
        client: TestClient,
        setup_db: AsyncSession
    ):
        """Verify query optimization with SQLModel"""
        # Create test data
        bills = [
            Bill(
                bill_id=f"HR{i}-117",
                congress_id=117,
                bill_type="hr",
                bill_number=i,
                title=f"Test Bill {i}"
            ) for i in range(10)
        ]
        setup_db.add_all(bills)
        await setup_db.commit()

        # Test optimized loading
        response = await client.get(
            "/api/bills/congress/117",
            params={"bill_type": "hr"}
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert len(data) == 10

        # Verify query performance
        query_stats = await setup_db.execute(
            text("""
                SELECT * FROM pg_stat_statements
                WHERE query LIKE '%SELECT%bills%'
                ORDER BY total_time DESC
                LIMIT 1
            """)
        )
        stats = query_stats.first()
        assert stats["mean_time"] < 100  # ms

    async def test_constraint_propagation(
        self,
        client: TestClient,
        setup_db: AsyncSession
    ):
        """Verify constraint handling across layers"""
        # Test invalid bill type
        invalid_bill = {
            "bill_id": "HR1234-117",
            "congress_id": 117,
            "bill_type": "invalid",
            "bill_number": 1234,
            "title": "Test Bill"
        }
        response = await client.post("/api/bills", json=invalid_bill)
        assert response.status_code == 422  # Validation error

        # Test duplicate prevention
        bill_data = {
            "bill_id": "HR1234-117",
            "congress_id": 117,
            "bill_type": "hr",
            "bill_number": 1234,
            "title": "Test Bill"
        }
        response = await client.post("/api/bills", json=bill_data)
        assert response.status_code == 201

        response = await client.post("/api/bills", json=bill_data)
        assert response.status_code == 409  # Conflict
```

### Database Performance Flow
```python
class TestDatabasePerformanceFlow(IntegrationTestBase):
    """Verify database performance optimizations"""

    async def test_index_utilization_flow(
        self,
        client: TestClient,
        setup_db: AsyncSession
    ):
        """Verify index usage across operations"""
        # Create test data
        await setup_db.execute(
            text("""
                INSERT INTO bills (bill_id, congress_id, bill_type, bill_number, title)
                SELECT
                    'HR' || i || '-117',
                    117,
                    'hr',
                    i,
                    'Test Bill ' || i
                FROM generate_series(1, 1000) i
            """)
        )
        await setup_db.commit()

        # Test congress_type index
        response = await client.get(
            "/api/bills/congress/117",
            params={"bill_type": "hr"}
        )
        assert response.status_code == 200

        # Verify index usage
        index_stats = await setup_db.execute(
            text("""
                SELECT idx_scan, idx_tup_read
                FROM pg_stat_user_indexes
                WHERE indexrelname = 'idx_bills_congress_type'
            """)
        )
        stats = index_stats.first()
        assert stats["idx_scan"] > 0

    async def test_text_search_flow(
        self,
        client: TestClient,
        setup_db: AsyncSession
    ):
        """Verify text search performance"""
        # Test trigram search
        response = await client.get(
            "/api/bills/search",
            params={"q": "Test Bill"}
        )
        assert response.status_code == 200

        # Verify gin index usage
        search_stats = await setup_db.execute(
            text("""
                SELECT idx_scan, idx_tup_read
                FROM pg_stat_user_indexes
                WHERE indexrelname = 'idx_bills_title_trgm'
            """)
        )
        stats = search_stats.first()
        assert stats["idx_scan"] > 0

    async def test_connection_pool_flow(
        self,
        client: TestClient,
        setup_db: AsyncSession
    ):
        """Verify connection pool behavior"""
        # Test concurrent requests
        async def make_request():
            return await client.get("/api/bills/HR1234-117")

        responses = await asyncio.gather(*[
            make_request() for _ in range(25)
        ])
        assert all(r.status_code in [200, 404] for r in responses)

        # Verify pool stats
        pool_stats = app.state.pool.get_stats()
        assert pool_stats["size"] <= 20  # Max pool size
        assert pool_stats["available"] >= 0  # No negative available connections
```

### Error Handling Flow
```python
class TestErrorHandlingFlow(IntegrationTestBase):
    """Verify error handling across system boundaries"""

    async def test_error_propagation_flow(
        self,
        client: TestClient,
        setup_db: AsyncSession
    ):
        """Verify error handling chain"""
        # Test database error propagation
        with LogCapture() as logs:
            response = await client.post(
                "/api/bills",
                json={"invalid": "data"}
            )

        assert response.status_code == 422
        error_response = APIError(**response.json())
        assert error_response.trace_id is not None

        # Verify error was logged
        error_log = logs.records[-1]
        assert error_log.levelno == 40  # ERROR
        assert error_log.trace_id == error_response.trace_id

    async def test_rate_limit_flow(
        self,
        client: TestClient,
        setup_db: AsyncSession
    ):
        """Verify rate limit handling"""
        # Simulate rate limit exceeded
        for _ in range(25):  # Exceed rate limit
            await client.get("/api/bills/TEST001")

        response = await client.get("/api/bills/TEST001")
        assert response.status_code == 429

        error_response = APIError(**response.json())
        assert error_response.retry_after is not None
        assert isinstance(error_response.retry_after, int)

class TestLoggingFlow(IntegrationTestBase):
    """Verify logging across system boundaries"""

    async def test_request_logging_flow(
        self,
        client: TestClient,
        setup_db: AsyncSession
    ):
        """Verify request logging chain"""
        with LogCapture() as logs:
            response = await client.get("/api/bills/TEST001")

        # Verify request log
        request_log = next(
            log for log in logs.records
            if log.msg == "request_started"
        )
        assert "trace_id" in request_log.__dict__
        assert "path" in request_log.__dict__
        assert "method" in request_log.__dict__

        # Verify response log
        response_log = next(
            log for log in logs.records
            if log.msg == "request_completed"
        )
        assert response_log.trace_id == request_log.trace_id
        assert "duration_ms" in response_log.__dict__
        assert "status_code" in response_log.__dict__

    async def test_error_logging_flow(
        self,
        client: TestClient,
        setup_db: AsyncSession
    ):
        """Verify error logging chain"""
        with LogCapture() as logs:
            response = await client.get("/api/bills/INVALID")

        error_log = logs.records[-1]
        assert error_log.levelno == 40  # ERROR
        assert "trace_id" in error_log.__dict__
        assert "error_type" in error_log.__dict__
        assert "bill_id" in error_log.__dict__
        assert error_log.bill_id == "INVALID"

class TestPerformanceMonitoring(IntegrationTestBase):
    """Verify performance monitoring across system"""

    THRESHOLDS = {
        "single_query": 10,    # ms
        "batch_query": 50,     # ms
        "search_query": 100,   # ms
        "relationship_load": 50 # ms
    }

    async def test_query_performance_monitoring(
        self,
        client: TestClient,
        setup_db: AsyncSession
    ):
        """Verify query performance monitoring"""
        with LogCapture() as logs:
            response = await client.get("/api/bills/TEST001")

        perf_log = next(
            log for log in logs.records
            if "duration_ms" in log.__dict__
        )
        assert perf_log.duration_ms < self.THRESHOLDS["single_query"]
        assert "query_type" in perf_log.__dict__
        assert "index_used" in perf_log.__dict__

    async def test_relationship_load_monitoring(
        self,
        client: TestClient,
        setup_db: AsyncSession
    ):
        """Verify relationship load monitoring"""
        with LogCapture() as logs:
            response = await client.get(
                "/api/bills/TEST001/full"
            )

        perf_log = next(
            log for log in logs.records
            if "relationship_load_ms" in log.__dict__
        )
        assert perf_log.relationship_load_ms < self.THRESHOLDS["relationship_load"]
        assert "relationships_loaded" in perf_log.__dict__
```
