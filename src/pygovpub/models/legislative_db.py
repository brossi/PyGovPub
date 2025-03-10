"""
SQLModel-based legislative database models.

This module defines database models for legislative data including bills,
congresses, committees, and bill versions.
"""

from datetime import date, datetime
from enum import Enum
from typing import List, Optional

from sqlmodel import Field, Relationship, SQLModel

from pygovpub.models.base import BaseTable, BaseEntity


class Congress(BaseTable, table=True):
    """Congress session tracking."""
    
    __tablename__ = "congresses"
    
    congress_id: int = Field(primary_key=True)
    """Numeric identifier for the congress (e.g. 118)."""
    
    start_date: date
    """When the congress session started."""
    
    end_date: date
    """When the congress session ends/ended."""
    
    # Relationships
    bills: List["Bill"] = Relationship(back_populates="congress")
    """Bills introduced in this congress."""
    
    committees: List["Committee"] = Relationship(back_populates="congress")
    """Committees active in this congress."""


class Bill(BaseTable, table=True):
    """Legislative bill tracking."""
    
    __tablename__ = "bills"
    
    bill_id: str = Field(primary_key=True)
    """Unique identifier for the bill (e.g. '118-hr1')."""
    
    congress_id: int = Field(foreign_key="congresses.congress_id")
    """Congress in which the bill was introduced."""
    
    bill_type: str = Field(max_length=10)
    # Valid values: 'hr', 's', 'hjres', 'sjres', 'hconres', 'sconres', 'hres', 'sres'
    """Type of bill (e.g. 'hr', 's', 'hjres', etc.)."""
    
    bill_number: int
    """Number assigned to the bill."""
    
    title: str
    """Official title of the bill."""
    
    introduced_date: Optional[date] = None
    """Date the bill was introduced."""
    
    status: Optional[str] = None
    """Current status of the bill."""
    
    last_action_date: Optional[date] = None
    """Date of the most recent action on the bill."""
    
    source_system: str = Field(max_length=10)
    # Valid values: 'govinfo', 'congress'
    """System that provided this bill record."""
    
    # Relationships
    congress: Optional[Congress] = Relationship(back_populates="bills")
    """Congress in which the bill was introduced."""
    
    versions: List["BillVersion"] = Relationship(back_populates="bill")
    """Different versions of the bill text."""
    
    sponsors: List["BillSponsor"] = Relationship(back_populates="bill")
    """Sponsors and cosponsors of the bill."""
    
    actions: List["BillAction"] = Relationship(back_populates="bill")
    """Actions taken on the bill."""
    
    # documents relationship is added after DocumentReference is imported


class BillVersion(BaseTable, table=True):
    """Bill version tracking."""
    
    __tablename__ = "bill_versions"
    
    version_id: str = Field(primary_key=True)
    """Unique identifier for the bill version."""
    
    bill_id: str = Field(foreign_key="bills.bill_id")
    """Bill that this version is associated with."""
    
    version_code: str = Field(max_length=10)
    # Valid values: 'ih', 'rh', 'eh', 'rcs', 'rs', 'es', 'enr', 'rdh', 'rah', 'rds', 'ras'
    """Code for the version (e.g. 'ih', 'rh', 'eh', etc.)."""
    
    published_date: Optional[date] = None
    """When this version was published."""
    
    govinfo_package_id: Optional[str] = Field(unique=True, default=None)
    """GovInfo.gov package ID for this version."""
    
    # Relationships
    bill: Optional[Bill] = Relationship(back_populates="versions")
    """Bill that this version is associated with."""


class BillAction(BaseTable, table=True):
    """Action taken on a bill."""
    
    __tablename__ = "bill_actions"
    
    action_id: Optional[int] = Field(default=None, primary_key=True)
    """Unique identifier for the action."""
    
    bill_id: str = Field(foreign_key="bills.bill_id")
    """Bill that this action is associated with."""
    
    action_date: date
    """Date the action occurred."""
    
    action_text: str
    """Description of the action."""
    
    action_type: Optional[str] = None
    """Type of action taken."""
    
    chamber: Optional[str] = Field(default=None, max_length=10)
    # Valid values: 'house', 'senate', 'both', NULL
    """Chamber where the action occurred."""
    
    committee_id: Optional[str] = Field(default=None, foreign_key="committees.committee_id")
    """Committee that took the action, if applicable."""
    
    # Relationships
    bill: Optional[Bill] = Relationship(back_populates="actions")
    """Bill that this action is associated with."""
    
    committee: Optional["Committee"] = Relationship(back_populates="actions")
    """Committee that took the action, if applicable."""


# Forward declare CommitteeMember for use in relationships
class CommitteeMember(BaseTable, table=True):
    """Committee membership linking members to committees."""
    
    __tablename__ = "committee_members"
    
    committee_id: str = Field(foreign_key="committees.committee_id", primary_key=True)
    """Committee the member serves on."""
    
    bioguide_id: str = Field(foreign_key="members.bioguide_id", primary_key=True)
    """Member serving on the committee."""
    
    role: str = Field(max_length=50)
    """Role on the committee (Chair, Ranking Member, etc.)."""
    
    start_date: Optional[date] = None
    """When the member began serving in this role."""
    
    end_date: Optional[date] = None
    """When the member ended serving in this role (if applicable)."""


