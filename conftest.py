"""
Pytest conftest.py file for PyGovPub project.

This file sets up the test environment including path configuration to ensure imports work properly.
"""

import os
import sys
import subprocess

# Update pip to avoid warnings
try:
    import pip
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', '--upgrade', 'pip'])
    print("Pip has been updated to the latest version")
except Exception as e:
    print(f"Warning: Failed to update pip: {e}")

# Add the parent directory and source directory to Python path so tests can find the modules
project_root = os.path.abspath(os.path.dirname(__file__))
src_path = os.path.join(project_root, 'src')
sys.path.insert(0, project_root)
sys.path.insert(0, src_path)

# This is critical for the editable package to work properly
os.environ['PYTHONPATH'] = src_path

# Print the current Python path for debugging
print("Python Path in conftest.py:", sys.path)