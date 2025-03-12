# Amendments API

## Overview

The Amendments API provides access to bill amendments from both Congress.gov and GovInfo.gov. It combines real-time amendment status from Congress.gov with authenticated amendment text from GovInfo.gov.

## Models

### Core Models

```python
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlmodel import SQLModel, Field, Relationship
from pydantic import validator

class AmendmentBase(SQLModel):
    """Base model for amendment data"""
    amendment_number: str = Field(..., description="Amendment number")
    amendment_type: str = Field(
        ...,
        description="Type of amendment",
        sa_column_kwargs={"check": "amendment_type IN ('house', 'senate')"}
    )
    status: Optional[str] = Field(
        None,
        description="Current amendment status",
        sa_column_kwargs={"index": True}
    )
    introduced_date: Optional[datetime] = Field(None, description="Date amendment was introduced")

    @validator("amendment_type")
    def validate_amendment_type(cls, v):
        if v not in {"house", "senate"}:
            raise ValueError("Amendment type must be 'house' or 'senate'")
        return v

class Amendment(AmendmentBase, table=True):
    """Database model for amendments"""
    __tablename__ = "amendments"

    amendment_id: str = Field(
        primary_key=True,
        max_length=50,
        description="Unique amendment identifier"
    )
    congress_id: int = Field(
        foreign_key="congresses.congress_id",
        sa_column_kwargs={"index": True}
    )
    bill_id: str = Field(foreign_key="bills.bill_id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column_kwargs={"onupdate": datetime.utcnow}
    )

    # Relationships with lazy loading
    actions: List["AmendmentAction"] = Relationship(
        back_populates="amendment",
        sa_relationship_kwargs={"lazy": "selectin"}
    )
    reports: List["AmendmentReport"] = Relationship(
        back_populates="amendment",
        sa_relationship_kwargs={"lazy": "selectin"}
    )

    class Config:
        orm_mode = True

class AmendmentAction(SQLModel, table=True):
    """Database model for amendment actions"""
    __tablename__ = "amendment_actions"

    action_id: int = Field(default=None, primary_key=True)
    amendment_id: str = Field(foreign_key="amendments.amendment_id")
    action_date: datetime = Field(...)
    action_text: str = Field(...)
    action_type: str = Field(
        ...,
        sa_column_kwargs={"check": "action_type IN ('REFERRAL', 'REPORT', 'DISCHARGE', 'OTHER')"}
    )
    committee_id: Optional[str] = Field(foreign_key="committees.committee_id")
    chamber: Optional[str] = Field(
        None,
        sa_column_kwargs={"check": "chamber IN ('house', 'senate', 'both')"}
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    amendment: Amendment = Relationship(back_populates="actions")

class AmendmentReport(SQLModel, table=True):
    """Database model for amendment committee reports"""
    __tablename__ = "amendment_committee_reports"

    report_id: str = Field(primary_key=True)
    amendment_id: str = Field(foreign_key="amendments.amendment_id")
    committee_id: str = Field(foreign_key="committees.committee_id")
    report_type: str = Field(...)
    publish_date: datetime
    govinfo_package_id: Optional[str] = Field(unique=True)
    digital_signature: Optional[str]
    signature_verified: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    amendment: Amendment = Relationship(back_populates="reports")

# API Request/Response Models
class AmendmentCreate(AmendmentBase):
    """Model for amendment creation requests"""
    congress_id: int
    bill_id: str

    class Config:
       json_schema_extra = {
            "example": {
                "amendment_number": "123",
                "amendment_type": "house",
                "congress_id": 117,
                "bill_id": "HR1234-117"
            }
        }

class AmendmentUpdate(SQLModel):
    """Model for amendment update requests"""
    status: Optional[str]
    introduced_date: Optional[datetime]

    class Config:
       json_schema_extra = {
            "example": {
                "status": "REPORTED",
                "introduced_date": "2023-03-01T00:00:00Z"
            }
        }

class AmendmentResponse(AmendmentBase):
    """Model for amendment API responses"""
    amendment_id: str
    congress_id: int
    bill_id: str
    actions: Optional[List[Dict[str, Any]]] = None
    reports: Optional[List[Dict[str, Any]]] = None
    glossary_terms: Optional[Dict[str, str]] = Field(
        None,
        description="Relevant glossary terms found in amendment text"
    )

    class Config:
        orm_mode = True
       json_schema_extra = {
            "example": {
                "amendment_id": "HAMDT123",
                "congress_id": 117,
                "bill_id": "HR1234-117",
                "amendment_number": "123",
                "amendment_type": "house",
                "status": "REPORTED"
            }
        }

## Service Layer

```python
from fastapi import Depends
from sqlmodel import select
from typing import Optional, List
from .logging import LogContext
from .rate_limiting import rate_limit_handler
import time

