# Storage Security

This document describes the security features for data storage in PyGovPub, including field-level encryption, key management, credential handling, and error handling.

## Field-Level Encryption

PyGovPub provides targeted encryption for sensitive metadata fields while leaving non-sensitive content unencrypted for better performance.

### Supported Features

- **Versioned Encryption Keys**: Support for multiple key versions to facilitate key rotation
- **HMAC Data Integrity**: Tamper detection through HMAC verification
- **Targeted Encryption**: Only specific sensitive fields are encrypted
- **Recursion Support**: Nested dictionary structures are properly handled
- **Legacy Format Support**: Maintains compatibility with older encryption formats

### Configuration

Encryption keys can be configured through environment variables:

```bash
# Primary encryption keys (versioned)
ENCRYPTION_KEY_V1="your-fernet-key-1"
ENCRYPTION_KEY_V2="your-fernet-key-2"

# For backward compatibility
ENCRYPTION_KEY="your-legacy-key"

# HMAC key for tamper detection
ENCRYPTION_HMAC_KEY="your-hmac-key"
```

If keys are not provided, they will be automatically generated and stored in `~/.pygovpub/keys/`.

### Usage

```python
from pygovpub.storage.security import StorageSecurity

# Initialize security
security = StorageSecurity()

# Encrypt sensitive fields in metadata
metadata = {
    "title": "Public Document",
    "api_key": "secret-key-123",  # This will be encrypted
    "classification": "CONFIDENTIAL",  # This will be encrypted
    "content": "This is regular content"  # This won't be encrypted
}

encrypted_metadata = security.process_metadata(metadata)

# Later, decrypt the metadata
decrypted_metadata = security.decrypt_metadata(encrypted_metadata)
```

### Key Rotation

For security best practices, encryption keys should be rotated periodically:

```python
# Generate a new key version
success = security.rotate_keys()

# Re-encrypt existing data with the new key
updated_data = security.rekey_data(existing_data)
```

Key rotation does not affect existing encrypted data but ensures new data uses the latest key version.

## Credential Management

The storage security module centralizes credential management to:

1. Provide a single access point for credentials
2. Enable credential rotation without service disruption
3. Keep an audit trail of credential access
4. Ensure secure storage of sensitive information

### Credential Access

```python
# Get credentials for a specific service
postgres_creds = security.get_credentials("postgres")
govinfo_creds = security.get_credentials("govinfo")

# Use credentials
connection_string = f"postgresql://user:{postgres_creds['password']}@localhost/dbname"
```

### Credential Reloading

Credentials can be reloaded without restarting the application:

```python
# Reload credentials from environment
success = security.reload_credentials()
if success:
    print("Credentials reloaded successfully")
```

## Audit Logging

All security-related operations are automatically logged to an audit trail:

- Key rotation events
- Credential access
- Decryption failures (potential tampering)
- Credential reloading

Audit logs are stored in `~/.pygovpub/audit/` as JSONL files and are rotated automatically.

## Error Handling

The security module provides a standardized error mapping layer to translate internal exceptions to API-friendly error responses:

```python
try:
    # Some storage operation
    result = storage.get_document(doc_id)
    return result
except Exception as e:
    # Map error to API-friendly format
    error_response = security.map_storage_error(e)
    return error_response
```

This helps prevent leaking sensitive information while providing useful error details for troubleshooting.

### Error Format

```json
{
  "error": true,
  "error_type": "ResourceNotFoundError",
  "message": "Requested resource not found",
  "reference_id": "a1b2c3d4e5",
  "status_code": 404,
  "detail": "Reference ID: a1b2c3d4e5"
}
```

## Integration with Health Checks

The security features integrate with PyGovPub's health check system:

```python
from pygovpub.diagnostics.health import run_health_check

# Run health check which includes security status
health_result = run_health_check()

# Check if any security issues detected
if health_result["status"] != "healthy":
    print("Warning: System health issues detected")
```

## Best Practices

1. **Regular Key Rotation**: Rotate encryption keys periodically (e.g., every 90 days)
2. **Minimal Field Encryption**: Only encrypt fields that contain sensitive information
3. **Monitor Audit Logs**: Review security audit logs regularly
4. **Backup Keys**: Maintain secure backups of encryption keys
5. **Environment Isolation**: Use different keys for development, testing, and production
6. **Error Handling**: Always use the error mapping layer for API responses

## Technical Details

### Encryption Algorithm

Field-level encryption uses the Fernet symmetric encryption scheme (AES-128-CBC with PKCS7 padding and HMAC-SHA256 for authentication).

### Key Storage

Keys are stored:
1. Preferentially in environment variables
2. As a fallback in files under `~/.pygovpub/keys/`

### HMAC Verification

The format of encrypted values includes a version, the encrypted data, and an HMAC digest:

```
__ENC_V{version}__:{encrypted_value}:{hmac_digest}
```

This format enables:
- Key rotation without data loss
- Verification of data integrity
- Detection of tampering attempts