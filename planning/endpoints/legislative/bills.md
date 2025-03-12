# Bills API

## Overview

The Bills API provides unified access to bill information from both Congress.gov and GovInfo.gov. It combines real-time status updates from Congress.gov with authenticated document content from GovInfo.gov.

## Models

### Core Models

```python
from datetime import date, datetime
from typing import Optional, List, Dict, Any
from sqlmodel import SQLModel, Field, Relationship
from pydantic import validator, constr, conint
from .base import BaseModel
from .errors import BillError
from .logging import LogContext
from .metrics import record_metric

# Base Models
class BillBase(BaseModel):
    """Base model for bill data"""
    bill_type: constr(regex="^(hr|s|hjres|sjres|hconres|sconres|hres|sres)$") = Field(
        ...,
        description="Type of bill",
        example="hr"
    )
    bill_number: conint(gt=0) = Field(
        ...,
        description="Bill number",
        example=1234
    )
    title: constr(min_length=1, max_length=2000) = Field(
        ...,
        description="Official bill title"
    )
    introduced_date: Optional[date] = Field(
        None,
        description="Date bill was introduced"
    )
    status: Optional[str] = Field(
        None,
        description="Current bill status",
        sa_column_kwargs={"index": True}
    )
    last_action_date: Optional[date] = Field(
        None,
        description="Date of last action",
        sa_column_kwargs={"index": True}
    )
    source_system: str = Field(
        ...,
        description="Origin system (congress/govinfo)",
        sa_column_kwargs={"check": "source_system IN ('congress', 'govinfo')"}
    )

    @validator("bill_type")
    def validate_bill_type(cls, v):
        valid_types = {"hr", "s", "hjres", "sjres", "hconres", "sconres", "hres", "sres"}
        if v not in valid_types:
            raise BillError(f"Invalid bill type. Must be one of: {', '.join(valid_types)}")
        return v

    @validator("source_system")
    def validate_source_system(cls, v):
        if v not in {"congress", "govinfo"}:
            raise BillError("Source system must be either 'congress' or 'govinfo'")
        return v

# Database Models
class Bill(BillBase, table=True):
    """Database model for bills"""
    __tablename__ = "bills"

    bill_id: str = Field(
        primary_key=True,
        max_length=50,
        description="Unique bill identifier"
    )
    congress_id: int = Field(
        foreign_key="congresses.congress_id",
        sa_column_kwargs={"index": True},
        description="Congress number"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Record creation timestamp"
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column_kwargs={"onupdate": datetime.utcnow},
        description="Last update timestamp"
    )

    # Relationships with lazy="selectin" for efficient loading
    versions: List["BillVersion"] = Relationship(
        back_populates="bill",
        sa_relationship_kwargs={"lazy": "selectin"}
    )
    sponsors: List["BillSponsor"] = Relationship(
        back_populates="bill",
        sa_relationship_kwargs={"lazy": "selectin"}
    )
    amendments: List["Amendment"] = Relationship(
        back_populates="bill",
        sa_relationship_kwargs={"lazy": "selectin"}
    )

    # Partition configuration for better performance
    __table_args__ = {
        "postgresql_partition_by": "RANGE (congress_id)",
        "info": {"partition_key": "congress_id"}
    }

    class Config:
        orm_mode = True

# Error Classes
class BillError(Exception):
    """Base class for bill errors"""
    entity_type: str = "bill"

class BillNotFoundError(BillError):
    """Raised when bill cannot be found"""
    status_code: int = 404
    detail: str = "Bill not found"

class BillValidationError(BillError):
    """Raised for bill data validation errors"""
    status_code: int = 422

class BillRateLimitError(BillError):
    """Raised when API rate limits are exceeded"""
    status_code: int = 429
    retry_after: int = 3600  # 1 hour default

# API Request/Response Models
class BillCreate(BillBase):
    """Model for bill creation requests"""
    congress_id: conint(gt=0)

    class Config:
       json_schema_extra = {
            "example": {
                "bill_type": "hr",
                "bill_number": 1234,
                "congress_id": 117,
                "title": "Example Bill Title",
                "source_system": "congress"
            }
        }

class BillUpdate(SQLModel):
    """Model for bill update requests"""
    title: Optional[str] = None
    status: Optional[str] = None
    last_action_date: Optional[date] = None

    class Config:
       json_schema_extra = {
            "example": {
                "status": "INTRODUCED",
                "last_action_date": "2023-03-01"
            }
        }

class BillResponse(BillBase):
    """Model for bill API responses"""
    bill_id: str
    congress_id: int
    versions: Optional[List["BillVersionResponse"]] = None
    sponsors: Optional[List["BillSponsorResponse"]] = None
    amendments: Optional[List["AmendmentResponse"]] = None
    authentication_status: Optional[str] = None

    class Config:
        orm_mode = True
       json_schema_extra = {
            "example": {
                "bill_id": "HR1234-117",
                "congress_id": 117,
                "bill_type": "hr",
                "bill_number": 1234,
                "title": "Example Bill",
                "status": "INTRODUCED",
                "authentication_status": "verified",
                "versions": [
                    {
                        "version_code": "ih",
                        "title": "Introduced in House",
                        "url": "https://www.govinfo.gov/content/pkg/BILLS-117hr1234ih/pdf/BILLS-117hr1234ih.pdf"
                    }
                ]
            }
        }

## Service Layer

```python
from fastapi import Depends, HTTPException
from sqlmodel import select
from typing import Optional, List
from .logging import LogContext
from .rate_limiting import rate_limit_handler
from .metrics import record_metric
import time

