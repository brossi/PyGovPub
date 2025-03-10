#!/usr/bin/env python3
"""Tests for the refactoring recommendations module."""

import unittest
from pathlib import Path
import ast
import tempfile
import os

# Import the module we're testing
try:
    from utilities.refactoring_recommendations import (
        RefactoringRecommender,
        ExtractMethodRecommendation,
        ExtractConditionalRecommendation,
        ReplaceNestedConditionalsRecommendation,
        DecomposeComplexExpressionRecommendation,
        ExtractClassRecommendation
    )
except ImportError:
    # When running directly
    from refactoring_recommendations import (
        RefactoringRecommender,
        ExtractMethodRecommendation,
        ExtractConditionalRecommendation,
        ReplaceNestedConditionalsRecommendation,
        DecomposeComplexExpressionRecommendation,
        ExtractClassRecommendation
    )


class TestRefactoringRecommender(unittest.TestCase):
    """Test suite for the RefactoringRecommender class."""

    def setUp(self):
        """Set up test environment."""
        self.recommender = RefactoringRecommender()

        # Create a temporary file with a long function
        self.long_function_code = '''
def long_function(a, b, c):
    """This is a long function that should be refactored."""
    # Step 1: Initialize variables
    result = 0
    temp = 0

    # Step 2: Perform calculation
    if a > 0:
        temp = a * 2
    else:
        temp = a * -1

    # Step 3: Process b
    if b > 0:
        temp += b
    else:
        temp -= b

    # Step 4: Process c
    if c > 0:
        temp += c
    else:
        temp -= c

    # Step 5: Calculate final result
    result = temp * 2

    return result
'''
        self.temp_file = tempfile.NamedTemporaryFile(suffix='.py', mode='w+', delete=False)
        self.temp_file.write(self.long_function_code)
        self.temp_file.close()

        # Create a temporary file with complex conditionals
        self.complex_conditional_code = '''
def process_data(data, threshold, flag, option):
    """Process data with complex conditionals."""
    result = None

    if data is not None and len(data) > 0:
        if threshold > 0 and threshold < 100:
            if flag is True and option in ['A', 'B', 'C']:
                if data[0] > threshold:
                    result = "High priority"
                else:
                    result = "Medium priority"
            else:
                result = "Low priority"
        else:
            result = "Invalid threshold"
    else:
        result = "No data"

    return result
'''
        self.complex_conditional_file = tempfile.NamedTemporaryFile(suffix='.py', mode='w+', delete=False)
        self.complex_conditional_file.write(self.complex_conditional_code)
        self.complex_conditional_file.close()

    def tearDown(self):
        """Clean up test environment."""
        os.unlink(self.temp_file.name)
        os.unlink(self.complex_conditional_file.name)

    def test_extract_method_recommendation(self):
        """Test extract method recommendation for a long function."""
        # Parse the code
        with open(self.temp_file.name, 'r') as f:
            code = f.read()
        tree = ast.parse(code)

        # Find the function node
        function_node = None
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == 'long_function':
                function_node = node
                break

        self.assertIsNotNone(function_node, "Function node not found")

        # Get recommendation
        recommendation = self.recommender.get_extract_method_recommendation(
            function_node,
            Path(self.temp_file.name),
            code
        )

        # Check recommendation
        self.assertIsInstance(recommendation, ExtractMethodRecommendation)
        self.assertEqual(recommendation.function_name, 'long_function')
        self.assertGreater(len(recommendation.extracted_methods), 0)
        self.assertIn("def", recommendation.refactored_code)

        # Check that the recommendation includes the original code
        self.assertIn("long_function", recommendation.original_code)

        # Check that the recommendation includes step-by-step instructions
        self.assertGreater(len(recommendation.instructions), 0)

    def test_extract_conditional_recommendation(self):
        """Test extract conditional recommendation for complex conditionals."""
        # Parse the code
        with open(self.complex_conditional_file.name, 'r') as f:
            code = f.read()
        tree = ast.parse(code)

        # Find the function node
        function_node = None
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == 'process_data':
                function_node = node
                break

        self.assertIsNotNone(function_node, "Function node not found")

        # Get recommendation
        recommendation = self.recommender.get_extract_conditional_recommendation(
            function_node,
            Path(self.complex_conditional_file.name),
            code
        )

        # Check recommendation
        self.assertIsInstance(recommendation, ExtractConditionalRecommendation)
        self.assertEqual(recommendation.function_name, 'process_data')
        self.assertGreater(len(recommendation.extracted_conditionals), 0)
        self.assertIn("def", recommendation.refactored_code)

        # Check that the recommendation includes the original code
        self.assertIn("process_data", recommendation.original_code)

        # Check that the recommendation includes step-by-step instructions
        self.assertGreater(len(recommendation.instructions), 0)

    def test_replace_nested_conditionals_recommendation(self):
        """Test replace nested conditionals recommendation."""
        # Parse the code
        with open(self.complex_conditional_file.name, 'r') as f:
            code = f.read()
        tree = ast.parse(code)

        # Find the function node
        function_node = None
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == 'process_data':
                function_node = node
                break

        self.assertIsNotNone(function_node, "Function node not found")

        # Get recommendation
        recommendation = self.recommender.get_replace_nested_conditionals_recommendation(
            function_node,
            Path(self.complex_conditional_file.name),
            code
        )

        # Check recommendation
        self.assertIsInstance(recommendation, ReplaceNestedConditionalsRecommendation)
        self.assertEqual(recommendation.function_name, 'process_data')
        self.assertIn("def", recommendation.refactored_code)

        # Check that the recommendation includes the original code
        self.assertIn("process_data", recommendation.original_code)

        # Check that the recommendation includes step-by-step instructions
        self.assertGreater(len(recommendation.instructions), 0)


if __name__ == '__main__':
    unittest.main()
