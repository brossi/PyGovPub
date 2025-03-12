"""
Secure search fallback patterns for encrypted fields.

This module provides mechanisms for searching across encrypted fields
while maintaining security. Since encrypted fields cannot be directly
searched in the database, this module implements alternative search
strategies that work on encrypted data.
"""

import time
from typing import Any, Dict, List, Optional, Set, Union, Callable

import structlog
from prometheus_client import Histogram, Counter

from pygovpub.storage.security import StorageSecurity

logger = structlog.get_logger()

# Metrics
SECURE_SEARCH_DURATION = Histogram(
    "secure_search_duration_seconds",
    "Duration of secure search operations",
    ["operation", "encrypted"]
)

SECURE_SEARCH_OPERATIONS = Counter(
    "secure_search_operations_total",
    "Number of secure search operations",
    ["operation", "encrypted", "status"]
)

ENCRYPTION_PROCESSING_DURATION = Histogram(
    "encryption_processing_duration_seconds",
    "Time spent processing encryption/decryption during search",
    ["operation"]
)


class SecureSearchFallback:
    """
    Provides fallback search mechanisms for encrypted fields.
    
    When fields are encrypted, standard database search operations won't work.
    This class provides alternative search strategies for encrypted data.
    """
    
    def __init__(self, security: StorageSecurity):
        """
        Initialize the secure search fallback.
        
        Args:
            security: Storage security instance for encryption/decryption
        """
        self.security = security
        self.fallback_active = False
        
    def decrypt_and_filter(
        self, 
        results: List[Dict[str, Any]], 
        field_name: str,
        predicate: Callable[[str], bool]
    ) -> List[Dict[str, Any]]:
        """
        Decrypt a specific field in results and filter based on predicate.
        
        This is used when you need to search an encrypted field that
        couldn't be searched directly in the database.
        
        Args:
            results: List of result dictionaries
            field_name: Name of the field to decrypt and filter
            predicate: Function that returns True for items to keep
            
        Returns:
            Filtered list of results
        """
        start_time = time.time()
        self.fallback_active = True
        filtered_results = []
        
        try:
            # Process results in batches to avoid memory issues with large datasets
            batch_size = 1000
            for i in range(0, len(results), batch_size):
                batch = results[i:i+batch_size]
                
                for item in batch:
                    # Handle nested fields (field.subfield notation)
                    if "." in field_name:
                        parts = field_name.split(".")
                        value = item
                        for part in parts:
                            if isinstance(value, dict) and part in value:
                                value = value[part]
                            else:
                                value = None
                                break
                    else:
                        value = item.get(field_name)
                    
                    if value:
                        # Create a temporary dict just to decrypt this field
                        decrypt_start = time.time()
                        temp = {field_name: value}
                        decrypted = self.security.decrypt_metadata(temp)
                        decrypted_value = decrypted[field_name]
                        
                        # Record encryption processing time
                        encryption_time = time.time() - decrypt_start
                        ENCRYPTION_PROCESSING_DURATION.labels(
                            operation="decrypt"
                        ).observe(encryption_time)
                        
                        # Apply predicate to determine if it matches
                        if predicate(decrypted_value):
                            filtered_results.append(item)
            
            duration = time.time() - start_time
            SECURE_SEARCH_DURATION.labels(
                operation="decrypt_and_filter", 
                encrypted="true"
            ).observe(duration)
            SECURE_SEARCH_OPERATIONS.labels(
                operation="decrypt_and_filter", 
                encrypted="true",
                status="success"
            ).inc()
            
            return filtered_results
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                "Error in decrypt_and_filter fallback", 
                error=str(e),
                field=field_name
            )
            SECURE_SEARCH_OPERATIONS.labels(
                operation="decrypt_and_filter", 
                encrypted="true",
                status="error"
            ).inc()
            
            # Return original results on error
            return results
    
    def search_by_prefix(
        self, 
        results: List[Dict[str, Any]], 
        field_name: str,
        prefix: str,
        case_sensitive: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Search for items with a field starting with the given prefix.
        
        Args:
            results: List of result dictionaries
            field_name: Name of the field to search
            prefix: Prefix to search for
            case_sensitive: Whether the search should be case-sensitive
            
        Returns:
            Filtered list of results
        """
        if not case_sensitive:
            prefix = prefix.lower()
            predicate = lambda x: x.lower().startswith(prefix) if isinstance(x, str) else False
        else:
            predicate = lambda x: x.startswith(prefix) if isinstance(x, str) else False
            
        return self.decrypt_and_filter(results, field_name, predicate)
    
    def search_by_exact_match(
        self, 
        results: List[Dict[str, Any]], 
        field_name: str,
        value: str,
        case_sensitive: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Search for items with an exact field match.
        
        Args:
            results: List of result dictionaries
            field_name: Name of the field to search
            value: Exact value to match
            case_sensitive: Whether the search should be case-sensitive
            
        Returns:
            Filtered list of results
        """
        if not case_sensitive:
            value = value.lower()
            predicate = lambda x: x.lower() == value if isinstance(x, str) else False
        else:
            predicate = lambda x: x == value if isinstance(x, str) else False
            
        return self.decrypt_and_filter(results, field_name, predicate)
    
    def search_by_contains(
        self, 
        results: List[Dict[str, Any]], 
        field_name: str,
        substring: str,
        case_sensitive: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Search for items with fields containing the substring.
        
        Args:
            results: List of result dictionaries
            field_name: Name of the field to search
            substring: Substring to search for
            case_sensitive: Whether the search should be case-sensitive
            
        Returns:
            Filtered list of results
        """
        if not case_sensitive:
            substring = substring.lower()
            predicate = lambda x: substring in x.lower() if isinstance(x, str) else False
        else:
            predicate = lambda x: substring in x if isinstance(x, str) else False
            
        return self.decrypt_and_filter(results, field_name, predicate)
    
    def search_by_range(
        self, 
        results: List[Dict[str, Any]], 
        field_name: str,
        min_value: Optional[str] = None,
        max_value: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for items with field values in the given range.
        
        Args:
            results: List of result dictionaries
            field_name: Name of the field to search
            min_value: Minimum value (inclusive)
            max_value: Maximum value (inclusive)
            
        Returns:
            Filtered list of results
        """
        def range_predicate(x: str) -> bool:
            if not isinstance(x, str):
                return False
            if min_value is not None and x < min_value:
                return False
            if max_value is not None and x > max_value:
                return False
            return True
            
        return self.decrypt_and_filter(results, field_name, range_predicate)
    
    def perform_batch_operations(
        self,
        results: List[Dict[str, Any]],
        operations: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Perform a batch of operations on encrypted fields.
        
        This allows executing multiple search/filter operations in a single pass,
        which is more efficient than multiple separate operations.
        
        Args:
            results: List of result dictionaries
            operations: List of operation specifications, each containing:
                - operation: The operation to perform ('prefix', 'exact', 'contains', 'range')
                - field: The field to search
                - value: The value to search for (or min_value/max_value for ranges)
                - case_sensitive: Whether the search is case sensitive
                
        Returns:
            Filtered list of results
        """
        # If no operations, return original results
        if not operations:
            return results
            
        start_time = time.time()
        self.fallback_active = True
        filtered_results = []
        
        try:
            # Process batches
            batch_size = 1000
            for i in range(0, len(results), batch_size):
                batch = results[i:i+batch_size]
                batch_result = []
                
                for item in batch:
                    # For each item, we need to check if it passes all operations
                    item_matches = True
                    
                    for op in operations:
                        operation_type = op.get("operation", "")
                        field_name = op.get("field", "")
                        case_sensitive = op.get("case_sensitive", False)
                        
                        # Skip invalid operations
                        if not operation_type or not field_name:
                            continue
                            
                        # Get field value (handling nested fields)
                        if "." in field_name:
                            parts = field_name.split(".")
                            value = item
                            for part in parts:
                                if isinstance(value, dict) and part in value:
                                    value = value[part]
                                else:
                                    value = None
                                    break
                        else:
                            value = item.get(field_name)
                            
                        if not value:
                            item_matches = False
                            break
                            
                        # Decrypt value
                        decrypt_start = time.time()
                        temp = {field_name: value}
                        decrypted = self.security.decrypt_metadata(temp)
                        decrypted_value = decrypted[field_name]
                        
                        # Record encryption processing time
                        encryption_time = time.time() - decrypt_start
                        ENCRYPTION_PROCESSING_DURATION.labels(
                            operation="decrypt_batch"
                        ).observe(encryption_time)
                        
                        # Apply appropriate operation
                        if operation_type == "prefix":
                            prefix = op.get("value", "")
                            if not case_sensitive:
                                prefix = prefix.lower()
                                match = isinstance(decrypted_value, str) and decrypted_value.lower().startswith(prefix)
                            else:
                                match = isinstance(decrypted_value, str) and decrypted_value.startswith(prefix)
                                
                        elif operation_type == "exact":
                            match_value = op.get("value", "")
                            if not case_sensitive:
                                match_value = match_value.lower()
                                match = isinstance(decrypted_value, str) and decrypted_value.lower() == match_value
                            else:
                                match = isinstance(decrypted_value, str) and decrypted_value == match_value
                                
                        elif operation_type == "contains":
                            substring = op.get("value", "")
                            if not case_sensitive:
                                substring = substring.lower()
                                match = isinstance(decrypted_value, str) and substring in decrypted_value.lower()
                            else:
                                match = isinstance(decrypted_value, str) and substring in decrypted_value
                                
                        elif operation_type == "range":
                            min_value = op.get("min_value")
                            max_value = op.get("max_value")
                            match = isinstance(decrypted_value, str)
                            if match and min_value is not None:
                                match = decrypted_value >= min_value
                            if match and max_value is not None:
                                match = decrypted_value <= max_value
                                
                        else:
                            # Unknown operation, consider it a non-match
                            match = False
                            
                        # If any operation fails, the item doesn't match
                        if not match:
                            item_matches = False
                            break
                            
                    # If all operations passed, add item to results
                    if item_matches:
                        batch_result.append(item)
                        
                # Add batch results to overall results
                filtered_results.extend(batch_result)
                
            duration = time.time() - start_time
            SECURE_SEARCH_DURATION.labels(
                operation="batch_operations", 
                encrypted="true"
            ).observe(duration)
            SECURE_SEARCH_OPERATIONS.labels(
                operation="batch_operations", 
                encrypted="true",
                status="success"
            ).inc()
            
            return filtered_results
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                "Error in batch operations", 
                error=str(e),
                operations=str(operations)
            )
            SECURE_SEARCH_OPERATIONS.labels(
                operation="batch_operations", 
                encrypted="true",
                status="error"
            ).inc()
            
            # Return original results on error
            return results
    
    def test_performance(self, field_count: int = 10000) -> Dict[str, Any]:
        """
        Test secure search performance with a large number of encrypted fields.
        
        Args:
            field_count: Number of fields to test with
            
        Returns:
            Performance test results
        """
        # Generate test data
        test_data = []
        for i in range(field_count):
            item = {
                "id": f"item-{i}",
                "api_key": f"api-key-{i % 100}",
                "classification": f"classification-{i % 10}",
                "restricted_note": f"restricted-note-{i}",
                "personal_data": f"personal-data-{i % 50}",
                "public_field": f"public-field-{i}"
            }
            test_data.append(item)
            
        # Encrypt the data
        encrypt_start = time.time()
        encrypted_data = [self.security.process_metadata(item) for item in test_data]
        encryption_time = time.time() - encrypt_start
        
        # Test search operations
        operations = [
            ("exact_match", "api_key", "api-key-42"),
            ("prefix", "classification", "classification-5"),
            ("contains", "restricted_note", "note-100"),
            ("range", "personal_data", "personal-data-10", "personal-data-20")
        ]
        
        results = {}
        for op_name, field, value, *args in operations:
            # Perform operation
            start_time = time.time()
            
            if op_name == "exact_match":
                filtered = self.search_by_exact_match(encrypted_data, field, value)
            elif op_name == "prefix":
                filtered = self.search_by_prefix(encrypted_data, field, value)
            elif op_name == "contains":
                filtered = self.search_by_contains(encrypted_data, field, value)
            elif op_name == "range":
                min_val, max_val = args[0], args[1] if len(args) > 1 else None
                filtered = self.search_by_range(encrypted_data, field, min_val, max_val)
                
            duration = time.time() - start_time
            
            # Record results
            results[op_name] = {
                "duration_ms": int(duration * 1000),
                "result_count": len(filtered),
                "throughput_items_per_sec": int(field_count / duration) if duration > 0 else 0
            }
            
        # Test batch operations
        batch_ops = [
            {"operation": "exact_match", "field": "api_key", "value": "api-key-42"},
            {"operation": "prefix", "field": "classification", "value": "classification-5"}
        ]
        
        start_time = time.time()
        filtered = self.perform_batch_operations(encrypted_data, batch_ops)
        duration = time.time() - start_time
        
        results["batch_operations"] = {
            "duration_ms": int(duration * 1000),
            "result_count": len(filtered),
            "throughput_items_per_sec": int(field_count / duration) if duration > 0 else 0
        }
        
        # Overall performance
        results["summary"] = {
            "total_items": field_count,
            "encryption_time_ms": int(encryption_time * 1000),
            "average_search_time_ms": int(sum(op["duration_ms"] for op in results.values()) / len(operations)),
            "encryption_enabled": self.security.encryption_enabled
        }
        
        return results
        
    def get_search_status(self) -> Dict[str, Any]:
        """
        Get status information about the secure search fallback.
        
        Returns:
            Status information dictionary
        """
        return {
            "fallback_active": self.fallback_active,
            "security_enabled": self.security.encryption_enabled,
            "supported_operations": [
                "prefix_search",
                "exact_match",
                "contains",
                "range",
                "batch_operations"
            ]
        }