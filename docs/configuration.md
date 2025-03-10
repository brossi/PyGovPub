# PyGovPub Configuration System

## Overview

The PyGovPub configuration system provides a flexible, secure, and environment-aware way to manage settings throughout the SDK. It supports multiple configuration sources with a clear precedence order, multiple file formats, and secure credential storage.

## Configuration Sources

Configuration is loaded from the following sources, in order of precedence (highest to lowest):

1. **Environment variables** - Override any other settings
2. **Configuration files** - Persistent storage of settings
3. **Default values** - Fallback values when no configuration is specified

## Environment Profiles

The system supports three environment profiles:

* **Development** (`development`) - Default profile with debugging enabled
* **Testing** (`test`) - Profile for running tests with mocks enabled
* **Production** (`production`) - Profile for production use with enhanced performance settings

To set the environment, use the `PYGOVPUB_ENV` environment variable or set it in the configuration file.

## Configuration Files

The system supports multiple configuration file formats:

* **JSON** (`.json`) - Standard JSON format
* **YAML** (`.yaml`, `.yml`) - YAML format for more readable configurations
* **ENV** (`.env`) - Environment variable format for simple settings

Configuration files are stored in the following locations:
* If `XDG_CONFIG_HOME` is set: `$XDG_CONFIG_HOME/pygovpub/config.{json|yaml|env}`
* Otherwise: `~/.pygovpub/config.{json|yaml|env}`

## Feature Flags

Feature flags allow conditional enabling of features across environments:

* `cache_enabled` - Enable/disable the caching system
* `advanced_routing` - Enable/disable advanced request routing
* `debug_mode` - Enable/disable debug mode

Feature flags can be set in configuration files:

```json
{
  "features": {
    "cache_enabled": true,
    "advanced_routing": false,
    "debug_mode": true
  }
}
```

Or using environment variables:

```bash
PYGOVPUB_FEATURES_CACHE_ENABLED=true
PYGOVPUB_FEATURES_ADVANCED_ROUTING=false
PYGOVPUB_FEATURES_DEBUG_MODE=true
```

## API Credentials Management

API credentials are securely stored with encryption when written to configuration files:

```json
{
  "api_keys": {
    "congress": "your-congress-api-key",
    "govinfo": "your-govinfo-api-key"
  }
}
```

Or using environment variables:

```bash
PYGOVPUB_API_CONGRESS_KEY=your-congress-api-key
PYGOVPUB_API_GOVINFO_KEY=your-govinfo-api-key
```

## Configuration Validation

The configuration system validates settings to ensure:

* Required API keys are present
* API base URLs are valid
* Required options are defined
* Feature flags are valid boolean values

## Usage Examples

### Basic Usage

```python
from pygovpub.config import get_config_manager, FeatureFlag

# Get the singleton configuration manager
config = get_config_manager()

# Access feature flags
is_caching_enabled = config.get_feature_flag(FeatureFlag.CACHE_ENABLED)

# Access API credentials
congress_api_key = config.get_api_key("congress")
govinfo_api_key = config.get_api_key("govinfo")

# Access other options
default_format = config.get_option("default_format")
cache_ttl = config.get_option("cache_ttl")
```

### Switching Environments

```python
from pygovpub.config import get_config_manager, Environment

config = get_config_manager()

# Switch to testing environment
config.switch_profile(Environment.TEST)

# Switch to production environment
config.switch_profile(Environment.PRODUCTION)
```

### Saving Configuration

```python
from pygovpub.config import get_config_manager, FeatureFlag

config = get_config_manager()

# Update settings
config.set_feature_flag(FeatureFlag.CACHE_ENABLED, True)
config.set_api_key("congress", "new-api-key")
config.set_option("cache_ttl", 7200)

# Save to file
config.save_to_file()
```

## Environment Variables Reference