class AmendmentError(APIError):
    """Base class for amendment errors"""
    entity_type: str = "amendment"

class AmendmentNotFoundError(AmendmentError):
    """Raised when amendment cannot be found"""
    status_code: int = 404
    detail: str = "Amendment not found"

class AmendmentService:
    """Service layer for amendment operations"""

    def __init__(self, session: AsyncSession = Depends(get_session)):
        self.session = session

    async def get_amendment(
        self,
        amendment_id: str,
        congress_id: int
    ) -> Amendment:
        """Get amendment by ID and congress"""
        with LogContext(operation="get_amendment") as log:
            start = time.perf_counter()
            try:
                query = select(Amendment).where(
                    Amendment.amendment_id == amendment_id,
                    Amendment.congress_id == congress_id
                ).options(
                    selectinload(Amendment.actions),
                    selectinload(Amendment.reports)
                )
                result = await self.session.execute(query)
                amendment = result.scalar_one_or_none()

                if not amendment:
                    raise AmendmentNotFoundError(f"Amendment {amendment_id} not found")

                duration_ms = (time.perf_counter() - start) * 1000
                log.info("amendment_retrieved",
                    duration_ms=duration_ms,
                    amendment_id=amendment_id
                )
                return amendment
            except Exception as e:
                log.error("amendment_retrieval_failed",
                    error=str(e),
                    amendment_id=amendment_id
                )
                raise

    @rate_limit_handler("congress")
    async def get_amendment_status(
        self,
        congress: int,
        amendment_id: str
    ) -> Dict[str, Any]:
        """Get amendment status from Congress.gov with rate limit handling"""
        return await self.congress_api.get_amendment(congress, amendment_id)

    async def create_amendment(
        self,
        amendment: AmendmentCreate
    ) -> Amendment:
        """Create new amendment"""
        with LogContext(operation="create_amendment") as log:
            start = time.perf_counter()
            try:
                db_amendment = Amendment.from_orm(amendment)
                self.session.add(db_amendment)
                await self.session.commit()
                await self.session.refresh(db_amendment)

                duration_ms = (time.perf_counter() - start) * 1000
                log.info("amendment_created",
                    duration_ms=duration_ms,
                    amendment_id=db_amendment.amendment_id
                )
                return db_amendment
            except Exception as e:
                log.error("amendment_creation_failed",
                    error=str(e),
                    amendment_data=amendment.dict()
                )
                raise

    async def update_amendment(
        self,
        amendment_id: str,
        updates: AmendmentUpdate
    ) -> Amendment:
        """Update existing amendment"""
        with LogContext(operation="update_amendment") as log:
            start = time.perf_counter()
            try:
                amendment = await self.get_amendment(amendment_id)
                update_data = updates.dict(exclude_unset=True)
                for key, value in update_data.items():
                    setattr(amendment, key, value)
                await self.session.commit()
                await self.session.refresh(amendment)

                duration_ms = (time.perf_counter() - start) * 1000
                log.info("amendment_updated",
                    duration_ms=duration_ms,
                    amendment_id=amendment_id
                )
                return amendment
            except Exception as e:
                log.error("amendment_update_failed",
                    error=str(e),
                    amendment_id=amendment_id,
                    updates=updates.dict()
                )
                raise
```

## FastAPI Endpoints

```python
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from typing import List, Optional

router = APIRouter(prefix="/amendments", tags=["Amendments"])

@router.get(
    "/{amendment_id}",
    response_model=AmendmentResponse,
    responses={
        404: {"description": "Amendment not found"},
        429: {"description": "Rate limit exceeded"}
    }
)
async def get_amendment(
    amendment_id: str = Path(..., description="Amendment identifier (e.g., 'HAMDT123')"),
    congress: int = Query(..., gt=0, description="Congress number"),
    service: AmendmentService = Depends()
) -> AmendmentResponse:
    """
    Retrieve amendment information combining Congress.gov status and GovInfo.gov content.

    Rate limits:
    - Congress.gov: 5,000 requests/hour
    - GovInfo.gov: 1,000 requests/hour (bulk downloads exempt)
    """
    return await service.get_amendment(amendment_id, congress)

@router.post(
    "/",
    response_model=AmendmentResponse,
    status_code=201,
    responses={
        409: {"description": "Amendment already exists"},
        422: {"description": "Validation error"}
    }
)
async def create_amendment(
    amendment: AmendmentCreate,
    service: AmendmentService = Depends()
) -> AmendmentResponse:
    """Create a new amendment record"""
    try:
        return await service.create_amendment(amendment)
    except IntegrityError:
        raise HTTPException(
            status_code=409,
            detail=f"Amendment {amendment.amendment_id} already exists"
        )

