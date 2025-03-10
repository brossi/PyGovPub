"""
SQLModel-based document database models.

This module defines database models for document handling, including
document references, versions, and authentication.
"""

from datetime import date, datetime
from typing import List, Optional, TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

from pygovpub.models.base import BaseTable, BaseEntity

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