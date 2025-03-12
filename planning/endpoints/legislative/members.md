# Members API

## Overview

The Members API provides access to congressional member information from Congress.gov, including current and historical member data, roles, committee assignments, and sponsored legislation. This endpoint focuses on member-specific data and their legislative activities.

## Models

### Core Models

```python
from datetime import date, datetime
from typing import Optional, List, Dict, Any
from sqlmodel import SQLModel, Field, Relationship
from pydantic import validator, constr
from .base import BaseModel
from .errors import MemberError
from .logging import LogContext
from .metrics import record_metric

# Base Models
class MemberBase(BaseModel):
    """Base model for member data"""
    first_name: constr(min_length=1, max_length=100) = Field(
        ...,
        description="Member's first name"
    )
    last_name: constr(min_length=1, max_length=100) = Field(
        ...,
        description="Member's last name"
    )
    state: Optional[constr(min_length=2, max_length=2)] = Field(
        None,
        description="State represented",
        example="NC"
    )
    party: Optional[str] = Field(
        None,
        description="Political party affiliation"
    )
    chamber: Optional[str] = Field(
        None,
        description="Chamber (house/senate)",
        sa_column_kwargs={"check": "chamber IN ('house', 'senate')"}
    )
    leadership_role: Optional[str] = Field(
        None,
        description="Leadership position if any"
    )

    @validator("chamber")
    def validate_chamber(cls, v):
        if v and v not in {"house", "senate"}:
            raise MemberError("Chamber must be either 'house' or 'senate'")
        return v

    @validator("state")
    def validate_state(cls, v):
        if v and len(v) != 2:
            raise MemberError("State must be a two-letter code")
        return v.upper() if v else v

# Database Models
class Member(MemberBase, table=True):
    """Database model for members"""
    __tablename__ = "members"

    member_id: str = Field(
        primary_key=True,
        max_length=20,
        description="Bioguide ID"
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

    # Relationships with lazy loading
    roles: List["MemberRole"] = Relationship(
        back_populates="member",
        sa_relationship_kwargs={"lazy": "selectin"}
    )
    committee_assignments: List["CommitteeAssignment"] = Relationship(
        back_populates="member",
        sa_relationship_kwargs={"lazy": "selectin"}
    )
    sponsored_bills: List["SponsoredLegislation"] = Relationship(
        back_populates="member",
        sa_relationship_kwargs={"lazy": "selectin"}
    )

    class Config:
        orm_mode = True

class MemberRole(SQLModel, table=True):
    """Database model for member roles"""
    __tablename__ = "member_roles"

    role_id: int = Field(default=None, primary_key=True)
    member_id: str = Field(
        foreign_key="members.member_id",
        description="Associated member's bioguide ID"
    )
    congress_id: int = Field(
        foreign_key="congresses.congress_id",
        description="Congress number"
    )
    chamber: str = Field(
        ...,
        description="Chamber served in",
        sa_column_kwargs={"check": "chamber IN ('house', 'senate')"}
    )
    state: str = Field(..., max_length=2)
    district: Optional[int] = None
    party: str = Field(..., description="Party affiliation during role")
    start_date: date = Field(..., description="Role start date")
    end_date: Optional[date] = Field(None, description="Role end date")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    member: Member = Relationship(back_populates="roles")

    __table_args__ = (
        {"UniqueConstraint": ("member_id", "congress_id", "chamber")}
    )

class CommitteeAssignment(SQLModel, table=True):
    """Database model for committee assignments"""
    __tablename__ = "committee_assignments"

    assignment_id: int = Field(default=None, primary_key=True)
    member_id: str = Field(
        foreign_key="members.member_id",
        description="Associated member's bioguide ID"
    )
    committee_id: str = Field(
        foreign_key="committees.committee_id",
        description="Associated committee ID"
    )
    congress_id: int = Field(
        foreign_key="congresses.congress_id",
        description="Congress number"
    )
    role: str = Field(..., description="Role on committee")
    start_date: date = Field(..., description="Assignment start date")
    end_date: Optional[date] = Field(None, description="Assignment end date")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    member: Member = Relationship(back_populates="committee_assignments")
    committee: "Committee" = Relationship()

class SponsoredLegislation(SQLModel, table=True):
    """Database model for sponsored legislation"""
    __tablename__ = "sponsored_legislation"

    sponsor_id: int = Field(default=None, primary_key=True)
    member_id: str = Field(
        foreign_key="members.member_id",
        description="Sponsoring member's bioguide ID"
    )
    bill_id: str = Field(
        foreign_key="bills.bill_id",
        description="Associated bill ID"
    )
    congress_id: int = Field(
        foreign_key="congresses.congress_id",
        description="Congress number"
    )
    sponsor_type: str = Field(
        ...,
        description="Type of sponsorship",
        sa_column_kwargs={"check": "sponsor_type IN ('sponsor', 'cosponsor')"}
    )
    sponsored_date: date = Field(..., description="Date of sponsorship")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    member: Member = Relationship(back_populates="sponsored_bills")
    bill: "Bill" = Relationship()

# Error Classes
class MemberError(Exception):
    """Base class for member errors"""
    entity_type: str = "member"

class MemberNotFoundError(MemberError):
    """Raised when member cannot be found"""
    status_code: int = 404
    detail: str = "Member not found"

class MemberValidationError(MemberError):
    """Raised for member data validation errors"""
    status_code: int = 422

class MemberRateLimitError(MemberError):
    """Raised when API rate limits are exceeded"""
    status_code: int = 429
    retry_after: int = 3600  # 1 hour default

# API Request/Response Models
class MemberCreate(MemberBase):
    """Model for member creation requests"""
    member_id: str

    class Config:
       json_schema_extra = {
            "example": {
                "member_id": "A000374",
                "first_name": "Alma",
                "last_name": "Adams",
                "state": "NC",
                "party": "D",
                "chamber": "house"
            }
        }

class MemberUpdate(SQLModel):
    """Model for member update requests"""
    party: Optional[str] = None
    leadership_role: Optional[str] = None
    state: Optional[str] = None

    class Config:
       json_schema_extra = {
            "example": {
                "leadership_role": "Speaker of the House",
                "state": "CA"
            }
        }

class MemberResponse(MemberBase):
    """Model for member API responses"""
    member_id: str
    roles: Optional[List[Dict[str, Any]]] = None
    committee_assignments: Optional[List[Dict[str, Any]]] = None
    sponsored_bills: Optional[List[Dict[str, Any]]] = None
    glossary_terms: Optional[Dict[str, str]] = Field(
        None,
        description="Relevant glossary terms found in member information"
    )

    class Config:
        orm_mode = True
       json_schema_extra = {
            "example": {
                "member_id": "A000374",
                "first_name": "Alma",
                "last_name": "Adams",
                "state": "NC",
                "party": "D",
                "chamber": "house",
                "roles": [
                    {
                        "congress_id": 117,
                        "chamber": "house",
                        "district": 12,
                        "start_date": "2021-01-03"
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

class MemberService:
    """Service layer for member operations"""

    def __init__(self, session: AsyncSession = Depends(get_session)):
        self.session = session
        self._setup_metrics()

    def _setup_metrics(self):
        """Initialize performance monitoring thresholds"""
        self.PERFORMANCE_THRESHOLDS = {
            "get_member": 50,        # ms
            "list_members": 100,     # ms
            "get_roles": 75,         # ms
            "get_committees": 75,    # ms
            "get_sponsored": 75,     # ms
            "relationship_load": 50   # ms
        }

    async def get_member(
        self,
        member_id: str,
        congress: Optional[int] = None
    ) -> Member:
        """Get member by ID with optional congress-specific data"""
        with LogContext(operation="get_member") as log:
            start = time.perf_counter()
            try:
                query = select(Member).where(
                    Member.member_id == member_id
                ).options(
                    selectinload(Member.roles),
                    selectinload(Member.committee_assignments),
                    selectinload(Member.sponsored_bills)
                )

                if congress:
                    query = query.join(MemberRole).filter(
                        MemberRole.congress_id == congress
                    )

                result = await self.session.execute(query)
                member = result.scalar_one_or_none()

                if not member:
                    raise MemberNotFoundError(f"Member {member_id} not found")

                duration_ms = (time.perf_counter() - start) * 1000
                await self._record_performance(
                    "get_member",
                    duration_ms,
                    log
                )
                return member

            except Exception as e:
                log.error("member_retrieval_failed",
                    error=str(e),
                    member_id=member_id
                )
                raise

    @rate_limit_handler("congress")
    async def get_member_sponsored_bills(
        self,
        member_id: str,
        congress: int
    ) -> List[Dict[str, Any]]:
        """Get member's sponsored bills with rate limit handling"""
        with LogContext(operation="get_sponsored") as log:
            start = time.perf_counter()
            try:
                bills = await self.congress_api.get_sponsored_legislation(
                    member_id,
                    congress
                )
                duration_ms = (time.perf_counter() - start) * 1000
                await self._record_performance(
                    "get_sponsored",
                    duration_ms,
                    log
                )
                return bills
            except Exception as e:
                log.error("sponsored_bills_retrieval_failed",
                    error=str(e),
                    member_id=member_id,
                    congress=congress
                )
                raise

    async def create_member(self, member: MemberCreate) -> Member:
        """Create new member"""
        with LogContext(operation="create_member") as log:
            start = time.perf_counter()
            try:
                db_member = Member.from_orm(member)
                self.session.add(db_member)
                await self.session.commit()
                await self.session.refresh(db_member)

                duration_ms = (time.perf_counter() - start) * 1000
                await self._record_performance(
                    "create_member",
                    duration_ms,
                    log
                )
                return db_member

            except Exception as e:
                log.error("member_creation_failed",
                    error=str(e),
                    member_data=member.dict()
                )
                raise

    async def update_member(
        self,
        member_id: str,
        updates: MemberUpdate
    ) -> Member:
        """Update existing member"""
        with LogContext(operation="update_member") as log:
            start = time.perf_counter()
            try:
                member = await self.get_member(member_id)
                update_data = updates.dict(exclude_unset=True)
                for key, value in update_data.items():
                    setattr(member, key, value)
                await self.session.commit()
                await self.session.refresh(member)

                duration_ms = (time.perf_counter() - start) * 1000
                await self._record_performance(
                    "update_member",
                    duration_ms,
                    log
                )
                return member

            except Exception as e:
                log.error("member_update_failed",
                    error=str(e),
                    member_id=member_id,
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
            name="member_operation_duration_ms",
            value=duration_ms,
            tags={"operation": operation}
        )
```

