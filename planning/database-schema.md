# PyGovPub Database Schema

## Overview

This document defines the database schema for PyGovPub, using PostgreSQL for structured API data. The schema is designed to:
- Normalize data across both Congress.gov and GovInfo.gov APIs
- Maintain referential integrity and source tracking
- Support efficient querying with appropriate indexing
- Enable basic text search capabilities
- Track document authentication and API usage

## SQLModel Integration

### Core Models

```python
from datetime import datetime
from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship
from pydantic import constr, conint

class Congress(SQLModel, table=True):
    """Congress session tracking"""
    __tablename__ = "congresses"

    congress_id: int = Field(primary_key=True)
    start_date: datetime
    end_date: datetime
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Bill(SQLModel, table=True):
    """Legislative bill tracking"""
    __tablename__ = "bills"

    bill_id: str = Field(primary_key=True)
    congress_id: int = Field(foreign_key="congresses.congress_id")
    bill_type: str = Field(
        max_length=10,
        sa_column_kwargs={
            "check": "bill_type IN ('hr', 's', 'hjres', 'sjres', 'hconres', 'sconres', 'hres', 'sres')"
        }
    )
    bill_number: int
    title: str
    introduced_date: Optional[datetime]
    status: Optional[str]
    last_action_date: Optional[datetime]
    source_system: str = Field(
        max_length=10,
        sa_column_kwargs={"check": "source_system IN ('govinfo', 'congress')"}
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column_kwargs={"onupdate": datetime.utcnow}
    )

    # Relationships
    versions: List["BillVersion"] = Relationship(back_populates="bill")
    sponsors: List["BillSponsor"] = Relationship(back_populates="bill")

    class Config:
        table = True

class BillVersion(SQLModel, table=True):
    """Bill version tracking"""
    __tablename__ = "bill_versions"

    version_id: str = Field(primary_key=True)
    bill_id: str = Field(foreign_key="bills.bill_id")
    version_code: str = Field(
        max_length=10,
        sa_column_kwargs={
            "check": "version_code IN ('ih', 'rh', 'eh', 'rcs', 'rs', 'es', 'enr')"
        }
    )
    published_date: Optional[datetime]
    govinfo_package_id: Optional[str] = Field(unique=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Committee(SQLModel, table=True):
    """Committee tracking"""
    __tablename__ = "committees"

    committee_id: str = Field(primary_key=True)
    congress_id: int = Field(foreign_key="congresses.congress_id")
    name: str
    chamber: str = Field(
        max_length=10,
        sa_column_kwargs={"check": "chamber IN ('house', 'senate', 'joint')"}
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column_kwargs={"onupdate": datetime.utcnow}
    )

## Database Connection Management

```python
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine
from asyncpg.pool import create_pool

async def init_db_pool():
    return await create_pool(
        user='user',
        password='password',
        database='database',
        min_size=5,
        max_size=20,
        max_inactive_connection_lifetime=300
    )

async def get_session() -> AsyncSession:
    engine = create_async_engine(
        "postgresql+asyncpg://user:password@localhost/db",
        echo=True,
        future=True
    )
    async with AsyncSession(engine) as session:
        yield session
```

## PostgreSQL Schema

### Data Type Standards

#### Monetary Values
All monetary values in the database follow these standards:
- **Storage Type**: `NUMERIC(20,2)` for monetary amounts
  - Provides exact decimal arithmetic
  - Supports up to 18 digits before decimal point and 2 after
  - Prevents floating-point precision errors
- **Currency**: All monetary values are stored in USD
- **Validation**:
  - Non-negative constraints where appropriate
  - Check constraints for reasonable value ranges
  - Currency code stored as 'USD' when needed for API responses

Example usage in table definitions:
```sql
amount NUMERIC(20,2) NOT NULL CHECK (amount >= 0),
currency VARCHAR(3) DEFAULT 'USD' CHECK (currency = 'USD')
```

### Core Tables

```sql
-- Schema Version Control
CREATE TABLE schema_versions (
    version_id SERIAL PRIMARY KEY,
    applied_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    description TEXT,
    script_name TEXT,
    checksum TEXT
);

