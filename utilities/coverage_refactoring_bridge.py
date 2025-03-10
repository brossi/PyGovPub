#!/usr/bin/env python3
"""
Coverage Refactoring Bridge

This module integrates coverage data with refactoring analysis to provide
coverage-aware refactoring recommendations.
"""

import argparse
import json
import logging
import os
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any, Union

import xml.etree.ElementTree as ET

# Import local modules
try:
    from utilities.source_analyzer import SourceAnalyzer, SourceFile, AnalysisError
    from utilities.refactoring_recommendations import RefactoringRecommender, RefactoringRecommendation
    from utilities.projected_coverage import CoverageAnalyzer
    from utilities.uncover_ignore import get_ignore_patterns
except ImportError:
    # For direct execution
    from source_analyzer import SourceAnalyzer, SourceFile, AnalysisError
    from refactoring_recommendations import RefactoringRecommender, RefactoringRecommendation
    from projected_coverage import CoverageAnalyzer
    from uncover_ignore import get_ignore_patterns

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

@dataclass
class RefactoringRiskScore:
    """Risk score for a refactoring opportunity."""
    function_name: str
    file_path: str
    cyclomatic_complexity: int
    cognitive_complexity: int
    coverage_percentage: float
    risk_score: float
    missing_lines: Set[int] = field(default_factory=set)
    optimization_priority: str = "UNKNOWN"
    optimization_reasons: List[str] = field(default_factory=list)

    @property
    def risk_level(self) -> str:
        """Get the risk level based on the risk score."""
        if self.risk_score >= 8.0:
            return "HIGH"
        elif self.risk_score >= 5.0:
            return "MEDIUM"
        else:
            return "LOW"

    @property
    def is_premature_optimization(self) -> bool:
        """Determine if refactoring this code might be premature optimization."""
        return self.optimization_priority == "LOW"


