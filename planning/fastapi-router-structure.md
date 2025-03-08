# FastAPI Integration Guide

## Technical Terms

### Response Models
- `BillResponse`: Standardized bill information response
- `GlossaryTermResponse`: Term definition response
- `APIError`: Error response structure

### Database Models
- `Bill`: Legislative bill tracking model
- `BillVersion`: Bill version and authentication model
- `Congress`: Congressional session model
- `GlossaryTerm`: Legislative term definition model

### Authentication Types
- `api_key`: API key in request header
- `hmac`: HMAC-SHA256 webhook validation
- `session`: Database session authentication

## Router Structure

PyGovPub's FastAPI implementation leverages SQLModel for type-safe database operations and efficient query handling.

### Core Dependencies

```python
from fastapi import FastAPI, Depends, HTTPException
from sqlmodel import SQLModel, select, Field, Relationship
from sqlmodel.ext.asyncio.session import AsyncSession
from typing import List, Optional
from datetime import datetime
from pydantic import constr, conint

from .database import get_session
from .models import Bill, BillVersion, Congress

# Core Models
class Bill(SQLModel, table=True):
    """Legislative bill tracking model"""
    __tablename__ = "bills"

    bill_id: str = Field(
        primary_key=True,
        max_length=50,
        description="Unique bill identifier (format: {type}{number}-{congress})"
    )
    congress_id: int = Field(
        foreign_key="congresses.congress_id",
        sa_column_kwargs={"index": True},
        description="Congressional session identifier"
    )
    bill_type: str = Field(
        max_length=10,
        sa_column_kwargs={
            "check": "bill_type IN ('hr', 's', 'hjres', 'sjres', 'hconres', 'sconres', 'hres', 'sres')"
        },
        description="Bill type code (hr: House Bill, s: Senate Bill, etc.)"
    )
    bill_number: int = Field(description="Numeric identifier within congress")
    title: str = Field(description="Official bill title")
    introduced_date: Optional[datetime] = Field(description="Date bill was introduced")
    status: Optional[str] = Field(
        max_length=50,
        sa_column_kwargs={"index": True},
        description="Current bill status"
    )
    last_action_date: Optional[datetime] = Field(
        None,
        sa_column_kwargs={"index": True},
        description="Date of most recent action"
    )
    source_system: str = Field(
        max_length=10,
        sa_column_kwargs={"check": "source_system IN ('govinfo', 'congress')"},
        description="Data source system"
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

    class Config:
        orm_mode = True

# Response Models
class BillResponse(SQLModel):
    """Standardized bill information response"""
    bill_id: str
    congress_id: int
    bill_type: str
    bill_number: int
    title: str
    introduced_date: Optional[datetime]
    status: Optional[str]

    class Config:
        orm_mode = True
        schema_extra = {
            "example": {
                "bill_id": "HR1234-117",
                "congress_id": 117,
                "bill_type": "hr",
                "bill_number": 1234,
                "title": "Example Bill",
                "status": "INTRODUCED"
            }
        }

### Router Organization

```python
# app/routers/bills.py
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select
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
    bill_id: str,
    session: AsyncSession = Depends(get_session)
):
    """
    Retrieve bill information.

    Rate limits:
    - Congress.gov: 5,000 requests/hour
    - GovInfo.gov: 1,000 requests/hour (bulk downloads exempt)
    """
    query = select(Bill).where(Bill.bill_id == bill_id)
    result = await session.execute(query)
    bill = result.scalar_one_or_none()

    if not bill:
        raise HTTPException(status_code=404, detail=f"Bill {bill_id} not found")
    return bill

@router.get("/congress/{congress_id}", response_model=List[Bill])
async def get_bills_by_congress(
    congress_id: int,
    bill_type: Optional[str] = None,
    status: Optional[str] = None,
    session: AsyncSession = Depends(get_session)
):
    query = select(Bill).where(Bill.congress_id == congress_id)

    if bill_type:
        query = query.where(Bill.bill_type == bill_type)
    if status:
        query = query.where(Bill.status == status)

    result = await session.execute(query)
    return result.scalars().all()

# app/routers/versions.py
@router.get("/versions/{version_id}", response_model=BillVersion)
async def get_bill_version(
    version_id: str,
    session: AsyncSession = Depends(get_session)
):
    query = select(BillVersion).where(BillVersion.version_id == version_id)
    result = await session.execute(query)
    version = result.scalar_one_or_none()

    if not version:
        raise HTTPException(status_code=404, detail=f"Version {version_id} not found")
    return version

# app/routers/glossary.py
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select
from typing import List, Optional

router = APIRouter(prefix="/glossary", tags=["Glossary"])

@router.get(
    "/terms/{term}",
    response_model=GlossaryTermResponse,
    responses={404: {"description": "Term not found"}}
)
async def get_term(
    term: str,
    session: AsyncSession = Depends(get_session)
):
    """Retrieve glossary term definition"""
    query = select(GlossaryTerm).where(GlossaryTerm.term == term)
    result = await session.execute(query)
    term = result.scalar_one_or_none()
    if not term:
        raise HTTPException(status_code=404, detail=f"Term '{term}' not found")
    return term

@router.get(
    "/search",
    response_model=List[GlossaryTermResponse]
)
async def search_terms(
    query: str,
    category: Optional[str] = None,
    session: AsyncSession = Depends(get_session)
):
    """Search glossary terms"""
    search_query = select(GlossaryTerm)
    if query:
        search_query = search_query.where(GlossaryTerm.term.ilike(f"%{query}%"))
    if category:
        search_query = search_query.where(GlossaryTerm.category == category)
    result = await session.execute(search_query)
    return result.scalars().all()
