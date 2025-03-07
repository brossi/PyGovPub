# Committees API

## Overview

The Committees API provides access to congressional committee information from Congress.gov, including committee membership, activities, hearings, and reports. This endpoint enables tracking of committee work and its impact on legislation.

## Models

### Core Models

```python
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from sqlmodel import SQLModel, Field, Relationship
from pydantic import validator, constr
from .base import BaseModel
from .errors import CommitteeError

class CommitteeBase(BaseModel):
    """Base model for committee data"""
    name: constr(min_length=1, max_length=255)
    chamber: Optional[str] = Field(
        None,
        description="Chamber the committee belongs to",
        sa_column_kwargs={"check": "chamber IN ('house', 'senate', 'joint')"}
    )
    type: Optional[str] = Field(
        None,
        description="Committee type",
        sa_column_kwargs={"check": "type IN ('standing', 'select', 'joint', 'subcommittee')"}
    )
    url: Optional[str] = Field(None, description="Official committee URL")

    @validator("chamber")
    def validate_chamber(cls, v):
        if v and v not in {"house", "senate", "joint"}:
            raise CommitteeError("Invalid chamber value")
        return v

    @validator("type")
    def validate_type(cls, v):
        if v and v not in {"standing", "select", "joint", "subcommittee"}:
            raise CommitteeError("Invalid committee type")
        return v

class Committee(CommitteeBase, table=True):
    """Database model for committees"""
    __tablename__ = "committees"

    committee_id: str = Field(
        primary_key=True,
        max_length=50,
        description="Unique committee identifier"
    )
    parent_committee_id: Optional[str] = Field(
        default=None,
        foreign_key="committees.committee_id",
        description="Parent committee ID for subcommittees"
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column_kwargs={"onupdate": datetime.utcnow}
    )

    # Relationships with lazy loading
    activities: List["CommitteeActivity"] = Relationship(
        back_populates="committee",
        sa_relationship_kwargs={"lazy": "selectin"}
    )
    reports: List["CommitteeReport"] = Relationship(
        back_populates="committee",
        sa_relationship_kwargs={"lazy": "selectin"}
    )
    parent: Optional["Committee"] = Relationship(
        sa_relationship_kwargs={
            "foreign_keys": "Committee.parent_committee_id",
            "remote_side": "Committee.committee_id",
            "lazy": "selectin"
        }
    )
    subcommittees: List["Committee"] = Relationship(
        sa_relationship_kwargs={
            "foreign_keys": "Committee.parent_committee_id",
            "lazy": "selectin"
        }
    )

    class Config:
        orm_mode = True

class CommitteeActivityBase(BaseModel):
    """Base model for committee activities"""
    activity_type: str = Field(
        ...,
        description="Type of committee activity",
        sa_column_kwargs={"check": "activity_type IN ('hearing', 'markup', 'meeting', 'report')"}
    )
    title: constr(min_length=1, max_length=500)
    date: Optional[date] = None
    status: Optional[str] = None

    @validator("activity_type")
    def validate_activity_type(cls, v):
        if v not in {"hearing", "markup", "meeting", "report"}:
            raise CommitteeError("Invalid activity type")
        return v

class CommitteeActivity(CommitteeActivityBase, table=True):
    """Database model for committee activities"""
    __tablename__ = "committee_activities"

    activity_id: int = Field(default=None, primary_key=True)
    committee_id: str = Field(
        foreign_key="committees.committee_id",
        description="Associated committee ID"
    )
    congress_id: int = Field(
        foreign_key="congresses.congress_id",
        description="Congress number"
    )
    related_bill_id: Optional[str] = Field(
        default=None,
        foreign_key="bills.bill_id",
        description="Related bill ID if applicable"
    )
    govinfo_package_id: Optional[str] = Field(
        default=None,
        description="GovInfo package ID for activity content"
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    committee: Committee = Relationship(back_populates="activities")

# Error Classes
class CommitteeError(Exception):
    """Base class for committee errors"""
    entity_type: str = "committee"

class CommitteeNotFoundError(CommitteeError):
    """Raised when committee cannot be found"""
    status_code: int = 404
    detail: str = "Committee not found"

class CommitteeValidationError(CommitteeError):
    """Raised for committee data validation errors"""
    status_code: int = 422

class CommitteeRateLimitError(CommitteeError):
    """Raised when API rate limits are exceeded"""
    status_code: int = 429
    retry_after: int = 3600  # 1 hour default

# API Request/Response Models
class CommitteeCreate(CommitteeBase):
    """Model for committee creation requests"""
    committee_id: str
    parent_committee_id: Optional[str] = None

    class Config:
        schema_extra = {
            "example": {
                "committee_id": "HSAG",
                "name": "House Committee on Agriculture",
                "chamber": "house",
                "type": "standing"
            }
        }

class CommitteeUpdate(SQLModel):
    """Model for committee update requests"""
    name: Optional[str] = None
    url: Optional[str] = None

    class Config:
        schema_extra = {
            "example": {
                "name": "Updated Committee Name",
                "url": "https://agriculture.house.gov"
            }
        }

class CommitteeResponse(CommitteeBase):
    """Model for committee API responses"""
    committee_id: str
    activities: Optional[List[Dict[str, Any]]] = None
    reports: Optional[List[Dict[str, Any]]] = None
    parent_committee_id: Optional[str] = None
    glossary_terms: Optional[Dict[str, str]] = Field(
        None,
        description="Relevant glossary terms and definitions found in committee information"
    )

    class Config:
        orm_mode = True
        schema_extra = {
            "example": {
                "committee_id": "HSAG",
                "name": "House Committee on Agriculture",
                "chamber": "house",
                "type": "standing",
                "activities": [
                    {
                        "activity_id": 1,
                        "activity_type": "hearing",
                        "title": "Farm Bill Oversight",
                        "date": "2023-06-15"
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

class CommitteeService:
    """Service layer for committee operations"""

    def __init__(self, session: AsyncSession = Depends(get_session)):
        self.session = session
        self._setup_metrics()

    def _setup_metrics(self):
        """Initialize performance monitoring thresholds"""
        self.PERFORMANCE_THRESHOLDS = {
            "get_committee": 50,      # ms
            "list_committees": 100,   # ms
            "get_activities": 75,     # ms
            "get_reports": 75,        # ms
            "relationship_load": 50   # ms
        }

    async def get_committee(
        self,
        committee_id: str,
        congress: Optional[int] = None,
        include_definitions: bool = False
    ) -> Committee:
        """Get committee by ID with optional congress-specific data"""
        with LogContext(operation="get_committee") as log:
            start = time.perf_counter()
            try:
                query = select(Committee).where(
                    Committee.committee_id == committee_id
                ).options(
                    selectinload(Committee.activities),
                    selectinload(Committee.reports)
                )

                if congress:
                    query = query.join(CommitteeActivity).filter(
                        CommitteeActivity.congress_id == congress
                    )

                result = await self.session.execute(query)
                committee = result.scalar_one_or_none()

                if not committee:
                    raise CommitteeNotFoundError(
                        f"Committee {committee_id} not found"
                    )

                if include_definitions:
                    self._add_glossary_terms(committee)

                duration_ms = (time.perf_counter() - start) * 1000
                await self._record_performance(
                    "get_committee",
                    duration_ms,
                    log
                )
                return committee

            except Exception as e:
                log.error("committee_retrieval_failed",
                    error=str(e),
                    committee_id=committee_id
                )
                raise

    @rate_limit_handler("congress")
    async def get_committee_activities(
        self,
        committee_id: str,
        congress: int
    ) -> List[Dict[str, Any]]:
        """Get committee activities with rate limit handling"""
        with LogContext(operation="get_activities") as log:
            start = time.perf_counter()
            try:
                activities = await self.congress_api.get_committee_activities(
                    committee_id,
                    congress
                )
                duration_ms = (time.perf_counter() - start) * 1000
                await self._record_performance(
                    "get_activities",
                    duration_ms,
                    log
                )
                return activities
            except Exception as e:
                log.error("activity_retrieval_failed",
                    error=str(e),
                    committee_id=committee_id,
                    congress=congress
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
            name="committee_operation_duration_ms",
            value=duration_ms,
            tags={"operation": operation}
        )

    def _add_glossary_terms(self, committee: Committee):
        """Add glossary terms to committee object"""
        # Implementation of _add_glossary_terms method
        pass

## FastAPI Endpoints

```python
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from typing import List, Optional

