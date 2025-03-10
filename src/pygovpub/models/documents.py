"""
SQLModel-based document database models.

This module defines database models for document handling, including
document references, versions, and authentication.
"""

from datetime import date, datetime
from enum import Enum, auto
from typing import List, Optional, TYPE_CHECKING, Dict, Any, Set

from pydantic import BaseModel
from sqlmodel import Field, Relationship, SQLModel

from pygovpub.auth.models import ApiSource
from pygovpub.models.base import BaseTable, BaseEntity

class DocumentType(str, Enum):
    """Types of documents available from GovInfo."""
    
    BILL = "bill"
    FEDERAL_REGISTER = "federal_register"
    CONGRESSIONAL_RECORD = "congressional_record"
    CODE_OF_FEDERAL_REGULATIONS = "cfr"
    STATUTE = "statute"
    PUBLIC_LAW = "public_law"
    CONGRESSIONAL_HEARING = "hearing"
    CONGRESSIONAL_REPORT = "report"
    CONGRESSIONAL_DOCUMENT = "document"
    COURT_OPINION = "court_opinion"
    OTHER = "other"


class DocumentFormat(str, Enum):
    """Available document formats."""
    
    PDF = "pdf"
    XML = "xml"
    HTML = "html"
    MODS = "mods"
    TEXT = "text"
    

class SourceReference(BaseModel):
    """Reference to a source for a document or other entity."""
    
    source: ApiSource
    """Source of the entity."""
    
    source_id: str
    """Identifier at the source."""
    
    source_url: Optional[str] = None
    """URL to access the entity at the source."""
    
    last_updated: Optional[datetime] = None
    """When the entity was last updated at the source."""


class Collection(BaseModel):
    """A collection of related documents."""
    
    code: str
    """Collection code (e.g., BILLS, FR)."""
    
    name: str
    """Human-readable name of the collection."""
    
    member_count: int
    """Number of documents in the collection."""
    
    last_updated: Optional[datetime] = None
    """When the collection was last updated."""
    
    description: Optional[str] = None
    """Description of the collection."""


class Package(BaseModel):
    """A document package from GovInfo.gov."""
    
    package_id: str
    """Package ID (e.g., BILLS-117hr1625enr)."""
    
    collection_code: Optional[str] = None
    """Collection code this package belongs to."""
    
    title: Optional[str] = None
    """Title of the document."""
    
    date_issued: Optional[date] = None
    """Date the document was issued."""
    
    last_modified: Optional[datetime] = None
    """When the package was last modified."""
    
    pdf_url: Optional[str] = None
    """URL to the PDF version."""
    
    xml_url: Optional[str] = None
    """URL to the XML version."""
    
    mods_url: Optional[str] = None
    """URL to the MODS metadata."""
    
    details: Dict[str, Any] = {}
    """Additional package details."""
    
    formats: List[DocumentFormat] = []
    """Available formats for this package."""
    
    source_reference: Optional[SourceReference] = None
    """Source reference information."""


class Granule(BaseModel):
    """A granule (subdivision) of a document package."""
    
    granule_id: str
    """Granule ID."""
    
    package_id: str
    """Package ID this granule belongs to."""
    
    title: Optional[str] = None
    """Title of the granule."""
    
    date_issued: Optional[date] = None
    """Date the granule was issued."""
    
    last_modified: Optional[datetime] = None
    """When the granule was last modified."""
    
    pdf_url: Optional[str] = None
    """URL to the PDF version."""
    
    xml_url: Optional[str] = None
    """URL to the XML version."""
    
    mods_url: Optional[str] = None
    """URL to the MODS metadata."""
    
    details: Dict[str, Any] = {}
    """Additional granule details."""
    
    formats: List[DocumentFormat] = []
    """Available formats for this granule."""
    
    source_reference: Optional[SourceReference] = None
    """Source reference information."""


