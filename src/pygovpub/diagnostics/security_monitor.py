"""Security monitoring for storage components."""
import os
import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import logging

from pygovpub.storage.security import StorageSecurity

logger = logging.getLogger(__name__)


def check_storage_security() -> Dict[str, Any]:
    """
    Check the security status of storage systems.
    
    Verifies encryption status, key integrity, and monitors for security events.
    
    Returns:
        Dictionary with storage security status information
    """
    try:
        # Initialize security with validation mode
        security = StorageSecurity(encryption_enabled=True)
        
        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "secure": True,
            "encryption_enabled": security.encryption_enabled,
            "key_versions": [],
            "audit_trail_active": False,
            "issues": []
        }
        
        # Check encryption keys
        try:
            if security.encryption_enabled:
                # Get current key version info
                if hasattr(security, "keys"):
                    result["key_versions"] = list(security.keys.keys.keys())
                    result["current_key_version"] = security.keys.CURRENT_VERSION
            else:
                result["secure"] = False
                result["issues"].append("Storage encryption is disabled")
        except Exception as e:
            result["secure"] = False
            result["issues"].append(f"Failed to verify encryption keys: {str(e)}")
            
        # Check audit trail
        try:
            result["audit_trail_active"] = hasattr(security, "_audit_trail") and security._audit_trail is not None
            if not result["audit_trail_active"]:
                result["secure"] = False
                result["issues"].append("Audit trail not active")
        except Exception as e:
            result["secure"] = False
            result["issues"].append(f"Failed to verify audit trail: {str(e)}")
            
        # Check for security events (access patterns)
        try:
            # Review audit logs for suspicious patterns
            audit_dir = os.path.expanduser("~/.pygovpub/audit")
            recent_events = []
            if os.path.exists(audit_dir):
                audit_files = sorted([f for f in os.listdir(audit_dir) if f.startswith("security-audit-")])
                # Check most recent file
                if audit_files:
                    latest_file = os.path.join(audit_dir, audit_files[-1])
                    with open(latest_file, "r") as f:
                        for line in f:
                            event = json.loads(line)
                            # Only capture sensitive events
                            if event.get("action") in ["credential_access", "key_rotation", "tamper_attempt"]:
                                recent_events.append(event)
                
                # Report suspicious patterns
                result["recent_security_events"] = len(recent_events)
                if recent_events:
                    result["security_events_sample"] = recent_events[:5]  # Only include a few samples
        except Exception as e:
            result["issues"].append(f"Failed to analyze security events: {str(e)}")
        
        # Test for tamper detection
        try:
            # Perform verification test with invalid data to confirm detection
            test_data = {"_test": "__ENC_V1__:gAAAAABh6tX7lQ==:invalid_hmac"}
            try:
                security.decrypt_metadata(test_data)
                # If no exception raised, that's a problem
                result["secure"] = False
                result["issues"].append("Tamper detection not functioning correctly")
            except ValueError:
                # Expected behavior - tamper detection works
                pass
            except Exception as e:
                # Other errors might indicate issues
                result["issues"].append(f"Unexpected error in tamper detection: {str(e)}")
        except Exception as e:
            result["issues"].append(f"Failed to verify tamper detection: {str(e)}")
        
        return result
    except Exception as e:
        logger.exception("Failed to check storage security")
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "secure": False,
            "error": str(e),
            "issues": ["Failed to initialize security verification"]
        }


def analyze_access_patterns(access_log_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Analyze credential access patterns for suspicious activity.
    
    Args:
        access_log_path: Optional path to security audit log
        
    Returns:
        Dictionary with access pattern analysis
    """
    if access_log_path is None:
        # Default path for audit logs
        audit_dir = os.path.expanduser("~/.pygovpub/audit")
        if not os.path.exists(audit_dir):
            return {"status": "no_data", "message": "No audit logs available for analysis"}
        
        # Find most recent audit file
        audit_files = sorted([f for f in os.listdir(audit_dir) if f.startswith("security-audit-")])
        if not audit_files:
            return {"status": "no_data", "message": "No audit logs available for analysis"}
        
        access_log_path = os.path.join(audit_dir, audit_files[-1])
    
    # Process the log file
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "normal",
        "access_patterns": {
            "credential_access": 0,
            "key_rotation": 0,
            "encryption_operations": 0,
            "decryption_operations": 0
        },
        "suspicious_activity": []
    }
    
    # Track events by timestamp to detect unusual patterns
    events_by_time = {}
    try:
        with open(access_log_path, "r") as f:
            for line in f:
                event = json.loads(line)
                
                # Count event types
                action = event.get("action", "unknown")
                results["access_patterns"][action] = results["access_patterns"].get(action, 0) + 1
                
                # Track events by time
                timestamp = event.get("timestamp", "")
                if timestamp:
                    hour = timestamp.split("T")[1].split(":")[0]
                    events_by_time[hour] = events_by_time.get(hour, 0) + 1
                
                # Check for suspicious patterns
                if action == "credential_access" and event.get("failure", False):
                    results["suspicious_activity"].append({
                        "type": "failed_credential_access",
                        "timestamp": event.get("timestamp"),
                        "credential_type": event.get("credential_type")
                    })
                elif action == "tamper_attempt":
                    results["suspicious_activity"].append({
                        "type": "data_tampering",
                        "timestamp": event.get("timestamp"),
                        "field": event.get("field")
                    })
        
        # Analyze access patterns for after-hours activity
        business_hours = ["09", "10", "11", "12", "13", "14", "15", "16", "17"]
        after_hours_activity = sum(count for hour, count in events_by_time.items() if hour not in business_hours)
        if after_hours_activity > 0:
            results["suspicious_activity"].append({
                "type": "after_hours_activity",
                "count": after_hours_activity
            })
        
        # Update status if suspicious activity found
        if results["suspicious_activity"]:
            results["status"] = "suspicious"
            
        return results
    except Exception as e:
        logger.exception("Failed to analyze access patterns")
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "error",
            "error": str(e)
        }