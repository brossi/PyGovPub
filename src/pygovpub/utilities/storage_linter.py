"""
Storage component linter for PyGovPub.

This module provides linting rules specific to storage components in PyGovPub.
It helps ensure consistent patterns and best practices across the storage layer.

Usage:
    python -m pygovpub.utilities.storage_linter [--path PATH] [--strict]
"""

import argparse
import ast
import os
import sys
import re
from typing import List, Dict, Any, Set, Tuple, Optional

# Define patterns and rules
STORAGE_FILE_PATTERNS = [
    r"storage/.*\.py$",
    r"auth/.*\.py$",
    r"core/database.*\.py$",
]

CONNECTION_STRING_PATTERNS = [
    r"(\"|\')sqlite:///.*(\"|\')",
    r"(\"|\')postgresql://.*(\"|\')",
    r"(\"|\')mysql://.*(\"|\')",
    r"(\"|\')lancedb://.*(\"|\')"
]

REQUIRED_CIRCUIT_BREAKER_PATTERNS = [
    r"@CONNECTION_CIRCUIT_BREAKER",
    r"circuit_breaker\(",
]

REQUIRED_ERROR_HANDLING_PATTERNS = [
    r"try:",
    r"except .*:",
    r"OPERATIONS\.labels\(.*error.*\)",
]

REQUIRED_MONITORING_PATTERNS = [
    r"OPERATIONS\.labels\(",
    r"OPERATION_DURATION\.labels\(",
]

BANNED_PATTERNS = [
    r"time\.sleep\(",  # Use asyncio.sleep instead
    r"Session\(\)(?!.*with)",  # Session without with statement
]

NAMING_CONVENTIONS = {
    "connection_pools": r"^[a-z][a-z0-9_]*$",  # snake_case
    "provider_classes": r"^[A-Z][a-zA-Z0-9]*Provider$",  # PascalCase with Provider suffix
}


