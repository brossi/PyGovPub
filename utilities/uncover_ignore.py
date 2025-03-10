"""
Utility module for handling ignore patterns in coverage analysis.
"""

import os
from pathlib import Path
from typing import List, Optional, Union


def read_ignore_patterns_from_file(file_path: Union[str, Path]) -> List[str]:
    """
    Read ignore patterns from a file.

    Args:
        file_path: Path to the file containing ignore patterns

    Returns:
        List of ignore patterns
    """
    path = Path(file_path) if isinstance(file_path, str) else file_path

    if not path.exists():
        return []

    with open(path, 'r') as f:
        return [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]


def get_ignore_patterns(uncoverignore_path: Optional[Union[str, Path]] = None) -> List[str]:
    """
    Get patterns to ignore in coverage analysis.

    Args:
        uncoverignore_path: Optional path to a .uncoverignore file

    Returns:
        List of patterns to ignore
    """
    # Default patterns
    patterns = [
        "*/__pycache__/*",
        "*/\\.pytest_cache/*",
        "*/\\.git/*",
        "*/venv/*",
        "*/env/*",
        "*/\\.venv/*",
        "*/\\.env/*",
        "*/site-packages/*",
        "*/dist-packages/*",
        "*/tests/*",
        "*/test_*",
        "*/*_test.py",
        "conftest.py",
    ]

    # Read from .uncoverignore file if it exists
    if uncoverignore_path is None:
        # Try to find .uncoverignore in the current directory or parent directories
        current_dir = Path.cwd()
        while current_dir != current_dir.parent:
            uncoverignore_file = current_dir / '.uncoverignore'
            if uncoverignore_file.exists():
                uncoverignore_path = uncoverignore_file
                break
            current_dir = current_dir.parent

    if uncoverignore_path:
        path = Path(uncoverignore_path) if isinstance(uncoverignore_path, str) else uncoverignore_path
        if path.exists():
            patterns.extend(read_ignore_patterns_from_file(path))

    return patterns
