"""
Command-line interface for PyGovPub SDK.

This package provides CLI commands for interacting with the PyGovPub SDK.
"""

import importlib.metadata

try:
    __version__ = importlib.metadata.version("pygovpub")
except importlib.metadata.PackageNotFoundError:
    __version__ = "0.1.0"  # Default version if not installed

# Legacy CLI entry points
from .mock_server import start_mock_server_cli
from .schema_monitor import main as schema_monitor_cli
from .health import main as health_cli

# New unified CLI
from .main import app, main
from . import congress, govinfo, config, output