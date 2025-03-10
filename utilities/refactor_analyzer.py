#!/usr/bin/env python3
"""
Refactoring Opportunity Analyzer

This script analyzes a codebase to identify refactoring opportunities based on
complexity metrics including cyclomatic complexity and cognitive complexity.

Usage:
    python refactor_analyzer.py [--path PATH] [--exclude PATTERN]
    python refactor_analyzer.py --file FILE
"""

import argparse
import json
import sys
import ast
from pathlib import Path
from typing import List, Dict, Any, Optional

try:
    # When run as a module
    from utilities.source_analyzer import SourceAnalyzer, SourceFile, AnalysisError
    from utilities.refactoring_recommendations import RefactoringRecommender
except ImportError:
    # When run directly
    from source_analyzer import SourceAnalyzer, SourceFile, AnalysisError
    from refactoring_recommendations import RefactoringRecommender

def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Analyze a codebase for refactoring opportunities"
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--path",
        type=str,
        help="Path to the codebase to analyze"
    )
    group.add_argument(
        "--file",
        type=str,
        help="Path to a specific file to analyze"
    )

    parser.add_argument(
        "--exclude",
        type=str,
        action="append",
        help="Glob patterns to exclude from analysis (can be specified multiple times)"
    )

    parser.add_argument(
        "--format",
        type=str,
        choices=["text", "json"],
        default="text",
        help="Output format (text or json)"
    )

    parser.add_argument(
        "--output",
        type=str,
        help="Output file (default: stdout)"
    )

    parser.add_argument(
        "--threshold-cc",
        type=int,
        default=10,
        help="Cyclomatic complexity threshold (default: 10)"
    )

    parser.add_argument(
        "--threshold-cog",
        type=int,
        default=15,
        help="Cognitive complexity threshold (default: 15)"
    )

    parser.add_argument(
        "--threshold-lines",
        type=int,
        default=30,
        help="Function length threshold in lines (default: 30)"
    )

    parser.add_argument(
        "--detailed",
        action="store_true",
        help="Include detailed refactoring recommendations with code examples"
    )

    parser.add_argument(
        "--recommendation-type",
        type=str,
        choices=["extract-method", "extract-conditional", "guard-clauses", "all"],
        default="all",
        help="Type of refactoring recommendations to include (default: all)"
    )

    return parser.parse_args()

def format_text_output(results: Dict[str, Any], detailed: bool = False) -> str:
    """Format analysis results as text.

    Args:
        results: The analysis results
        detailed: Whether to include detailed recommendations

    Returns:
        The formatted output as a string
    """
    output = []

    # Add summary
    summary = results.get("summary", {})
    output.append("=== Codebase Analysis Summary ===")
    output.append(f"Total files analyzed: {summary.get('total_files', 0)}")
    output.append(f"Total lines of code: {summary.get('total_lines', 0)}")
    output.append(f"Total functions: {summary.get('total_functions', 0)}")
    output.append(f"Total classes: {summary.get('total_classes', 0)}")
    output.append(f"Average cyclomatic complexity: {summary.get('avg_cyclomatic_complexity', 0):.2f}")
    output.append(f"Average cognitive complexity: {summary.get('avg_cognitive_complexity', 0):.2f}")
    output.append(f"Files needing refactoring: {summary.get('files_needing_refactoring', 0)}")
    output.append("")

    # Add refactoring opportunities
    opportunities = results.get("refactoring_opportunities", [])
    if opportunities:
        output.append("=== Refactoring Opportunities ===")
        for opp in opportunities:
            output.append(f"File: {opp.get('file', 'Unknown')}")
            output.append(f"  {opp.get('type', 'Function')}: {opp.get('name', 'Unknown')} (lines {opp.get('start_line', '?')}-{opp.get('end_line', '?')})")
            output.append(f"  Cyclomatic complexity: {opp.get('cyclomatic_complexity', 0)}")
            output.append(f"  Cognitive complexity: {opp.get('cognitive_complexity', 0)}")
            output.append("  Reasons:")
            for reason in opp.get("reasons", []):
                output.append(f"    - {reason}")
            output.append("  Suggestions:")
            for suggestion in opp.get("suggestions", []):
                output.append(f"    - {suggestion}")

            # Add detailed recommendations if available and requested
            if detailed and "recommendations" in opp:
                output.append("")
                output.append("  Detailed Recommendations:")
                for rec in opp.get("recommendations", []):
                    output.append(rec)

            output.append("")
    else:
        output.append("No refactoring opportunities identified.")

    return "\n".join(output)

