"""
Advanced Metadata Models Module.

This module provides models for advanced metadata capabilities including:
- Version history tracking
- Audit trails
- Provenance records
- Access control
"""

from typing import Dict, List, Optional, Any, Union, Set
from enum import Enum, auto
from datetime import datetime, date
from pydantic import BaseModel, Field, field_validator

from pygovpub.models.documents import DocumentType, SourceReference
from pygovpub.auth.models import ApiSource


class VersionAction(str, Enum):
    """
    Version Action Enum.
    
    Enumeration of actions that can be performed on versions.
    """
    
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    RESTORE = "restore"
    MERGE = "merge"
    BRANCH = "branch"
    TAG = "tag"


class VersionHistory(BaseModel):
    """
    Version History Model.
    
    Represents the version history of an entity.
    """
    
    # Entity information
    entity_id: str = Field(..., description="ID of the entity")
    entity_type: str = Field(..., description="Type of the entity")
    
    # Version information
    current_version: str = Field(..., description="ID of the current version")
    versions: List[Dict[str, Any]] = Field(..., description="List of versions")
    
    # Additional metadata
    created_at: Optional[datetime] = Field(None, description="When this history record was created")
    updated_at: Optional[datetime] = Field(None, description="When this history record was last updated")
    
    @field_validator('versions')
    def validate_versions(cls, v):
        """Validate that versions contain required fields."""
        required_fields = {"version_id", "timestamp", "action"}
        for version in v:
            if not required_fields.issubset(set(version.keys())):
                missing = required_fields - set(version.keys())
                raise ValueError(f"Version missing required fields: {missing}")
        return v


class AuditAction(str, Enum):
    """
    Audit Action Enum.
    
    Enumeration of actions that can be audited.
    """
    
    VIEW = "view"
    CREATE = "create"
    EDIT = "edit"
    DELETE = "delete"
    EXPORT = "export"
    IMPORT = "import"
    LOGIN = "login"
    LOGOUT = "logout"
    SEARCH = "search"
    DOWNLOAD = "download"
    UPLOAD = "upload"
    SHARE = "share"
    PERMISSION_CHANGE = "permission_change"
    API_ACCESS = "api_access"
    OTHER = "other"


class AuditTrail(BaseModel):
    """
    Audit Trail Model.
    
    Represents an audit trail for an entity, recording various actions.
    """
    
    # Entity information
    entity_id: str = Field(..., description="ID of the entity")
    entity_type: str = Field(..., description="Type of the entity")
    
    # Audit records
    audit_records: List[Dict[str, Any]] = Field(..., description="List of audit records")
    
    # Additional metadata
    created_at: Optional[datetime] = Field(None, description="When this audit trail was created")
    updated_at: Optional[datetime] = Field(None, description="When this audit trail was last updated")
    
    @field_validator('audit_records')
    def validate_audit_records(cls, v):
        """Validate that audit records contain required fields."""
        required_fields = {"record_id", "timestamp", "action"}
        for record in v:
            if not required_fields.issubset(set(record.keys())):
                missing = required_fields - set(record.keys())
                raise ValueError(f"Audit record missing required fields: {missing}")
        return v


class ProvenanceAgent(str, Enum):
    """
    Provenance Agent Enum.
    
    Enumeration of agent types for provenance attribution.
    """
    
    PERSON = "person"
    ORGANIZATION = "organization"
    SOFTWARE = "software"
    SERVICE = "service"
    UNKNOWN = "unknown"


class ProvenanceRecord(BaseModel):
    """
    Provenance Record Model.
    
    Represents the provenance of an entity, recording its origin and derivation.
    """
    
    # Provenance metadata
    provenance_id: str = Field(..., description="Unique identifier for this provenance record")
    
    # Entity information
    entity_id: str = Field(..., description="ID of the entity")
    entity_type: str = Field(..., description="Type of the entity")
    
    # Source information
    source_system: str = Field(..., description="System from which the entity was sourced")
    attribution: Dict[str, Any] = Field(..., description="Attribution information")
    
    # Derivation information
    derived_from: List[str] = Field(default_factory=list, description="IDs of source entities")
    
    # Temporal information
    generation_time: str = Field(..., description="When the entity was generated")
    
    # Methodology information
    methodology: Optional[str] = Field(None, description="Methodology used to create the entity")
    confidence_level: Optional[float] = Field(None, description="Confidence level in the data")
    
    # Additional metadata
    created_at: Optional[datetime] = Field(None, description="When this provenance record was created")
    updated_at: Optional[datetime] = Field(None, description="When this provenance record was last updated")
    
    @field_validator('attribution')
    def validate_attribution(cls, v):
        """Validate that attribution contains required fields."""
        required_fields = {"agent_id", "agent_type"}
        if not required_fields.issubset(set(v.keys())):
            missing = required_fields - set(v.keys())
            raise ValueError(f"Attribution missing required fields: {missing}")
        return v


class AccessLevel(str, Enum):
    """
    Access Level Enum.
    
    Enumeration of access levels for entities.
    """
    
    PRIVATE = "private"
    RESTRICTED = "restricted"
    INTERNAL = "internal"
    PUBLIC = "public"
    EMBARGOED = "embargoed"


class AccessControl(BaseModel):
    """
    Access Control Model.
    
    Represents access control settings for an entity.
    """
    
    # Entity information
    entity_id: str = Field(..., description="ID of the entity")
    entity_type: str = Field(..., description="Type of the entity")
    
    # Ownership
    owner_id: str = Field(..., description="ID of the entity owner")
    
    # Access level
    access_level: AccessLevel = Field(..., description="Access level for the entity")
    
    # Permissions
    permissions: List[Dict[str, Any]] = Field(default_factory=list, description="List of permissions")
    
    # Temporal restrictions
    embargo_until: Optional[str] = Field(None, description="When the embargo expires (if applicable)")
    
    # Additional restrictions
    restrictions: List[str] = Field(default_factory=list, description="List of restrictions")
    
    # Additional metadata
    created_at: Optional[datetime] = Field(None, description="When this access control record was created")
    updated_at: Optional[datetime] = Field(None, description="When this access control record was last updated")
    
    @field_validator('permissions')
    def validate_permissions(cls, v):
        """Validate that permissions contain required fields."""
        for permission in v:
            if not any(key in permission for key in ["user_id", "group_id", "role_id"]):
                raise ValueError("Permission must include user_id, group_id, or role_id")
            if "permission" not in permission:
                raise ValueError("Permission must include a permission value")
        return v