| Environment Variable | Description | Example Value |
|---------------------|-------------|---------------|
| `PYGOVPUB_ENV` | Current environment | `development`, `test`, `production` |
| `PYGOVPUB_FEATURES_CACHE_ENABLED` | Enable caching | `true`, `false` |
| `PYGOVPUB_FEATURES_ADVANCED_ROUTING` | Enable advanced routing | `true`, `false` |
| `PYGOVPUB_FEATURES_DEBUG_MODE` | Enable debug mode | `true`, `false` |
| `PYGOVPUB_API_CONGRESS_KEY` | Congress.gov API key | `your-api-key` |
| `PYGOVPUB_API_GOVINFO_KEY` | GovInfo.gov API key | `your-api-key` |
| `PYGOVPUB_API_CONGRESS_URL` | Congress.gov API URL | `https://api.congress.gov/v3` |
| `PYGOVPUB_API_GOVINFO_URL` | GovInfo.gov API URL | `https://api.govinfo.gov` |
| `PYGOVPUB_OPTIONS_DEFAULT_FORMAT` | Default output format | `text`, `json`, `yaml` |
| `PYGOVPUB_OPTIONS_CACHE_TTL` | Cache time-to-live in seconds | `3600` |

## Security Considerations

- API keys and other sensitive information are encrypted when stored in configuration files
- Encryption uses machine-specific information to derive the encryption key
- Environment variables are not encrypted, so ensure they are properly secured
- The configuration system supports rotating API keys with easy update methods

## Database Configuration

PyGovPub supports multiple database backends, with PostgreSQL being the primary recommended database for production use. SQLite is supported for local development and testing.

### Database Environment Variables

Database connection is configured using the following environment variables:

| Variable       | Description                          | Default Value         |
|----------------|--------------------------------------|-----------------------|
| `DB_TYPE`      | Database type (postgresql, sqlite)   | sqlite                |
| `DB_HOST`      | Database host                        | :memory: (for SQLite) |
| `DB_PORT`      | Database port                        | (database default)    |
| `DB_NAME`      | Database name                        | pygovpub              |
| `DB_USER`      | Database username                    | (empty)               |
| `DB_PASSWORD`  | Database password                    | (empty)               |

### PostgreSQL Configuration

For production use, PostgreSQL is recommended. Set up PostgreSQL as follows:

1. Install PostgreSQL on your system or use a cloud-hosted PostgreSQL instance.

2. Create a database and user for PyGovPub:

```sql
CREATE DATABASE pygovpub;
CREATE USER pygovpub_user WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE pygovpub TO pygovpub_user;
```

3. Configure environment variables:

```bash
export DB_TYPE=postgresql
export DB_HOST=localhost
export DB_PORT=5432  # Default PostgreSQL port
export DB_NAME=pygovpub
export DB_USER=pygovpub_user
export DB_PASSWORD=your_secure_password
```

4. Initialize the database tables:

```python
from pygovpub.core.database import create_tables
create_tables()
```

### SQLite Configuration (Development)

For local development, SQLite is a convenient option:

1. Configure environment variables:

```bash
export DB_TYPE=sqlite
export DB_HOST=/path/to/your/database.db  # Or :memory: for in-memory database
```

2. Initialize the database tables as shown above.

## Testing with PostgreSQL

To run tests with PostgreSQL:

1. Set up a test PostgreSQL database:

```sql
CREATE DATABASE pygovpub_test;
CREATE USER pygovpub_test WITH PASSWORD 'test_password';
GRANT ALL PRIVILEGES ON DATABASE pygovpub_test TO pygovpub_test;
```

2. Configure environment variables for testing:

```bash
export DB_TYPE=postgresql
export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=pygovpub_test
export DB_USER=pygovpub_test
export DB_PASSWORD=test_password
```

3. Run tests:

```bash
pytest tests/unit/pygovpub/core/test_postgres.py
```

To skip PostgreSQL tests when PostgreSQL is not available:

```bash
export SKIP_POSTGRES_TESTS=true
pytest
```