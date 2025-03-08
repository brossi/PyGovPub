# PyGovPub SDK

Python SDK for unified access to U.S. Federal Government data through integration with Congress.gov and GovInfo.gov APIs.

## Overview

PyGovPub simplifies access to legislative and regulatory data, providing a unified interface to multiple government APIs. It ensures document authenticity, manages API rate limits, and normalizes data from different sources.

### Key Features

- **Unified API Access**: Single interface to both Congress.gov and GovInfo.gov APIs
- **Data Normalization**: Consistent schemas across disparate data sources
- **Authentication Management**: Automatic API key handling and rate limit tracking
- **Mock Server**: Local development without consuming API quotas
- **Record/Replay**: Record real API responses for testing and development

## Installation

```bash
pip install pygovpub
```

## Quick Start

### Configuration

Create a `.env` file with your API keys:

```bash
# API Keys
CONGRESS_GOV_API_KEY=your_congress_api_key
GOVINFO_API_KEY=your_govinfo_api_key

# Optional settings
PYGOVPUB_ENV=development  # development, test, or production
PYGOVPUB_MOCK_ENABLED=true  # Use mock server for development
```

### Basic Usage

```python
import pygovpub
from pygovpub import client

# Create a client
pygovpub_client = client.PyGovPubClient()

# Get a bill from Congress.gov
bill = pygovpub_client.get_bill(
    congress=117,
    bill_type="hr",
    bill_number=1
)
print(f"Bill: {bill.title}")

# Get bill document from GovInfo.gov
document = pygovpub_client.get_bill_document(
    package_id="BILLS-117hr1enr"
)
print(f"Document: {document.title}")
```

## Development Mode

For development without consuming real API quotas:

```python
import os
os.environ["PYGOVPUB_MOCK_ENABLED"] = "true"

# Now all API calls will use the mock server
```

### Running the Mock Server Standalone

```bash
# Run the mock server on the default port (8000)
pygovpub-mock

# Run with custom settings
pygovpub-mock --port 9000 --latency 200 --rate-limits
```

## Documentation

For detailed documentation, see:

- [API Reference](docs/api_reference.md)
- [Mock Server Guide](docs/mock_server.md)
- [Authentication](docs/authentication.md)
- [Data Models](docs/data_models.md)

## License

MIT License