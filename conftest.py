"""
Pytest conftest.py file for PyGovPub project.

This file sets up the test environment including path configuration to ensure imports work properly.
"""

import os
import sys
import subprocess
from pathlib import Path

# Configuration to ensure consistent test environment
def setup_test_paths():
    """Configure Python path to ensure imports work correctly."""
    # Get project root directory (where conftest.py is located)
    project_root = Path(__file__).absolute().parent
    
    # Source directory containing the package
    src_dir = project_root / 'src'
    
    # Add paths to sys.path if not already there
    # This ensures both direct imports and package imports work
    for path in [str(project_root), str(src_dir)]:
        if path not in sys.path:
            sys.path.insert(0, path)
    
    # Set PYTHONPATH environment variable for child processes
    os.environ['PYTHONPATH'] = f"{str(src_dir)}:{os.environ.get('PYTHONPATH', '')}"
    
    return project_root, src_dir

# Run path setup
project_root, src_dir = setup_test_paths()

# Log path information for debugging
print(f"PyGovPub test environment setup:")
print(f"- Project root: {project_root}")
print(f"- Source directory: {src_dir}")
print(f"- sys.path[0:3]: {sys.path[0:3]}")
print(f"- PYTHONPATH: {os.environ.get('PYTHONPATH')}")

# Update pip to avoid warnings (but only if not running in CI environment)
if not os.environ.get('CI'):
    try:
        subprocess.check_call(
            [sys.executable, '-m', 'pip', 'install', '--quiet', '--upgrade', 'pip'],
            stdout=subprocess.DEVNULL
        )
    except Exception as e:
        print(f"Warning: Failed to update pip: {e}", file=sys.stderr)

# Install required testing packages if needed
required_packages = [
    'pytest-pythonpath',
    'structlog',
    'tenacity',
    'prometheus-client'
]

try:
    import importlib.metadata

    # Get installed packages
    installed_packages = {dist.metadata["Name"].lower() for dist in importlib.metadata.distributions()}
    
    # Check which required packages are missing
    missing_packages = [pkg for pkg in required_packages 
                        if pkg.lower() not in installed_packages]
    
    if missing_packages and not os.environ.get('CI'):
        print(f"Installing missing test dependencies: {', '.join(missing_packages)}")
        subprocess.check_call(
            [sys.executable, '-m', 'pip', 'install', '--quiet'] + missing_packages,
            stdout=subprocess.DEVNULL
        )
except Exception as e:
    print(f"Warning: Failed to check or install dependencies: {e}", file=sys.stderr)