class CoverageRefactoringBridge:
    """Bridge between coverage analysis and refactoring recommendations."""

    def __init__(self, package: str, stub_dirs: Optional[List[str]] = None):
        """Initialize the bridge.

        Args:
            package: The package to analyze
            stub_dirs: Directories containing test stubs
        """
        self.package = package
        self.stub_dirs = stub_dirs or []
        self.source_analyzer = SourceAnalyzer()
        self.recommender = RefactoringRecommender()
        self.coverage_analyzer = CoverageAnalyzer(package, self.stub_dirs)

        # Cache for analysis results
        self.coverage_data = {}
        self.refactoring_opportunities = []
        self.risk_scores = []

    def analyze(self, root_path: Path) -> Dict[str, Any]:
        """Analyze the codebase for coverage-aware refactoring opportunities.

        Args:
            root_path: The root path of the codebase to analyze

        Returns:
            A dictionary containing analysis results
        """
        # Get coverage data
        self.coverage_data = self.coverage_analyzer.get_current_coverage()

        # Get refactoring opportunities
        exclude_patterns = get_ignore_patterns()
        refactoring_results = self.source_analyzer.analyze_codebase(root_path, exclude_patterns)
        self.refactoring_opportunities = refactoring_results.get("refactoring_opportunities", [])

        # Calculate risk scores for each refactoring opportunity
        self.calculate_risk_scores()

        # Generate coverage-aware refactoring recommendations
        recommendations = self.generate_coverage_aware_recommendations()

        # Prepare the results
        results = {
            "coverage_data": self.coverage_data,
            "refactoring_opportunities": self.refactoring_opportunities,
            "risk_scores": [vars(score) for score in self.risk_scores],
            "recommendations": recommendations,
            "summary": {
                "total_files": refactoring_results.get("summary", {}).get("total_files", 0),
                "total_functions": refactoring_results.get("summary", {}).get("total_functions", 0),
                "total_classes": refactoring_results.get("summary", {}).get("total_classes", 0),
                "avg_cyclomatic_complexity": refactoring_results.get("summary", {}).get("avg_cyclomatic_complexity", 0),
                "avg_cognitive_complexity": refactoring_results.get("summary", {}).get("avg_cognitive_complexity", 0),
                "avg_coverage": self._calculate_average_coverage(),
                "high_risk_count": len([s for s in self.risk_scores if s.risk_level == "HIGH"]),
                "medium_risk_count": len([s for s in self.risk_scores if s.risk_level == "MEDIUM"]),
                "low_risk_count": len([s for s in self.risk_scores if s.risk_level == "LOW"]),
                "premature_optimization_count": len([s for s in self.risk_scores if s.is_premature_optimization])
            }
        }

        return results

    def calculate_risk_scores(self) -> None:
        """Calculate risk scores for refactoring opportunities."""
        self.risk_scores = []

        for opportunity in self.refactoring_opportunities:
            file_path = opportunity.get("file", "")
            function_name = opportunity.get("name", "")

            # Get coverage data for the file
            coverage_data = self._get_coverage_for_file(file_path)
            coverage_percentage = coverage_data.get("coverage", 0.0)
            missing_lines = set(coverage_data.get("missing_lines", []))

            # Get complexity metrics
            cyclomatic_complexity = opportunity.get("cyclomatic_complexity", 0)
            cognitive_complexity = opportunity.get("cognitive_complexity", 0)

            # Calculate risk score
            # Formula: (cyclomatic_complexity * 0.4 + cognitive_complexity * 0.3) * (1 + (100 - coverage_percentage) / 100)
            complexity_factor = (cyclomatic_complexity * 0.4 + cognitive_complexity * 0.3)
            coverage_factor = 1 + ((100 - coverage_percentage) / 100)
            risk_score = complexity_factor * coverage_factor

            # Assess optimization priority
            optimization_priority, optimization_reasons = self._assess_optimization_priority(
                opportunity,
                coverage_percentage,
                risk_score
            )

            # Create risk score object
            risk_score_obj = RefactoringRiskScore(
                function_name=function_name,
                file_path=file_path,
                cyclomatic_complexity=cyclomatic_complexity,
                cognitive_complexity=cognitive_complexity,
                coverage_percentage=coverage_percentage,
                risk_score=risk_score,
                missing_lines=missing_lines,
                optimization_priority=optimization_priority,
                optimization_reasons=optimization_reasons
            )

            self.risk_scores.append(risk_score_obj)

        # Sort risk scores by risk score (descending)
        self.risk_scores.sort(key=lambda x: x.risk_score, reverse=True)

    def _assess_optimization_priority(self,
                                     opportunity: Dict[str, Any],
                                     coverage_percentage: float,
                                     risk_score: float) -> Tuple[str, List[str]]:
        """
        Assess whether refactoring might be premature optimization.

        Returns:
            Tuple of (priority, list of reasons)
        """
        reasons = []

        # Get metrics
        cyclomatic_complexity = opportunity.get("cyclomatic_complexity", 0)
        cognitive_complexity = opportunity.get("cognitive_complexity", 0)
        function_length = opportunity.get("end_line", 0) - opportunity.get("start_line", 0) + 1

        # Check if the function is called frequently
        # This is a placeholder - in a real implementation, you would get this from profiling data
        is_frequently_called = False  # Placeholder

        # Check if the function is in a critical path
        # This is a placeholder - in a real implementation, you would get this from dependency analysis
        is_critical_path = False  # Placeholder

        # Assess priority based on multiple factors
        if risk_score >= 8.0:
            priority = "HIGH"
            reasons.append("High risk score indicates significant technical debt")
        elif coverage_percentage < 50.0:
            priority = "MEDIUM"
            reasons.append("Low test coverage makes refactoring risky but necessary")
        elif cyclomatic_complexity > 15:
            priority = "HIGH"
            reasons.append("Extremely high complexity indicates maintenance issues")
        elif function_length > 100:
            priority = "MEDIUM"
            reasons.append("Very long function affects readability and maintainability")
        elif is_frequently_called:
            priority = "HIGH"
            reasons.append("Function is called frequently, optimizing it will have high impact")
        elif is_critical_path:
            priority = "MEDIUM"
            reasons.append("Function is in a critical path, improvements will have system-wide benefits")
        elif function_length < 30 and cyclomatic_complexity < 5 and cognitive_complexity < 5:
            priority = "LOW"
            reasons.append("Function is relatively simple, refactoring may be premature optimization")
        elif coverage_percentage > 90.0 and risk_score < 5.0:
            priority = "LOW"
            reasons.append("Well-tested code with acceptable complexity, refactoring may be premature")
        else:
            priority = "MEDIUM"
            reasons.append("Standard refactoring candidate")

        return priority, reasons

    def generate_coverage_aware_recommendations(self) -> List[Dict[str, Any]]:
        """Generate coverage-aware refactoring recommendations."""
        recommendations = []

        for risk in self.risk_scores:
            # Find the original refactoring opportunity
            opportunity = next(
                (opp for opp in self.refactoring_opportunities
                 if opp.get("name") == risk.function_name and opp.get("file") == risk.file_path),
                {}
            )

            # Generate test recommendations
            test_recommendations = self._generate_test_recommendations(risk)

            # Create recommendation
            recommendation = {
                "function_name": risk.function_name,
                "file_path": risk.file_path,
                "risk_level": risk.risk_level,
                "risk_score": risk.risk_score,
                "coverage_percentage": risk.coverage_percentage,
                "cyclomatic_complexity": risk.cyclomatic_complexity,
                "cognitive_complexity": risk.cognitive_complexity,
                "reasons": opportunity.get("reasons", []),
                "suggestions": opportunity.get("suggestions", []),
                "test_recommendations": test_recommendations,
                "optimization_priority": risk.optimization_priority,
                "optimization_reasons": risk.optimization_reasons,
                "is_premature_optimization": risk.is_premature_optimization
            }

            recommendations.append(recommendation)

        return recommendations

    def _get_coverage_for_file(self, file_path: str) -> Dict[str, Any]:
        """Get coverage data for a file."""
        # Try direct match
        if file_path in self.coverage_data:
            return self.coverage_data[file_path]

        # Try to match by normalizing paths
        normalized_path = file_path.replace('\\', '/')
        for path, data in self.coverage_data.items():
            if path.replace('\\', '/').endswith(normalized_path):
                return data

            # Try matching by file name
            if Path(path).name == Path(file_path).name:
                return data

        return {}

    def _calculate_average_coverage(self) -> float:
        """Calculate the average coverage percentage."""
        if not self.coverage_data:
            return 0.0

        total_statements = 0
        total_covered = 0

        for file_data in self.coverage_data.values():
            statements = file_data.get("statements", 0)
            missing = len(file_data.get("missing_lines", set()))

            total_statements += statements
            total_covered += (statements - missing)

        if total_statements == 0:
            return 100.0

        return (total_covered / total_statements) * 100.0

    def _generate_test_recommendations(self, risk: RefactoringRiskScore) -> List[str]:
        """Generate test recommendations based on missing coverage."""
        recommendations = []

        if risk.coverage_percentage < 80:
            recommendations.append(f"Increase test coverage before refactoring (current: {risk.coverage_percentage:.1f}%)")

        if risk.missing_lines:
            recommendations.append(f"Write tests for {len(risk.missing_lines)} missing lines")

            # If there are specific patterns in the missing lines, add more specific recommendations
            if len(risk.missing_lines) > 10:
                recommendations.append("Focus on testing error handling and edge cases")

        return recommendations

    def format_text_output(self, results: Dict[str, Any], hide_premature_optimizations: bool = False) -> str:
        """
        Format results as text output.

        Args:
            results: Analysis results
            hide_premature_optimizations: If True, hide recommendations flagged as premature optimizations

        Returns:
            Formatted text output
        """
        output = []

        # Add summary
        output.append("=== Coverage-Aware Refactoring Analysis ===")
        summary = results.get("summary", {})
        output.append(f"Total files analyzed: {summary.get('total_files', 0)}")
        output.append(f"Total functions: {summary.get('total_functions', 0)}")
        output.append(f"Total classes: {summary.get('total_classes', 0)}")
        output.append(f"Average cyclomatic complexity: {summary.get('avg_cyclomatic_complexity', 0):.2f}")
        output.append(f"Average cognitive complexity: {summary.get('avg_cognitive_complexity', 0):.2f}")
        output.append(f"Average coverage: {summary.get('avg_coverage', 0):.2f}%")
        output.append(f"High risk refactorings: {summary.get('high_risk_count', 0)}")
        output.append(f"Medium risk refactorings: {summary.get('medium_risk_count', 0)}")
        output.append(f"Low risk refactorings: {summary.get('low_risk_count', 0)}")
        output.append(f"Potential premature optimizations: {summary.get('premature_optimization_count', 0)}")

        # Add recommendations
        output.append("\n=== Coverage-Aware Refactoring Recommendations ===")

        # Group recommendations by risk level
        recommendations = results.get("recommendations", [])

        if hide_premature_optimizations:
            recommendations = [r for r in recommendations if not r.get("is_premature_optimization", False)]
            output.append("\nNote: Premature optimizations are hidden. Use --show-all to display them.")

        high_risk = [r for r in recommendations if r.get("risk_level") == "HIGH"]
        medium_risk = [r for r in recommendations if r.get("risk_level") == "MEDIUM"]
        low_risk = [r for r in recommendations if r.get("risk_level") == "LOW"]

        # Add high risk recommendations
        if high_risk:
            output.append("\n--- HIGH RISK REFACTORINGS ---")
            for rec in high_risk:
                self._format_recommendation(rec, output)

        # Add medium risk recommendations
        if medium_risk:
            output.append("\n--- MEDIUM RISK REFACTORINGS ---")
            for rec in medium_risk:
                self._format_recommendation(rec, output)

        # Add low risk recommendations
        if low_risk:
            output.append("\n--- LOW RISK REFACTORINGS ---")
            for rec in low_risk:
                self._format_recommendation(rec, output)

        return "\n".join(output)

    def _format_recommendation(self, rec: Dict[str, Any], output: List[str]) -> None:
        """Format a single recommendation and append to output list."""
        output.append(f"\nFile: {rec.get('file_path', '')}")
        output.append(f"Function: {rec.get('function_name', '')}")
        output.append(f"Risk Score: {rec.get('risk_score', 0):.2f}")
        output.append(f"Coverage: {rec.get('coverage_percentage', 0):.2f}%")
        output.append(f"Cyclomatic Complexity: {rec.get('cyclomatic_complexity', 0)}")
        output.append(f"Cognitive Complexity: {rec.get('cognitive_complexity', 0)}")

        # Add optimization priority
        output.append(f"Optimization Priority: {rec.get('optimization_priority', 'UNKNOWN')}")
        if rec.get("is_premature_optimization", False):
            output.append("⚠️ Potential Premature Optimization")

        # Add reasons
        if rec.get("reasons"):
            output.append("\nReasons:")
            for reason in rec.get("reasons", []):
                output.append(f"  - {reason}")

        # Add suggestions
        if rec.get("suggestions"):
            output.append("\nRefactoring Suggestions:")
            for suggestion in rec.get("suggestions", []):
                output.append(f"  - {suggestion}")

        # Add optimization reasons
        if rec.get("optimization_reasons"):
            output.append("\nOptimization Assessment:")
            for reason in rec.get("optimization_reasons", []):
                output.append(f"  - {reason}")

        # Add test recommendations
        if rec.get("test_recommendations"):
            output.append("\nTest Recommendations:")
            for test_rec in rec.get("test_recommendations", []):
                output.append(f"  - {test_rec}")

        # Add detailed recommendations if available
        if "detailed_recommendations" in rec:
            output.append("\nDetailed Recommendations:")
            output.append(rec.get("detailed_recommendations", ""))