# Define DocumentReference directly here instead of importing from legislative_db
class DocumentReference(BaseTable, table=True):
    """Reference to a document, such as a bill text."""
    
    __tablename__ = "document_references"
    
    document_id: str = Field(primary_key=True)
    """Unique identifier for the document."""
    
    document_type: str
    """Type of document (bill, law, report, etc.)."""
    
    source_id: str
    """ID of the source entity (bill_id, etc.)."""
    
    source_type: str
    """Type of the source entity (bill, committee, etc.)."""
    
    source_system: str = Field(max_length=10)
    # Valid values: 'govinfo', 'congress'
    """System that provided this document reference."""
    
    bill_id: Optional[str] = Field(default=None)
    """Reference to bill, if this is a bill document."""
    
    pdf_url: Optional[str] = None
    """URL to the PDF version of the document."""
    
    xml_url: Optional[str] = None
    """URL to the XML version of the document."""
    
    html_url: Optional[str] = None
    """URL to the HTML version of the document."""
    
    # Relationships
    versions: List["DocumentVersion"] = Relationship(back_populates="document")
    """Different versions of this document."""
    
    authentication: Optional["DocumentAuthentication"] = Relationship(back_populates="document")
    """Authentication information for this document."""
    
    # Bill relationship will be set dynamically after Bill class is defined


class DocumentVersion(BaseTable, table=True):
    """Document version tracking."""
    
    __tablename__ = "document_versions"
    
    version_id: str = Field(primary_key=True)
    """Unique identifier for the document version."""
    
    document_id: str = Field(foreign_key="document_references.document_id")
    """Document that this version is associated with."""
    
    version_code: str = Field(max_length=20)
    """Code for the version."""
    
    published_date: Optional[date] = None
    """When this version was published."""
    
    govinfo_package_id: Optional[str] = Field(unique=True, default=None)
    """GovInfo.gov package ID for this version."""
    
    pdf_url: Optional[str] = None
    """URL to the PDF version of the document."""
    
    xml_url: Optional[str] = None
    """URL to the XML version of the document."""
    
    digital_signature: Optional[str] = None
    """Digital signature for this document version."""
    
    signature_verified: Optional[bool] = None
    """Whether the digital signature has been verified."""
    
    # Relationships
    document: DocumentReference = Relationship(back_populates="versions")
    """Document that this version is associated with."""


class DocumentAuthentication(BaseTable, table=True):
    """Document authentication tracking."""
    
    __tablename__ = "document_authentications"
    
    authentication_id: Optional[int] = Field(default=None, primary_key=True)
    """Unique identifier for the authentication record."""
    
    document_id: str = Field(foreign_key="document_references.document_id", unique=True)
    """Document that this authentication is for."""
    
    digital_signature: Optional[str] = None
    """Digital signature for the document."""
    
    signature_verified: bool = Field(default=False)
    """Whether the digital signature has been verified."""
    
    verification_date: Optional[datetime] = None
    """When the signature was last verified."""
    
    authentication_status: str = Field(default="unverified")
    """Status of authentication (unverified, verified, invalid, etc.)."""
    
    # Relationships
    document: DocumentReference = Relationship(back_populates="authentication")
    """Document that this authentication is for."""


class DocumentContentCache(BaseTable, table=True):
    """Cache for document content."""
    
    __tablename__ = "document_content_cache"
    
    cache_id: Optional[int] = Field(default=None, primary_key=True)
    """Unique identifier for the cache entry."""
    
    document_id: str = Field(foreign_key="document_references.document_id")
    """Document that this content is for."""
    
    version_id: Optional[str] = Field(default=None, foreign_key="document_versions.version_id")
    """Version that this content is for (if applicable)."""
    
    content_type: str = Field(max_length=20)
    # Valid values: 'text', 'xml', 'html', 'metadata'
    """Type of cached content."""
    
    content: str
    """The cached content."""
    
    cached_at: datetime = Field(default_factory=lambda: datetime.now())
    """When the content was cached."""
    
    expires_at: Optional[datetime] = None
    """When the cache entry expires."""
    
    etag: Optional[str] = None
    """ETag from the source server, if available."""
    
    # Relationships
    document: DocumentReference = Relationship()
    """Document that this content is for."""
    
    version: Optional[DocumentVersion] = Relationship()
    """Version that this content is for (if applicable)."""