class BillService:
    """Service layer for bill operations"""

    def __init__(self, session: AsyncSession = Depends(get_session)):
        self.session = session
        self._setup_metrics()

    def _setup_metrics(self):
        """Initialize performance monitoring thresholds"""
        self.PERFORMANCE_THRESHOLDS = {
            "get_bill": 50,        # ms
            "list_bills": 100,     # ms
            "get_versions": 75,    # ms
            "get_sponsors": 50,    # ms
            "get_amendments": 75,  # ms
            "relationship_load": 50 # ms
        }

    async def get_bill(
        self,
        bill_id: str,
        congress_id: int
    ) -> Bill:
        """Get bill by ID and congress"""
        with LogContext(operation="get_bill") as log:
            start = time.perf_counter()
            try:
                query = select(Bill).where(
                    Bill.bill_id == bill_id,
                    Bill.congress_id == congress_id
                ).options(
                    selectinload(Bill.versions),
                    selectinload(Bill.sponsors),
                    selectinload(Bill.amendments)
                )

                result = await self.session.execute(query)
                bill = result.scalar_one_or_none()

                if not bill:
                    raise BillNotFoundError(f"Bill {bill_id} not found")

                duration_ms = (time.perf_counter() - start) * 1000
                await self._record_performance(
                    "get_bill",
                    duration_ms,
                    log
                )
                return bill

            except Exception as e:
                log.error("bill_retrieval_failed",
                    error=str(e),
                    bill_id=bill_id,
                    congress_id=congress_id
                )
                raise

    @rate_limit_handler("congress")
    async def get_bill_status(
        self,
        bill_id: str,
        congress_id: int
    ) -> Dict[str, Any]:
        """Get bill status from Congress.gov with rate limit handling"""
        with LogContext(operation="get_bill_status") as log:
            start = time.perf_counter()
            try:
                status = await self.congress_api.get_bill_status(
                    bill_id,
                    congress_id
                )
                duration_ms = (time.perf_counter() - start) * 1000
                await self._record_performance(
                    "get_bill_status",
                    duration_ms,
                    log
                )
                return status
            except Exception as e:
                log.error("bill_status_retrieval_failed",
                    error=str(e),
                    bill_id=bill_id,
                    congress_id=congress_id
                )
                raise

    async def create_bill(self, bill: BillCreate) -> Bill:
        """Create new bill"""
        with LogContext(operation="create_bill") as log:
            start = time.perf_counter()
            try:
                db_bill = Bill.from_orm(bill)
                self.session.add(db_bill)
                await self.session.commit()
                await self.session.refresh(db_bill)

                duration_ms = (time.perf_counter() - start) * 1000
                await self._record_performance(
                    "create_bill",
                    duration_ms,
                    log
                )
                return db_bill

            except Exception as e:
                log.error("bill_creation_failed",
                    error=str(e),
                    bill_data=bill.dict()
                )
                raise

    async def update_bill(
        self,
        bill_id: str,
        updates: BillUpdate
    ) -> Bill:
        """Update existing bill"""
        with LogContext(operation="update_bill") as log:
            start = time.perf_counter()
            try:
                bill = await self.get_bill(bill_id)
                update_data = updates.dict(exclude_unset=True)
                for key, value in update_data.items():
                    setattr(bill, key, value)
                await self.session.commit()
                await self.session.refresh(bill)

                duration_ms = (time.perf_counter() - start) * 1000
                await self._record_performance(
                    "update_bill",
                    duration_ms,
                    log
                )
                return bill

            except Exception as e:
                log.error("bill_update_failed",
                    error=str(e),
                    bill_id=bill_id,
                    updates=updates.dict()
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
            name="bill_operation_duration_ms",
            value=duration_ms,
            tags={"operation": operation}
        )
