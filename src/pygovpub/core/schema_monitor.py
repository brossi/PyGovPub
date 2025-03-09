"""
Schema monitoring for API responses.

This module tracks API schemas and detects changes in external API responses,
ensuring the SDK can adapt to evolving APIs and maintain compatibility.
"""

import json
import logging
import os
import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import jsonschema
from genson import SchemaBuilder
from deepdiff import DeepDiff
from pydantic import BaseModel, Field

from pygovpub.auth.models import ApiSource
from pygovpub.error_reporting import report_error

logger = logging.getLogger(__name__)


class SchemaVersion(BaseModel):
    """Schema version information."""
    
    api_source: ApiSource
    """Source API."""
    
    version_string: str
    """API version string."""
    
    schema_hash: str
    """Hash of the schema structure."""
    
    first_seen: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    """When this schema version was first detected."""
    
    last_seen: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    """When this schema version was last seen."""
    
    is_supported: bool = True
    """Whether this schema version is supported by the SDK."""


class SchemaChange(BaseModel):
    """API schema change details."""
    
    api_source: ApiSource
    """Source API."""
    
    endpoint: str
    """API endpoint where the change was detected."""
    
    change_type: str
    """Type of change (added, removed, modified, etc.)."""
    
    field_path: str
    """Path to the changed field (dot notation)."""
    
    old_value: Optional[Any] = None
    """Previous value or schema (for removals or modifications)."""
    
    new_value: Optional[Any] = None
    """New value or schema (for additions or modifications)."""
    
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    """When the change was detected."""
    
    is_breaking: bool = False
    """Whether this is a breaking change."""


