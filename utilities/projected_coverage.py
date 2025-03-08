#!/usr/bin/env python3
"""
Projected Code Coverage Calculator

This script analyzes current test coverage and test stubs to predict
the final coverage when all stub tests are implemented.

Usage:
    python projected_coverage.py [--stub-dir DIR] [--package PKG]
"""

import os
import re
import sys
import ast
import argparse
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Dict, Set, List, Tuple, Optional


class CoverageAnalyzer:
    """Analyzes current coverage and test stubs to project future coverage."""
    
    def __init__(self, package: str, stub_dirs: List[str]):
        self.package = package
        self.stub_dirs = stub_dirs
        self.current_coverage = {}
        self.missing_lines = defaultdict(set)
        self.stub_coverage = defaultdict(set)
        
    def get_current_coverage(self) -> Dict[str, Dict]:
        """Run coverage and parse detailed results."""
        result = subprocess.run(
            ["pytest", "--cov-report", "term-missing", f"--cov={self.package}", "tests/"],
            capture_output=True,
            text=True
        )
        
        coverage_data = {}
        current_file = None
        
        # Regular expression to match coverage report lines
        file_pattern = r"^([\w./]+)\s+(\d+)\s+(\d+)\s+(\d+)%\s+(.*)$"
        
        for line in result.stdout.split('\n'):
            match = re.match(file_pattern, line.strip())
            if match:
                filepath, stmts, miss, _, missing = match.groups()
                
                # Store missing lines
                missing_set = set()
                if missing and missing != "":
                    for range_str in missing.split(', '):
                        if '-' in range_str:
                            start, end = map(int, range_str.split('-'))
                            missing_set.update(range(start, end + 1))
                        else:
                            try:
                                missing_set.add(int(range_str))
                            except ValueError:
                                pass
                
                coverage_data[filepath] = {
                    'statements': int(stmts),
                    'missing': int(miss),
                    'missing_lines': missing_set
                }
                
                self.missing_lines[filepath] = missing_set
        
        self.current_coverage = coverage_data
        return coverage_data
    
    def analyze_test_stubs(self) -> Dict[str, Set[int]]:
        """Analyze test stubs to see which missing lines they would cover."""
        
        # Map the module path to its actual file path
        module_to_file = {}
        for file_path in self.current_coverage:
            parts = file_path.split('/')
            if len(parts) > 1:
                module = '.'.join(parts)
                module_to_file[module] = file_path
        
        # Pattern to find line coverage comments
        line_comment_pattern = re.compile(r'#\s*(?:STUB:\s*)?This tests (?:line|lines) (\d+(?:-\d+)?(?:,\s*\d+(?:-\d+)?)*)')
        
        for stub_dir in self.stub_dirs:
            for stub_file in Path(stub_dir).glob('**/*.py'):
                with open(stub_file, 'r') as f:
                    content = f.read()
                
                # Look for line coverage comments
                for line in content.split('\n'):
                    match = line_comment_pattern.search(line)
                    if match:
                        line_refs = match.group(1)
                        for line_ref in line_refs.split(','):
                            line_ref = line_ref.strip()
                            
                            if '-' in line_ref:
                                start, end = map(int, line_ref.split('-'))
                                covered_lines = set(range(start, end + 1))
                            else:
                                covered_lines = {int(line_ref)}
                            
                            # Try to determine which file this test covers
                            try:
                                tree = ast.parse(content)
                                imports = []
                                
                                for node in ast.walk(tree):
                                    if isinstance(node, ast.Import):
                                        for name in node.names:
                                            imports.append(name.name)
                                    elif isinstance(node, ast.ImportFrom):
                                        if node.module:
                                            imports.append(node.module)
                                
                                # Find relevant module based on imports
                                for module in imports:
                                    for potential_module in module_to_file:
                                        if module in potential_module:
                                            file_path = module_to_file[potential_module]
                                            self.stub_coverage[file_path].update(covered_lines)
                                            break
                                    else:
                                        continue
                                    break
                            except Exception as e:
                                print(f"Error analyzing {stub_file}: {e}", file=sys.stderr)
        
        return dict(self.stub_coverage)
    
    def calculate_projected_coverage(self) -> Dict[str, Dict]:
        """Calculate projected coverage after stubs are implemented."""
        projected = {}
        
        for file_path, data in self.current_coverage.items():
            # Get the set of lines that would be covered by stubs
            stub_covered = self.stub_coverage.get(file_path, set())
            
            # Calculate new missing lines (current missing minus those covered by stubs)
            new_missing = data['missing_lines'] - stub_covered
            new_missing_count = len(new_missing)
            
            # Calculate projected coverage
            statements = data['statements']
            covered = statements - new_missing_count
            percentage = round(100 * covered / statements, 1) if statements else 100
            
            projected[file_path] = {
                'statements': statements,
                'missing': new_missing_count,
                'covered': covered,
                'percentage': percentage,
                'current_percentage': round(100 * (statements - data['missing']) / statements, 1) if statements else 100,
                'improvement': round(percentage - (100 * (statements - data['missing']) / statements), 1) if statements else 0
            }
        
        return projected
    
    def display_results(self, projected: Dict[str, Dict]) -> None:
        """Display the projected coverage results in a readable format."""
        total_stmts = sum(data['statements'] for data in projected.values())
        total_missing = sum(data['missing'] for data in projected.values())
        total_covered = total_stmts - total_missing
        total_percentage = round(100 * total_covered / total_stmts, 1) if total_stmts else 100
        
        print("\n=================== PROJECTED COVERAGE REPORT ===================")
        print(f"{'Module':<40} {'Stmts':>8} {'Miss':>8} {'Cover':>8} {'Current':>8} {'Gain':>8}")
        print(f"{'-'*40} {'-'*8} {'-'*8} {'-'*8} {'-'*8} {'-'*8}")
        
        for file_path, data in sorted(projected.items()):
            print(f"{file_path:<40} {data['statements']:>8} {data['missing']:>8} {data['percentage']:>7}% {data['current_percentage']:>7}% {data['improvement']:>7}%")
        
        print(f"{'-'*40} {'-'*8} {'-'*8} {'-'*8} {'-'*8} {'-'*8}")
        print(f"{'TOTAL':<40} {total_stmts:>8} {total_missing:>8} {total_percentage:>7}% ")
        print("==================================================================\n")
        
        # Show any lines that would still be uncovered
        if total_missing > 0:
            print("Lines that would still be uncovered after implementing stubs:")
            for file_path, data in sorted(projected.items()):
                if data['missing'] > 0:
                    missing_lines = sorted(self.missing_lines[file_path] - self.stub_coverage.get(file_path, set()))
                    if missing_lines:
                        print(f"\n{file_path}:")
                        self._format_missing_lines(missing_lines)
        else:
            print("All lines would be covered after implementing stubs! 🎉")
    
    def _format_missing_lines(self, lines: List[int]) -> None:
        """Format missing lines in a human-readable way."""
        ranges = []
        start = end = lines[0]
        
        for line in lines[1:]:
            if line == end + 1:
                end = line
            else:
                if start == end:
                    ranges.append(str(start))
                else:
                    ranges.append(f"{start}-{end}")
                start = end = line
        
        if start == end:
            ranges.append(str(start))
        else:
            ranges.append(f"{start}-{end}")
        
        print("  " + ", ".join(ranges))


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Project code coverage based on test stubs")
    parser.add_argument("--stub-dir", dest="stub_dirs", action="append", default=[],
                        help="Directory containing test stubs (can specify multiple)")
    parser.add_argument("--package", default="pygovpub.auth",
                        help="Package to analyze (default: pygovpub.auth)")
    
    args = parser.parse_args()
    
    # Use default stub directory if none provided
    if not args.stub_dirs:
        args.stub_dirs = ["tests/unit/auth"]
    
    analyzer = CoverageAnalyzer(args.package, args.stub_dirs)
    analyzer.get_current_coverage()
    analyzer.analyze_test_stubs()
    projected = analyzer.calculate_projected_coverage()
    analyzer.display_results(projected)


if __name__ == "__main__":
    main()