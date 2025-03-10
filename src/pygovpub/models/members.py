"""
SQLModel-based member and vote database models.

This module defines database models for congressional members, their roles,
votes, and committee memberships.
"""

from datetime import date, datetime
from typing import List, Optional

from sqlmodel import Field, Relationship, SQLModel

from typing import TYPE_CHECKING
from pygovpub.models.base import BaseTable, BaseEntity

# Handle circular imports
if TYPE_CHECKING:
    from pygovpub.models.legislative_db import Member, Committee
else:
    # Use string references for runtime
    from typing import Any
    Member: Any
    Committee: Any


# CommitteeMember is now defined in legislative_db.py

# Update CommitteeMember relationships in legislative_db.py after Member is defined
def setup_committee_member_relationships():
    """Set up relationships for CommitteeMember class"""
    from pygovpub.models.legislative_db import CommitteeMember, Committee, Member
    
    # Add relationships to CommitteeMember
    CommitteeMember.committee = Relationship(Committee, back_populates="committee_members")
    CommitteeMember.member = Relationship(Member, back_populates="committee_memberships")


class Role(BaseTable, table=True):
    """Congressional role for a member."""
    
    __tablename__ = "roles"
    
    role_id: str = Field(primary_key=True)
    """Unique identifier for the role."""
    
    bioguide_id: str = Field(foreign_key="members.bioguide_id")
    """Member in this role."""
    
    congress_id: int = Field(foreign_key="congresses.congress_id")
    """Congress during which the role was held."""
    
    chamber: str = Field(max_length=10)
    # Valid values: 'house', 'senate'
    """Chamber where the role was held."""
    
    state: str = Field(max_length=2)
    """State represented in this role."""
    
    district: Optional[str] = None
    """District represented in this role (House only)."""
    
    party: str = Field(max_length=50)
    """Political party during this role."""
    
    leadership_title: Optional[str] = None
    """Leadership position, if any (Speaker, Majority Leader, etc.)."""
    
    start_date: date
    """When the role began."""
    
    end_date: Optional[date] = None
    """When the role ended (if applicable)."""
    
    # Relationships
    member: "Member" = Relationship(back_populates="roles")
    """Member in this role."""


class Vote(BaseTable, table=True):
    """Congressional vote."""
    
    __tablename__ = "votes"
    
    vote_id: str = Field(primary_key=True)
    """Unique identifier for the vote."""
    
    congress_id: int = Field(foreign_key="congresses.congress_id")
    """Congress during which the vote occurred."""
    
    chamber: str = Field(max_length=10)
    # Valid values: 'house', 'senate'
    """Chamber where the vote occurred."""
    
    vote_number: int
    """Number assigned to the vote within the congress and chamber."""
    
    vote_date: date
    """Date the vote occurred."""
    
    question: str
    """Question being voted on."""
    
    vote_type: str
    """Type of vote (roll call, voice, etc.)."""
    
    bill_id: Optional[str] = Field(default=None, foreign_key="bills.bill_id")
    """Bill being voted on, if applicable."""
    
    result: str
    """Result of the vote (passed, failed, etc.)."""
    
    # Relationships
    members: List[Member] = Relationship(
        back_populates="votes",
        link_model="MemberVote"
    )
    """Members who participated in this vote."""
    
    member_votes: List["MemberVote"] = Relationship(back_populates="vote")
    """Individual vote positions."""


class MemberVote(BaseTable, table=True):
    """Individual member's vote position."""
    
    __tablename__ = "member_votes"
    
    vote_id: str = Field(foreign_key="votes.vote_id", primary_key=True)
    """Vote being cast."""
    
    bioguide_id: str = Field(foreign_key="members.bioguide_id", primary_key=True)
    """Member casting the vote."""
    
    vote_position: str = Field(max_length=20)
    # Valid values: 'Yea', 'Nay', 'Present', 'Not Voting'
    """Position taken on the vote."""
    
    vote_cast_time: Optional[datetime] = None
    """When the vote was cast."""
    
    # Relationships
    vote: "Vote" = Relationship(back_populates="member_votes")
    """Vote being cast."""
    
    member: "Member" = Relationship(back_populates="member_votes")
    """Member casting the vote."""