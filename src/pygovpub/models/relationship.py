"""
Relationship Models Module.

This module provides models for complex relationships between entities,
including hierarchical relationships, many-to-many mappings, temporal
relationships, and relationship constraints.
"""

from typing import Dict, List, Optional, Any, Union, Set
from enum import Enum, auto
from datetime import datetime, date
from pydantic import BaseModel, Field, field_validator

from pygovpub.models.documents import DocumentType, SourceReference
from pygovpub.auth.models import ApiSource


class EntityType(str, Enum):
    """
    Entity Type Enum.
    
    Enumeration of entity types that can participate in relationships.
    """
    
    BILL = "bill"
    MEMBER = "member"
    COMMITTEE = "committee"
    CFR_TITLE = "cfr_title"
    CFR_PART = "cfr_part"
    CFR_SECTION = "cfr_section"
    COURT_OPINION = "court_opinion"
    FEDERAL_REGISTER = "federal_register"
    PUBLIC_LAW = "public_law"
    DOCUMENT = "document"
    AMENDMENT = "amendment"
    OTHER = "other"


class RelationshipDirection(str, Enum):
    """
    Relationship Direction Enum.
    
    Enumeration of relationship directions.
    """
    
    SOURCE_TO_TARGET = "source_to_target"
    TARGET_TO_SOURCE = "target_to_source"
    BIDIRECTIONAL = "bidirectional"


class HierarchicalRelationship(BaseModel):
    """
    Hierarchical Relationship Model.
    
    Represents a parent-child relationship between entities.
    """
    
    # Relationship metadata
    relationship_id: str = Field(..., description="Unique identifier for this relationship")
    
    # Parent information
    parent_id: str = Field(..., description="ID of the parent entity")
    parent_type: EntityType = Field(..., description="Type of the parent entity")
    
    # Child information
    child_id: str = Field(..., description="ID of the child entity")
    child_type: EntityType = Field(..., description="Type of the child entity")
    
    # Relationship information
    relationship_type: str = Field(..., description="Type of hierarchical relationship")
    
    # Temporal information
    start_date: Optional[str] = Field(None, description="When this relationship became effective")
    end_date: Optional[str] = Field(None, description="When this relationship ended (if applicable)")
    
    # Additional properties
    properties: Dict[str, Any] = Field(default_factory=dict, description="Additional properties of the relationship")
    
    # Metadata
    created_at: Optional[datetime] = Field(None, description="When this relationship was created")
    updated_at: Optional[datetime] = Field(None, description="When this relationship was last updated")


class ManyToManyMapping(BaseModel):
    """
    Many-to-Many Mapping Model.
    
    Represents a many-to-many relationship between collections of entities.
    """
    
    # Mapping metadata
    mapping_id: str = Field(..., description="Unique identifier for this mapping")
    
    # Entity A collection information
    entity_a_collection: str = Field(..., description="Name of entity A collection")
    entity_a_type: EntityType = Field(..., description="Type of entities in collection A")
    
    # Entity B collection information
    entity_b_collection: str = Field(..., description="Name of entity B collection")
    entity_b_type: EntityType = Field(..., description="Type of entities in collection B")
    
    # Mapping data
    mappings: List[Dict[str, Any]] = Field(..., description="List of mappings between entities")
    
    # Mapping information
    mapping_type: str = Field(..., description="Type of mapping relationship")
    direction: RelationshipDirection = Field(RelationshipDirection.SOURCE_TO_TARGET, description="Direction of the relationship")
    
    # Temporal information
    effective_date: Optional[str] = Field(None, description="When this mapping became effective")
    expiration_date: Optional[str] = Field(None, description="When this mapping expires/expired")
    
    # Metadata
    created_at: Optional[datetime] = Field(None, description="When this mapping was created")
    updated_at: Optional[datetime] = Field(None, description="When this mapping was last updated")


class HistoricalState(BaseModel):
    """
    Historical State Model.
    
    Represents a historical state of an entity in a temporal relationship.
    """
    
    # State metadata
    state_id: str = Field(..., description="Unique identifier for this state")
    state_type: str = Field(..., description="Type of state")
    
    # Temporal information
    timestamp: str = Field(..., description="When this state was recorded")
    
    # State details
    properties: Dict[str, Any] = Field(default_factory=dict, description="Properties of this state")
    
    # Reference information
    reference_id: Optional[str] = Field(None, description="ID of a reference document/entity")
    reference_type: Optional[str] = Field(None, description="Type of reference document/entity")


class TemporalRelationship(BaseModel):
    """
    Temporal Relationship Model.
    
    Represents the temporal history of an entity's states.
    """
    
    # Relationship metadata
    temporal_id: str = Field(..., description="Unique identifier for this temporal relationship")
    
    # Entity information
    entity_id: str = Field(..., description="ID of the entity")
    entity_type: EntityType = Field(..., description="Type of the entity")
    
    # Historical states
    history: List[Dict[str, Any]] = Field(..., description="List of historical states")
    
    # Current state
    current_state_id: str = Field(..., description="ID of the current state")
    
    # Temporal range
    start_date: Optional[str] = Field(None, description="Start date of the temporal range")
    end_date: Optional[str] = Field(None, description="End date of the temporal range")
    
    # Metadata
    created_at: Optional[datetime] = Field(None, description="When this relationship was created")
    updated_at: Optional[datetime] = Field(None, description="When this relationship was last updated")


class RelationshipConstraint(BaseModel):
    """
    Relationship Constraint Model.
    
    Represents constraints on relationships between entities.
    """
    
    # Constraint metadata
    constraint_id: str = Field(..., description="Unique identifier for this constraint")
    
    # Relationship information
    relationship_type: str = Field(..., description="Type of relationship this constraint applies to")
    
    # Entity types
    source_entity_type: EntityType = Field(..., description="Type of source entity")
    target_entity_type: EntityType = Field(..., description="Type of target entity")
    
    # Constraint details
    cardinality: str = Field(..., description="Cardinality of the relationship (ONE_TO_ONE, ONE_TO_MANY, etc.)")
    required: bool = Field(False, description="Whether the relationship is required")
    
    # Validation rules
    validation_rules: List[Dict[str, Any]] = Field(default_factory=list, description="Rules for validating the relationship")
    
    # Description
    description: Optional[str] = Field(None, description="Description of the constraint")