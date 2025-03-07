# Regulatory Content API

## Overview

The Regulatory Content API provides access to regulatory materials from GovInfo.gov, including Federal Register documents, Code of Federal Regulations (CFR), and related regulatory content. This endpoint handles retrieval, authentication, and tracking of regulatory documents and their relationships to legislative materials.

## Endpoints

### Get Regulatory Document

```python
async def get_regulatory_document(
    self,
    document_id: str,
    document_type: str,
    version_date: Optional[date] = None
) -> RegulatoryDocument:
    """
    Retrieve regulatory document with authentication and version tracking

    Args:
        document_id (str): Document identifier
        document_type (str): Type of document ('FR', 'CFR', 'ECFR')
        version_date (Optional[date]): Specific version date for CFR/ECFR

    Returns:
        RegulatoryDocument: Document content with metadata and authentication
    """
```

#### Source APIs Used

1. GovInfo.gov:
   - Endpoint: `/packages/{packageId}`
   - Endpoint: `/cfr/{title}/{part}/{section}`
   - Endpoint: `/fr/{volume}/{page}`
   - Rate Limit: Part of 1,000 requests/hour
   - Used for: Regulatory document content and authentication

#### Database Schema

```sql
-- Regulatory Documents
CREATE TABLE regulatory_documents (
    document_id VARCHAR(100) PRIMARY KEY,
    document_type VARCHAR(10) CHECK (document_type IN ('FR', 'CFR', 'ECFR')),
    title INTEGER,
    part INTEGER,
    section VARCHAR(50),
    volume INTEGER,
    page INTEGER,
    effective_date DATE,
    publication_date DATE,
    agency VARCHAR(100),
    subject TEXT,
    digital_signature TEXT,
    signature_verified BOOLEAN DEFAULT FALSE,
    verification_date TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Document Versions (for CFR/ECFR)
CREATE TABLE regulatory_versions (
    version_id SERIAL PRIMARY KEY,
    document_id VARCHAR(100) REFERENCES regulatory_documents(document_id),
    version_date DATE NOT NULL,
    change_type VARCHAR(50),
    superseded_by_id VARCHAR(100),
    content_hash TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (document_id, version_date)
);

-- Legislative References
CREATE TABLE regulatory_references (
    reference_id SERIAL PRIMARY KEY,
    document_id VARCHAR(100) REFERENCES regulatory_documents(document_id),
    referenced_entity_type VARCHAR(50),
    referenced_entity_id VARCHAR(100),
    reference_type VARCHAR(50),
    citation_text TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Agency Information
CREATE TABLE regulatory_agencies (
    agency_id VARCHAR(20) PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    parent_agency_id VARCHAR(20) REFERENCES regulatory_agencies(agency_id),
    cfr_title_authority INTEGER[],
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
```

### Implementation

```python
class RegulatoryService:
    def __init__(self, client: Client):
        self.client = client
        self.pg = client.pg
        self.govinfo_api = client.govinfo_api

    async def get_regulatory_document(
        self,
        document_id: str,
        document_type: str,
        version_date: Optional[date] = None
    ) -> RegulatoryDocument:
        """Get regulatory document content"""
        # Check cache/database first
        cached_doc = await self._get_cached_document(
            document_id,
            version_date
        )
        if cached_doc and not self._needs_refresh(cached_doc):
            return cached_doc

        # Get document from GovInfo
        document_data = await self._fetch_document(
            document_id,
            document_type,
            version_date
        )

        # Verify authenticity
        is_verified = await self._verify_signature(
            document_data.get('digitalSignature')
        )
        document_data['signature_verified'] = is_verified

        # Get legislative references
        references = await self._get_legislative_references(document_id)
        document_data['legislative_references'] = references

        # Store and return
        document = await self._store_document_data(
            document_data,
            document_type,
            version_date
        )
        return document

    async def _fetch_document(
        self,
        document_id: str,
        document_type: str,
        version_date: Optional[date]
    ) -> Dict[str, Any]:
        """Fetch document from appropriate endpoint"""
        try:
            if document_type == 'FR':
                volume, page = self._parse_fr_citation(document_id)
                return await self.govinfo_api.get_fr_document(volume, page)
            elif document_type in ('CFR', 'ECFR'):
                title, part, section = self._parse_cfr_citation(document_id)
                return await self.govinfo_api.get_cfr_section(
                    title,
                    part,
                    section,
                    version_date
                )
            else:
                raise InvalidDocumentTypeError(
                    f"Unknown document type: {document_type}"
                )
        except Exception as e:
            await self._handle_fetch_error(document_id, str(e))
            raise

    async def _store_document_data(
        self,
        data: Dict[str, Any],
        document_type: str,
        version_date: Optional[date]
    ) -> RegulatoryDocument:
        """Store document in database"""
        async with self.pg.transaction():
            # Insert/update document
            document_id = await self.pg.fetchval("""
                INSERT INTO regulatory_documents (
                    document_id, document_type, title,
                    part, section, volume, page,
                    effective_date, publication_date,
                    agency, subject, digital_signature,
                    signature_verified, verification_date
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, CURRENT_TIMESTAMP)
                ON CONFLICT (document_id) DO UPDATE SET
                    effective_date = EXCLUDED.effective_date,
                    digital_signature = EXCLUDED.digital_signature,
                    signature_verified = EXCLUDED.signature_verified,
                    verification_date = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING document_id
            """, data['documentId'], document_type,
                data.get('title'), data.get('part'),
                data.get('section'), data.get('volume'),
                data.get('page'), data.get('effectiveDate'),
                data['publicationDate'], data['agency'],
                data['subject'], data.get('digitalSignature'),
                data['signature_verified'])

            # Store version if applicable
            if version_date and document_type in ('CFR', 'ECFR'):
                await self.pg.execute("""
                    INSERT INTO regulatory_versions (
                        document_id, version_date,
                        change_type, content_hash
                    ) VALUES ($1, $2, $3, $4)
                    ON CONFLICT (document_id, version_date) DO UPDATE SET
                        content_hash = EXCLUDED.content_hash
                """, document_id, version_date,
                    data.get('changeType'),
                    self._generate_content_hash(data))

            # Store legislative references
            for ref in data.get('legislative_references', []):
                await self.pg.execute("""
                    INSERT INTO regulatory_references (
                        document_id, referenced_entity_type,
                        referenced_entity_id, reference_type,
                        citation_text
                    ) VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT DO NOTHING
                """, document_id, ref['entity_type'],
                    ref['entity_id'], ref['reference_type'],
                    ref['citation'])

        return await self._get_cached_document(document_id, version_date)
```