@router.patch(
    "/{amendment_id}",
    response_model=AmendmentResponse,
    responses={
        404: {"description": "Amendment not found"},
        422: {"description": "Validation error"}
    }
)
async def update_amendment(
    amendment_id: str,
    updates: AmendmentUpdate,
    service: AmendmentService = Depends()
) -> AmendmentResponse:
    """Update an existing amendment"""
    return await service.update_amendment(amendment_id, updates)

@router.get(
    "/bill/{bill_id}",
    response_model=List[AmendmentResponse],
    responses={
        429: {"description": "Rate limit exceeded"}
    }
)
async def list_bill_amendments(
    bill_id: str = Path(..., description="Bill identifier"),
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0),
    service: AmendmentService = Depends()
) -> List[AmendmentResponse]:
    """List amendments for a specific bill"""
    return await service.list_bill_amendments(
        bill_id=bill_id,
        limit=limit,
        offset=offset
    )
```

## Performance Monitoring

```python
PERFORMANCE_THRESHOLDS = {
    "single_query": 10,    # ms
    "batch_query": 50,     # ms
    "search_query": 100,   # ms
    "relationship_load": 50 # ms
}

class AmendmentMetrics:
    """Performance monitoring for amendment operations"""

    @staticmethod
    async def record_query_time(
        operation: str,
        duration_ms: float,
        log: LogContext
    ):
        """Record query execution time"""
        threshold = PERFORMANCE_THRESHOLDS.get(operation, 100)
        if duration_ms > threshold:
            log.warning("slow_query_execution",
                operation=operation,
                duration_ms=duration_ms,
                threshold_ms=threshold
            )

        await record_metric(
            name="amendment_query_duration_ms",
            value=duration_ms,
            tags={"operation": operation}
        )
```

## Testing

```python
from .test_utils import IntegrationTestBase, LogCapture

class TestAmendmentEndpoints(IntegrationTestBase):
    """Integration tests for amendment endpoints"""

    async def test_amendment_lifecycle(
        self,
        client: TestClient,
        setup_db: AsyncSession
    ):
        """Test complete amendment lifecycle"""
        # Create amendment
        amendment_data = {
            "amendment_number": "123",
            "amendment_type": "house",
            "congress_id": 117,
            "bill_id": "HR1234-117"
        }
        with LogCapture() as logs:
            response = await client.post("/api/amendments", json=amendment_data)

        assert response.status_code == 201
        amendment_id = response.json()["data"]["amendment_id"]

        # Verify creation was logged
        creation_log = next(
            log for log in logs.records
            if log.msg == "amendment_created"
        )
        assert creation_log.duration_ms < PERFORMANCE_THRESHOLDS["single_query"]

        # Update amendment
        update_data = {
            "status": "REPORTED"
        }
        response = await client.patch(
            f"/api/amendments/{amendment_id}",
            json=update_data
        )
        assert response.status_code == 200

        # Verify update
        response = await client.get(f"/api/amendments/{amendment_id}")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["status"] == "REPORTED"

    async def test_error_handling(
        self,
        client: TestClient,
        setup_db: AsyncSession
    ):
        """Test error handling scenarios"""
        # Test not found
        response = await client.get("/api/amendments/INVALID")
        assert response.status_code == 404
        error = APIError(**response.json())
        assert error.error == "AmendmentNotFoundError"

        # Test validation error
        response = await client.post(
            "/api/amendments",
            json={"invalid": "data"}
        )
        assert response.status_code == 422

        # Test rate limit
        for _ in range(25):  # Exceed rate limit
            await client.get("/api/amendments/TEST001")

        response = await client.get("/api/amendments/TEST001")
        assert response.status_code == 429
        error = APIError(**response.json())
        assert error.retry_after is not None
```

## Glossary Integration

The amendments API supports optional glossary term integration. Add `include_definitions=true` to include relevant legislative terms and their definitions in the response.

### Response Enhancement

```python
class AmendmentResponse(BaseModel):
    # ... existing fields ...

    glossary_terms: Optional[Dict[str, str]] = Field(
        None,
        description="Relevant glossary terms found in amendment text"
    )
```

### Usage Example

```python
# Get amendment information with glossary terms
amendment = await client.get_amendment(
    "HAMDT123",
    congress=117,
    include_definitions=True
)

# Access glossary terms
if amendment.glossary_terms:
    for term, definition in amendment.glossary_terms.items():
        print(f"Term: {term}")
        print(f"Definition: {definition}")
        print("---")
```

The glossary integration focuses on terms found in:
- Amendment purpose
- Amendment text
- Amendment type
- Amendment status
- Related bill information
