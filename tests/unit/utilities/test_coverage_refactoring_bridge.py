#!/usr/bin/env python3
"""Unit tests for the coverage_refactoring_bridge module."""

import unittest
from unittest.mock import patch, MagicMock, mock_open
import json
import os
from pathlib import Path
import tempfile
import sys
from io import StringIO

# Import the module under test
from utilities.coverage_refactoring_bridge import (
    RefactoringRiskScore,
    CoverageRefactoringBridge
)

# Import other required modules
from utilities.refactoring_recommendations import RefactoringRecommendation
from utilities.source_analyzer import SourceFile


class TestRefactoringRiskScore(unittest.TestCase):
    """Test suite for the RefactoringRiskScore class."""

    def test_risk_level_high(self):
        """Test that risk level is HIGH when score is >= 8.0."""
        score = RefactoringRiskScore(
            function_name="test_func",
            file_path="test.py",
            cyclomatic_complexity=10,
            cognitive_complexity=15,
            coverage_percentage=50.0,
            risk_score=8.0
        )
        self.assertEqual(score.risk_level, "HIGH")

    def test_risk_level_medium(self):
        """Test that risk level is MEDIUM when score is >= 5.0 and < 8.0."""
        score = RefactoringRiskScore(
            function_name="test_func",
            file_path="test.py",
            cyclomatic_complexity=8,
            cognitive_complexity=10,
            coverage_percentage=70.0,
            risk_score=5.0
        )
        self.assertEqual(score.risk_level, "MEDIUM")

    def test_risk_level_low(self):
        """Test that risk level is LOW when score is < 5.0."""
        score = RefactoringRiskScore(
            function_name="test_func",
            file_path="test.py",
            cyclomatic_complexity=5,
            cognitive_complexity=5,
            coverage_percentage=90.0,
            risk_score=4.9
        )
        self.assertEqual(score.risk_level, "LOW")