class StorageLinter:
    """Linter for storage components."""
    
    def __init__(self, strict: bool = False):
        """Initialize linter.
        
        Args:
            strict: If True, treat warnings as errors
        """
        self.strict = strict
        self.errors = []
        self.warnings = []
    
    def lint_file(self, file_path: str) -> bool:
        """Lint a storage-related file.
        
        Args:
            file_path: Path to Python file
            
        Returns:
            True if file passed all checks, False otherwise
        """
        # Skip if not a storage-related file
        if not self._is_storage_file(file_path):
            return True
            
        # Read file content
        with open(file_path, "r") as f:
            content = f.read()
        
        # Parse AST for deeper analysis
        try:
            tree = ast.parse(content)
        except SyntaxError as e:
            self.errors.append(f"{file_path}: Syntax error - {str(e)}")
            return False
        
        # Run all checks
        passed_all = True
        
        if not self._check_connection_string_safety(file_path, content):
            passed_all = False
            
        if not self._check_error_handling(file_path, content):
            passed_all = False
            
        if not self._check_circuit_breakers(file_path, content):
            passed_all = False
            
        if not self._check_monitoring(file_path, content):
            passed_all = False
            
        if not self._check_banned_patterns(file_path, content):
            passed_all = False
            
        if not self._check_naming_conventions(file_path, tree):
            passed_all = False
        
        return passed_all
    
    def _is_storage_file(self, file_path: str) -> bool:
        """Check if file is a storage-related file.
        
        Args:
            file_path: Path to Python file
            
        Returns:
            True if file is storage-related, False otherwise
        """
        for pattern in STORAGE_FILE_PATTERNS:
            if re.search(pattern, file_path):
                return True
        return False
    
    def _check_connection_string_safety(self, file_path: str, content: str) -> bool:
        """Check for unsafe connection strings.
        
        Args:
            file_path: Path to the file
            content: File content
            
        Returns:
            True if no issues found, False otherwise
        """
        passed = True
        for pattern in CONNECTION_STRING_PATTERNS:
            for match in re.finditer(pattern, content):
                conn_string = match.group(0)
                # Check for hardcoded credentials
                if "password" in conn_string and not re.search(r"password=(.*?)\$|password=:.*?:", conn_string):
                    self.errors.append(f"{file_path}: Hardcoded password in connection string: {conn_string}")
                    passed = False
                    
                # Check for absolute paths in SQLite connection strings
                if "sqlite:///" in conn_string and not "/:memory:" in conn_string:
                    if re.search(r"sqlite:///[A-Za-z]:|sqlite:///\/", conn_string):
                        self.warnings.append(f"{file_path}: Absolute path in SQLite connection string: {conn_string}")
                        if self.strict:
                            passed = False
        
        return passed
    
    def _check_error_handling(self, file_path: str, content: str) -> bool:
        """Check for proper error handling.
        
        Args:
            file_path: Path to the file
            content: File content
            
        Returns:
            True if no issues found, False otherwise
        """
        # Skip files that don't need error handling (e.g., model definitions)
        if "_model" in file_path.lower() or "models.py" in file_path.lower():
            return True
            
        passed = True
        
        # Check if file has typical database operations
        has_db_operations = (
            "session" in content.lower() or 
            "engine" in content.lower() or
            "execute" in content.lower() or
            "query" in content.lower()
        )
        
        if has_db_operations:
            # Check for try-except blocks
            if not re.search(r"try:", content):
                self.errors.append(f"{file_path}: Missing try-except blocks for error handling")
                passed = False
                
            # Check for error metrics
            has_error_metrics = False
            for pattern in REQUIRED_ERROR_HANDLING_PATTERNS:
                if re.search(pattern, content):
                    has_error_metrics = True
                    break
                    
            if not has_error_metrics:
                self.warnings.append(f"{file_path}: Missing error metrics tracking")
                if self.strict:
                    passed = False
        
        return passed
    
    def _check_circuit_breakers(self, file_path: str, content: str) -> bool:
        """Check for circuit breaker usage.
        
        Args:
            file_path: Path to the file
            content: File content
            
        Returns:
            True if no issues found, False otherwise
        """
        # Skip files that don't need circuit breakers
        if (
            "_model" in file_path.lower() or 
            "models.py" in file_path.lower() or
            "interface.py" in file_path.lower()
        ):
            return True
            
        passed = True
        
        # Check if file has methods that should have circuit breakers
        has_public_methods = bool(re.search(r"def [a-z][a-zA-Z0-9_]*\(", content))
        has_db_operations = (
            "session" in content.lower() or 
            "engine" in content.lower() or
            "execute" in content.lower() or
            "query" in content.lower()
        )
        
        if has_public_methods and has_db_operations:
            # Check for circuit breaker patterns
            has_circuit_breaker = False
            for pattern in REQUIRED_CIRCUIT_BREAKER_PATTERNS:
                if re.search(pattern, content):
                    has_circuit_breaker = True
                    break
                    
            if not has_circuit_breaker:
                self.warnings.append(f"{file_path}: Missing circuit breaker for database operations")
                if self.strict:
                    passed = False
        
        return passed
    
    def _check_monitoring(self, file_path: str, content: str) -> bool:
        """Check for monitoring metrics.
        
        Args:
            file_path: Path to the file
            content: File content
            
        Returns:
            True if no issues found, False otherwise
        """
        # Skip files that don't need monitoring
        if (
            "_model" in file_path.lower() or 
            "models.py" in file_path.lower()
        ):
            return True
            
        passed = True
        
        # Check if file has database operations
        has_db_operations = (
            "session" in content.lower() or 
            "engine" in content.lower() or
            "execute" in content.lower() or
            "query" in content.lower()
        )
        
        if has_db_operations:
            # Check for monitoring patterns
            has_monitoring = False
            for pattern in REQUIRED_MONITORING_PATTERNS:
                if re.search(pattern, content):
                    has_monitoring = True
                    break
                    
            if not has_monitoring:
                self.warnings.append(f"{file_path}: Missing monitoring metrics for database operations")
                if self.strict:
                    passed = False
        
        return passed
    
    def _check_banned_patterns(self, file_path: str, content: str) -> bool:
        """Check for banned patterns.
        
        Args:
            file_path: Path to the file
            content: File content
            
        Returns:
            True if no issues found, False otherwise
        """
        passed = True
        
        for pattern in BANNED_PATTERNS:
            if re.search(pattern, content):
                self.errors.append(f"{file_path}: Contains banned pattern: {pattern}")
                passed = False
        
        return passed
    
    def _check_naming_conventions(self, file_path: str, tree: ast.AST) -> bool:
        """Check naming conventions.
        
        Args:
            file_path: Path to the file
            tree: AST tree of the file
            
        Returns:
            True if no issues found, False otherwise
        """
        passed = True
        
        # Check class names
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Check provider class naming
                if "Provider" in node.name:
                    if not re.match(NAMING_CONVENTIONS["provider_classes"], node.name):
                        self.errors.append(f"{file_path}: Class {node.name} does not follow provider naming convention (PascalCase with Provider suffix)")
                        passed = False
            
            # Check variable names
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and "pool" in target.id.lower():
                        if not re.match(NAMING_CONVENTIONS["connection_pools"], target.id):
                            self.errors.append(f"{file_path}: Variable {target.id} does not follow connection pool naming convention (snake_case)")
                            passed = False
        
        return passed
    
    def lint_directory(self, directory: str) -> Tuple[int, int]:
        """Lint all Python files in directory.
        
        Args:
            directory: Path to directory
            
        Returns:
            Tuple of (error_count, warning_count)
        """
        error_count = 0
        warning_count = 0
        
        for root, _, files in os.walk(directory):
            for file in files:
                if file.endswith(".py"):
                    file_path = os.path.join(root, file)
                    if not self.lint_file(file_path):
                        error_count += 1
        
        error_count = len(self.errors)
        warning_count = len(self.warnings)
        
        return error_count, warning_count
    
    def print_report(self) -> None:
        """Print lint report."""
        if self.errors:
            print("\nErrors:")
            for error in self.errors:
                print(f"  - {error}")
                
        if self.warnings:
            print("\nWarnings:")
            for warning in self.warnings:
                print(f"  - {warning}")
                
        print(f"\nSummary: {len(self.errors)} errors, {len(self.warnings)} warnings")


def main() -> int:
    """Run linter from command line."""
    parser = argparse.ArgumentParser(description="Storage component linter for PyGovPub")
    parser.add_argument("--path", default="src/pygovpub", help="Path to lint")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as errors")
    
    args = parser.parse_args()
    
    linter = StorageLinter(strict=args.strict)
    error_count, warning_count = linter.lint_directory(args.path)
    linter.print_report()
    
    if error_count > 0 or (args.strict and warning_count > 0):
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())