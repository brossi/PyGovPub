"""
Legislative data models for PyGovPub SDK.

This module defines Pydantic models for legislative data types
including bills, amendments, committees, and members.
"""

from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, HttpUrl

from pygovpub.auth.models import ApiSource


class Chamber(str, Enum):
    """Congressional chamber."""
    
    HOUSE = "house"
    SENATE = "senate"
    JOINT = "joint"


class BillType(str, Enum):
    """Types of legislative bills/resolutions."""
    
    HOUSE_BILL = "hr"
    SENATE_BILL = "s"
    HOUSE_JOINT_RESOLUTION = "hjres"
    SENATE_JOINT_RESOLUTION = "sjres"
    HOUSE_CONCURRENT_RESOLUTION = "hconres"
    SENATE_CONCURRENT_RESOLUTION = "sconres"
    HOUSE_RESOLUTION = "hres"
    SENATE_RESOLUTION = "sres"


class BillStatus(str, Enum):
    """Status of a bill in the legislative process."""
    
    INTRODUCED = "introduced"
    REFERRED = "referred"
    REPORTED = "reported"
    FAILED_PASSAGE = "failed_passage"
    PASSED_HOUSE = "passed_house"
    PASSED_SENATE = "passed_senate"
    PASSED_BOTH = "passed_both"
    RESOLVING_DIFFERENCES = "resolving_differences"
    TO_PRESIDENT = "to_president"
    VETOED = "vetoed"
    ENACTED = "enacted"
    BECAME_LAW = "became_law"


class BillVersionCode(str, Enum):
    """Standard codes for bill versions."""
    
    INTRODUCED_HOUSE = "ih"
    REPORTED_HOUSE = "rh"
    ENGROSSED_HOUSE = "eh"
    RECEIVED_IN_SENATE = "rds"
    REFERRED_IN_SENATE = "rfs"
    INTRODUCED_SENATE = "is"
    REPORTED_SENATE = "rs"
    ENGROSSED_SENATE = "es"
    RECEIVED_IN_HOUSE = "rdh"
    REFERRED_IN_HOUSE = "rfh"
    ENROLLED_BILL = "enr"
    PUBLIC_PRINT = "pp"


class SourceReference(BaseModel):
    """Reference to a data source."""
    
    source: ApiSource
    """API source that provided the data."""
    
    source_id: str
    """Identifier at the source."""
    
    source_url: Optional[HttpUrl] = None
    """URL to access the resource at the source."""
    
    last_updated: Optional[datetime] = None
    """When the data was last updated at the source."""


class PolicyArea(BaseModel):
    """Policy area classification."""
    
    name: str
    """Name of the policy area."""
    
    code: Optional[str] = None
    """Code for the policy area."""


class BillSummary(BaseModel):
    """Summary of a bill."""
    
    text: str
    """Summary text."""
    
    action_date: Optional[date] = None
    """Date associated with the action for this summary."""
    
    version_code: Optional[str] = None
    """Version code for the bill at the time of summary."""
    
    update_date: Optional[date] = None
    """Date the summary was last updated."""


class BillSponsor(BaseModel):
    """Sponsor of a bill."""
    
    bioguide_id: str
    """Bioguide ID for the member."""
    
    full_name: str
    """Full name of the sponsor."""
    
    first_name: Optional[str] = None
    """First name of the sponsor."""
    
    last_name: Optional[str] = None
    """Last name of the sponsor."""
    
    party: Optional[str] = None
    """Political party of the sponsor."""
    
    state: Optional[str] = None
    """State represented by the sponsor."""
    
    district: Optional[str] = None
    """District represented by the sponsor (House only)."""
    
    sponsor_type: str = "sponsor"
    """Type of sponsorship."""
    
    sponsor_date: Optional[date] = None
    """Date of sponsorship."""


class BillAction(BaseModel):
    """Action taken on a bill."""
    
    action_date: date
    """Date of the action."""
    
    text: str
    """Description of the action."""
    
    chamber: Optional[Chamber] = None
    """Chamber where the action occurred."""
    
    action_code: Optional[str] = None
    """Code for the action type."""
    
    action_type: Optional[str] = None
    """Type of action."""
    
    committee_id: Optional[str] = None
    """Committee ID if the action is committee-related."""
    
    committee_name: Optional[str] = None
    """Committee name if the action is committee-related."""