## FastAPI Endpoints

```python
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from typing import List, Optional

router = APIRouter(prefix="/members", tags=["Members"])

@router.get(
    "/{member_id}",
    response_model=MemberResponse,
    responses={
        404: {"description": "Member not found"},
        429: {"description": "Rate limit exceeded"}
    }
)
async def get_member(
    member_id: str = Path(
        ...,
        description="Member's bioguide ID"
    ),
    congress: Optional[int] = Query(
        None,
        gt=0,
        description="Congress number for specific session data"
    ),
    service: MemberService = Depends()
) -> MemberResponse:
    """
    Retrieve member information with optional congress-specific data.

    Rate limits:
    - Congress.gov: 5,000 requests/hour
    """
    return await service.get_member(member_id, congress)

@router.get(
    "/congress/{congress_id}",
    response_model=List[MemberResponse],
    responses={
        429: {"description": "Rate limit exceeded"}
    }
)
async def list_members(
    congress_id: int = Path(
        ...,
        gt=0,
        description="Congress number"
    ),
    chamber: Optional[str] = Query(
        None,
        description="Filter by chamber (house/senate)"
    ),
    state: Optional[str] = Query(
        None,
        min_length=2,
        max_length=2,
        description="Filter by state (two-letter code)"
    ),
    party: Optional[str] = Query(
        None,
        description="Filter by party"
    ),
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0),
    service: MemberService = Depends()
) -> List[MemberResponse]:
    """List members for a specific congress with optional filters"""
    return await service.list_members(
        congress_id=congress_id,
        chamber=chamber,
        state=state,
        party=party,
        limit=limit,
        offset=offset
    )

@router.post(
    "/",
    response_model=MemberResponse,
    status_code=201,
    responses={
        409: {"description": "Member already exists"},
        422: {"description": "Validation error"}
    }
)
async def create_member(
    member: MemberCreate,
    service: MemberService = Depends()
) -> MemberResponse:
    """Create a new member record"""
    try:
        return await service.create_member(member)
    except IntegrityError:
        raise HTTPException(
            status_code=409,
            detail=f"Member {member.member_id} already exists"
        )

@router.patch(
    "/{member_id}",
    response_model=MemberResponse,
    responses={
        404: {"description": "Member not found"},
        422: {"description": "Validation error"}
    }
)
async def update_member(
    member_id: str,
    updates: MemberUpdate,
    service: MemberService = Depends()
) -> MemberResponse:
    """Update an existing member"""
    return await service.update_member(member_id, updates)
```

