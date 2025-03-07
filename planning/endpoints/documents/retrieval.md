# Document Retrieval & Authentication API

## Overview

The Document Retrieval & Authentication API provides secure access to official government documents from GovInfo.gov, including bills, reports, and other legislative materials. This endpoint handles document authentication, digital signatures, and content verification to ensure document integrity.

## Models

### Core Models

```python
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from sqlmodel import SQLModel, Field, Relationship
from pydantic import validator, constr
from .base import BaseModel
from .errors import DocumentError
from .logging import LogContext
from .metrics import record_metric
import hashlib

# Base Models
class DocumentPackageBase(BaseModel):
    """Base model for document package data"""
    document_type: str = Field(
        ...,
        description="Type of document",
        sa_column_kwargs={"check": "document_type IN ('bill', 'report', 'hearing', 'amendment')"}
    )
    title: str = Field(..., description="Document title")
    published_date: date = Field(..., description="Publication date")
    last_modified_date: date = Field(..., description="Last modification date")
    collection_code: str = Field(..., description="GovInfo collection code")
    branch: Optional[str] = Field(
        None,
        description="Government branch",
        sa_column_kwargs={"check": "branch IN ('legislative', 'executive', 'judicial')"}
    )
    pages: Optional[int] = Field(None, description="Number of pages")

    @validator("document_type")
    def validate_document_type(cls, v):
        valid_types = {"bill", "report", "hearing", "amendment"}
        if v not in valid_types:
            raise DocumentError(f"Invalid document type. Must be one of: {', '.join(valid_types)}")
        return v

    @validator("branch")
    def validate_branch(cls, v):
        if v and v not in {"legislative", "executive", "judicial"}:
            raise DocumentError("Branch must be legislative, executive, or judicial")
        return v

# Database Models
class DocumentPackage(DocumentPackageBase, table=True):
    """Database model for document packages"""
    __tablename__ = "document_packages"

    package_id: str = Field(
        primary_key=True,
        max_length=100,
        description="GovInfo package identifier"
    )
    congress_id: Optional[int] = Field(
        foreign_key="congresses.congress_id",
        description="Associated congress number"
    )
    digital_signature: Optional[str] = Field(
        None,
        description="Document's digital signature"
    )
    signature_verified: bool = Field(
        default=False,
        description="Whether signature is verified"
    )
    verification_date: Optional[datetime] = Field(
        None,
        description="Date of signature verification"
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
    contents: List["DocumentContent"] = Relationship(
        back_populates="package",
        sa_relationship_kwargs={"lazy": "selectin"}
    )
    authentications: List["DocumentAuthentication"] = Relationship(
        back_populates="package",
        sa_relationship_kwargs={"lazy": "selectin"}
    )

    class Config:
        orm_mode = True

class DocumentContent(SQLModel, table=True):
    """Database model for document content"""
    __tablename__ = "document_content"

    content_id: int = Field(default=None, primary_key=True)
    package_id: str = Field(
        foreign_key="document_packages.package_id",
        description="Associated package ID"
    )
    content_type: str = Field(
        ...,
        description="Content format",
        sa_column_kwargs={"check": "content_type IN ('pdf', 'xml', 'html')"}
    )
    content_url: str = Field(..., description="Content URL")
    content_hash: str = Field(..., description="Content hash")
    content_size: int = Field(..., description="Content size in bytes")
    last_validated_at: datetime = Field(
        ...,
        description="Last content validation timestamp"
    )
    is_official: bool = Field(
        default=False,
        description="Whether content is official"
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    package: DocumentPackage = Relationship(back_populates="contents")

    __table_args__ = (
        {"UniqueConstraint": ("package_id", "content_type")}
    )

class DocumentAuthentication(SQLModel, table=True):
    """Database model for document authentication history"""
    __tablename__ = "document_authentication"

    auth_id: int = Field(default=None, primary_key=True)
    package_id: str = Field(
        foreign_key="document_packages.package_id",
        description="Associated package ID"
    )
    verification_date: datetime = Field(
        ...,
        description="Verification timestamp"
    )
    signature_status: str = Field(
        ...,
        description="Signature verification status"
    )
    verification_method: str = Field(
        ...,
        description="Method used for verification"
    )
    error_message: Optional[str] = Field(
        None,
        description="Error message if verification failed"
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    package: DocumentPackage = Relationship(back_populates="authentications")

# Error Classes
class DocumentError(Exception):
    """Base class for document errors"""
    entity_type: str = "document"

class DocumentNotFoundError(DocumentError):
    """Raised when document cannot be found"""
    status_code: int = 404
    detail: str = "Document not found"

class DocumentValidationError(DocumentError):
    """Raised for document validation errors"""
    status_code: int = 422

class DocumentAuthenticationError(DocumentError):
    """Raised for document authentication failures"""
    status_code: int = 401
    detail: str = "Document authentication failed"

class DocumentRateLimitError(DocumentError):
    """Raised when API rate limits are exceeded"""
    status_code: int = 429
    retry_after: int = 3600  # 1 hour default

# API Request/Response Models
class DocumentPackageCreate(DocumentPackageBase):
    """Model for document package creation requests"""
    package_id: str

    class Config:
        schema_extra = {
            "example": {
                "package_id": "BILLS-117hr1234ih",
                "document_type": "bill",
                "title": "H.R. 1234 - Example Bill",
                "published_date": "2023-03-01",
                "last_modified_date": "2023-03-01",
                "collection_code": "BILLS",
                "branch": "legislative",
                "pages": 10
            }
        }

class DocumentPackageUpdate(SQLModel):
    """Model for document package update requests"""
    title: Optional[str] = None
    last_modified_date: Optional[date] = None
    digital_signature: Optional[str] = None

    class Config:
        schema_extra = {
            "example": {
                "last_modified_date": "2023-03-02",
                "digital_signature": "updated_signature"
            }
        }

class DocumentPackageResponse(DocumentPackageBase):
    """Model for document package API responses"""
    package_id: str
    signature_verified: bool
    contents: Optional[List[Dict[str, Any]]] = None
    authentications: Optional[List[Dict[str, Any]]] = None

    class Config:
        orm_mode = True
        schema_extra = {
            "example": {
                "package_id": "BILLS-117hr1234ih",
                "document_type": "bill",
                "title": "H.R. 1234 - Example Bill",
                "published_date": "2023-03-01",
                "last_modified_date": "2023-03-01",
                "collection_code": "BILLS",
                "branch": "legislative",
                "pages": 10,
                "signature_verified": True,
                "contents": [
                    {
                        "content_type": "pdf",
                        "content_url": "https://api.govinfo.gov/packages/BILLS-117hr1234ih/pdf",
                        "content_hash": "sha256:abc123...",
                        "content_size": 1024000,
                        "is_official": True
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

class DocumentService:
    """Service layer for document operations"""

    def __init__(self, session: AsyncSession = Depends(get_session)):
        self.session = session
        self._setup_metrics()

    def _setup_metrics(self):
        """Initialize performance monitoring thresholds"""
        self.PERFORMANCE_THRESHOLDS = {
            "get_document": 100,       # ms
            "list_documents": 150,     # ms
            "verify_signature": 200,   # ms
            "get_content": 500,        # ms
            "relationship_load": 50    # ms
        }

    async def get_document(
        self,
        package_id: str,
        content_type: Optional[str] = None
    ) -> DocumentPackage:
        """Get document package by ID with optional content"""
        with LogContext(operation="get_document") as log:
            start = time.perf_counter()
            try:
                query = select(DocumentPackage).where(
                    DocumentPackage.package_id == package_id
                ).options(
                    selectinload(DocumentPackage.contents),
                    selectinload(DocumentPackage.authentications)
                )

                result = await self.session.execute(query)
                package = result.scalar_one_or_none()

                if not package:
                    raise DocumentNotFoundError(
                        f"Document package {package_id} not found"
                    )

                # Get content if requested and not cached
                if content_type and not any(
                    c.content_type == content_type for c in package.contents
                ):
                    await self._fetch_content(package, content_type)

                duration_ms = (time.perf_counter() - start) * 1000
                await self._record_performance(
                    "get_document",
                    duration_ms,
                    log
                )
                return package

            except Exception as e:
                log.error("document_retrieval_failed",
                    error=str(e),
                    package_id=package_id
                )
                raise

    @rate_limit_handler("govinfo")
    async def _fetch_content(
        self,
        package: DocumentPackage,
        content_type: str
    ) -> None:
        """Fetch document content from GovInfo"""
        with LogContext(operation="get_content") as log:
            start = time.perf_counter()
            try:
                content_data = await self.govinfo_api.get_package_content(
                    package.package_id,
                    content_type
                )

                content = DocumentContent(
                    package_id=package.package_id,
                    content_type=content_type,
                    content_url=content_data["url"],
                    content_hash=content_data["hash"],
                    content_size=content_data["size"],
                    last_validated_at=datetime.utcnow(),
                    is_official=package.signature_verified
                )
                self.session.add(content)
                await self.session.commit()
                await self.session.refresh(package)

                duration_ms = (time.perf_counter() - start) * 1000
                await self._record_performance(
                    "get_content",
                    duration_ms,
                    log
                )

            except Exception as e:
                log.error("content_fetch_failed",
                    error=str(e),
                    package_id=package.package_id,
                    content_type=content_type
                )
                raise

    async def verify_document(
        self,
        package_id: str,
        signature: str
    ) -> bool:
        """Verify document signature"""
        with LogContext(operation="verify_signature") as log:
            start = time.perf_counter()
            try:
                package = await self.get_document(package_id)
                is_verified = await self._verify_signature(signature)

                # Record verification
                auth = DocumentAuthentication(
                    package_id=package_id,
                    verification_date=datetime.utcnow(),
                    signature_status="verified" if is_verified else "failed",
                    verification_method="digital_signature"
                )
                self.session.add(auth)

                # Update package
                package.signature_verified = is_verified
                package.verification_date = datetime.utcnow()
                await self.session.commit()
                await self.session.refresh(package)

                duration_ms = (time.perf_counter() - start) * 1000
                await self._record_performance(
                    "verify_signature",
                    duration_ms,
                    log
                )
                return is_verified

            except Exception as e:
                log.error("signature_verification_failed",
                    error=str(e),
                    package_id=package_id
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
            name="document_operation_duration_ms",
            value=duration_ms,
            tags={"operation": operation}
        )
```