router = APIRouter(prefix="/committees", tags=["Committees"])

@router.get(
    "/{committee_id}",
    response_model=CommitteeResponse,
    responses={
        404: {"description": "Committee not found"},
        429: {"description": "Rate limit exceeded"}
    }
)
async def get_committee(
    committee_id: str = Path(
        ...,
        description="Committee identifier (e.g., 'HSAG')"
    ),
    congress: Optional[int] = Query(
        None,
        gt=0,
        description="Congress number for specific session data"
    ),
    include_definitions: bool = Query(
        False,
        description="Include glossary terms in response"
    ),
    service: CommitteeService = Depends()
) -> CommitteeResponse:
    """
    Retrieve committee information with optional congress-specific data.

    Rate limits:
    - Congress.gov: 5,000 requests/hour
    - GovInfo.gov: 1,000 requests/hour (bulk downloads exempt)
    """
    return await service.get_committee(committee_id, congress, include_definitions)

@router.get(
    "/",
    response_model=List[CommitteeResponse],
    responses={
        429: {"description": "Rate limit exceeded"}
    }
)
async def list_committees(
    chamber: Optional[str] = Query(
        None,
        description="Filter by chamber (house/senate/joint)"
    ),
    type: Optional[str] = Query(
        None,
        description="Filter by committee type"
    ),
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0),
    service: CommitteeService = Depends()
) -> List[CommitteeResponse]:
    """List committees with optional filters"""
    return await service.list_committees(
        chamber=chamber,
        type=type,
        limit=limit,
        offset=offset
    )

