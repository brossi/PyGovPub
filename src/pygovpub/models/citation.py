"""
Citation Models Module.

This module provides models for citations and cross-references between 
different types of documents and entities in the legal and regulatory domain.
"""

from typing import Dict, List, Optional, Any, Union, Set
from enum import Enum, auto
from datetime import datetime, date
from pydantic import BaseModel, Field, field_validator

from pygovpub.models.documents import DocumentType, SourceReference
from pygovpub.auth.models import ApiSource


class CitationType(str, Enum):
    """
    Citation Type Enum.
    
    Enumeration of citation types.
    """
    
    BILL = "bill_citation"
    USC = "usc_citation"
    CFR = "cfr_citation"
    FEDERAL_REGISTER = "fr_citation"
    PUBLIC_LAW = "public_law_citation"
    STATUTE = "statute_citation"
    COURT_CASE = "court_case_citation"
    REGULATION = "regulation_citation"
    OTHER = "other_citation"


class Citation(BaseModel):
    """
    Citation Model.
    
    Represents a citation from one entity to another.
    """
    
    # Citation metadata
    citation_id: str = Field(..., description="Unique identifier for this citation")
    citation_type: CitationType = Field(..., description="Type of citation")
    text: str = Field(..., description="The citation text as it appears in the source")
    
    # Source information
    source_entity_id: str = Field(..., description="ID of the entity containing the citation")
    source_entity_type: str = Field(..., description="Type of the entity containing the citation")
    
    # Target information
    target_entity_id: str = Field(..., description="ID of the entity being cited")
    target_entity_type: str = Field(..., description="Type of the entity being cited")
    
    # Location information
    location_in_source: Dict[str, Any] = Field(default_factory=dict, description="Where the citation appears in the source")
    
    # Additional metadata
    extracted_at: Optional[datetime] = Field(None, description="When this citation was extracted")
    extracted_by: Optional[str] = Field(None, description="Method or system that extracted this citation")
    confidence_score: Optional[float] = Field(None, description="Confidence score for the citation extraction")


class ResolutionStatus(str, Enum):
    """
    Resolution Status Enum.
    
    Enumeration of resolution statuses for citations.
    """
    
    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"
    AMBIGUOUS = "ambiguous"
    INVALID = "invalid"
    PENDING = "pending"


class ResolutionMethod(str, Enum):
    """
    Resolution Method Enum.
    
    Enumeration of methods used to resolve citations.
    """
    
    AUTOMATIC = "automatic"
    MANUAL = "manual"
    INFERRED = "inferred"
    VALIDATED = "validated"


class ReferenceResolution(BaseModel):
    """
    Reference Resolution Model.
    
    Represents the resolution of a citation to a specific entity.
    """
    
    # Resolution metadata
    resolution_id: str = Field(..., description="Unique identifier for this resolution")
    citation_id: str = Field(..., description="ID of the citation being resolved")
    resolution_status: str = Field(..., description="Status of the resolution")
    resolution_method: str = Field(..., description="Method used to resolve the citation")
    
    # Resolution details
    confidence_score: float = Field(..., description="Confidence score for the resolution")
    target_information: Dict[str, Any] = Field(default_factory=dict, description="Information about the resolved target")
    
    # Temporal information
    resolution_date: Optional[str] = Field(None, description="When the resolution was performed")
    last_validated: Optional[str] = Field(None, description="When the resolution was last validated")
    
    # Additional metadata
    notes: Optional[str] = Field(None, description="Notes about the resolution")
    validation_history: List[Dict[str, Any]] = Field(default_factory=list, description="History of validation attempts")


class RelationshipType(str, Enum):
    """
    Relationship Type Enum.
    
    Enumeration of relationship types between entities.
    """
    
    REFERENCES = "references"
    AMENDS = "amends"
    IMPLEMENTS = "implements"
    SUPERSEDES = "supersedes"
    INVALIDATES = "invalidates"
    AUTHORIZES = "authorizes"
    RELATED_TO = "related_to"


class BidirectionalLink(BaseModel):
    """
    Bidirectional Link Model.
    
    Represents a bidirectional link between two entities.
    """
    
    # Link metadata
    link_id: str = Field(..., description="Unique identifier for this link")
    
    # Entity A information
    entity_a_id: str = Field(..., description="ID of entity A")
    entity_a_type: str = Field(..., description="Type of entity A")
    
    # Entity B information
    entity_b_id: str = Field(..., description="ID of entity B")
    entity_b_type: str = Field(..., description="Type of entity B")
    
    # Relationship information
    relationship_type: str = Field(..., description="Type of relationship between the entities")
    
    # Citation information
    citations: List[str] = Field(default_factory=list, description="IDs of citations related to this link")
    
    # Additional properties
    properties: Dict[str, Any] = Field(default_factory=dict, description="Additional properties of the link")
    
    # Temporal information
    created_at: Optional[datetime] = Field(None, description="When this link was created")
    updated_at: Optional[datetime] = Field(None, description="When this link was last updated")
    