## FastAPI Endpoints

```python
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from typing import List, Optional

router = APIRouter(prefix="/documents", tags=["Documents"])

@router.get(
    "/{package_id}",
    response_model=DocumentPackageResponse,
    responses={
        404: {"description": "Document not found"},
        429: {"description": "Rate limit exceeded"}
    }
)
async def get_document(
    package_id: str = Path(
        ...,
        description="GovInfo package identifier"
    ),
    content_type: Optional[str] = Query(
        None,
        description="Content format (pdf/xml/html)"
    ),
    service: DocumentService = Depends()
) -> DocumentPackageResponse:
    """
    Retrieve document package with optional content.

    Rate limits:
    - GovInfo.gov: 1,000 requests/hour
    """
    return await service.get_document(package_id, content_type)

@router.get(
    "/",
    response_model=List[DocumentPackageResponse],
    responses={
        429: {"description": "Rate limit exceeded"}
    }
)
async def list_documents(
    document_type: Optional[str] = Query(
        None,
        description="Filter by document type"
    ),
    congress: Optional[int] = Query(
        None,
        gt=0,
        description="Filter by congress number"
    ),
    collection: Optional[str] = Query(
        None,
        description="Filter by collection code"
    ),
    verified_only: bool = Query(
        False,
        description="Only return verified documents"
    ),
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0),
    service: DocumentService = Depends()
) -> List[DocumentPackageResponse]:
    """List document packages with optional filters"""
    return await service.list_documents(
        document_type=document_type,
        congress=congress,
        collection=collection,
        verified_only=verified_only,
        limit=limit,
        offset=offset
    )

@router.post(
    "/{package_id}/verify",
    response_model=Dict[str, bool],
    responses={
        404: {"description": "Document not found"},
        401: {"description": "Authentication failed"},
        422: {"description": "Validation error"}
    }
)
async def verify_document(
    package_id: str = Path(
        ...,
        description="GovInfo package identifier"
    ),
    signature: str = Query(
        ...,
        description="Digital signature to verify"
    ),
    service: DocumentService = Depends()
) -> Dict[str, bool]:
    """Verify document signature"""
    is_verified = await service.verify_document(package_id, signature)
    return {"verified": is_verified}
```

