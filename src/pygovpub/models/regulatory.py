"""
Regulatory Models Module.

This module provides models for regulatory content including:
- Code of Federal Regulations (CFR)
- Federal Register
- Court Opinions
- Regulatory Process
"""

from typing import Dict, List, Optional, Any, Union
from enum import Enum, auto
from datetime import datetime, date
from pydantic import BaseModel, Field, field_validator

from pygovpub.models.documents import DocumentType, SourceReference
from pygovpub.auth.models import ApiSource


class CfrChapter(BaseModel):
    """
    CFR Chapter Model.
    
    Represents a chapter within a CFR title.
    """
    
    # Chapter metadata
    chapter_number: str = Field(..., description="Chapter number (typically Roman numeral)")
    chapter_name: str = Field(..., description="Chapter name")
    
    # Optional fields
    subchapters: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Subchapters within this chapter")


class CfrTitle(BaseModel):
    """
    CFR Title Model.
    
    Represents a title within the Code of Federal Regulations.
    """
    
    # Title metadata
    title_number: int = Field(..., description="Title number (1-50)")
    title_name: str = Field(..., description="Title name")
    
    # Chapter information
    chapters: List[CfrChapter] = Field(default_factory=list, description="Chapters within this title")
    
    # Source reference
    source_reference: Optional[SourceReference] = Field(None, description="Source reference information")
    
    @field_validator('title_number')
    def validate_title_number(cls, v):
        """Validate title number is within range 1-50."""
        if v < 1 or v > 50:
            raise ValueError(f"Title number must be between 1 and 50, got {v}")
        return v


class CfrSection(BaseModel):
    """
    CFR Section Model.
    
    Represents a section within a part of the CFR.
    """
    
    # Section metadata
    section_number: str = Field(..., description="Section number (e.g. '50.1')")
    section_heading: str = Field(..., description="Section heading")
    section_content: Optional[str] = Field(None, description="Section content text")
    
    # Parent references
    part_number: int = Field(..., description="Part number this section belongs to")
    title_number: int = Field(..., description="Title number this section belongs to")
    
    # Source reference
    source_reference: Optional[SourceReference] = Field(None, description="Source reference information")
    
    # Publication information
    year: Optional[int] = Field(None, description="Year of CFR edition")
    date_issued: Optional[str] = Field(None, description="Date section was issued")


class CfrPart(BaseModel):
    """
    CFR Part Model.
    
    Represents a part within a chapter of the CFR.
    """
    
    # Part metadata
    part_number: int = Field(..., description="Part number")
    part_name: str = Field(..., description="Part name")
    
    # Parent references
    title_number: int = Field(..., description="Title number this part belongs to")
    chapter_number: str = Field(..., description="Chapter number this part belongs to")
    
    # Sections in this part
    sections: List[CfrSection] = Field(default_factory=list, description="Sections within this part")
    
    # Source reference
    source_reference: Optional[SourceReference] = Field(None, description="Source reference information")
    
    # Publication information
    year: Optional[int] = Field(None, description="Year of CFR edition")
    date_issued: Optional[str] = Field(None, description="Date part was issued")


class CourtType(str, Enum):
    """
    Court Type Enum.
    
    Enumeration of U.S. federal courts.
    """
    
    # Supreme Court
    SCOTUS = "Supreme Court of the United States"
    
    # Circuit Courts
    CADC = "United States Court of Appeals for the District of Columbia Circuit"
    CA1 = "United States Court of Appeals for the First Circuit"
    CA2 = "United States Court of Appeals for the Second Circuit"
    CA3 = "United States Court of Appeals for the Third Circuit"
    CA4 = "United States Court of Appeals for the Fourth Circuit"
    CA5 = "United States Court of Appeals for the Fifth Circuit"
    CA6 = "United States Court of Appeals for the Sixth Circuit"
    CA7 = "United States Court of Appeals for the Seventh Circuit"
    CA8 = "United States Court of Appeals for the Eighth Circuit"
    CA9 = "United States Court of Appeals for the Ninth Circuit"
    CA10 = "United States Court of Appeals for the Tenth Circuit"
    CA11 = "United States Court of Appeals for the Eleventh Circuit"
    CAFC = "United States Court of Appeals for the Federal Circuit"
    
    # District Courts added as needed


