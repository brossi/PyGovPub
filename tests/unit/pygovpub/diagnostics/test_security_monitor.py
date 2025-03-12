"""Tests for storage security monitoring."""
import os
import json
import pytest
from unittest.mock import patch, mock_open, MagicMock

from pygovpub.diagnostics.security_monitor import check_storage_security, analyze_access_patterns
from pygovpub.storage.security import StorageSecurity


@pytest.fixture
def mock_audit_log():
    """Sample security audit log data for testing."""
    return [
        json.dumps({
            "timestamp": "2025-03-12T10:15:30.123Z",
            "action": "credential_access",
            "credential_type": "api_key",
            "user_id": "system",
            "success": True
        }),
        json.dumps({
            "timestamp": "2025-03-12T10:16:45.456Z",
            "action": "encryption_operations",
            "field_count": 5,
            "success": True
        }),
        json.dumps({
            "timestamp": "2025-03-12T10:17:20.789Z",
            "action": "decryption_operations",
            "field_count": 3,
            "success": True
        }),
        json.dumps({
            "timestamp": "2025-03-12T22:05:10.321Z",
            "action": "credential_access",
            "credential_type": "database",
            "user_id": "unknown",
            "success": False,
            "failure": True
        }),
        json.dumps({
            "timestamp": "2025-03-12T22:07:35.654Z",
            "action": "tamper_attempt",
            "field": "api_key",
            "severity": "high"
        })
    ]


def test_check_storage_security_with_encryption_enabled():
    """Test security check with encryption enabled."""
    with patch("pygovpub.storage.security.StorageSecurity") as mock_security:
        # Setup mock
        instance = mock_security.return_value
        instance.encryption_enabled = True
        instance.keys.keys = {"1": "key1", "2": "key2"}
        instance.keys.CURRENT_VERSION = "2"
        instance._audit_trail = True
        
        # Mock decrypt_metadata to raise ValueError (expected for tamper detection)
        instance.decrypt_metadata.side_effect = ValueError("HMAC verification failed")
        
        # Mock directory listing and file reading
        with patch("os.path.exists", return_value=True), \
             patch("os.listdir", return_value=["security-audit-2025-03-12.json"]), \
             patch("builtins.open", mock_open(read_data="\n".join([
                 '{"action": "credential_access", "timestamp": "2025-03-12T10:15:30Z"}',
                 '{"action": "key_rotation", "timestamp": "2025-03-12T11:20:15Z"}'
             ]))):
            
            # Run the check
            result = check_storage_security()
            
            # Verify results
            assert result["secure"] is True
            assert result["encryption_enabled"] is True
            assert result["key_versions"] == ["1", "2"]
            assert result["current_key_version"] == "2"
            assert result["audit_trail_active"] is True
            assert result["recent_security_events"] == 2
            assert len(result["issues"]) == 0


def test_check_storage_security_with_encryption_disabled():
    """Test security check with encryption disabled."""
    with patch("pygovpub.storage.security.StorageSecurity") as mock_security:
        # Setup mock
        instance = mock_security.return_value
        instance.encryption_enabled = False
        
        # Run the check
        result = check_storage_security()
        
        # Verify results
        assert result["secure"] is False
        assert result["encryption_enabled"] is False
        assert "Storage encryption is disabled" in result["issues"]


def test_check_storage_security_with_tamper_detection_failure():
    """Test security check with tamper detection failure."""
    with patch("pygovpub.storage.security.StorageSecurity") as mock_security:
        # Setup mock
        instance = mock_security.return_value
        instance.encryption_enabled = True
        
        # Mock decrypt_metadata to not raise an exception (tamper detection failure)
        instance.decrypt_metadata.return_value = {"_test": "decrypted"}
        
        # Run the check
        result = check_storage_security()
        
        # Verify results
        assert result["secure"] is False
        assert "Tamper detection not functioning correctly" in result["issues"]


def test_analyze_access_patterns_normal(mock_audit_log):
    """Test access pattern analysis with normal patterns."""
    with patch("builtins.open", mock_open(read_data="\n".join(mock_audit_log[:3]))):
        # Only include the normal business hours logs (index 0-2)
        result = analyze_access_patterns("mock_path")
        
        # Verify results
        assert result["status"] == "normal"
        assert result["access_patterns"]["credential_access"] == 1
        assert result["access_patterns"]["encryption_operations"] == 1
        assert result["access_patterns"]["decryption_operations"] == 1
        assert len(result["suspicious_activity"]) == 0


def test_analyze_access_patterns_suspicious(mock_audit_log):
    """Test access pattern analysis with suspicious patterns."""
    with patch("builtins.open", mock_open(read_data="\n".join(mock_audit_log))):
        # Include all logs, including suspicious ones
        result = analyze_access_patterns("mock_path")
        
        # Verify results
        assert result["status"] == "suspicious"
        assert result["access_patterns"]["credential_access"] == 2
        assert result["access_patterns"]["tamper_attempt"] == 1
        assert len(result["suspicious_activity"]) == 3
        
        # Verify specific suspicious activities
        activities = [a["type"] for a in result["suspicious_activity"]]
        assert "failed_credential_access" in activities
        assert "data_tampering" in activities
        assert "after_hours_activity" in activities


def test_analyze_access_patterns_no_data():
    """Test access pattern analysis with no data."""
    with patch("os.path.exists", return_value=False):
        result = analyze_access_patterns()
        
        # Verify results
        assert result["status"] == "no_data"
        assert "No audit logs available" in result["message"]


def test_check_storage_security_integration():
    """Test integration with real StorageSecurity class."""
    with patch.dict(os.environ, {"PYGOVPUB_ENCRYPTION_KEY_V1": "some-dummy-key-for-testing"}, clear=True), \
         patch("pygovpub.storage.security.Fernet"), \
         patch("os.path.exists", return_value=False):
        
        # Run the check with the real class (but mocked internals)
        result = check_storage_security()
        
        # Basic verification that it runs without exceptions
        assert "timestamp" in result
        assert "secure" in result