### Usage Example

```python
from pygovpub import Client
from datetime import date

client = Client(govinfo_key="your_govinfo_key")

# Get Federal Register document
fr_doc = await client.get_regulatory_document(
    "87-FR-12345",  # Volume-Page citation
    "FR"
)
print(f"FR Document: {fr_doc.subject}")
print(f"Published: {fr_doc.publication_date}")
print(f"Agency: {fr_doc.agency}")

# Get current CFR section
cfr_doc = await client.get_regulatory_document(
    "12-CFR-1026.43",  # Title-Part-Section
    "CFR"
)
print(f"CFR Section: {cfr_doc.section}")
print(f"Effective: {cfr_doc.effective_date}")

# Get historical CFR version
historical_cfr = await client.get_regulatory_document(
    "12-CFR-1026.43",
    "CFR",
    version_date=date(2020, 1, 1)
)

# Get related legislative materials
for ref in historical_cfr.legislative_references:
    if ref.entity_type == 'bill':
        bill = await client.get_bill(ref.entity_id)
        print(f"Related Bill: {bill.title}")
```

## Testing

```python
async def test_regulatory_retrieval():
    """Test regulatory document retrieval"""
    client = Client(govinfo_key="test_key")

    # Test FR document
    fr_doc = await client.get_regulatory_document(
        "87-FR-12345",
        "FR"
    )
    assert fr_doc.document_id == "87-FR-12345"
    assert fr_doc.document_type == "FR"
    assert fr_doc.signature_verified is not None

    # Test CFR document
    cfr_doc = await client.get_regulatory_document(
        "12-CFR-1026.43",
        "CFR"
    )
    assert cfr_doc.title == 12
    assert cfr_doc.part == 1026
    assert cfr_doc.section == "43"

    # Test versioning
    old_version = await client.get_regulatory_document(
        "12-CFR-1026.43",
        "CFR",
        version_date=date(2020, 1, 1)
    )
    assert old_version.version_date == date(2020, 1, 1)
    assert old_version.content_hash != cfr_doc.content_hash
```

## Error Handling

```python
class RegulatoryError(Exception):
    """Base class for regulatory errors"""
    pass

class InvalidDocumentTypeError(RegulatoryError):
    """Raised when document type is invalid"""
    pass

class DocumentVersionError(RegulatoryError):
    """Raised when requested version is unavailable"""
    pass

async def handle_regulatory_error(
    self,
    error: Exception,
    document_id: str
) -> None:
    """Handle regulatory document errors"""
    await self.pg.execute("""
        INSERT INTO sync_errors (
            source_system,
            entity_type,
            entity_id,
            error_message,
            error_time
        ) VALUES ($1, $2, $3, $4, CURRENT_TIMESTAMP)
    """, 'govinfo', 'regulatory', document_id, str(error))
```
