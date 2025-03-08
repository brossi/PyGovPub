# PyGovPub Mock Server

## Overview

The PyGovPub SDK includes a mock server that simulates the Congress.gov and GovInfo.gov APIs for development and testing purposes. This allows developers to work on applications without consuming API quotas or requiring internet connectivity.

## Features

- **Mock API Response**: Realistic responses that match the structure of the actual APIs
- **Authentication Simulation**: Verify API keys and handle errors appropriately
- **Rate Limit Simulation**: Optionally simulate API rate limiting
- **Configurable Latency**: Add realistic network latency to responses
- **Record/Replay**: Record real API responses and save them as fixtures
- **Static Fixtures**: Use predefined fixtures for common requests

## Configuration

Configure the mock server using environment variables in your `.env` file:

```bash
# Enable mock server (true/false)
PYGOVPUB_MOCK_ENABLED=true

# Simulate API latency in milliseconds
PYGOVPUB_MOCK_LATENCY_MS=100

# Simulate API rate limits (true/false)
PYGOVPUB_MOCK_SIMULATE_RATE_LIMITS=false

# Enable recording mode to capture real API responses (true/false)
PYGOVPUB_MOCK_RECORD_MODE=false

# Path to fixtures directory (relative to package)
PYGOVPUB_MOCK_FIXTURES_PATH=fixtures
```

## Usage

### Basic Usage

To use the mock server in your application, simply set `PYGOVPUB_MOCK_ENABLED=true` in your environment variables. The SDK will automatically route requests to the mock server instead of the real APIs.

```python
import os
from pygovpub import config
from pygovpub.client import PyGovPubClient

# Enable mock mode
os.environ["PYGOVPUB_MOCK_ENABLED"] = "true"

# Create client
client = PyGovPubClient()

# Make requests as usual
bill = client.get_bill(congress=117, bill_type="hr", bill_number=1)
print(bill.title)  # Output: "For the People Act of 2021" (from mock data)
```

### Starting the Mock Server Standalone

You can also run the mock server independently for testing:

```python
import asyncio
from pygovpub.mock import start_mock_server, stop_mock_server

async def main():
    # Start the server on port 8000
    await start_mock_server(host="127.0.0.1", port=8000)
    print("Mock server running at http://127.0.0.1:8000")
    
    try:
        # Keep the server running
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        # Stop the server
        await stop_mock_server()
        print("Mock server stopped")

if __name__ == "__main__":
    asyncio.run(main())
```

### Record and Replay

To record real API responses for later use:

1. Set `PYGOVPUB_MOCK_RECORD_MODE=true` in your environment
2. Configure your API keys:
   ```
   CONGRESS_GOV_API_KEY=your_key_here
   GOVINFO_API_KEY=your_key_here
   ```
3. Run your application to make API requests
4. Responses will be saved to your fixtures directory

You can also use the Recorder API directly:

```python
import asyncio
from pygovpub.mock.recorder import recording_session

async def record_bills():
    async with recording_session("congress") as recorder:
        # Record a bill response
        await recorder.record_request("bill/117/hr/1")
        
        # Record another with query parameters
        await recorder.record_request(
            "bill/117/s/1", 
            params={"format": "json"}
        )
    
    print("Recording complete")

asyncio.run(record_bills())
```

## Supported Endpoints

### Congress.gov API

- `GET /congress/v3/bill/{congress}/{bill_type}/{bill_number}`
- `GET /congress/v3/amendment/{congress}/{amendment_type}/{amendment_number}`
- `GET /congress/v3/member/{bioguide_id}`
- `GET /congress/v3/committee/{congress}/{chamber}/{committee_code}`

### GovInfo.gov API

- `GET /collections`
- `GET /packages/{package_id}`
- `GET /packages/{package_id}/summary`
- `GET /packages/{package_id}/content`

## Managing Fixtures

### Fixture Directory Structure

```
fixtures/
├── defaults/                  # Default fixtures for each endpoint
│   ├── congress_bill.json
│   ├── congress_member.json
│   ├── govinfo_collections.json
│   └── govinfo_package.json
├── congress/                  # Specific fixtures for Congress.gov API
│   ├── bill/
│   │   └── 117_hr_1.json
│   ├── member/
│   │   └── A000000.json
│   └── committee/
│       └── 117_house_hsju.json
├── govinfo/                   # Specific fixtures for GovInfo.gov API
│   ├── collections.json
│   ├── packages/
│   │   └── BILLS-117hr1enr.json
│   └── content/
│       └── BILLS-117hr1enr.pdf
└── recordings/                # Recorded API responses
    └── congress_20230101/
        ├── metadata.json
        └── bill_117_hr_1.json
```

### Adding Custom Fixtures

To add your own fixtures, create files in the appropriate directory following the structure above. The mock server will look for specific fixtures first, then fall back to default fixtures if no specific match is found.

For example, to add a fixture for a specific bill:

1. Create a file at `fixtures/congress/bill/117_hr_1234.json`
2. Add the response JSON:

```json
{
  "bill": {
    "congress": 117,
    "type": "hr", 
    "number": "1234",
    "title": "My Custom Test Bill"
  }
}
```

## Health Check

The mock server includes a health check endpoint:

```
GET /health
```

Example response:

```json
{
  "status": "ok",
  "version": "1.0.0",
  "apis": {
    "congress": {
      "status": "ok",
      "rate_limit": {
        "limit": 5000,
        "remaining": 4995,
        "reset": 1680000000
      }
    },
    "govinfo": {
      "status": "ok",
      "rate_limit": {
        "limit": 1000,
        "remaining": 999,
        "reset": 1680000000
      }
    }
  }
}
```

## Advanced Usage

### Custom Rate Limits

The mock server simulates the actual rate limits of the APIs:
- Congress.gov: 5,000 requests/hour
- GovInfo.gov: 1,000 requests/hour

To test how your application handles rate limit errors, enable rate limit simulation:

```
PYGOVPUB_MOCK_SIMULATE_RATE_LIMITS=true
```

### Simulating Latency

To test how your application handles network latency, set the latency parameter:

```
PYGOVPUB_MOCK_LATENCY_MS=500  # Add 500ms delay to each request
```

### Managing Sessions

To manage recording sessions:

```python
from pygovpub.mock.recorder import Recorder

recorder = Recorder()

# List all recording sessions
sessions = recorder.list_sessions()
for session in sessions:
    print(f"{session['recording_id']} - {session['api_name']} - {session['request_count']} requests")

# Save a recorded response as a fixture
await recorder.save_fixture(
    session_id="congress_20230101",
    endpoint="bill/117/hr/1",
    fixture_type="default"  # or "specific"
)
```