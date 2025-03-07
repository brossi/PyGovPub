# Domain-Specific Glossary Integration: Implementation Recommendations

## Executive Summary

This document outlines a simple approach for integrating a legislative glossary into the PyGovPub SDK. The goal is to provide users with easy access to definitions of legislative terms they encounter while using the SDK.

## Core Implementation

### 1. Basic Term Model

```python
# models/glossary.py
from pydantic import BaseModel
from typing import Optional

class GlossaryTerm(BaseModel):
    """Simple model for legislative terms"""
    term: str
    definition: str
    category: Optional[str] = None  # e.g., "legislative", "procedural"
    source: Optional[str] = None    # e.g., "congress.gov/glossary"
```

### 2. Core Functions

```python
# glossary.py
from typing import List, Optional, Dict

class GlossaryService:
    """Basic glossary functionality"""

    def get_term(self, term: str) -> Optional[GlossaryTerm]:
        """Get definition for a specific term"""
        pass

    def search_terms(self, query: str) -> List[GlossaryTerm]:
        """Simple search for terms"""
        pass

    def enrich_text(self, text: str) -> Dict[str, str]:
        """Add term definitions to text content"""
        pass
```

## Usage

### Basic Usage

```python
from pygovpub import Client

# Initialize client
client = Client()

# Look up a term
term = client.glossary.get_term("bill")
print(f"{term.term}: {term.definition}")

# Get definitions in content
bill = client.get_bill("HR1234", include_definitions=True)
```

## Implementation Plan

1. **Phase 1: Core Functionality** (MVP)
   - Basic term storage and retrieval
   - Simple text search
   - Term lookup in API responses

2. **Phase 2: Enhancements** (If needed)
   - Add categories
   - Improve search
   - Add more terms

## Endpoint Integrations

### Bills API Integration

1. **Response Model Enhancement**
```python
class BillResponse(BaseModel):
    """Standard bill response model"""
    # ... existing fields ...

    glossary_terms: Optional[Dict[str, str]] = Field(
        None,
        description="Relevant glossary terms and definitions found in the bill text"
    )
```

2. **API Endpoint Update**
```python
@router.get("/{congress}/{bill_id}")
async def get_bill(
    congress: int,
    bill_id: str,
    include_definitions: bool = False,  # New parameter
    service: BillService = Depends()
) -> BillResponse:
    """
    Get bill information.

    Set include_definitions=true to include relevant glossary terms
    found in the bill text and title.
    """
    bill = await service.get_bill(bill_id, congress)

    if include_definitions:
        # Simple glossary enrichment
        terms = service.glossary.find_terms_in_text(
            f"{bill.title} {bill.summary if bill.summary else ''}"
        )
        if terms:
            bill.glossary_terms = terms

    return bill
```

3. **Service Integration**
```python
class BillService:
    """Service layer for bill operations"""

    def __init__(
        self,
        session: AsyncSession = Depends(get_session),
        glossary: GlossaryService = Depends()
    ):
        self.session = session
        self.glossary = glossary
```

### Committees API Integration

1. **Response Model Enhancement**
```python
class CommitteeResponse(BaseModel):
    """Standard committee response model"""
    # ... existing fields ...

    glossary_terms: Optional[Dict[str, str]] = Field(
        None,
        description="Relevant glossary terms and definitions found in committee information"
    )
```

2. **API Endpoint Update**
```python
@router.get("/{congress}/{committee_id}")
async def get_committee(
    congress: int,
    committee_id: str,
    include_definitions: bool = False,
    service: CommitteeService = Depends()
) -> CommitteeResponse:
    """
    Get committee information.

    Set include_definitions=true to include relevant glossary terms
    found in the committee description and jurisdiction.
    """
    committee = await service.get_committee(committee_id, congress)

    if include_definitions:
        # Simple glossary enrichment
        terms = service.glossary.find_terms_in_text(
            f"{committee.name} {committee.jurisdiction if committee.jurisdiction else ''}"
        )
        if terms:
            committee.glossary_terms = terms

    return committee
```

### Members API Integration

1. **Response Model Enhancement**
```python
class MemberResponse(BaseModel):
    """Standard member response model"""
    # ... existing fields ...

    glossary_terms: Optional[Dict[str, str]] = Field(
        None,
        description="Relevant glossary terms found in member information"
    )
```

2. **API Endpoint Update**
```python
@router.get("/{congress}/{member_id}")
async def get_member(
    congress: int,
    member_id: str,
    include_definitions: bool = False,
    service: MemberService = Depends()
) -> MemberResponse:
    """
    Get member information.

    Set include_definitions=true to include relevant glossary terms
    found in member roles and committee assignments.
    """
    member = await service.get_member(member_id, congress)

    if include_definitions:
        # Simple glossary enrichment
        terms = service.glossary.find_terms_in_text(
            f"{member.roles} {member.committee_assignments if member.committee_assignments else ''}"
        )
        if terms:
            member.glossary_terms = terms

    return member
```

### Amendments API Integration

1. **Response Model Enhancement**
```python
class AmendmentResponse(BaseModel):
    """Standard amendment response model"""
    # ... existing fields ...

    glossary_terms: Optional[Dict[str, str]] = Field(
        None,
        description="Relevant glossary terms found in amendment text"
    )
```

2. **API Endpoint Update**
```python
@router.get("/{congress}/{amendment_id}")
async def get_amendment(
    congress: int,
    amendment_id: str,
    include_definitions: bool = False,
    service: AmendmentService = Depends()
) -> AmendmentResponse:
    """
    Get amendment information.

    Set include_definitions=true to include relevant glossary terms
    found in the amendment purpose and text.
    """
    amendment = await service.get_amendment(amendment_id, congress)

    if include_definitions:
        # Simple glossary enrichment
        terms = service.glossary.find_terms_in_text(
            f"{amendment.purpose} {amendment.text if amendment.text else ''}"
        )
        if terms:
            amendment.glossary_terms = terms

    return amendment
```

### Service Integration Pattern
All services follow the same dependency injection pattern:

```python
class BaseService:
    """Base service with glossary integration"""

    def __init__(
        self,
        session: AsyncSession = Depends(get_session),
        glossary: GlossaryService = Depends()
    ):
        self.session = session
        self.glossary = glossary
```

### Integration Benefits
1. Minimal impact on existing code
2. Optional functionality (backward compatible)
3. Easy to extend to other endpoints
4. Focused on high-value content (bill text and summaries)
5. Simple implementation path

## Data Source

Initial glossary terms will be sourced from:
- Congress.gov's glossary
- Senate.gov's glossary
- House.gov's glossary

## Best Practices

1. Keep definitions clear and concise
2. Use official sources for terms
3. Focus on commonly used terms first
4. Keep the implementation simple

## Conclusion

This minimal implementation provides the essential glossary functionality needed for the SDK while remaining simple to maintain and use.
