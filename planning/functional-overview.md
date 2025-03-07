# PyGovPub: Unified Federal Government Data SDK

## Overview

PyGovPub is a Python SDK that provides unified access to U.S. Federal Government public data and information by seamlessly integrating the GovInfo.gov and Congress.gov APIs. This SDK abstracts away the complexity of choosing between data sources, allowing users to focus on what information they need rather than where to find it.

## Core Design Principles

1. **Source-Appropriate Routing**: Automatically routes requests to the optimal data source based on documented strengths:
   - Congress.gov for legislative process, member data, and real-time updates
   - GovInfo.gov for authenticated documents and historical records
2. **Smart Response Normalization**: Handles the different data structures:
   - Congress.gov's nested JSON with relationships (24-hour refresh cycle)
   - GovInfo.gov's flat metadata with authenticated document links
3. **Resource Management**:
   - GovInfo.gov: 1,000 requests/hour (bulk downloads exempt)
   - Congress.gov: 5,000 requests/hour
   - Automatic rate limit tracking and quota management
   - Usage monitoring and analytics
   - Error tracking and reporting
4. **Type Safety**: Full typing support for modern Python development
5. **Data Integrity**:
   - Document authentication verification
   - Digital signature validation
   - Source system tracking
   - Version conflict resolution
   - Historical data partitioning

## High-Level Architecture

### 1. Core Components

```
pygovpub/
├── core/
│   ├── client.py          # Main client interface
│   ├── auth.py           # Dual API authentication
│   ├── config.py         # Configuration management
│   ├── sync.py          # Data synchronization
│   ├── monitor.py       # API usage tracking
│   └── exceptions.py     # Custom exceptions
├── sources/
│   ├── govinfo/         # GovInfo.gov integration
│   │   ├── documents.py # Document retrieval
│   │   ├── bulk.py     # Bulk data handling
│   │   ├── auth.py     # Document authentication
│   │   └── search.py    # Full-text search
│   └── congress/        # Congress.gov integration
│       ├── legislative.py # Process tracking
│       ├── members.py    # Member data
│       ├── treaties.py   # Treaty tracking
│       └── nominations.py # Executive nominations
├── models/
│   ├── common.py        # Shared data models
│   ├── legislative.py   # Legislative content models
│   ├── executive.py     # Executive branch models
│   └── federal.py       # Federal document models
└── utils/
    ├── cache.py         # Caching mechanisms
    ├── rate_limit.py    # Rate limit tracking
    ├── validation.py    # Input validation
    ├── sync.py         # Sync management
    └── verify.py       # Signature verification
```

### 2. Primary Resource Categories

#### Congress.gov Primary
- Legislative Process Tracking
  - Bill status and actions (24-hour refresh cycle)
  - Committee activities and reports
  - Amendment relationships
- Member Information
  - Bioguide IDs and profiles
  - Committee assignments
  - Sponsorship networks
- Real-time Updates
  - Floor proceedings
  - Voting records
  - Treaty status
- Executive Branch
  - Nominations and confirmations
  - Executive communications
  - Treaty processing

#### GovInfo.gov Primary
- Official Documents
  - Authenticated PDFs and XML
  - Digital signatures for legal validity
  - Signature verification
  - All bill versions (IH → ENR)
  - Public laws and statutes
- Regulatory Content
  - Federal Register notices
  - Code of Federal Regulations
  - Agency rulemaking
- Historical Records
  - Pre-1973 legislative materials (with quality metadata)
  - Court opinions (100+ federal courts)
  - Presidential documents
- Bulk Data Access
  - Full XML repositories
  - Granular document updates
  - Cross-branch relationships

### 3. Key Features

#### Smart Source Selection
- Automatic routing based on documented API strengths
- Fallback mechanisms for overlapping data
- Cross-reference between sources when beneficial
- Source-specific versioning and conflict resolution
- Real-time update integration:
  - GovInfo `/collections/lastModified` webhooks
  - Congress.gov streaming floor updates
  - Cross-source synchronization

#### Data Normalization
- Standardized response objects
- Preserved relationships
- Consistent identifier system
- Historical data handling

#### Resource Management
- API-specific rate limit tracking
- Bulk download optimization
- Efficient caching
- Usage monitoring and quota management
- Real-time sync management:
  - Webhook processing queues
  - Stream processing handlers
  - Update conflict resolution

## Usage Patterns

### 1. Legislative Process Tracking
```python
from pygovpub import Client

client = Client(
    govinfo_key="your_govinfo_key",
    congress_key="your_congress_key"
)

# Combines status from Congress.gov with authenticated text from GovInfo
bill = client.get_bill("HR 1234", congress=117)
print(f"Authentication Status: {bill.authentication_status}")
print(f"Source System: {bill.source_system}")
print(f"Last Sync: {bill.last_sync}")

# Subscribe to real-time updates
async def handle_update(update):
    print(f"New update for {update.bill_id}: {update.action}")

client.subscribe_updates("HR 1234", callback=handle_update)
```

### 2. Member Information
```