@router.post(
    "/",
    response_model=CommitteeResponse,
    status_code=201,
    responses={
        409: {"description": "Committee already exists"},
        422: {"description": "Validation error"}
    }
)
async def create_committee(
    committee: CommitteeCreate,
    service: CommitteeService = Depends()
) -> CommitteeResponse:
    """Create a new committee record"""
    return await service.create_committee(committee)

@router.patch(
    "/{committee_id}",
    response_model=CommitteeResponse,
    responses={
        404: {"description": "Committee not found"},
        422: {"description": "Validation error"}
    }
)
async def update_committee(
    committee_id: str,
    updates: CommitteeUpdate,
    service: CommitteeService = Depends()
) -> CommitteeResponse:
    """Update an existing committee"""
    return await service.update_committee(committee_id, updates)
```

## Testing

```python
from .test_utils import IntegrationTestBase, LogCapture
from .errors import CommitteeError, CommitteeNotFoundError

class TestCommitteeEndpoints(IntegrationTestBase):
    """Integration tests for committee endpoints"""

    async def test_committee_lifecycle(
        self,
        client: TestClient,
        setup_db: AsyncSession
    ):
        """Test complete committee lifecycle"""
        # Create committee
        committee_data = {
            "committee_id": "HSAG",
            "name": "House Committee on Agriculture",
            "chamber": "house",
            "type": "standing"
        }
        with LogCapture() as logs:
            response = await client.post(
                "/api/committees",
                json=committee_data
            )

        assert response.status_code == 201
        committee_id = response.json()["data"]["committee_id"]

        # Verify creation was logged
        creation_log = next(
            log for log in logs.records
            if log.msg == "committee_created"
        )
        assert creation_log.duration_ms < self.PERFORMANCE_THRESHOLDS["get_committee"]

        # Update committee
        update_data = {
            "url": "https://agriculture.house.gov"
        }
        response = await client.patch(
            f"/api/committees/{committee_id}",
            json=update_data
        )
        assert response.status_code == 200

        # Verify update
        response = await client.get(f"/api/committees/{committee_id}")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["url"] == update_data["url"]

    async def test_error_handling(
        self,
        client: TestClient,
        setup_db: AsyncSession
    ):
        """Test error handling scenarios"""
        # Test not found
        response = await client.get("/api/committees/INVALID")
        assert response.status_code == 404
        error = CommitteeError(**response.json())
        assert error.error == "CommitteeNotFoundError"

        # Test validation error
        response = await client.post(
            "/api/committees",
            json={"invalid": "data"}
        )
        assert response.status_code == 422

        # Test rate limit
        for _ in range(25):  # Exceed rate limit
            await client.get("/api/committees/HSAG")

        response = await client.get("/api/committees/HSAG")
        assert response.status_code == 429
        error = CommitteeError(**response.json())
        assert error.retry_after is not None

    async def test_performance_monitoring(
        self,
        client: TestClient,
        setup_db: AsyncSession
    ):
        """Test performance monitoring"""
        with LogCapture() as logs:
            # Create multiple committees to trigger performance warning
            for i in range(10):
                await client.post(
                    "/api/committees",
                    json={
                        "committee_id": f"TEST{i}",
                        "name": f"Test Committee {i}",
                        "chamber": "house",
                        "type": "standing"
                    }
                )

        # Check for slow operation warnings
        slow_ops = [
            log for log in logs.records
            if log.msg == "slow_operation"
        ]
        assert len(slow_ops) > 0
```

## Glossary Integration

The committees API supports optional glossary term integration. Add `include_definitions=true` to include relevant legislative terms and their definitions in the response.

### Response Enhancement

```python
class CommitteeResponse(BaseModel):
    # ... existing fields ...

    glossary_terms: Optional[Dict[str, str]] = Field(
        None,
        description="Relevant glossary terms and definitions found in committee information"
    )
```

### Usage Example

```python
# Get committee information with glossary terms
committee = await client.get_committee(
    "HSAG",
    congress=117,
    include_definitions=True
)

# Access glossary terms
if committee.glossary_terms:
    for term, definition in committee.glossary_terms.items():
        print(f"Term: {term}")
        print(f"Definition: {definition}")
        print("---")
```

The glossary integration focuses on terms found in:
- Committee name and type
- Committee jurisdiction
- Subcommittee information
- Activity descriptions