def main():
    """Run the coverage refactoring bridge."""
    parser = argparse.ArgumentParser(
        description="Analyze code for refactoring opportunities with coverage awareness"
    )

    parser.add_argument(
        "--package",
        required=True,
        help="Package to analyze"
    )

    parser.add_argument(
        "--path",
        required=True,
        help="Path to the codebase to analyze"
    )

    parser.add_argument(
        "--stub-dir",
        action="append",
        default=[],
        help="Directory containing test stubs (can be specified multiple times)"
    )

    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (text or json)"
    )

    parser.add_argument(
        "--output",
        help="Output file (default: stdout)"
    )

    parser.add_argument(
        "--detailed",
        action="store_true",
        help="Include detailed refactoring recommendations"
    )

    parser.add_argument(
        "--show-all",
        action="store_true",
        help="Show all refactoring recommendations, including potential premature optimizations"
    )

    args = parser.parse_args()

    # Create bridge
    bridge = CoverageRefactoringBridge(args.package, args.stub_dir)

    # Analyze codebase
    results = bridge.analyze(Path(args.path))

    # Format output
    if args.format == "json":
        output = json.dumps(results, indent=2)
    else:
        output = bridge.format_text_output(results, hide_premature_optimizations=not args.show_all)

    # Write output
    if args.output:
        with open(args.output, "w") as f:
            f.write(output)
    else:
        print(output)


if __name__ == "__main__":
    sys.exit(main())
