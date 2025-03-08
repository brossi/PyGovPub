# Setting Up PyGovPub

This guide walks you through setting up the PyGovPub SDK for development and usage.

## Installation

### From PyPI

The simplest way to install PyGovPub is from PyPI:

```bash
pip install pygovpub
```

### From Source

For development or to get the latest features:

```bash
git clone https://github.com/yourusername/pygovpub.git
cd pygovpub
pip install -e .
```

This installs the package in development mode, allowing you to modify the code and see changes immediately.

## Environment Setup

PyGovPub uses environment variables for configuration. Create a `.env` file in your project root:

```bash
# Environment (development, test, production)
PYGOVPUB_ENV=development

# API Keys
CONGRESS_GOV_API_KEY=your_congress_api_key
GOVINFO_API_KEY=your_govinfo_api_key

# Mock Server Configuration
PYGOVPUB_MOCK_ENABLED=true
PYGOVPUB_MOCK_LATENCY_MS=100
PYGOVPUB_MOCK_SIMULATE_RATE_LIMITS=false
PYGOVPUB_MOCK_RECORD_MODE=false
PYGOVPUB_MOCK_FIXTURES_PATH=fixtures
```

## API Keys

### Congress.gov API Key

1. Visit [Congress.gov API Documentation](https://api.congress.gov/)
2. Register for an API key
3. Add the key to your `.env` file as `CONGRESS_GOV_API_KEY`

### GovInfo.gov API Key

1. Visit [GovInfo.gov API Documentation](https://api.govinfo.gov/)
2. Register for an API key
3. Add the key to your `.env` file as `GOVINFO_API_KEY`

## Development Setup

For development, you'll want to install the additional dependencies:

```bash
pip install -e ".[dev]"
```

This installs development tools like:

- black (code formatter)
- isort (import sorter)
- mypy (type checker)
- flake8 (linter)
- pytest (testing framework)

## Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_config.py

# Run with coverage report
pytest --cov=pygovpub
```

## Using the Mock Server

The mock server allows development without consuming API quotas:

```bash
# Start the mock server
pygovpub-mock

# With custom settings
pygovpub-mock --port 9000 --latency 200 --rate-limits
```

In your code, enable mock mode:

```python
import os
os.environ["PYGOVPUB_MOCK_ENABLED"] = "true"

# Now all API calls will use the mock server
```

## Recording Real API Responses

To create fixtures from real API responses:

```bash
# Enable recording mode
export PYGOVPUB_MOCK_RECORD_MODE=true
export PYGOVPUB_MOCK_ENABLED=true
export CONGRESS_GOV_API_KEY=your_key
export GOVINFO_API_KEY=your_key

# Run the mock server
pygovpub-mock --record

# Make API requests through the mock server
# They will be recorded as fixtures
```

## Next Steps

- Read the [API Reference](api_reference.md)
- Explore the [Mock Server Guide](mock_server.md)
- Learn about [Authentication](authentication.md)