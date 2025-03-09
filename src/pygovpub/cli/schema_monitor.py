"""
CLI commands for schema monitoring.

This module provides CLI commands for monitoring and managing API schemas.
"""

import argparse
import json
import sys
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from pygovpub.auth.models import ApiSource
from pygovpub.core.schema_monitor import (
    get_recent_changes,
    get_supported_versions,
    default_monitor
)


def format_datetime(dt: datetime) -> str:
    """Format a datetime for display."""
    return dt.strftime("%Y-%m-%d %H:%M:%S %Z")


def list_schemas_command(args: argparse.Namespace) -> None:
    """List all known API schemas."""
    # Get all schemas from the monitor
    schemas = {}
    for key, schema in default_monitor.schemas.items():
        api_source, endpoint = key.split(":", 1)
        if api_source not in schemas:
            schemas[api_source] = []
        
        # Get version info
        version_info = default_monitor.versions.get(key)
        version_str = version_info.version_string if version_info else "unknown"
        last_seen = format_datetime(version_info.last_seen) if version_info else "unknown"
        
        # Count properties
        property_count = len(schema.get("properties", {}))
        
        schemas[api_source].append({
            "endpoint": endpoint,
            "version": version_str,
            "last_seen": last_seen,
            "properties": property_count
        })
    
    # Print results
    print("\nAPI Schema Registry:")
    print("===================\n")
    
    total_endpoints = 0
    
    for api_source, endpoints in schemas.items():
        print(f"\n{api_source.upper()} API: {len(endpoints)} endpoints")
        print("-" * (len(api_source) + 12))
        
        # Sort endpoints by name
        endpoints.sort(key=lambda e: e["endpoint"])
        
        for endpoint in endpoints:
            print(f"  {endpoint['endpoint']}")
            print(f"    Version: {endpoint['version']}")
            print(f"    Last seen: {endpoint['last_seen']}")
            print(f"    Properties: {endpoint['properties']}")
            print()
            
        total_endpoints += len(endpoints)
    
    print(f"\nTotal Endpoints: {total_endpoints}")


def list_changes_command(args: argparse.Namespace) -> None:
    """List recent schema changes."""
    # Get recent changes
    changes = get_recent_changes(limit=args.limit)
    
    # Group by API
    changes_by_api = {}
    for change in changes:
        api = change.api_source.value
        if api not in changes_by_api:
            changes_by_api[api] = []
        changes_by_api[api].append(change)
    
    # Print results
    print("\nRecent Schema Changes:")
    print("=====================\n")
    
    if not changes:
        print("No schema changes detected.")
        return
    
    for api, api_changes in changes_by_api.items():
        print(f"\n{api.upper()} API: {len(api_changes)} changes")
        print("-" * (len(api) + 12))
        
        for change in api_changes:
            # Format change type with breaking indicator
            change_type = change.change_type
            if change.is_breaking:
                change_type = f"{change_type} (BREAKING)"
                
            print(f"  Endpoint: {change.endpoint}")
            print(f"  Change: {change_type}")
            print(f"  Field: {change.field_path}")
            print(f"  Time: {format_datetime(change.timestamp)}")
            print()
    
    print(f"\nTotal Changes: {len(changes)}")


def list_versions_command(args: argparse.Namespace) -> None:
    """List supported API versions."""
    # Get supported versions
    versions = get_supported_versions()
    
    # Print results
    print("\nSupported API Versions:")
    print("=====================\n")
    
    if not versions:
        print("No API versions detected.")
        return
    
    for api, api_versions in versions.items():
        print(f"\n{api.upper()} API: {len(api_versions)} versions")
        print("-" * (len(api) + 12))
        
        for version in api_versions:
            print(f"  Version: {version.version_string}")
            print(f"  First seen: {format_datetime(version.first_seen)}")
            print(f"  Last seen: {format_datetime(version.last_seen)}")
            print()
    
    print(f"\nTotal API Sources: {len(versions)}")


def create_parser() -> argparse.ArgumentParser:
    """Create command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="Monitor and manage API schemas"
    )
    
    subparsers = parser.add_subparsers(
        title="commands",
        dest="command",
        help="Command to execute"
    )
    
    # List schemas command
    list_schemas_parser = subparsers.add_parser(
        "list-schemas",
        help="List all known API schemas"
    )
    list_schemas_parser.set_defaults(func=list_schemas_command)
    
    # List changes command
    list_changes_parser = subparsers.add_parser(
        "list-changes",
        help="List recent schema changes"
    )
    list_changes_parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum number of changes to display"
    )
    list_changes_parser.set_defaults(func=list_changes_command)
    
    # List versions command
    list_versions_parser = subparsers.add_parser(
        "list-versions",
        help="List supported API versions"
    )
    list_versions_parser.set_defaults(func=list_versions_command)
    
    return parser


def main() -> None:
    """Main entry point for the CLI."""
    parser = create_parser()
    args = parser.parse_args()
    
    if not hasattr(args, "func"):
        parser.print_help()
        sys.exit(1)
    
    # Execute the command
    args.func(args)


if __name__ == "__main__":
    main()