def main() -> int:
    """Main entry point."""
    args = parse_args()

    try:
        analyzer = SourceAnalyzer()
        recommender = RefactoringRecommender()

        if args.file:
            # Analyze a single file
            file_path = Path(args.file)
            if not file_path.exists():
                print(f"Error: File not found: {file_path}", file=sys.stderr)
                return 1

            source_file = analyzer.identify_source_file(file_path)
            opportunities = analyzer.identify_refactoring_opportunities(source_file)
            quality_metrics = analyzer.calculate_quality_metrics(source_file)

            # Add detailed recommendations if requested
            if args.detailed:
                source_code = source_file.read()
                tree = analyzer.parse_source(source_file)

                for opp in opportunities:
                    # Find the corresponding AST node
                    function_node = None
                    for node in ast.walk(tree):
                        if (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and
                            node.name == opp['name'] and
                            node.lineno == opp['start_line']):
                            function_node = node
                            break

                    if function_node:
                        recommendations = []

                        # Generate recommendations based on the type of issue
                        if args.recommendation_type in ["extract-method", "all"] and "Function is too long" in " ".join(opp.get("reasons", [])):
                            rec = recommender.get_extract_method_recommendation(function_node, file_path, source_code)
                            recommendations.append(rec.format_recommendation())

                        if args.recommendation_type in ["extract-conditional", "all"] and "High cyclomatic complexity" in " ".join(opp.get("reasons", [])):
                            rec = recommender.get_extract_conditional_recommendation(function_node, file_path, source_code)
                            recommendations.append(rec.format_recommendation())

                        if args.recommendation_type in ["guard-clauses", "all"] and "High cognitive complexity" in " ".join(opp.get("reasons", [])):
                            rec = recommender.get_replace_nested_conditionals_recommendation(function_node, file_path, source_code)
                            recommendations.append(rec.format_recommendation())

                        if recommendations:
                            opp["recommendations"] = recommendations

            results = {
                "metrics": {
                    str(file_path): {
                        "loc": quality_metrics.loc,
                        "sloc": quality_metrics.sloc,
                        "cyclomatic_complexity": quality_metrics.cyclomatic_complexity,
                        "cognitive_complexity": quality_metrics.cognitive_complexity,
                        "maintainability_index": quality_metrics.maintainability_index
                    }
                },
                "refactoring_opportunities": [],
                "summary": {
                    "total_files": 1,
                    "total_lines": quality_metrics.loc,
                    "total_functions": 0,  # Will be updated below
                    "total_classes": 0,    # Will be updated below
                    "avg_cyclomatic_complexity": quality_metrics.cyclomatic_complexity,
                    "avg_cognitive_complexity": quality_metrics.cognitive_complexity,
                    "files_needing_refactoring": 1 if opportunities else 0
                }
            }

            # Add file path to opportunities
            for opp in opportunities:
                opp["file"] = str(file_path)
                results["refactoring_opportunities"].append(opp)

            # Count functions and classes
            tree = analyzer.parse_source(source_file)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    results["summary"]["total_functions"] += 1
                elif isinstance(node, ast.ClassDef):
                    results["summary"]["total_classes"] += 1

        else:
            # Analyze a codebase
            root_path = Path(args.path)
            if not root_path.exists():
                print(f"Error: Path not found: {root_path}", file=sys.stderr)
                return 1

            exclude_patterns = args.exclude or ['**/venv/**', '**/.git/**', '**/__pycache__/**', '**/.pytest_cache/**']
            results = analyzer.analyze_codebase(root_path, exclude_patterns)

            # Add detailed recommendations if requested
            if args.detailed:
                for opp in results.get("refactoring_opportunities", []):
                    file_path = Path(opp["file"])
                    if not file_path.exists():
                        continue

                    try:
                        source_file = analyzer.identify_source_file(file_path)
                        source_code = source_file.read()
                        tree = analyzer.parse_source(source_file)

                        # Find the corresponding AST node
                        function_node = None
                        for node in ast.walk(tree):
                            if (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and
                                node.name == opp['name'] and
                                node.lineno == opp['start_line']):
                                function_node = node
                                break

                        if function_node:
                            recommendations = []

                            # Generate recommendations based on the type of issue
                            if args.recommendation_type in ["extract-method", "all"] and "Function is too long" in " ".join(opp.get("reasons", [])):
                                rec = recommender.get_extract_method_recommendation(function_node, file_path, source_code)
                                recommendations.append(rec.format_recommendation())

                            if args.recommendation_type in ["extract-conditional", "all"] and "High cyclomatic complexity" in " ".join(opp.get("reasons", [])):
                                rec = recommender.get_extract_conditional_recommendation(function_node, file_path, source_code)
                                recommendations.append(rec.format_recommendation())

                            if args.recommendation_type in ["guard-clauses", "all"] and "High cognitive complexity" in " ".join(opp.get("reasons", [])):
                                rec = recommender.get_replace_nested_conditionals_recommendation(function_node, file_path, source_code)
                                recommendations.append(rec.format_recommendation())

                            if recommendations:
                                opp["recommendations"] = recommendations
                    except Exception as e:
                        print(f"Warning: Failed to generate recommendations for {file_path}: {str(e)}", file=sys.stderr)

        # Format and output results
        if args.format == "json":
            output = json.dumps(results, indent=2)
        else:
            output = format_text_output(results, args.detailed)

        if args.output:
            with open(args.output, "w") as f:
                f.write(output)
        else:
            print(output)

        return 0

    except AnalysisError as e:
        print(f"Analysis error: {str(e)}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {str(e)}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())