-- API Usage Tracking
CREATE TABLE api_usage (
    usage_id SERIAL PRIMARY KEY,
    api_source VARCHAR(10) NOT NULL CHECK (api_source IN ('govinfo', 'congress')),
    request_time TIMESTAMPTZ NOT NULL,
    endpoint TEXT NOT NULL,
    rate_limit_remaining INTEGER,
    reset_time TIMESTAMPTZ,
    response_time INTEGER, -- in milliseconds
    success BOOLEAN,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Sync Status
CREATE TABLE sync_status (
    sync_id SERIAL PRIMARY KEY,
    entity_type VARCHAR(50) NOT NULL,
    last_sync_time TIMESTAMPTZ,
    next_sync_time TIMESTAMPTZ,
    source_system VARCHAR(10) NOT NULL CHECK (source_system IN ('govinfo', 'congress')),
    status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Sync Errors
CREATE TABLE sync_errors (
    error_id SERIAL PRIMARY KEY,
    sync_id INTEGER REFERENCES sync_status(sync_id),
    source_system VARCHAR(10),
    entity_type TEXT,
    entity_id TEXT,
    error_message TEXT,
    error_time TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    resolved BOOLEAN DEFAULT FALSE,
    resolution_notes TEXT
);

-- Congresses
CREATE TABLE congresses (
    congress_id INTEGER PRIMARY KEY,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Members
CREATE TABLE members (
    bioguide_id VARCHAR(10) PRIMARY KEY,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    state CHAR(2),
    party VARCHAR(50),
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Committees
CREATE TABLE committee_members (
    committee_id VARCHAR(20) REFERENCES committees(committee_id),
    bioguide_id VARCHAR(10) REFERENCES members(bioguide_id),
    role VARCHAR(50) NOT NULL,
    start_date DATE,
    end_date DATE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (committee_id, bioguide_id)
);

-- Bills (Now Partitioned)
CREATE TABLE bills (
    bill_id VARCHAR(50) PRIMARY KEY,
    congress_id INTEGER REFERENCES congresses(congress_id),
    bill_type VARCHAR(10) NOT NULL,
    bill_number INTEGER NOT NULL,
    title TEXT NOT NULL,
    introduced_date DATE,
    status VARCHAR(50),
    last_action_date DATE,
    source_system VARCHAR(10) NOT NULL CHECK (source_system IN ('govinfo', 'congress')),
    source_updated_at TIMESTAMPTZ,
    source_version VARCHAR(20),
    original_format TEXT,
    scan_quality INTEGER,
    digitization_date DATE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT valid_bill_type CHECK (bill_type IN ('hr', 's', 'hjres', 'sjres', 'hconres', 'sconres', 'hres', 'sres'))
) PARTITION BY RANGE (congress_id);

-- Create partitions
CREATE TABLE bills_historical PARTITION OF bills
    FOR VALUES FROM (1) TO (93);  -- Pre-1973

CREATE TABLE bills_modern PARTITION OF bills
    FOR VALUES FROM (93) TO (MAXVALUE);

-- Bill Versions (Updated with Authentication)
CREATE TABLE bill_versions (
    version_id VARCHAR(100) PRIMARY KEY,
    bill_id VARCHAR(50) REFERENCES bills(bill_id),
    version_code VARCHAR(10) NOT NULL,
    published_date DATE,
    govinfo_package_id VARCHAR(100) UNIQUE,
    pdf_url TEXT,
    xml_url TEXT,
    digital_signature TEXT,
    signature_verified BOOLEAN DEFAULT FALSE,
    verification_date TIMESTAMPTZ,
    authentication_status VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT valid_version_code CHECK (version_code IN ('ih', 'rh', 'eh', 'rcs', 'rs', 'es', 'enr', 'rdh', 'rah', 'rds', 'ras'))
);

-- Bill Actions
CREATE TABLE bill_actions (
    action_id SERIAL PRIMARY KEY,
    bill_id VARCHAR(50) REFERENCES bills(bill_id),
    action_date DATE NOT NULL,
    action_text TEXT NOT NULL,
    action_type VARCHAR(50),
    chamber VARCHAR(10),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT valid_chamber CHECK (chamber IN ('house', 'senate', 'both', null))
);

-- Bill Sponsors
CREATE TABLE bill_sponsors (
    bill_id VARCHAR(50) REFERENCES bills(bill_id),
    bioguide_id VARCHAR(10) REFERENCES members(bioguide_id),
    sponsor_type VARCHAR(20) NOT NULL,
    sponsor_date DATE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (bill_id, bioguide_id),
    CONSTRAINT valid_sponsor_type CHECK (sponsor_type IN ('sponsor', 'cosponsor', 'withdrawn'))
);

-- Amendments
CREATE TABLE amendments (
    amendment_id VARCHAR(50) PRIMARY KEY,
    congress_id INTEGER REFERENCES congresses(congress_id),
    bill_id VARCHAR(50) REFERENCES bills(bill_id),
    amendment_number VARCHAR(20) NOT NULL,
    amendment_type VARCHAR(20),
    status VARCHAR(50),
    introduced_date DATE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Amendment Actions
CREATE TABLE amendment_actions (
    action_id SERIAL PRIMARY KEY,
    amendment_id VARCHAR(50) REFERENCES amendments(amendment_id),
    action_date DATE NOT NULL,
    action_text TEXT NOT NULL,
    action_type VARCHAR(50),
    committee_id VARCHAR(20) REFERENCES committees(committee_id),
    chamber VARCHAR(10) CHECK (chamber IN ('house', 'senate', 'both', null)),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT valid_action_type CHECK (action_type IN ('REFERRAL', 'REPORT', 'DISCHARGE', 'OTHER'))
);

-- Amendment Committee Reports
CREATE TABLE amendment_committee_reports (
    report_id VARCHAR(50) PRIMARY KEY,
    amendment_id VARCHAR(50) REFERENCES amendments(amendment_id),
    committee_id VARCHAR(20) REFERENCES committees(committee_id),
    report_type VARCHAR(50),
    publish_date DATE,
    govinfo_package_id VARCHAR(100) UNIQUE,
    digital_signature TEXT,
    signature_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Laws
CREATE TABLE laws (
    law_id VARCHAR(50) PRIMARY KEY,
    congress_id INTEGER REFERENCES congresses(congress_id),
    law_type VARCHAR(10) NOT NULL,
    law_number INTEGER NOT NULL,
    title TEXT NOT NULL,
    enacted_date DATE,
    bill_id VARCHAR(50) REFERENCES bills(bill_id),
    govinfo_package_id VARCHAR(100) UNIQUE,
    pdf_url TEXT,
    xml_url TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT valid_law_type CHECK (law_type IN ('public', 'private'))
);

-- Treaties
CREATE TABLE treaties (
    treaty_id VARCHAR(50) PRIMARY KEY,
    congress_id INTEGER REFERENCES congresses(congress_id),
    treaty_number VARCHAR(20) NOT NULL,
    title TEXT NOT NULL,
    submission_date DATE,
    status VARCHAR(50),
    resolution_date DATE,
    govinfo_package_id VARCHAR(100) UNIQUE,
    digital_signature TEXT,
    signature_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Nominations
CREATE TABLE nominations (
    nomination_id VARCHAR(50) PRIMARY KEY,
    congress_id INTEGER REFERENCES congresses(congress_id),
    nominee_name TEXT NOT NULL,
    position TEXT NOT NULL,
    agency TEXT,
    status VARCHAR(50),
    received_date DATE,
    committee_referral VARCHAR(20) REFERENCES committees(committee_id),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Executive Communications
CREATE TABLE executive_communications (
    communication_id VARCHAR(50) PRIMARY KEY,
    congress_id INTEGER REFERENCES congresses(congress_id),
    title TEXT NOT NULL,
    agency TEXT,
    received_date DATE,
    govinfo_package_id VARCHAR(100) UNIQUE,
    digital_signature TEXT,
    signature_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Real-time Updates
CREATE TABLE update_streams (
    stream_id SERIAL PRIMARY KEY,
    stream_type VARCHAR(50) NOT NULL,  -- 'webhook', 'congress_stream'
    entity_type VARCHAR(50) NOT NULL,
    last_sequence_id TEXT,
    last_processed_at TIMESTAMPTZ,
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Update Queue
CREATE TABLE update_queue (
    update_id SERIAL PRIMARY KEY,
    stream_id INTEGER REFERENCES update_streams(stream_id),
    payload JSONB NOT NULL,
    sequence_id TEXT,
    received_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMPTZ,
    status VARCHAR(20) DEFAULT 'pending',
    error_message TEXT,
    retry_count INTEGER DEFAULT 0
);

-- Update Subscriptions
CREATE TABLE update_subscriptions (
    subscription_id SERIAL PRIMARY KEY,
    entity_type VARCHAR(50) NOT NULL,
    entity_id TEXT NOT NULL,
    callback_url TEXT,
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    last_notification_at TIMESTAMPTZ
);

-- Create indices for performance
CREATE INDEX idx_amendment_actions_committee ON amendment_actions(committee_id);
CREATE INDEX idx_amendment_actions_date ON amendment_actions(action_date);
CREATE INDEX idx_amendment_committee_reports ON amendment_committee_reports(amendment_id, committee_id);

-- Glossary Terms
CREATE TABLE glossary_terms (
    term_id SERIAL PRIMARY KEY,
    term VARCHAR(255) NOT NULL UNIQUE,
    definition TEXT NOT NULL,
    category VARCHAR(50),
    source VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Term References (for tracking where terms appear)
CREATE TABLE term_references (
    reference_id SERIAL PRIMARY KEY,
    term_id INTEGER REFERENCES glossary_terms(term_id),
    entity_type VARCHAR(50) NOT NULL,
    entity_id VARCHAR(255) NOT NULL,
    context TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_term_reference UNIQUE (term_id, entity_type, entity_id)
);

-- Create indices for performance
CREATE INDEX idx_glossary_terms_term ON glossary_terms(term);
CREATE INDEX idx_term_references_entity ON term_references(entity_type, entity_id);
```

### Regulatory Content

```sql
-- Federal Register Documents
CREATE TABLE federal_register_docs (
    fr_doc_id VARCHAR(50) PRIMARY KEY,
    document_number VARCHAR(50) UNIQUE NOT NULL,
    title TEXT NOT NULL,
    document_type VARCHAR(50),
    publication_date DATE,
    effective_date DATE,
    agency VARCHAR(255),
    govinfo_package_id VARCHAR(100) UNIQUE,
    pdf_url TEXT,
    xml_url TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- CFR Parts
CREATE TABLE cfr_parts (
    cfr_part_id VARCHAR(50) PRIMARY KEY,
    title INTEGER NOT NULL,
    chapter INTEGER NOT NULL,
    part INTEGER NOT NULL,
    heading TEXT NOT NULL,
    govinfo_package_id VARCHAR(100) UNIQUE,
    effective_date DATE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_cfr_part UNIQUE (title, chapter, part)
);

-- Court Opinions
CREATE TABLE court_opinions (
    opinion_id VARCHAR(100) PRIMARY KEY,
    court_code VARCHAR(20) NOT NULL,
    case_number VARCHAR(50),
    case_name TEXT,
    filing_date DATE,
    nature_suit_code VARCHAR(10),
    govinfo_package_id VARCHAR(100) UNIQUE,
    pdf_url TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
```

### Cross-Reference Tables

```sql
-- Bill-to-CFR References
CREATE TABLE bill_cfr_references (
    bill_id VARCHAR(50) REFERENCES bills(bill_id),
    cfr_part_id VARCHAR(50) REFERENCES cfr_parts(cfr_part_id),
    reference_type VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (bill_id, cfr_part_id)
);

-- Law-to-FR References
CREATE TABLE law_fr_references (
    law_id VARCHAR(50) REFERENCES laws(law_id),
    fr_doc_id VARCHAR(50) REFERENCES federal_register_docs(fr_doc_id),
    reference_type VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (law_id, fr_doc_id)
);

-- Committee Report References
CREATE TABLE committee_report_references (
    report_id VARCHAR(50) PRIMARY KEY,
    committee_id VARCHAR(20) REFERENCES committees(committee_id),
    bill_id VARCHAR(50) REFERENCES bills(bill_id),
    report_type VARCHAR(50),
    publish_date DATE,
    govinfo_package_id VARCHAR(100) UNIQUE,
    pdf_url TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
```

## ChromaDB Collections

### Document Collections

```python
# Full Text Documents Collection
documents_collection = client.create_collection(
    name="full_text_documents",
    metadata={
        "description": "Vector embeddings for full document text",
        "source": "GovInfo.gov PDF/XML content"
    }
)

# Document schema
document_schema = {
    "id": "unique_document_id",
    "text": "full_document_text",
    "metadata": {
        "document_type": "bill|law|fr_doc|cfr|opinion",
        "source_id": "original_id_from_postgres",
        "congress": "congress_number",
        "date": "publication_date",
        "title": "document_title",
        "version": "document_version"
    },
    "embedding": "vector_embedding"
}

# Congressional Record Speeches Collection
speeches_collection = client.create_collection(
    name="congressional_record_speeches",
    metadata={
        "description": "Vector embeddings for congressional speeches and remarks",
        "source": "Congress.gov Congressional Record"
    }
)

# Speech schema
speech_schema = {
    "id": "unique_speech_id",
    "text": "speech_text",
    "metadata": {
        "speaker_bioguide_id": "member_bioguide_id",
        "date": "speech_date",
        "chamber": "house|senate",
        "topic": "speech_topic",
        "bill_reference": "related_bill_id"
    },
    "embedding": "vector_embedding"
}

# Committee Hearing Collection
hearings_collection = client.create_collection(
    name="committee_hearings",
    metadata={
        "description": "Vector embeddings for committee hearing transcripts",
        "source": "Congress.gov Committee Hearings"
    }
)

# Hearing schema
hearing_schema = {
    "id": "unique_hearing_id",
    "text": "hearing_text",
    "metadata": {
        "committee_id": "committee_id",
        "date": "hearing_date",
        "title": "hearing_title",
        "witnesses": ["witness_names"],
        "bill_references": ["related_bill_ids"]
    },
    "embedding": "vector_embedding"
}
```

## Integration Points

### PostgreSQL to ChromaDB Linkage

```python
class DocumentLink:
    def __init__(self, postgres_conn, chroma_client):
        self.pg = postgres_conn
        self.chroma = chroma_client

    async def combined_search(self, query_text, filters=None):
        """
        Perform combined search across PostgreSQL and ChromaDB
        """
        # Vector similarity search
        similar_docs = self.chroma.query(
            collection_name="full_text_documents",
            query_text=query_text,
            where=filters,
            n_results=10
        )

        # Metadata-based search
        metadata_results = await self.pg.fetch_many("""
            WITH ranked_results AS (
                SELECT
                    b.bill_id,
                    b.title,
                    b.source_system,
                    bv.signature_verified,
                    ts_rank(to_tsvector('english', b.title), plainto_tsquery($1)) as rank
                FROM bills b
                LEFT JOIN bill_versions bv ON b.bill_id = bv.bill_id
                WHERE to_tsvector('english', b.title) @@ plainto_tsquery($1)
                UNION ALL
                SELECT
                    fr.fr_doc_id,
                    fr.title,
                    'govinfo' as source_system,
                    true as signature_verified,
                    ts_rank(to_tsvector('english', fr.title), plainto_tsquery($1)) as rank
                FROM federal_register_docs fr
                WHERE to_tsvector('english', fr.title) @@ plainto_tsquery($1)
            )
            SELECT * FROM ranked_results
            ORDER BY rank DESC
            LIMIT 10
        """, query_text)

        # Combine and normalize results
        combined_results = []
        for doc in similar_docs:
            combined_results.append({
                "id": doc.id,
                "title": doc.metadata.title,
                "source": doc.metadata.source,
                "score": doc.score,
                "is_authenticated": doc.metadata.get("signature_verified", False)
            })

        for result in metadata_results:
            combined_results.append({
                "id": result["bill_id"] or result["fr_doc_id"],
                "title": result["title"],
                "source": result["source_system"],
                "score": float(result["rank"]),
                "is_authenticated": result["signature_verified"]
            })

        # Sort by normalized score
        return sorted(combined_results, key=lambda x: x["score"], reverse=True)

    async def process_update(self, update_payload):
        """
        Process real-time updates from webhooks or streams
        """
        async with self.pg.transaction():
            # Record the update
            update_id = await self.pg.fetchval("""
                INSERT INTO update_queue (stream_id, payload, sequence_id)
                VALUES ($1, $2, $3)
                RETURNING update_id
            """, update_payload["stream_id"], update_payload["data"],
                update_payload.get("sequence_id"))

            # Update relevant tables
            if update_payload["entity_type"] == "bill":
                await self.update_bill(update_payload["data"])
            elif update_payload["entity_type"] == "nomination":
                await self.update_nomination(update_payload["data"])

            # Notify subscribers
            await self.notify_subscribers(update_payload["entity_type"],
                                       update_payload["entity_id"])

            # Mark as processed
            await self.pg.execute("""
                UPDATE update_queue
                SET status = 'processed', processed_at = CURRENT_TIMESTAMP
                WHERE update_id = $1
            """, update_id)
```

## Indexing Strategy

```sql
-- Primary Indices (already created by PRIMARY KEY constraints)
-- Additional Performance Indices

-- Bills
CREATE INDEX idx_bills_congress_type ON bills(congress_id, bill_type);
CREATE INDEX idx_bills_status ON bills(status);
CREATE INDEX idx_bills_last_action ON bills(last_action_date);

-- Bill Versions
CREATE INDEX idx_bill_versions_package ON bill_versions(govinfo_package_id);

-- Actions
CREATE INDEX idx_actions_date ON bill_actions(action_date);
CREATE INDEX idx_actions_type ON bill_actions(action_type);

-- Federal Register
CREATE INDEX idx_fr_publication ON federal_register_docs(publication_date);
CREATE INDEX idx_fr_agency ON federal_register_docs(agency);

-- CFR
CREATE INDEX idx_cfr_title_part ON cfr_parts(title, part);

-- Full Text Search
CREATE INDEX idx_bills_text ON bills USING gin(to_tsvector('english', title));
CREATE INDEX idx_fr_text ON federal_register_docs USING gin(to_tsvector('english', title));

-- Authentication Indices
CREATE INDEX idx_bill_versions_auth ON bill_versions(signature_verified);
CREATE INDEX idx_doc_auth_log ON document_authentications(document_type, document_id);

-- API Usage Indices
CREATE INDEX idx_api_usage_source ON api_usage(api_source, request_time);
CREATE INDEX idx_api_usage_endpoint ON api_usage(endpoint, success);

-- Sync Status Indices
CREATE INDEX idx_sync_status ON sync_status(entity_type, source_system, status);
CREATE INDEX idx_sync_errors_unresolved ON sync_errors(resolved) WHERE NOT resolved;

-- Real-time Update Indices
CREATE INDEX idx_update_queue_status ON update_queue(status) WHERE status = 'pending';
CREATE INDEX idx_update_queue_stream ON update_queue(stream_id, sequence_id);
CREATE INDEX idx_subscriptions_entity ON update_subscriptions(entity_type, entity_id) WHERE active = true;
```

## Maintenance Considerations

1. **Data Synchronization**
   - Regular updates from both APIs
   - Version history preservation
   - Conflict resolution strategy
   - Source system tracking

2. **Authentication Management**
   - Regular signature verification
   - Authentication status updates
   - Digital signature storage

3. **Vector Updates**
   - Periodic re-embedding of updated documents
   - Incremental updates for new content
   - Embedding model version tracking

4. **Performance Optimization**
   - Historical data partitioning
   - Regular VACUUM and analysis
   - Embedding cache management
   - API usage monitoring

5. **Error Handling**
   - Sync error tracking and resolution
   - Authentication failure management
   - Rate limit violation prevention

6. **Real-Time Processing**
   - Monitor webhook reliability
   - Track stream processing latency
   - Handle update conflicts
   - Manage subscription notifications
   - Implement retry mechanisms

## Performance Optimization

### Essential Indexes

```sql
-- Primary table indexes
CREATE INDEX idx_bills_congress_type ON bills(congress_id, bill_type);
CREATE INDEX idx_bills_status ON bills(status);
CREATE INDEX idx_bills_last_action ON bills(last_action_date);
CREATE INDEX idx_bill_versions_package ON bill_versions(govinfo_package_id);
CREATE INDEX idx_api_usage_source ON api_usage(api_source, request_time);

-- Text search support
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE INDEX idx_bills_title_trgm ON bills USING gin (title gin_trgm_ops);

-- Basic partitioning for bills
ALTER TABLE bills PARTITION BY RANGE (congress_id);
CREATE TABLE bills_historical PARTITION OF bills
    FOR VALUES FROM (1) TO (93);  -- Pre-1973
CREATE TABLE bills_modern PARTITION OF bills
    FOR VALUES FROM (93) TO (MAXVALUE);
```

### Core Integrity Constraints

```sql
-- Foreign key constraints
ALTER TABLE bill_versions
    ADD CONSTRAINT fk_bill_versions_bill
    FOREIGN KEY (bill_id)
    REFERENCES bills(bill_id);

ALTER TABLE bill_sponsors
    ADD CONSTRAINT fk_bill_sponsors_bill
    FOREIGN KEY (bill_id)
    REFERENCES bills(bill_id);

-- Essential check constraints
ALTER TABLE bills
    ADD CONSTRAINT valid_bill_type
    CHECK (bill_type IN ('hr', 's', 'hjres', 'sjres', 'hconres', 'sconres', 'hres', 'sres'));

ALTER TABLE bill_versions
    ADD CONSTRAINT valid_version_code
    CHECK (version_code IN ('ih', 'rh', 'eh', 'rcs', 'rs', 'es', 'enr', 'rdh', 'rah', 'rds', 'ras'));
```