## Testing

```python
from .test_utils import IntegrationTestBase, LogCapture
from .errors import DocumentError, DocumentNotFoundError

class TestDocumentEndpoints(IntegrationTestBase):
    """Integration tests for document endpoints"""

    async def test_document_retrieval(
        self,
        client: TestClient,
        setup_db: AsyncSession
    ):
        """Test document retrieval"""
        # Get document without content
        response = await client.get(
            "/api/documents/BILLS-117hr1234ih"
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["package_id"] == "BILLS-117hr1234ih"
        assert "contents" in data

        # Get document with content
        response = await client.get(
            "/api/documents/BILLS-117hr1234ih",
            params={"content_type": "pdf"}
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert len(data["contents"]) > 0
        assert data["contents"][0]["content_type"] == "pdf"

    async def test_document_verification(
        self,
        client: TestClient,
        setup_db: AsyncSession
    ):
        """Test document verification"""
        # Verify valid signature
        response = await client.post(
            "/api/documents/BILLS-117hr1234ih/verify",
            params={"signature": "valid_signature"}
        )
        assert response.status_code == 200
        assert response.json()["data"]["verified"] is True

        # Verify invalid signature
        response = await client.post(
            "/api/documents/BILLS-117hr1234ih/verify",
            params={"signature": "invalid_signature"}
        )
        assert response.status_code == 401
        error = DocumentError(**response.json())
        assert error.error == "DocumentAuthenticationError"

    async def test_error_handling(
        self,
        client: TestClient,
        setup_db: AsyncSession
    ):
        """Test error handling scenarios"""
        # Test not found
        response = await client.get(
            "/api/documents/INVALID"
        )
        assert response.status_code == 404
        error = DocumentError(**response.json())
        assert error.error == "DocumentNotFoundError"

        # Test rate limit
        for _ in range(900):  # Near GovInfo limit
            await client.get(
                "/api/documents/BILLS-117hr1234ih",
                params={"content_type": "pdf"}
            )

        response = await client.get(
            "/api/documents/BILLS-117hr1234ih",
            params={"content_type": "pdf"}
        )
        assert response.status_code == 429
        error = DocumentError(**response.json())
        assert error.error == "DocumentRateLimitError"
        assert error.retry_after is not None

    async def test_performance_monitoring(
        self,
        client: TestClient,
        setup_db: AsyncSession
    ):
        """Test performance monitoring"""
        with LogCapture() as logs:
            # Make multiple document requests
            for _ in range(10):
                await client.get(
                    "/api/documents/BILLS-117hr1234ih",
                    params={"content_type": "pdf"}
                )

        # Check for slow operation warnings
        slow_ops = [
            log for log in logs.records
            if log.msg == "slow_operation"
        ]
        assert len(slow_ops) > 0

    async def test_content_caching(
        self,
        client: TestClient,
        setup_db: AsyncSession
    ):
        """Test document content caching"""
        # First request fetches content
        response = await client.get(
            "/api/documents/BILLS-117hr1234ih",
            params={"content_type": "pdf"}
        )
        assert response.status_code == 200
        data = response.json()["data"]
        content_hash = data["contents"][0]["content_hash"]

        # Second request uses cached content
        with LogCapture() as logs:
            response = await client.get(
                "/api/documents/BILLS-117hr1234ih",
                params={"content_type": "pdf"}
            )

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["contents"][0]["content_hash"] == content_hash

        # Verify no content fetch operation was logged
        content_fetches = [
            log for log in logs.records
            if log.msg == "content_fetch"
        ]
        assert len(content_fetches) == 0
```
