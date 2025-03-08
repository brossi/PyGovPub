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
   - Document authentication verification (using digital signatures)
   - Digital signature validation (PKI-based verification)
   - Source system tracking (origin attribution)
   - Version conflict resolution (handling API version mismatches)
   - Historical data partitioning (pre/post-1973 separation)

## Technical Terms

### Bill Version Codes
- `ih`: Introduced in House
- `rh`: Reported in House
- `eh`: Engrossed in House
- `rcs`: Reference in Committee Senate
- `rs`: Reported in Senate
- `es`: Engrossed in Senate
- `enr`: Enrolled Bill

### API Response Types
- `nested_json`: Hierarchical data with relationships (Congress.gov)
- `flat_metadata`: Document-centric data structure (GovInfo.gov)
- `bulk_xml`: Complete XML repositories for offline processing
- `streaming_updates`: Real-time data feeds

### Authentication Methods
- `api_key`: Standard API key authentication
- `digital_signature`: PKI-based document verification
- `hmac`: HMAC-SHA256 for webhook validation

## High-Level Architecture

### 1. Core Components

```
pygovpub/
├── core/
│   ├── client.py          # Main client interface
│   ├── auth.py           # API authentication manager
│   ├── config.py         # Configuration handler
│   ├── sync.py          # Data synchronization manager
│   ├── monitor.py       # API usage tracker
│   └── exceptions.py     # Custom error definitions
├── sources/
│   ├── govinfo/         # GovInfo.gov integration
│   │   ├── documents.py # Document retrieval
│   │   ├── bulk.py     # Bulk data processor
│   │   ├── auth.py     # Document authenticator
│   │   └── search.py    # Full-text search engine
│   └── congress/        # Congress.gov integration
│       ├── legislative.py # Process tracker
│       ├── members.py    # Member data manager
│       ├── treaties.py   # Treaty tracker
│       └── nominations.py # Nomination processor
├── models/
│   ├── common.py        # Shared data models
│   ├── legislative.py   # Legislative models
│   ├── executive.py     # Executive models
│   └── federal.py       # Federal document models
└── utils/
    ├── cache.py         # Cache manager
    ├── rate_limit.py    # Rate limiter
    ├── validation.py    # Input validator
    ├── sync.py         # Sync controller
    └── verify.py       # Signature verifier
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
