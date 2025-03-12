"""Tests for RBAC integration with storage security."""
import pytest
from unittest.mock import patch, MagicMock

from pygovpub.storage.security import StorageSecurity
from pygovpub.exceptions import AuthenticationError


class MockRBACProvider:
    """Mock RBAC provider for testing."""

    def __init__(self):
        self.roles = {
            "admin": ["read", "write", "delete", "encrypt", "decrypt"],
            "editor": ["read", "write"],
            "viewer": ["read"],
            "security_admin": ["read", "write", "delete", "encrypt", "decrypt", "rotate_keys"]
        }
        self.user_roles = {
            "user1": ["admin"],
            "user2": ["editor"],
            "user3": ["viewer"],
            "user4": ["security_admin"]
        }

    def check_permission(self, user_id, permission):
        """Check if user has the required permission."""
        if user_id not in self.user_roles:
            return False

        user_permissions = []
        for role in self.user_roles[user_id]:
            if role in self.roles:
                user_permissions.extend(self.roles[role])

        return permission in user_permissions

    def get_user_roles(self, user_id):
        """Get roles for a user."""
        return self.user_roles.get(user_id, [])


@pytest.fixture
def rbac_provider():
    """Create a mock RBAC provider."""
    return MockRBACProvider()


@pytest.fixture
def security_with_rbac(rbac_provider):
    """Create a StorageSecurity instance with RBAC integration."""
    with patch.object(StorageSecurity, "_check_rbac_permission") as mock_check_permission:
        # Configure the mock method to delegate to our rbac_provider
        mock_check_permission.side_effect = lambda user_id, permission: rbac_provider.check_permission(user_id, permission)
        
        security = StorageSecurity(encryption_enabled=True)
        security.rbac_provider = rbac_provider
        return security


@pytest.mark.parametrize("user_id,operation,expected_result", [
    ("user1", "encrypt", True),  # admin can encrypt
    ("user1", "decrypt", True),  # admin can decrypt
    ("user1", "rotate_keys", False),  # admin cannot rotate keys
    ("user2", "encrypt", False),  # editor cannot encrypt
    ("user2", "read", True),  # editor can read
    ("user3", "read", True),  # viewer can read
    ("user3", "write", False),  # viewer cannot write
    ("user4", "rotate_keys", True),  # security_admin can rotate keys
])
def test_rbac_permission_checking(security_with_rbac, user_id, operation, expected_result):
    """Test RBAC permission checking for storage operations."""
    assert security_with_rbac._check_rbac_permission(user_id, operation) == expected_result


def test_encrypt_with_rbac(security_with_rbac):
    """Test encryption with RBAC permissions."""
    with patch.object(security_with_rbac, "_check_rbac_permission", return_value=True):
        # User has permission
        data = {"sensitive_field": "value"}
        encrypted = security_with_rbac.encrypt_metadata(data, user_id="user1")
        assert "sensitive_field" in encrypted
        assert encrypted["sensitive_field"] != "value"

    with patch.object(security_with_rbac, "_check_rbac_permission", return_value=False):
        # User doesn't have permission
        with pytest.raises(AuthenticationError) as excinfo:
            security_with_rbac.encrypt_metadata(data, user_id="user3")
        
        assert "permission" in str(excinfo.value).lower()
        assert hasattr(excinfo.value, "error_code")
        assert excinfo.value.error_code == "PERMISSION_DENIED"


def test_decrypt_with_rbac(security_with_rbac):
    """Test decryption with RBAC permissions."""
    # First encrypt with a user who has permission
    with patch.object(security_with_rbac, "_check_rbac_permission", return_value=True):
        data = {"sensitive_field": "value"}
        encrypted = security_with_rbac.encrypt_metadata(data, user_id="user1")
    
    # Now try to decrypt with different users
    with patch.object(security_with_rbac, "_check_rbac_permission", return_value=True):
        # User has permission
        decrypted = security_with_rbac.decrypt_metadata(encrypted, user_id="user1")
        assert decrypted["sensitive_field"] == "value"

    with patch.object(security_with_rbac, "_check_rbac_permission", return_value=False):
        # User doesn't have permission
        with pytest.raises(AuthenticationError) as excinfo:
            security_with_rbac.decrypt_metadata(encrypted, user_id="user3")
        
        assert "permission" in str(excinfo.value).lower()
        assert excinfo.value.error_code == "PERMISSION_DENIED"


def test_credential_access_with_rbac(security_with_rbac):
    """Test credential access with RBAC permissions."""
    with patch.object(security_with_rbac, "_get_credential_from_env", return_value="credential_value"), \
         patch.object(security_with_rbac, "_check_rbac_permission", return_value=True):
        # User has permission
        credential = security_with_rbac.get_credential("API_KEY", user_id="user1")
        assert credential == "credential_value"

    with patch.object(security_with_rbac, "_get_credential_from_env", return_value="credential_value"), \
         patch.object(security_with_rbac, "_check_rbac_permission", return_value=False):
        # User doesn't have permission
        with pytest.raises(AuthenticationError) as excinfo:
            security_with_rbac.get_credential("API_KEY", user_id="user3")
        
        assert "permission" in str(excinfo.value).lower()
        assert excinfo.value.error_code == "PERMISSION_DENIED"


def test_key_rotation_with_rbac(security_with_rbac):
    """Test key rotation with RBAC permissions."""
    with patch.object(security_with_rbac, "_check_rbac_permission", return_value=True), \
         patch.object(security_with_rbac.keys, "rotate_keys") as mock_rotate:
        # User has permission
        security_with_rbac.rotate_encryption_keys(user_id="user4")
        mock_rotate.assert_called_once()

    with patch.object(security_with_rbac, "_check_rbac_permission", return_value=False), \
         patch.object(security_with_rbac.keys, "rotate_keys") as mock_rotate:
        # User doesn't have permission
        with pytest.raises(AuthenticationError) as excinfo:
            security_with_rbac.rotate_encryption_keys(user_id="user3")
        
        assert "permission" in str(excinfo.value).lower()
        assert excinfo.value.error_code == "PERMISSION_DENIED"
        mock_rotate.assert_not_called()


def test_audit_logging_rbac_events(security_with_rbac):
    """Test audit logging of RBAC-related events."""
    with patch.object(security_with_rbac, "_audit_trail") as mock_audit, \
         patch.object(security_with_rbac, "_check_rbac_permission", return_value=False):
        # Attempt operation without permission
        try:
            security_with_rbac.encrypt_metadata({"field": "value"}, user_id="user3")
        except AuthenticationError:
            pass
        
        # Verify audit log entry was created
        mock_audit.log_event.assert_called_once()
        args = mock_audit.log_event.call_args[0]
        assert args[0] == "permission_denied"  # action
        assert "user3" in str(args[1])  # details