```

## FastAPI Endpoints

```python
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from typing import List, Optional

router = APIRouter(prefix="/bills", tags=["Bills"])

@router.get(
    "/{bill_id}",
    response_model=BillResponse,
    responses={
        404: {"description": "Bill not found"},
        429: {"description": "Rate limit exceeded"}
    }
)
async def get_bill(
    bill_id: str = Path(
        ...,
        description="Bill identifier (e.g., 'HR1234')"
    ),
    congress: int = Query(
        ...,
        gt=0,
        description="Congress number"
    ),
    service: BillService = Depends()
) -> BillResponse:
    """
    Retrieve bill information combining Congress.gov status and GovInfo.gov content.

    Rate limits:
    - Congress.gov: 5,000 requests/hour
    - GovInfo.gov: 1,000 requests/hour
    """
    return await service.get_bill(bill_id, congress)

@router.get(
    "/congress/{congress_id}",
    response_model=List[BillResponse],
    responses={
        429: {"description": "Rate limit exceeded"}
    }
)
async def list_bills(
    congress_id: int = Path(
        ...,
        gt=0,
        description="Congress number"
    ),
    bill_type: Optional[str] = Query(
        None,
        description="Filter by bill type"
    ),
    status: Optional[str] = Query(
        None,
        description="Filter by status"
    ),
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0),
    service: BillService = Depends()
) -> List[BillResponse]:
    """List bills for a specific congress with optional filters"""
    return await service.list_bills(
        congress_id=congress_id,
        bill_type=bill_type,
        status=status,
        limit=limit,
        offset=offset
    )

@router.post(
    "/",
    response_model=BillResponse,
    status_code=201,
    responses={
        409: {"description": "Bill already exists"},
        422: {"description": "Validation error"}
    }
)
async def create_bill(
    bill: BillCreate,
    service: BillService = Depends()
) -> BillResponse:
    """Create a new bill record"""
    try:
        return await service.create_bill(bill)
    except IntegrityError:
        raise HTTPException(
            status_code=409,
            detail=f"Bill {bill.bill_id} already exists"
        )

@router.patch(
    "/{bill_id}",
    response_model=BillResponse,
    responses={
        404: {"description": "Bill not found"},
        422: {"description": "Validation error"}
    }
)
async def update_bill(
    bill_id: str,
    updates: BillUpdate,
    service: BillService = Depends()
) -> BillResponse:
    """Update an existing bill"""
    return await service.update_bill(bill_id, updates)
```

## Testing

```python
from .test_utils import IntegrationTestBase, LogCapture
from .errors import BillError, BillNotFoundError