class Committee(BaseTable, table=True):
    """Committee tracking."""
    
    __tablename__ = "committees"
    
    committee_id: str = Field(primary_key=True)
    """Unique identifier for the committee."""
    
    congress_id: int = Field(foreign_key="congresses.congress_id")
    """Congress the committee is part of."""
    
    name: str
    """Name of the committee."""
    
    chamber: str = Field(max_length=10)
    # Valid values: 'house', 'senate', 'joint'
    """Chamber the committee belongs to."""
    
    parent_committee_id: Optional[str] = Field(default=None, foreign_key="committees.committee_id")
    """Parent committee for subcommittees."""
    
    # Relationships
    congress: Optional[Congress] = Relationship(back_populates="committees")
    """Congress the committee is part of."""
    
    actions: List[BillAction] = Relationship(back_populates="committee")
    """Actions taken by this committee."""
    
    # These relationships will be set up in setup_committee_member_relationship
    
    subcommittees: List["Committee"] = Relationship(
        sa_relationship_kwargs={
            "primaryjoin": "Committee.committee_id==Committee.parent_committee_id",
            "remote_side": "[Committee.parent_committee_id]"
        }
    )
    """Subcommittees under this committee."""


class BillSponsor(BaseTable, table=True):
    """Sponsor of a bill."""
    
    __tablename__ = "bill_sponsors"
    
    bill_id: str = Field(foreign_key="bills.bill_id", primary_key=True)
    """Bill being sponsored."""
    
    bioguide_id: str = Field(foreign_key="members.bioguide_id", primary_key=True)
    """Member sponsoring the bill."""
    
    sponsor_type: str = Field()
    # Valid values: 'sponsor', 'cosponsor', 'withdrawn'
    """Type of sponsorship."""
    
    sponsor_date: Optional[date] = None
    """Date of sponsorship."""
    
    # Relationships
    bill: Bill = Relationship(back_populates="sponsors")
    """Bill being sponsored."""
    
    member: "Member" = Relationship(back_populates="sponsored_bills")
    """Member sponsoring the bill."""


class Member(BaseTable, table=True):
    """Congressional member (Representative or Senator)."""
    
    __tablename__ = "members"
    
    bioguide_id: str = Field(primary_key=True)
    """Bioguide ID for the member."""
    
    first_name: str
    """First name of the member."""
    
    last_name: str
    """Last name of the member."""
    
    state: str = Field(max_length=2)
    """State represented by the member."""
    
    party: str = Field(max_length=50)
    """Political party of the member."""
    
    active: bool = Field(default=True)
    """Whether the member is currently serving."""
    
    # Relationships
    sponsored_bills: List[BillSponsor] = Relationship(back_populates="member")
    """Bills sponsored by this member."""
    
    # Committee relationships will be set up in setup_committee_member_relationship
    
    # Role relationship will be set up later
    # roles: List["Role"] = Relationship(back_populates="member")
    
    # Votes relationship will be set up later
    # votes: List["Vote"] = Relationship(
    #     back_populates="members",
    #     sa_relationship_kwargs={"secondary": "member_votes"}
    # )
    # 
    # member_votes: List["MemberVote"] = Relationship(back_populates="member")
    # """Vote positions for this member."""


# Import DocumentReference from documents.py to avoid duplication
# Import at the end of the file to avoid circular imports
from pygovpub.models.documents import DocumentReference

# Setup document_bill relationship at module import time
def setup_bill_document_relationship():
    """
    Setup the relationship between Bill and DocumentReference.
    Called after both classes are defined.
    """
    # Define Bill class attribute for documents
    setattr(Bill, "documents", Relationship(
        back_populates="bill",
        sa_relationship_kwargs={"foreign_keys": "[DocumentReference.bill_id]"}
    ))
    
    # Define DocumentReference class attribute for bill
    setattr(DocumentReference, "bill", Relationship(
        back_populates="documents",
        sa_relationship_kwargs={"foreign_keys": "[DocumentReference.bill_id]"}
    ))


def setup_committee_member_relationship():
    """
    Setup the relationship between Committee, Member and CommitteeMember.
    Called after all three classes are defined.
    """
    # Define CommitteeMember relationship to Committee
    setattr(CommitteeMember, "committee", Relationship(
        sa_relationship_kwargs={"foreign_keys": "[CommitteeMember.committee_id]"}
    ))
    
    # Define CommitteeMember relationship to Member
    setattr(CommitteeMember, "member", Relationship(
        sa_relationship_kwargs={"foreign_keys": "[CommitteeMember.bioguide_id]"}
    ))
    
    # Define Committee relationship to members through CommitteeMember
    setattr(Committee, "members", Relationship(
        sa_relationship_kwargs={
            "secondary": "committee_members",
            "overlaps": "committee_members"
        }
    ))
    
    # Define Committee relationship to CommitteeMember
    setattr(Committee, "committee_members", Relationship(
        sa_relationship_kwargs={"overlaps": "members"}
    ))
    
    # Define Member relationship to committees through CommitteeMember
    setattr(Member, "committees", Relationship(
        sa_relationship_kwargs={
            "secondary": "committee_members",
            "overlaps": "committee_memberships"
        }
    ))
    
    # Define Member relationship to CommitteeMember
    setattr(Member, "committee_memberships", Relationship(
        sa_relationship_kwargs={"overlaps": "committees"}
    ))


# Call the setup functions to establish relationships
setup_bill_document_relationship()
setup_committee_member_relationship()