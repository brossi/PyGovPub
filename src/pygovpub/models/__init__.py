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
]