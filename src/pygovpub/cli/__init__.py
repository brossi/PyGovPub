"""
Command-line interface for PyGovPub SDK.
"""

from .mock_server import start_mock_server_cli
from .schema_monitor import main as schema_monitor_cli
from .health import main as health_cli