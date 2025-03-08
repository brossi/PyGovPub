# [LM-BT-001] Bill Status Information Retrieval

## Context & Goal
**As a** [Policy Professional](../../personas.md#policy-professional),
**I want to** retrieve authoritative bill status information,
**So that** I can track legislative developments accurately and reliably.

## Acceptance Criteria
- [ ] Bill Identification
  - Accept bill identifiers in both Congress.gov and GovInfo.gov formats
  - Support standard bill types:

    | Abbreviation | Full Name |
    |-------------|-----------|
    | HR | House Bill |
    | S | Senate Bill |
    | HJRES | House Joint Resolution |
    | SJRES | Senate Joint Resolution |
    | HCONRES | House Concurrent Resolution |
    | SCONRES | Senate Concurrent Resolution |
    | HRES | House Simple Resolution |
    | SRES | Senate Simple Resolution |

  - Validate congress numbers against available ranges
  - Handle version identifiers:

    | Abbreviation | Description |
    |-------------|-------------|
    | enr | Enrolled Bill |
    | ih | Introduced in House |
    | is | Introduced in Senate |
    | rfs | Referred to Senate |
    | rhs | Referred to House |

  - Provide clear feedback for invalid identifiers
  - Support single bill and batch operations

- [ ] Status Information
  - Retrieve current bill status
  - Include official status codes and descriptions
  - Provide timestamps for all status changes
  - Ensure data is from authoritative sources
  - Include relevant bill text when available

- [ ] Data Quality
  - Cross-validate status information
  - Verify data authenticity
  - Track information provenance
  - Log validation results
  - Handle conflicting information gracefully

## Technical Context
- Multiple authoritative data sources available
- Rate limits and authentication required
- Status information may need reconciliation
- Response formats require standardization
- Data freshness requirements vary by field

## Related
### User Stories
- LM-BT-002: Bill Action History Tracking
- LM-BT-003: Bill Status Change Notifications

## Status
- Version: 1.1.1
- Status: Active
- Last Updated: 2025-03-07 21:51 UTC

- Change History:
  - 1.1.1: Removed redundant Personas section
  - 1.1.0: Added comprehensive version identifier support and enhanced data quality requirements
  - 1.0.0: Expanded scope to support both Congress.gov and GovInfo.gov APIs
  - 0.1.0: Initial draft with Congress.gov focus