class TestBillEndpoints(IntegrationTestBase):
    """Integration tests for bill endpoints"""

    async def test_bill_lifecycle(
        self,
        client: TestClient,
        setup_db: AsyncSession
    ):
        """Test complete bill lifecycle"""
        # Create bill
        bill_data = {
            "bill_type": "hr",
            "bill_number": 1234,
            "congress_id": 117,
            "title": "Test Bill",
            "source_system": "congress"
        }
        with LogCapture() as logs:
            response = await client.post(
                "/api/bills",
                json=bill_data
            )

        assert response.status_code == 201
        bill_id = response.json()["data"]["bill_id"]

        # Verify creation was logged
        creation_log = next(
            log for log in logs.records
            if log.msg == "bill_created"
        )
        assert creation_log.duration_ms < self.PERFORMANCE_THRESHOLDS["get_bill"]

        # Update bill
        update_data = {
            "status": "INTRODUCED",
            "last_action_date": "2023-03-01"
        }
        response = await client.patch(
            f"/api/bills/{bill_id}",
            json=update_data
        )
        assert response.status_code == 200

        # Verify update
        response = await client.get(
            f"/api/bills/{bill_id}",
            params={"congress": 117}
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["status"] == update_data["status"]
        assert data["last_action_date"] == update_data["last_action_date"]

    async def test_error_handling(
        self,
        client: TestClient,
        setup_db: AsyncSession
    ):
        """Test error handling scenarios"""
        # Test not found
        response = await client.get(
            "/api/bills/INVALID",
            params={"congress": 117}
        )
        assert response.status_code == 404
        error = BillError(**response.json())
        assert error.error == "BillNotFoundError"

        # Test validation error
        response = await client.post(
            "/api/bills",
            json={"invalid": "data"}
        )
        assert response.status_code == 422

        # Test rate limit
        for _ in range(25):  # Exceed rate limit
            await client.get(
                "/api/bills/HR1234",
                params={"congress": 117}
            )

        response = await client.get(
            "/api/bills/HR1234",
            params={"congress": 117}
        )
        assert response.status_code == 429
        error = BillError(**response.json())
        assert error.retry_after is not None

    async def test_performance_monitoring(
        self,
        client: TestClient,
        setup_db: AsyncSession
    ):
        """Test performance monitoring"""
        with LogCapture() as logs:
            # Create multiple bills to trigger performance warning
            for i in range(10):
                await client.post(
                    "/api/bills",
                    json={
                        "bill_type": "hr",
                        "bill_number": i + 1,
                        "congress_id": 117,
                        "title": f"Test Bill {i}",
                        "source_system": "congress"
                    }
                )

        # Check for slow operation warnings
        slow_ops = [
            log for log in logs.records
            if log.msg == "slow_operation"
        ]
        assert len(slow_ops) > 0

    async def test_bill_relationships(
        self,
        client: TestClient,
        setup_db: AsyncSession
    ):
        """Test bill relationship loading"""
        # Create bill with relationships
        bill_data = {
            "bill_type": "hr",
            "bill_number": 1234,
            "congress_id": 117,
            "title": "Test Bill",
            "source_system": "congress"
        }
        response = await client.post(
            "/api/bills",
            json=bill_data
        )
        bill_id = response.json()["data"]["bill_id"]

        # Add version
        version_data = {
            "bill_id": bill_id,
            "version_code": "ih",
            "title": "Introduced in House"
        }
        await client.post(
            f"/api/bills/{bill_id}/versions",
            json=version_data
        )

        # Add sponsor
        sponsor_data = {
            "bill_id": bill_id,
            "member_id": "S000148",
            "sponsor_type": "primary"
        }
        await client.post(
            f"/api/bills/{bill_id}/sponsors",
            json=sponsor_data
        )

        # Verify relationships are loaded
        response = await client.get(
            f"/api/bills/{bill_id}",
            params={"congress": 117}
        )
        data = response.json()["data"]
        assert len(data["versions"]) == 1
        assert len(data["sponsors"]) == 1
        assert data["versions"][0]["version_code"] == "ih"
        assert data["sponsors"][0]["member_id"] == "S000148"
```
