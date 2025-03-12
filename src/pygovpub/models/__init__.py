"""
Data models for PyGovPub.

This package contains all data models for the PyGovPub SDK, including:
- Pydantic models for API data
- SQLModel models for database storage 
- Response models for API responses
- Enums for consistent type checking
"""

# Import legislative models (Pydantic)
from pygovpub.models.legislative import (
    Chamber,
    BillType,
    BillStatus,
    BillVersionCode,
    SourceReference,
    PolicyArea,
    BillSummary,
    BillSponsor as BillSponsorData,
    BillAction as BillActionData,
    BillVersion as BillVersionData,
    Bill as BillData,
    Member as MemberData,
    Committee as CommitteeData
)

# Import response models
from pygovpub.models.response import (
    ResponseMetadata,
    PaginationInfo,
    ApiError,
    ApiResponse
)

# Import transformers
from pygovpub.models.transformers import (
    transform_congress_response,
    transform_govinfo_response,
    create_error_response
)

# Import base models (SQLModel)
from pygovpub.models.base import (
    BaseTable,
    BaseEntity
)

# Import regulatory models (Pydantic)
from pygovpub.models.regulatory import (
    # CFR models
    CfrTitle,
    CfrChapter,
    CfrPart,
    CfrSection,
    # Court Opinion models
    CourtType,
    CourtOpinion,
    # Federal Register models
    FrDocumentType,
    FederalRegisterDocument,
    # Regulatory Process models
    RegulatoryProcessStatus,
    RegulatoryProcess
)

# Import citation models (Pydantic)
from pygovpub.models.citation import (
    # Citation models
    CitationType,
    Citation,
    # Resolution models
    ResolutionStatus,
    ResolutionMethod,
    ReferenceResolution,
    # Relationship models
    RelationshipType,
    BidirectionalLink
)

# Import relationship models (Pydantic)
from pygovpub.models.relationship import (
    # Entity types
    EntityType,
    # Relationship types
    RelationshipDirection,
    # Hierarchy models
    HierarchicalRelationship,
    # Many-to-many models
    ManyToManyMapping,
    # Temporal models
    HistoricalState,
    TemporalRelationship,
    # Constraint models
    RelationshipConstraint
)

# Import advanced metadata models (Pydantic)
from pygovpub.models.advanced_metadata import (
    # Version history models
    VersionAction,
    VersionHistory,
    # Audit trail models
    AuditAction,
    AuditTrail,
    # Provenance models
    ProvenanceAgent,
    ProvenanceRecord,
    # Access control models
    AccessLevel,
    AccessControl
)

# Import model optimization tools
from pygovpub.models.optimization import (
    # Optimized model base class
    OptimizedModel,
    # Lazy loading
    LazyLoadableModel,
    lazy_load,
    # Batch processing
    BatchProcessor,
    batch_process,
    # Serialization optimization
    SerializationOptimizer
)

# Import other models gradually as they are needed
# Database models will be imported here once they are fully tested

__all__ = [
    # Legislative models (Pydantic)
    "Chamber", "BillType", "BillStatus", "BillVersionCode",
    "SourceReference", "PolicyArea", "BillSummary",
    "BillSponsorData", "BillActionData", "BillVersionData",
    "BillData", "MemberData", "CommitteeData",
    
    # Response models
    "ResponseMetadata", "PaginationInfo", "ApiError", "ApiResponse",
    
    # Transformers
    "transform_congress_response", "transform_govinfo_response", "create_error_response",
    
    # Base models (SQLModel)
    "BaseTable", "BaseEntity",
    
    # Regulatory models
    "CfrTitle", "CfrChapter", "CfrPart", "CfrSection",
    "CourtType", "CourtOpinion",
    "FrDocumentType", "FederalRegisterDocument",
    "RegulatoryProcessStatus", "RegulatoryProcess",
    
    # Citation models
    "CitationType", "Citation",
    "ResolutionStatus", "ResolutionMethod", "ReferenceResolution",
    "RelationshipType", "BidirectionalLink",
    
    # Complex relationship models
    "EntityType", "RelationshipDirection",
    "HierarchicalRelationship", "ManyToManyMapping",
    "HistoricalState", "TemporalRelationship", "RelationshipConstraint",
    
    # Advanced metadata models
    "VersionAction", "VersionHistory",
    "AuditAction", "AuditTrail",
    "ProvenanceAgent", "ProvenanceRecord",
    "AccessLevel", "AccessControl",
    
    # Model optimization tools
    "OptimizedModel", "LazyLoadableModel", "lazy_load",
    "BatchProcessor", "batch_process", "SerializationOptimizer",
]