## Testing

```python
from .test_utils import IntegrationTestBase, LogCapture
from .errors import MemberError, MemberNotFoundError

class TestMemberEndpoints(IntegrationTestBase):
    """Integration tests for member endpoints"""

    async def test_member_lifecycle(
        self,
        client: TestClient,
        setup_db: AsyncSession
    ):
        """Test complete member lifecycle"""
        # Create member
        member_data = {
            "member_id": "A000374",
            "first_name": "Alma",
            "last_name": "Adams",
            "state": "NC",
            "party": "D",
            "chamber": "house"
        }
        with LogCapture() as logs:
            response = await client.post(
                "/api/members",
                json=member_data
            )

        assert response.status_code == 201
        member_id = response.json()["data"]["member_id"]

        # Verify creation was logged
        creation_log = next(
            log for log in logs.records
            if log.msg == "member_created"
        )
        assert creation_log.duration_ms < self.PERFORMANCE_THRESHOLDS["get_member"]

        # Update member
        update_data = {
            "leadership_role": "Committee Chair"
        }
        response = await client.patch(
            f"/api/members/{member_id}",
            json=update_data
        )
        assert response.status_code == 200

        # Verify update
        response = await client.get(f"/api/members/{member_id}")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["leadership_role"] == update_data["leadership_role"]

    async def test_error_handling(
        self,
        client: TestClient,
        setup_db: AsyncSession
    ):
        """Test error handling scenarios"""
        # Test not found
        response = await client.get("/api/members/INVALID")
        assert response.status_code == 404
        error = MemberError(**response.json())
        assert error.error == "MemberNotFoundError"

        # Test validation error
        response = await client.post(
            "/api/members",
            json={"invalid": "data"}
        )
        assert response.status_code == 422

        # Test rate limit
        for _ in range(25):  # Exceed rate limit
            await client.get("/api/members/A000374")

        response = await client.get("/api/members/A000374")
        assert response.status_code == 429
        error = MemberError(**response.json())
        assert error.retry_after is not None

    async def test_performance_monitoring(
        self,
        client: TestClient,
        setup_db: AsyncSession
    ):
        """Test performance monitoring"""
        with LogCapture() as logs:
            # Create multiple members to trigger performance warning
            for i in range(10):
                await client.post(
                    "/api/members",
                    json={
                        "member_id": f"TEST{i}",
                        "first_name": f"Test{i}",
                        "last_name": "Member",
                        "state": "CA",
                        "party": "I",
                        "chamber": "house"
                    }
                )

        # Check for slow operation warnings
        slow_ops = [
            log for log in logs.records
            if log.msg == "slow_operation"
        ]
        assert len(slow_ops) > 0

    async def test_member_relationships(
        self,
        client: TestClient,
        setup_db: AsyncSession
    ):
        """Test member relationship loading"""
        # Create member with relationships
        member_data = {
            "member_id": "A000374",
            "first_name": "Alma",
            "last_name": "Adams",
            "state": "NC",
            "party": "D",
            "chamber": "house"
        }
        response = await client.post(
            "/api/members",
            json=member_data
        )
        member_id = response.json()["data"]["member_id"]

        # Add role
        role_data = {
            "congress_id": 117,
            "chamber": "house",
            "district": 12,
            "start_date": "2021-01-03"
        }
        await client.post(
            f"/api/members/{member_id}/roles",
            json=role_data
        )

        # Add committee assignment
        assignment_data = {
            "committee_id": "HSAG",
            "congress_id": 117,
            "role": "Chair",
            "start_date": "2021-01-03"
        }
        await client.post(
            f"/api/members/{member_id}/committees",
            json=assignment_data
        )

        # Verify relationships are loaded
        response = await client.get(
            f"/api/members/{member_id}",
            params={"congress": 117}
        )
        data = response.json()["data"]
        assert len(data["roles"]) == 1
        assert len(data["committee_assignments"]) == 1
        assert data["roles"][0]["congress_id"] == 117
        assert data["committee_assignments"][0]["committee_id"] == "HSAG"
```

## Glossary Integration

The members API supports optional glossary term integration. Add `include_definitions=true` to include relevant legislative terms and their definitions in the response.

### Response Enhancement

```python
class MemberResponse(BaseModel):
    # ... existing fields ...

    glossary_terms: Optional[Dict[str, str]] = Field(
        None,
        description="Relevant glossary terms found in member information"
    )
```

### Usage Example

```python
# Get member information with glossary terms
member = await client.get_member(
    "L000551",
    congress=117,
    include_definitions=True
)

# Access glossary terms
if member.glossary_terms:
    for term, definition in member.glossary_terms.items():
        print(f"Term: {term}")
        print(f"Definition: {definition}")
        print("---")
```

The glossary integration focuses on terms found in:
- Member roles and positions
- Committee assignments
- Sponsored legislation
- Leadership positions