class BillVersion(BaseModel):
    """Version of a bill text."""
    
    version_code: BillVersionCode
    """Code for the version."""
    
    version_name: str
    """Name of the version."""
    
    publish_date: Optional[date] = None
    """Date the version was published."""
    
    govinfo_package_id: Optional[str] = None
    """Package ID in GovInfo.gov."""
    
    pdf_url: Optional[HttpUrl] = None
    """URL to the PDF version."""
    
    xml_url: Optional[HttpUrl] = None
    """URL to the XML version."""
    
    html_url: Optional[HttpUrl] = None
    """URL to the HTML version."""


class Bill(BaseModel):
    """Legislative bill or resolution."""
    
    # Core identifiers
    bill_id: str = Field(..., description="Unique identifier for the bill")
    congress: int = Field(..., description="Congress number")
    bill_type: BillType = Field(..., description="Type of bill or resolution")
    bill_number: int = Field(..., description="Number assigned to the bill")
    
    # Titles
    title: str = Field(..., description="Official title of the bill")
    short_title: Optional[str] = None
    popular_title: Optional[str] = None
    
    # Dates and status
    introduced_date: Optional[date] = None
    latest_action_date: Optional[date] = None
    status: Optional[BillStatus] = None
    
    # Origin information
    origin_chamber: Chamber
    
    # People and committees
    sponsor: Optional[BillSponsor] = None
    cosponsors: List[BillSponsor] = Field(default_factory=list)
    committees: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Content and versions
    versions: List[BillVersion] = Field(default_factory=list)
    actions: List[BillAction] = Field(default_factory=list)
    summaries: List[BillSummary] = Field(default_factory=list)
    
    # Classification
    policy_area: Optional[PolicyArea] = None
    subjects: List[str] = Field(default_factory=list)
    
    # Source information
    source_reference: SourceReference
    
    # Law information if enacted
    law_number: Optional[str] = None
    
    class Config:
        """Model configuration."""
        
        validate_assignment = True


class Member(BaseModel):
    """Congressional member (Representative or Senator)."""
    
    # Core identifiers
    bioguide_id: str = Field(..., description="Bioguide ID")
    first_name: str
    last_name: str
    full_name: Optional[str] = None
    
    # Current information
    state: str
    party: str
    chamber: Optional[Chamber] = None
    district: Optional[str] = None
    
    # Dates
    term_start: Optional[date] = None
    term_end: Optional[date] = None
    
    # Biographical details
    birth_year: Optional[int] = None
    death_year: Optional[int] = None
    
    # URLs and media
    official_url: Optional[HttpUrl] = None
    image_url: Optional[HttpUrl] = None
    
    # Contact info
    office_address: Optional[str] = None
    phone: Optional[str] = None
    
    # Terms of service
    terms: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Leadership positions
    leadership_positions: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Current member status
    is_active: bool = True
    
    # Source information
    source_reference: SourceReference


class Committee(BaseModel):
    """Congressional committee."""
    
    # Core identifiers
    committee_id: str = Field(..., description="Committee system code")
    name: str
    chamber: Chamber
    congress: int
    
    # Committee details
    committee_type: Optional[str] = None  # "standing", "joint", etc.
    jurisdiction: Optional[str] = None
    website: Optional[HttpUrl] = None
    
    # Members
    chair: Optional[Dict[str, Any]] = None
    ranking_member: Optional[Dict[str, Any]] = None
    members: List[Dict[str, Any]] = Field(default_factory=list)
    subcommittees: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Source information
    source_reference: SourceReference


class Amendment(BaseModel):
    """Legislative amendment to a bill."""
    
    # Core identifiers
    amendment_id: str = Field(..., description="Unique identifier for the amendment")
    number: str = Field(..., description="Amendment number")
    congress: int = Field(..., description="Congress number")
    
    # Related bill
    bill_id: Optional[str] = None
    
    # Amendment details
    title: Optional[str] = None
    description: Optional[str] = None
    purpose: Optional[str] = None
    
    # Dates
    submitted_date: Optional[date] = None
    latest_action_date: Optional[date] = None
    
    # People and committees
    sponsor: Optional[BillSponsor] = None
    cosponsors: List[BillSponsor] = Field(default_factory=list)
    
    # Actions
    actions: List[BillAction] = Field(default_factory=list)
    
    # Amendment type and status
    type: Optional[str] = None
    status: Optional[str] = None
    
    # Source information
    source_reference: SourceReference
    
    # Core identifiers
    committee_id: str = Field(..., description="Committee system code")
    name: str
    
    # Organization
    chamber: Chamber
    parent_committee_id: Optional[str] = None
    
    # Classification
    committee_type: str
    subcommittees: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Status
    is_current: bool = True
    
    # Congress information
    congress: int
    
    # Source information
    source_reference: SourceReference