class CourtOpinion(BaseModel):
    """
    Court Opinion Model.
    
    Represents a federal court opinion.
    """
    
    # Opinion metadata
    package_id: str = Field(..., description="GovInfo package ID")
    title: str = Field(..., description="Opinion title")
    court: CourtType = Field(..., description="Court that issued the opinion")
    docket_number: str = Field(..., description="Docket number")
    
    # Date information
    date_issued: str = Field(..., description="Date opinion was issued (YYYY-MM-DD)")
    year: Optional[int] = Field(None, description="Year of opinion")
    
    # Additional metadata
    part_name: Optional[str] = Field(None, description="Name of part within volume")
    judges: Optional[List[str]] = Field(default_factory=list, description="Judges who authored or joined the opinion")
    
    # Content information
    content_urls: Dict[str, str] = Field(default_factory=dict, description="URLs to opinion content in different formats")
    summary: Optional[str] = Field(None, description="Opinion summary")
    
    # Source reference
    source_reference: Optional[SourceReference] = Field(None, description="Source reference information")
    
    @field_validator('year', mode='before')
    def derive_year(cls, v, info):
        """Derive year from date_issued if not provided."""
        values = info.data
        if v is None and 'date_issued' in values:
            try:
                return int(values['date_issued'].split('-')[0])
            except (ValueError, IndexError):
                pass
        return v


class FrDocumentType(str, Enum):
    """
    Federal Register Document Type Enum.
    
    Enumeration of Federal Register document types.
    """
    
    RULE = "Rule"
    PROPOSED_RULE = "Proposed Rule"
    NOTICE = "Notice"
    PRESIDENTIAL_DOCUMENT = "Presidential Document"
    CORRECTION = "Correction"


class FederalRegisterDocument(BaseModel):
    """
    Federal Register Document Model.
    
    Represents a document published in the Federal Register.
    """
    
    # Document metadata
    document_number: str = Field(..., description="Federal Register document number")
    title: str = Field(..., description="Document title")
    type: str = Field(..., description="Document type")
    agency: str = Field(..., description="Issuing agency")
    
    # Date information
    publication_date: str = Field(..., description="Publication date (YYYY-MM-DD)")
    effective_date: Optional[str] = Field(None, description="Effective date (YYYY-MM-DD)")
    
    # CFR impact
    cfr_references: List[Dict[str, Any]] = Field(default_factory=list, description="CFR titles and parts affected")
    
    # Additional metadata
    abstract: Optional[str] = Field(None, description="Document abstract")
    action: Optional[str] = Field(None, description="Action being taken")
    
    # Content information
    content_urls: Optional[Dict[str, str]] = Field(default_factory=dict, description="URLs to document content in different formats")
    
    # Source reference
    source_reference: Optional[SourceReference] = Field(None, description="Source reference information")


class RegulatoryProcessStatus(str, Enum):
    """
    Regulatory Process Status Enum.
    
    Enumeration of regulatory process statuses.
    """
    
    OPEN = "Open"
    CLOSED = "Closed"
    WITHDRAWN = "Withdrawn"
    COMPLETED = "Completed"


class RegulatoryProcess(BaseModel):
    """
    Regulatory Process Model.
    
    Represents an agency regulatory process.
    """
    
    # Process metadata
    process_id: str = Field(..., description="Process identifier (e.g., docket number)")
    title: str = Field(..., description="Process title")
    agency: str = Field(..., description="Agency conducting the process")
    status: str = Field(..., description="Current status of the process")
    
    # Date information
    start_date: str = Field(..., description="Start date (YYYY-MM-DD)")
    end_date: Optional[str] = Field(None, description="End date, if closed (YYYY-MM-DD)")
    
    # Related documents
    documents: List[Dict[str, Any]] = Field(default_factory=list, description="Documents related to this process")
    
    # CFR impact
    cfr_impacts: List[Dict[str, Any]] = Field(default_factory=list, description="CFR titles and parts impacted")
    
    # Additional metadata
    description: Optional[str] = Field(None, description="Process description")
    comments_count: Optional[int] = Field(None, description="Number of public comments received")
    
    # Source reference
    source_reference: Optional[SourceReference] = Field(None, description="Source reference information")