```

### Main Application

```python
# app/main.py
from fastapi import FastAPI
from sqlmodel import SQLModel
from .database import engine, init_db_pool
from .routers import bills, versions

app = FastAPI(
    title="PyGovPub API",
    description="Unified access to U.S. Federal Government public data"
)

@app.on_event("startup")
async def startup():
    # Initialize connection pool
    app.state.pool = await init_db_pool()

    # Create database tables
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

@app.on_event("shutdown")
async def shutdown():
    await app.state.pool.close()

# Include routers
app.include_router(bills.router)
app.include_router(versions.router)
```

## Error Handling

```python
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError, OperationalError

class APIError(BaseModel):
    error: str
    detail: str
    entity_type: Optional[str]
    retry_after: Optional[int]
    trace_id: str

@app.exception_handler(IntegrityError)
async def integrity_error_handler(request, exc):
    return JSONResponse(
        status_code=400,
        content=APIError(
            error="IntegrityError",
            detail="Database integrity error",
            entity_type="bill",
            trace_id=request.state.trace_id
        ).dict()
    )

@app.exception_handler(OperationalError)
async def operational_error_handler(request, exc):
    return JSONResponse(
        status_code=503,
        content=APIError(
            error="OperationalError",
            detail="Database operation failed",
            trace_id=request.state.trace_id
        ).dict()
    )
```

## Query Optimization

### Efficient Loading Patterns

```python
# Example of optimized relationship loading
@router.get("/bills/{bill_id}/full", response_model=BillWithRelations)
async def get_bill_with_relations(
    bill_id: str,
    session: AsyncSession = Depends(get_session)
):
    query = select(Bill).where(Bill.bill_id == bill_id).options(
        selectinload(Bill.versions),
        selectinload(Bill.sponsors)
    )
    result = await session.execute(query)
    bill = result.scalar_one_or_none()

    if not bill:
        raise HTTPException(status_code=404, detail=f"Bill {bill_id} not found")
    return bill
```

### Response Models

```python
class BillResponse(SQLModel):
    bill_id: str
    congress_id: int
    bill_type: str
    bill_number: int
    title: str
    introduced_date: Optional[datetime]
    status: Optional[str]

    class Config:
        orm_mode = True

class BillWithRelations(BillResponse):
    versions: List[BillVersion]
    sponsors: List[BillSponsor]
```

## Database Session Management

```python
from contextlib import asynccontextmanager
from sqlmodel.ext.asyncio.session import AsyncSession

@asynccontextmanager
async def get_session() -> AsyncSession:
    session = AsyncSession(engine)
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
```

## Middleware Integration

PyGovPub works well with FastAPI middleware for authentication, rate limiting, and error tracking:

```python
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from pygovpub.exceptions import ApiRateLimitError

app = FastAPI()

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limit tracking middleware
class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)

            # Check if client is from app state
            if hasattr(request.state, "client"):
                client = request.state.client
                # Update rate limit tracking
                await client.track_request_from_response(response)

            return response
        except ApiRateLimitError as e:
            # Handle rate limit errors
            return JSONResponse(
                status_code=429,
                content={"detail": str(e)},
                headers={"Retry-After": str(e.retry_after)}
            )

app.add_middleware(RateLimitMiddleware)
```

## Documentation Links
Auth_Doc[endpoints/authentication/configuration.md]
Router_Doc[endpoints/routing/smart_router.md]
Congress_Doc[endpoints/congress/api.md]
GovInfo_Doc[endpoints/govinfo/api.md]
DB_Doc[planning/database-schema.md]
Error_Doc[endpoints/error/handling.md]
Webhook_Doc[endpoints/updates/webhooks.md]

## Error Handling

Configure global exception handlers for PyGovPub exceptions:

```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pygovpub.exceptions import (
    PyGovPubException,
    AuthenticationError,
    ApiRateLimitError,
    DocumentNotFoundError
)

app = FastAPI()

@app.exception_handler(PyGovPubException)
async def pygovpub_exception_handler(request: Request, exc: PyGovPubException):
    status_code = getattr(exc, "status_code", 500)
    return JSONResponse(
        status_code=status_code,
        content={
            "error": exc.__class__.__name__,
            "detail": str(exc)
        }
    )

@app.exception_handler(AuthenticationError)
async def auth_error_handler(request: Request, exc: AuthenticationError):
    return JSONResponse(
        status_code=401,
        content={
            "error": "AuthenticationError",
            "detail": str(exc)
        }
    )

@app.exception_handler(ApiRateLimitError)
async def rate_limit_error_handler(request: Request, exc: ApiRateLimitError):
    return JSONResponse(
        status_code=429,
        content={
            "error": "RateLimitExceeded",
            "detail": str(exc),
            "retry_after": exc.retry_after
        },
        headers={"Retry-After": str(exc.retry_after)}
    )

@app.exception_handler(DocumentNotFoundError)
async def document_not_found_handler(request: Request, exc: DocumentNotFoundError):
    return JSONResponse(
        status_code=404,
        content={
            "error": "DocumentNotFound",
            "detail": str(exc)
        }
    )
```

### Data Type Handling

#### Monetary Values
All monetary values in API responses follow these standards:
- **Format**: Decimal string with exactly 2 decimal places
- **Currency**: Always USD, included in response
- **Response Structure**:
```json
{
  "amount": "1234.56",
  "currency": "USD"
}
```

- **Validation**:
  - Input validation ensures proper decimal format
  - Non-negative values where appropriate
  - Currency code must be "USD"

- **Type Annotations**:
```python
from decimal import Decimal
from typing import Literal

class MonetaryAmount(BaseModel):
    amount: Decimal = Field(..., ge=0, decimal_places=2)
    currency: Literal["USD"] = "USD"
```
