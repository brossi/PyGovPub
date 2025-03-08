"""Unit tests for the PyGovPub authentication module."""

# Import the actual package modules to make them available to tests
import sys
import os

# Add src directory to path if not already there
src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../src'))
if src_path not in sys.path:
    sys.path.insert(0, src_path)

try:
    import pygovpub
    import pygovpub.auth
    from pygovpub.auth import auth_manager, models, rate_limiter
except ImportError as e:
    print(f"Warning: Failed to import auth modules: {e}")