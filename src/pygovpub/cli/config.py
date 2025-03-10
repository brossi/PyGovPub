"""
Configuration management for the CLI.

This module provides functions for managing configuration,
including environment variables and configuration files.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Create console for output
console = Console()

# Default configuration values
DEFAULT_CONFIG = {
    "api_keys": {
        "congress": "",
        "govinfo": ""
    },
    "options": {
        "default_format": "text",
        "cache_enabled": True,
        "cache_ttl": 3600
    }
}

# Environment variable prefix
ENV_PREFIX = "PYGOVPUB_"


def get_environment_value(name: str) -> Optional[str]:
    """Get value from environment variable."""
    return os.environ.get(name)


def set_environment_value(name: str, value: str) -> None:
    """Set environment variable value."""
    os.environ[name] = value


def get_config_file_path() -> Path:
    """Get path to configuration file."""
    # Use XDG_CONFIG_HOME if available, otherwise use ~/.pygovpub
    config_dir = os.environ.get("XDG_CONFIG_HOME")
    if config_dir:
        return Path(config_dir) / "pygovpub" / "config.json"
    else:
        return Path.home() / ".pygovpub" / "config.json"


def read_config_file() -> Dict[str, Any]:
    """Read configuration from file."""
    config_path = get_config_file_path()
    if not config_path.exists():
        return DEFAULT_CONFIG.copy()
    
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        
        # Ensure all required sections and keys exist
        for section, values in DEFAULT_CONFIG.items():
            if section not in config:
                config[section] = values
            else:
                for key, default_value in values.items():
                    if key not in config[section]:
                        config[section][key] = default_value
        
        return config
    except Exception as e:
        console.print(f"[red]Error reading config file: {e}[/red]")
        return DEFAULT_CONFIG.copy()


def write_config_file(config: Dict[str, Any]) -> None:
    """Write configuration to file."""
    config_path = get_config_file_path()
    
    # Create directory if it doesn't exist
    os.makedirs(config_path.parent, exist_ok=True)
    
    try:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, sort_keys=True)
    except Exception as e:
        console.print(f"[red]Error writing config file: {e}[/red]")


def get_config_value(key: str) -> Any:
    """Get configuration value by key.
    
    Keys should be in format "section.key", e.g., "api_keys.congress".
    """
    # Check environment variable first
    env_key = ENV_PREFIX + key.upper().replace(".", "_")
    env_value = get_environment_value(env_key)
    if env_value is not None:
        return env_value
    
    # If not in environment, check config file
    config = read_config_file()
    
    # Parse key
    parts = key.split(".")
    if len(parts) != 2:
        raise ValueError(f"Invalid config key: {key}. Must be in format 'section.key'")
    
    section, subkey = parts
    
    # Check if section and key exist
    if section not in config:
        return None
    
    if subkey not in config[section]:
        return None
    
    return config[section][subkey]


def set_config_value(key: str, value: str) -> None:
    """Set configuration value by key.
    
    Keys should be in format "section.key", e.g., "api_keys.congress".
    """
    # Parse key
    parts = key.split(".")
    if len(parts) != 2:
        raise ValueError(f"Invalid config key: {key}. Must be in format 'section.key'")
    
    section, subkey = parts
    
    # Get current config
    config = read_config_file()
    
    # Create section if it doesn't exist
    if section not in config:
        config[section] = {}
    
    # Set value
    config[section][subkey] = value
    
    # Write config
    write_config_file(config)


def list_config() -> None:
    """List all configuration values."""
    config = read_config_file()
    
    # Create table for output
    table = Table(title="PyGovPub Configuration")
    table.add_column("Section", style="cyan")
    table.add_column("Key", style="green")
    table.add_column("Value")
    table.add_column("Source", style="dim")
    
    # Add rows for each config value
    for section, values in sorted(config.items()):
        for key, value in sorted(values.items()):
            # Check if value is overridden by environment variable
            env_key = ENV_PREFIX + f"{section}_{key}".upper()
            env_value = get_environment_value(env_key)
            
            if env_value is not None:
                source = "Environment"
                display_value = env_value
            else:
                source = "Config File"
                display_value = str(value)
            
            # Hide API keys for security
            if section == "api_keys" and display_value:
                display_value = "********" + display_value[-4:] if len(display_value) > 4 else "********"
            
            table.add_row(section, key, display_value, source)
    
    console.print(table)


def check_required_config() -> List[str]:
    """Check for required configuration values."""
    missing = []
    
    # Check API keys
    for api in ["congress", "govinfo"]:
        key = f"api_keys.{api}"
        value = get_config_value(key)
        if not value:
            missing.append(key)
    
    return missing