class TestCoverageRefactoringBridge(unittest.TestCase):
    """Test suite for the CoverageRefactoringBridge class."""

    def setUp(self):
        """Set up test environment."""
        # Create a mock CoverageAnalyzer
        self.mock_coverage_analyzer = MagicMock()
        self.mock_coverage_analyzer.get_current_coverage.return_value = {
            "test_file.py": {
                "statements": 100,
                "missing_lines": {10, 20, 30, 40, 50},
                "coverage": 95.0
            }
        }

        # Create a mock SourceAnalyzer
        self.mock_source_analyzer = MagicMock()
        self.mock_source_analyzer.analyze_codebase.return_value = {
            "refactoring_opportunities": [
                {
                    "name": "test_function",
                    "file": "test_file.py",
                    "type": "FunctionDef",
                    "start_line": 1,
                    "end_line": 100,
                    "cyclomatic_complexity": 15,
                    "cognitive_complexity": 20,
                    "reasons": ["Function is too long (100 lines)"],
                    "suggestions": ["Break down into smaller functions"]
                }
            ],
            "summary": {
                "total_files": 1,
                "total_functions": 10,
                "total_classes": 2,
                "avg_cyclomatic_complexity": 5.0,
                "avg_cognitive_complexity": 8.0
            }
        }

        # Create a mock RefactoringRecommender
        self.mock_recommender = MagicMock()

        # Create the bridge with mocked dependencies
        with patch('utilities.coverage_refactoring_bridge.CoverageAnalyzer', return_value=self.mock_coverage_analyzer), \
             patch('utilities.coverage_refactoring_bridge.SourceAnalyzer', return_value=self.mock_source_analyzer), \
             patch('utilities.coverage_refactoring_bridge.RefactoringRecommender', return_value=self.mock_recommender):
            self.bridge = CoverageRefactoringBridge("test_package", ["test_stub_dir"])

    def test_calculate_risk_scores(self):
        """Test calculating risk scores."""
        # Set up the bridge with test data
        self.bridge.coverage_data = {
            "test_file.py": {
                "statements": 100,
                "missing_lines": {10, 20, 30, 40, 50},
                "coverage": 95.0
            }
        }

        self.bridge.refactoring_opportunities = [
            {
                "name": "test_function",
                "file": "test_file.py",
                "cyclomatic_complexity": 15,
                "cognitive_complexity": 20
            }
        ]

        # Calculate risk scores
        self.bridge.calculate_risk_scores()

        # Check that a risk score was created
        self.assertEqual(len(self.bridge.risk_scores), 1)

        # Check the risk score values
        risk_score = self.bridge.risk_scores[0]
        self.assertEqual(risk_score.function_name, "test_function")
        self.assertEqual(risk_score.file_path, "test_file.py")
        self.assertEqual(risk_score.cyclomatic_complexity, 15)
        self.assertEqual(risk_score.cognitive_complexity, 20)
        self.assertEqual(risk_score.coverage_percentage, 95.0)

        # Check that the risk score formula was applied correctly
        # Formula: (cyclomatic_complexity * 0.4 + cognitive_complexity * 0.3) * (1 + (100 - coverage_percentage) / 100)
        expected_score = (15 * 0.4 + 20 * 0.3) * (1 + (100 - 95.0) / 100)
        self.assertAlmostEqual(risk_score.risk_score, expected_score, places=2)

    def test_generate_coverage_aware_recommendations(self):
        """Test generating coverage-aware recommendations."""
        # Set up the bridge with test data
        self.bridge.risk_scores = [
            RefactoringRiskScore(
                function_name="test_function",
                file_path="test_file.py",
                cyclomatic_complexity=15,
                cognitive_complexity=20,
                coverage_percentage=95.0,
                risk_score=10.0,
                missing_lines={10, 20, 30, 40, 50}
            )
        ]

        self.bridge.refactoring_opportunities = [
            {
                "name": "test_function",
                "file": "test_file.py",
                "cyclomatic_complexity": 15,
                "cognitive_complexity": 20,
                "reasons": ["Function is too long (100 lines)"],
                "suggestions": ["Break down into smaller functions"]
            }
        ]

        # Generate recommendations
        recommendations = self.bridge.generate_coverage_aware_recommendations()

        # Check that a recommendation was created
        self.assertEqual(len(recommendations), 1)

        # Check the recommendation values
        recommendation = recommendations[0]
        self.assertEqual(recommendation["function_name"], "test_function")
        self.assertEqual(recommendation["file_path"], "test_file.py")
        self.assertEqual(recommendation["risk_level"], "HIGH")
        self.assertEqual(recommendation["risk_score"], 10.0)
        self.assertEqual(recommendation["coverage_percentage"], 95.0)
        self.assertEqual(recommendation["cyclomatic_complexity"], 15)
        self.assertEqual(recommendation["cognitive_complexity"], 20)
        self.assertEqual(recommendation["reasons"], ["Function is too long (100 lines)"])
        self.assertEqual(recommendation["suggestions"], ["Break down into smaller functions"])

        # Check that test recommendations were generated
        self.assertIn("test_recommendations", recommendation)
        self.assertIsInstance(recommendation["test_recommendations"], list)
        self.assertGreater(len(recommendation["test_recommendations"]), 0)

    def test_format_text_output(self):
        """Test formatting text output."""
        # Create test results
        results = {
            "summary": {
                "total_files": 1,
                "total_functions": 10,
                "total_classes": 2,
                "avg_cyclomatic_complexity": 5.0,
                "avg_cognitive_complexity": 8.0,
                "avg_coverage": 95.0,
                "high_risk_count": 1,
                "medium_risk_count": 2,
                "low_risk_count": 3
            },
            "recommendations": [
                {
                    "function_name": "test_function",
                    "file_path": "test_file.py",
                    "risk_level": "HIGH",
                    "risk_score": 10.0,
                    "coverage_percentage": 95.0,
                    "cyclomatic_complexity": 15,
                    "cognitive_complexity": 20,
                    "reasons": ["Function is too long (100 lines)"],
                    "suggestions": ["Break down into smaller functions"],
                    "test_recommendations": ["Write tests for 5 missing lines"]
                }
            ]
        }

        # Format the output
        output = self.bridge.format_text_output(results)

        # Check that the output contains expected sections
        self.assertIn("=== Coverage-Aware Refactoring Analysis ===", output)
        self.assertIn("Total files analyzed: 1", output)
        self.assertIn("Average coverage: 95.00%", output)
        self.assertIn("=== Coverage-Aware Refactoring Recommendations ===", output)
        self.assertIn("--- HIGH RISK REFACTORINGS ---", output)
        self.assertIn("File: test_file.py", output)
        self.assertIn("Function: test_function", output)
        self.assertIn("Risk Score: 10.00", output)
        self.assertIn("Coverage: 95.00%", output)
        self.assertIn("Cyclomatic Complexity: 15", output)
        self.assertIn("Cognitive Complexity: 20", output)
        self.assertIn("Function is too long (100 lines)", output)
        self.assertIn("Break down into smaller functions", output)
        self.assertIn("Write tests for 5 missing lines", output)


if __name__ == "__main__":
    unittest.main()