class SchemaMonitor:
    """Monitors API schemas and detects changes using established libraries."""
    
    def __init__(
        self,
        schema_dir: Optional[str] = None,
        track_changes: bool = True,
        alert_on_breaking: bool = True
    ):
        """Initialize schema monitor.
        
        Args:
            schema_dir: Directory to store schemas (defaults to a 'schemas' dir in package)
            track_changes: Whether to track and log schema changes
            alert_on_breaking: Whether to alert on breaking changes
        """
        # Set up schema storage directory
        if schema_dir is None:
            # Default to a 'schemas' directory in the package
            package_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.schema_dir = os.path.join(package_dir, 'schemas')
        else:
            self.schema_dir = schema_dir
            
        # Create directory if it doesn't exist
        os.makedirs(self.schema_dir, exist_ok=True)
        
        # Configuration
        self.track_changes = track_changes
        self.alert_on_breaking = alert_on_breaking
        
        # Cached schemas
        self.schemas: Dict[str, Dict[str, Any]] = {}
        self.versions: Dict[str, SchemaVersion] = {}
        self.recent_changes: List[SchemaChange] = []
        
        # Load existing schemas
        self._load_stored_schemas()
    
    def _get_schema_path(self, api_source: ApiSource, endpoint: str) -> str:
        """Get the file path for a schema."""
        # Sanitize endpoint for file system
        sanitized = endpoint.replace('/', '_').replace('?', '_').strip('_')
        return os.path.join(self.schema_dir, f"{api_source.value}_{sanitized}.json")
    
    def _load_stored_schemas(self) -> None:
        """Load all stored schemas from disk."""
        if not os.path.exists(self.schema_dir):
            return
            
        for filename in os.listdir(self.schema_dir):
            if not filename.endswith('.json'):
                continue
                
            try:
                file_path = os.path.join(self.schema_dir, filename)
                with open(file_path, 'r') as f:
                    schema_data = json.load(f)
                    
                if 'api_source' in schema_data and 'endpoint' in schema_data and 'schema' in schema_data:
                    api_source = ApiSource(schema_data['api_source'])
                    endpoint = schema_data['endpoint']
                    schema = schema_data['schema']
                    
                    key = f"{api_source.value}:{endpoint}"
                    self.schemas[key] = schema
                    
                    # Load version information if available
                    if 'version' in schema_data:
                        version_data = schema_data['version']
                        self.versions[key] = SchemaVersion(
                            api_source=api_source,
                            version_string=version_data['version_string'],
                            schema_hash=version_data['schema_hash'],
                            first_seen=datetime.fromisoformat(version_data['first_seen']),
                            last_seen=datetime.fromisoformat(version_data['last_seen']),
                            is_supported=version_data['is_supported']
                        )
            except Exception as e:
                logger.warning(f"Error loading schema {filename}: {e}")
    
    def _store_schema(self, api_source: ApiSource, endpoint: str, schema: Dict[str, Any]) -> None:
        """Store a schema to disk."""
        key = f"{api_source.value}:{endpoint}"
        
        # Add version information if available
        storage_data = {
            'api_source': api_source.value,
            'endpoint': endpoint,
            'schema': schema
        }
        
        if key in self.versions:
            storage_data['version'] = {
                'version_string': self.versions[key].version_string,
                'schema_hash': self.versions[key].schema_hash,
                'first_seen': self.versions[key].first_seen.isoformat(),
                'last_seen': self.versions[key].last_seen.isoformat(),
                'is_supported': self.versions[key].is_supported
            }
            
        file_path = self._get_schema_path(api_source, endpoint)
        with open(file_path, 'w') as f:
            json.dump(storage_data, f, indent=2)
    
    def _compute_schema_hash(self, schema: Dict[str, Any]) -> str:
        """Compute a hash for a schema."""
        # Sort the dictionary to ensure consistent hashing
        schema_str = json.dumps(schema, sort_keys=True)
        return hashlib.sha256(schema_str.encode()).hexdigest()[:16]
    
    def _generate_schema(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a JSON schema from data using genson."""
        builder = SchemaBuilder()
        builder.add_object(data)
        return builder.to_schema()
    
    def _detect_changes(
        self, 
        old_schema: Dict[str, Any], 
        new_schema: Dict[str, Any],
        api_source: ApiSource,
        endpoint: str
    ) -> List[SchemaChange]:
        """Detect changes between two schemas using DeepDiff."""
        changes = []
        
        # Use DeepDiff to detect differences
        diff = DeepDiff(old_schema, new_schema, ignore_order=True)
        
        # Process type changes (these are breaking changes)
        for path, change in diff.get('type_changes', {}).items():
            # Clean up the path format from DeepDiff (remove "root" and convert to dot notation)
            clean_path = path.replace("root['", "").replace("']", "").replace("']['", ".")
            
            changes.append(SchemaChange(
                api_source=api_source,
                endpoint=endpoint,
                change_type="type_changed",
                field_path=clean_path,
                old_value=change['old_type'],
                new_value=change['new_type'],
                is_breaking=True  # Type changes are always breaking
            ))
        
        # Process dictionary item additions (it's a set in DeepDiff)
        for path in diff.get('dictionary_item_added', []):
            clean_path = path.replace("root['", "").replace("']", "").replace("']['", ".")
            
            # Check if this is a required field addition (breaking changes)
            is_breaking = False
            if 'required' in clean_path:
                is_breaking = True
                
            changes.append(SchemaChange(
                api_source=api_source,
                endpoint=endpoint,
                change_type="added",
                field_path=clean_path,
                new_value=None,  # We don't have direct access to the value through DeepDiff
                is_breaking=is_breaking
            ))
        
        # Process dictionary item removals (potentially breaking)
        for path in diff.get('dictionary_item_removed', []):
            clean_path = path.replace("root['", "").replace("']", "").replace("']['", ".")
            
            # Check if this is a removal from "required" fields (non-breaking)
            is_breaking = True
            if 'required' in clean_path:
                is_breaking = False
                
            changes.append(SchemaChange(
                api_source=api_source,
                endpoint=endpoint,
                change_type="removed",
                field_path=clean_path,
                old_value=None,  # We don't have the old value from DeepDiff
                is_breaking=is_breaking
            ))
        
        # Process values that changed
        for path, change in diff.get('values_changed', {}).items():
            clean_path = path.replace("root['", "").replace("']", "").replace("']['", ".")
            
            changes.append(SchemaChange(
                api_source=api_source,
                endpoint=endpoint,
                change_type="modified",
                field_path=clean_path,
                old_value=change['old_value'],
                new_value=change['new_value'],
                # Changes to "type" or to required fields are breaking
                is_breaking='type' in clean_path or 'required' in clean_path
            ))
        
        return changes
    
    def get_latest_schema(self, api_source: ApiSource, endpoint: str) -> Optional[Dict[str, Any]]:
        """Get the latest schema for an API endpoint."""
        key = f"{api_source.value}:{endpoint}"
        return self.schemas.get(key)
    
    def get_schema_version(self, api_source: ApiSource, endpoint: str) -> Optional[SchemaVersion]:
        """Get schema version information for an API endpoint."""
        key = f"{api_source.value}:{endpoint}"
        return self.versions.get(key)
    
    def validate_response(
        self, 
        api_source: ApiSource, 
        endpoint: str, 
        response_data: Dict[str, Any],
        version_string: Optional[str] = None
    ) -> Tuple[bool, List[SchemaChange]]:
        """Validate an API response against the known schema."""
        key = f"{api_source.value}:{endpoint}"
        changes: List[SchemaChange] = []
        
        # Generate a schema from the response
        new_schema = self._generate_schema(response_data)
        
        # Compare with existing schema
        if key in self.schemas:
            # We have an existing schema for this endpoint
            existing_schema = self.schemas[key]
            
            # Calculate hash of new schema
            new_hash = self._compute_schema_hash(new_schema)
            
            # Check if the schema has changed
            if key in self.versions:
                old_hash = self.versions[key].schema_hash
                
                if old_hash != new_hash:
                    # Schema has changed, detect specific changes
                    changes = self._detect_changes(existing_schema, new_schema, api_source, endpoint)
                    
                    # Update version information
                    self.versions[key].schema_hash = new_hash
                    self.versions[key].last_seen = datetime.now(timezone.utc)
                    
                    # Store the new schema
                    self.schemas[key] = new_schema
                    self._store_schema(api_source, endpoint, new_schema)
                    
                    # Store the changes
                    if self.track_changes:
                        self.recent_changes.extend(changes)
                        
                        # Alert on breaking changes
                        breaking_changes = [c for c in changes if c.is_breaking]
                        if breaking_changes and self.alert_on_breaking:
                            message = f"Breaking schema changes detected for {api_source.value} {endpoint}:"
                            for change in breaking_changes:
                                message += f"\n- {change.change_type}: {change.field_path}"
                                
                            report_error(
                                message=message,
                                error_code="SCHEMA_BREAKING_CHANGE",
                                source=f"{api_source.value}_api",
                                details={
                                    "changes": [c.model_dump() for c in breaking_changes],
                                    "endpoint": endpoint
                                }
                            )
                else:
                    # Schema hasn't changed, just update last_seen
                    self.versions[key].last_seen = datetime.now(timezone.utc)
        else:
            # First time seeing this endpoint, store the schema
            self.schemas[key] = new_schema
            
            # Create version info
            schema_hash = self._compute_schema_hash(new_schema)
            self.versions[key] = SchemaVersion(
                api_source=api_source,
                version_string=version_string or "unknown",
                schema_hash=schema_hash
            )
            
            # Store the new schema
            self._store_schema(api_source, endpoint, new_schema)
            
            # Log the new endpoint
            logger.info(f"New API endpoint discovered: {api_source.value} {endpoint}")
        
        # Validate the response against the schema
        try:
            # Always use the latest schema
            jsonschema.validate(instance=response_data, schema=self.schemas[key])
            return True, changes
        except jsonschema.exceptions.ValidationError as e:
            # Schema validation failed
            logger.warning(f"Schema validation failed for {api_source.value} {endpoint}: {e}")
            
            # Regenerate and store an updated schema that includes this response
            if key in self.schemas:
                # Re-add this instance to adjust the schema
                builder = SchemaBuilder(schema=self.schemas[key])
                builder.add_object(response_data)
                updated_schema = builder.to_schema()
                
                # Update and store the schema
                self.schemas[key] = updated_schema
                schema_hash = self._compute_schema_hash(updated_schema)
                self.versions[key].schema_hash = schema_hash
                self._store_schema(api_source, endpoint, updated_schema)
                
            return False, changes
    
    def get_recent_changes(self, limit: int = 100) -> List[SchemaChange]:
        """Get recent schema changes."""
        return sorted(
            self.recent_changes, 
            key=lambda c: c.timestamp, 
            reverse=True
        )[:limit]
    
    def clear_recent_changes(self) -> None:
        """Clear the list of recent changes."""
        self.recent_changes = []
    
    def get_supported_versions(self) -> Dict[str, List[SchemaVersion]]:
        """Get all supported API versions."""
        result: Dict[str, List[SchemaVersion]] = {}
        
        for key, version in self.versions.items():
            if version.is_supported:
                api = version.api_source.value
                if api not in result:
                    result[api] = []
                result[api].append(version)
                
        return result
    
    def mark_version_unsupported(
        self, 
        api_source: ApiSource, 
        version_string: str
    ) -> None:
        """Mark a specific API version as unsupported."""
        for key, version in self.versions.items():
            if version.api_source == api_source and version.version_string == version_string:
                version.is_supported = False
                
                # Update stored schema
                if key in self.schemas:
                    endpoint = key.split(':', 1)[1]
                    self._store_schema(api_source, endpoint, self.schemas[key])


# Initialize default monitor
default_monitor = SchemaMonitor()


def validate_response(
    api_source: ApiSource, 
    endpoint: str, 
    response_data: Dict[str, Any],
    version_string: Optional[str] = None
) -> Tuple[bool, List[SchemaChange]]:
    """Validate an API response using the default monitor."""
    return default_monitor.validate_response(
        api_source=api_source,
        endpoint=endpoint,
        response_data=response_data,
        version_string=version_string
    )


def get_recent_changes(limit: int = 100) -> List[SchemaChange]:
    """Get recent schema changes from the default monitor."""
    return default_monitor.get_recent_changes(limit)


def get_supported_versions() -> Dict[str, List[SchemaVersion]]:
    """Get all supported API versions from the default monitor."""
    return default_monitor.get_supported_versions()