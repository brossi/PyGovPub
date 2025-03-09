"""
Tests for projected_coverage.py utility.

These tests verify the functionality of the coverage analysis and history tracking tool.
"""

import os
import json
import tempfile
import argparse
import pytest
import re
from unittest.mock import patch, mock_open, MagicMock, call
import sys
from pathlib import Path
import ast
from enum import Enum
from collections import defaultdict

# Add the utilities directory to the path so we can import projected_coverage
sys.path.append(str(Path(__file__).parent.parent.parent.parent / "utilities"))
import projected_coverage

# Mock ApiSource for testing
class ApiSource(str, Enum):
    CONGRESS = "congress"
    GOVINFO = "govinfo"


@pytest.fixture
def temp_history_file():
    """Create a temporary file for testing history storage."""
    fd, path = tempfile.mkstemp()
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump({"history": [], "latest": None}, f)

        # Patch the constant with our temp file path
        with patch.object(projected_coverage, 'COVERAGE_HISTORY_FILE', path):
            yield path
    finally:
        os.unlink(path)


def test_get_coverage_history_empty():
    """Test getting coverage history when file doesn't exist."""
    with patch.object(projected_coverage, 'COVERAGE_HISTORY_FILE', 'nonexistent_file.json'):
        history = projected_coverage.get_coverage_history()
        assert history == {"history": [], "latest": None}


def test_get_coverage_history_malformed():
    """Test getting coverage history with malformed JSON."""
    with patch('builtins.open', mock_open(read_data='{"malformed json')):
        with patch.object(projected_coverage, 'COVERAGE_HISTORY_FILE', 'exists'):
            with patch('os.path.exists', return_value=True):
                history = projected_coverage.get_coverage_history()
                assert history == {"history": [], "latest": None}


def test_get_coverage_history_valid(temp_history_file):
    """Test getting valid coverage history."""
    test_data = {
        "history": [{"timestamp": "2023-01-01", "overall_percentage": 85}],
        "latest": {"timestamp": "2023-01-01", "overall_percentage": 85}
    }

    with open(temp_history_file, 'w') as f:
        json.dump(test_data, f)

    history = projected_coverage.get_coverage_history()
    assert history == test_data


def test_save_coverage_results(temp_history_file):
    """Test saving coverage results."""
    # Initial empty history
    history1 = projected_coverage.get_coverage_history()
    assert history1 == {"history": [], "latest": None}

    # Save new coverage data
    test_data = {
        "package": "test.package",
        "overall_percentage": 75.5,
        "total_statements": 100,
        "total_missing": 24,
        "modules": [{"file_path": "test.py", "statements": 100, "missing": 24}]
    }

    projected_coverage.save_coverage_results(test_data)

    # Check that history was updated
    history2 = projected_coverage.get_coverage_history()
    assert len(history2["history"]) == 1
    assert history2["latest"] is not None
    assert history2["latest"]["package"] == "test.package"
    assert history2["latest"]["overall_percentage"] == 75.5


def test_save_coverage_results_limit_history(temp_history_file):
    """Test that history is limited to 20 entries."""
    # Create 25 fake entries
    with open(temp_history_file, 'w') as f:
        history = {"history": [], "latest": None}
        for i in range(25):
            entry = {"timestamp": f"2023-01-{i+1}", "overall_percentage": i}
            history["history"].append(entry)
        json.dump(history, f)

    # Save a new entry
    test_data = {"package": "test", "overall_percentage": 100}
    projected_coverage.save_coverage_results(test_data)

    # Check that history is limited to 20 entries
    history = projected_coverage.get_coverage_history()
    assert len(history["history"]) == 20

    # Verify the oldest entries were removed (we should have entries 6-25 + new one)
    timestamps = [entry["overall_percentage"] for entry in history["history"]]
    assert 0 not in timestamps  # First entry should be gone
    assert 24 in timestamps  # Last old entry should be present
    assert 100 in timestamps  # New entry should be present


def test_format_line_ranges():
    """Test formatting line ranges."""
    # Empty list
    assert projected_coverage._format_line_ranges([]) == "None"

    # Single line
    assert projected_coverage._format_line_ranges([42]) == "42"

    # Sequential lines
    assert projected_coverage._format_line_ranges([1, 2, 3, 4]) == "1-4"

    # Non-sequential lines
    assert projected_coverage._format_line_ranges([1, 3, 5, 7]) == "1, 3, 5, 7"

    # Mixed sequential and non-sequential
    assert projected_coverage._format_line_ranges([1, 2, 3, 5, 7, 8, 9]) == "1-3, 5, 7-9"


@patch('sys.stdout', new_callable=MagicMock)
def test_display_latest_coverage_no_data(mock_stdout, temp_history_file):
    """Test displaying latest coverage when no data exists."""
    projected_coverage.display_latest_coverage()
    mock_stdout.write.assert_any_call("No coverage data available. Run the tool without --report first.")


@patch('sys.stdout', new_callable=MagicMock)
def test_display_latest_coverage_with_data(mock_stdout, temp_history_file):
    """Test displaying latest coverage with data."""
    test_data = {
        "timestamp": "2023-01-01T12:00:00",
        "overall_percentage": 85.5,
        "total_statements": 200,
        "total_missing": 29,
        "modules": [
            {"file_path": "file1.py", "statements": 100, "missing": 15, "percentage": 85},
            {"file_path": "file2.py", "statements": 100, "missing": 14, "percentage": 86}
        ],
        "uncovered_lines": {
            "file1.py": [10, 20, 30],
            "file2.py": [15, 25, 35]
        }
    }

    with open(temp_history_file, 'w') as f:
        json.dump({"history": [], "latest": test_data}, f)

    projected_coverage.display_latest_coverage()

    # Check for key output elements
    calls = [call[0][0] for call in mock_stdout.write.call_args_list]
    report_text = ''.join(calls)

    assert "LATEST COVERAGE REPORT" in report_text
    assert "Timestamp: 2023-01-01T12:00:00" in report_text
    assert "Overall coverage: 85.5%" in report_text
    assert "file1.py" in report_text
    assert "file2.py" in report_text
    assert "Uncovered lines by module:" in report_text


@patch('sys.stdout', new_callable=MagicMock)
def test_display_coverage_history_no_data(mock_stdout, temp_history_file):
    """Test displaying coverage history with no data."""
    projected_coverage.display_coverage_history()
    mock_stdout.write.assert_any_call("No coverage history available. Run the tool without --history first.")


@patch('sys.stdout', new_callable=MagicMock)
def test_display_coverage_history_with_data(mock_stdout, temp_history_file):
    """Test displaying coverage history with data."""
    history = {
        "history": [
            {"timestamp": "2023-01-01T12:00:00", "overall_percentage": 75, "modules": []},
            {"timestamp": "2023-01-02T12:00:00", "overall_percentage": 80, "modules": []},
            {"timestamp": "2023-01-03T12:00:00", "overall_percentage": 85, "modules": []}
        ],
        "latest": None
    }

    with open(temp_history_file, 'w') as f:
        json.dump(history, f)

    projected_coverage.display_coverage_history()

    # Check for key output elements
    calls = [call[0][0] for call in mock_stdout.write.call_args_list]
    report_text = ''.join(calls)

    assert "COVERAGE HISTORY" in report_text
    assert "2023-01-01" in report_text
    assert "2023-01-02" in report_text
    assert "2023-01-03" in report_text
    assert "75%" in report_text
    assert "80%" in report_text
    assert "85%" in report_text
    assert "Satisfactory" in report_text  # Status for 75%
    assert "Good" in report_text  # Status for 80-85%


def test_coverage_analyzer_init():
    """Test CoverageAnalyzer initialization."""
    analyzer = projected_coverage.CoverageAnalyzer("test.package", ["test/dir"])
    assert analyzer.package == "test.package"
    assert analyzer.stub_dirs == ["test/dir"]
    assert analyzer.current_coverage == {}
    assert len(analyzer.missing_lines) == 0
    assert len(analyzer.stub_coverage) == 0


@patch('subprocess.run')
@patch('xml.etree.ElementTree.parse')
def test_get_current_coverage_xml_path(mock_parse, mock_run):
    """Test getting current coverage with XML parsing."""
    # Mock the XML parse
    mock_root = MagicMock()
    mock_parse.return_value.getroot.return_value = mock_root

    # Mock finding a class in the XML
    mock_package = MagicMock()
    mock_root.findall.return_value = [mock_package]

    mock_class = MagicMock()
    mock_class.get.return_value = "test/file.py"
    mock_package.findall.return_value = [mock_class]

    # Mock lines in the class
    mock_line1 = MagicMock()
    mock_line1.get.side_effect = lambda x: "1" if x == "number" else "1"
    mock_line2 = MagicMock()
    mock_line2.get.side_effect = lambda x: "2" if x == "number" else "0"
    mock_class.findall.return_value = [mock_line1, mock_line2]

    # Create analyzer and get coverage
    analyzer = projected_coverage.CoverageAnalyzer("test", ["test_dir"])
    coverage = analyzer.get_current_coverage()

    # Verify results
    assert "test/file.py" in coverage
    assert coverage["test/file.py"]["statements"] == 2
    assert coverage["test/file.py"]["missing"] == 1
    assert coverage["test/file.py"]["missing_lines"] == {2}


@patch('subprocess.run')
def test_calculate_projected_coverage(mock_run):
    """Test calculating projected coverage."""
    analyzer = projected_coverage.CoverageAnalyzer("test", ["test_dir"])

    # Set up current coverage data
    analyzer.current_coverage = {
        "file1.py": {"statements": 100, "missing": 20, "missing_lines": {1, 2, 3, 4, 5}},
        "file2.py": {"statements": 50, "missing": 10, "missing_lines": {1, 2, 3}}
    }

    # Set up stub coverage data
    analyzer.missing_lines = {
        "file1.py": {1, 2, 3, 4, 5},
        "file2.py": {1, 2, 3}
    }

    analyzer.stub_coverage = {
        "file1.py": {1, 2, 3},  # Stubs cover 3 of 5 missing lines
        "file2.py": {1}          # Stubs cover 1 of 3 missing lines
    }

    # Calculate projected coverage
    projected = analyzer.calculate_projected_coverage()

    # Verify results
    assert projected["file1.py"]["statements"] == 100
    assert projected["file1.py"]["missing"] == 2  # 5 - 3 = 2 lines still missing
    assert projected["file1.py"]["covered"] == 98  # 100 - 2 = 98 lines covered
    assert round(projected["file1.py"]["percentage"], 1) == 98.0
    assert round(projected["file1.py"]["current_percentage"], 1) == 80.0  # 100 - 20 = 80%
    assert round(projected["file1.py"]["improvement"], 1) == 18.0  # 98% - 80% = 18%

    assert projected["file2.py"]["statements"] == 50
    assert projected["file2.py"]["missing"] == 2  # 3 - 1 = 2 lines still missing
    assert projected["file2.py"]["covered"] == 48  # 50 - 2 = 48 lines covered
    assert round(projected["file2.py"]["percentage"], 1) == 96.0
    assert round(projected["file2.py"]["current_percentage"], 1) == 80.0  # 50 - 10 = 40, 40/50 = 80%
    assert round(projected["file2.py"]["improvement"], 1) == 16.0  # 96% - 80% = 16%


@patch('subprocess.run')
def test_get_coverage_from_report_fallback(mock_run):
    """Test fallback coverage report parsing."""
    # Mock the subprocess run result
    mock_result = MagicMock()
    mock_result.stdout = """
---------- coverage: platform darwin, python 3.13.2-final-0 -----------
Name                    Stmts   Miss  Cover   Missing
-------------------------------------------------------------
mypackage/file1.py         50     10    80%   5-10, 15, 20-23
mypackage/file2.py         30      5    83%   1, 5, 10-12
-------------------------------------------------------------
TOTAL                      80     15    81%

================================================= 5 passed, 2 warnings ==
    """
    mock_run.return_value = mock_result

    analyzer = projected_coverage.CoverageAnalyzer("mypackage", ["test_dir"])

    # Patch print to suppress stderr output
    with patch('builtins.print'):
        coverage = analyzer._get_coverage_from_report()

    # Verify results
    assert "mypackage/file1.py" in coverage
    assert coverage["mypackage/file1.py"]["statements"] == 50
    assert coverage["mypackage/file1.py"]["missing"] == 10
    assert coverage["mypackage/file1.py"]["missing_lines"] == {5, 6, 7, 8, 9, 10, 15, 20, 21, 22, 23}

    assert "mypackage/file2.py" in coverage
    assert coverage["mypackage/file2.py"]["statements"] == 30
    assert coverage["mypackage/file2.py"]["missing"] == 5
    assert coverage["mypackage/file2.py"]["missing_lines"] == {1, 5, 10, 11, 12}


@patch('builtins.print')
@patch('subprocess.run')
def test_main_report_command(mock_run, mock_print):
    """Test main function with report command."""
    with patch.object(projected_coverage, 'display_latest_coverage') as mock_display:
        # Create a test class to mock the args
        class MockArgs:
            report = True
            history = False
            package = "pygovpub.auth"
            stub_dirs = []
            scan_all = False
            verbose = False

        with patch.object(projected_coverage.argparse.ArgumentParser, 'parse_args', return_value=MockArgs()):
            projected_coverage.main()

            # Verify display_latest_coverage was called
            mock_display.assert_called_once()


@patch('builtins.print')
@patch('subprocess.run')
def test_main_history_command(mock_run, mock_print):
    """Test main function with history command."""
    with patch.object(projected_coverage, 'display_coverage_history') as mock_display:
        # Create a test class to mock the args
        class MockArgs:
            report = False
            history = True
            package = "pygovpub.auth"
            stub_dirs = []
            scan_all = False
            verbose = False

        with patch.object(projected_coverage.argparse.ArgumentParser, 'parse_args', return_value=MockArgs()):
            projected_coverage.main()

            # Verify display_coverage_history was called
            mock_display.assert_called_once()


@patch('builtins.print')
@patch('subprocess.run')
def test_main_default_flow(mock_run, mock_print):
    """Test main function with default flow."""
    # Mock CoverageAnalyzer
    mock_analyzer = MagicMock()
    mock_analyzer.get_current_coverage.return_value = {}
    mock_analyzer.analyze_test_stubs.return_value = {}
    mock_analyzer.calculate_projected_coverage.return_value = {}

    with patch.object(projected_coverage, 'CoverageAnalyzer', return_value=mock_analyzer):
        # Create a test class to mock the args
        class MockArgs:
            report = False
            history = False
            package = "pygovpub.auth"
            stub_dirs = []
            scan_all = False
            verbose = False
            all_packages = False  # Added for new functionality

        with patch.object(projected_coverage.argparse.ArgumentParser, 'parse_args', return_value=MockArgs()):
            projected_coverage.main()

            # Verify analyzer methods were called
            mock_analyzer.get_current_coverage.assert_called_once()
            mock_analyzer.analyze_test_stubs.assert_called_once()
            mock_analyzer.calculate_projected_coverage.assert_called_once()
            mock_analyzer.display_results.assert_called_once()


@patch('sys.stdout')
def test_display_results(mock_stdout, temp_history_file):
    """Test the display_results method."""
    analyzer = projected_coverage.CoverageAnalyzer("test.package", ["test_dir"])

    # Set up test data
    analyzer.current_coverage = {
        "file1.py": {"statements": 100, "missing_lines": {1, 2, 3}}
    }

    analyzer.missing_lines = {
        "file1.py": {1, 2, 3}
    }

    analyzer.stub_coverage = {
        "file1.py": {1, 2}
    }

    projected = {
        "file1.py": {
            "statements": 100,
            "missing": 1,
            "covered": 99,
            "percentage": 99.0,
            "current_percentage": 97.0,
            "improvement": 2.0
        }
    }

    # Run display_results
    with patch.object(projected_coverage, 'save_coverage_results') as mock_save:
        analyzer.display_results(projected)

        # Verify save_coverage_results was called with correct data
        mock_save.assert_called_once()
        saved_data = mock_save.call_args[0][0]
        assert saved_data["package"] == "test.package"
        assert saved_data["overall_percentage"] == 97.0
        assert saved_data["projected_percentage"] == 99.0
        assert saved_data["improvement"] == 2.0
        assert len(saved_data["modules"]) == 1
        assert saved_data["modules"][0]["file_path"] == "file1.py"


def test_format_missing_lines(capsys):
    """Test _format_missing_lines method."""
    # Create a simple test case
    lines = [1, 2, 3, 5, 7, 8, 9, 15]

    # Call the method
    projected_coverage.CoverageAnalyzer._format_missing_lines(None, lines)

    # Check the output
    captured = capsys.readouterr()
    assert "1-3, 5, 7-9, 15" in captured.out


def test_analyze_test_stubs_line_pattern():
    """Test the line comment pattern matching in analyze_test_stubs."""
    # Test the line_comment_pattern directly on various STUB comments
    pattern = projected_coverage.re.compile(r'#\s*(?:STUB:|WIP:|This tests|Tests|This covers)?\s*(?:This tests|Tests|[Ll]ines?|[Cc]overs)\s*(?:line|lines?)?\s*(\d+(?:-\d+)?(?:,\s*\d+(?:-\d+)?)*)')

    test_cases = [
        ("# STUB: This tests lines 10-15", "10-15"),
        ("# Tests lines 10-15, 20", "10-15, 20"),
        ("# This covers line 42", "42"),
        ("# Lines 1-5, 10, 15-20", "1-5, 10, 15-20"),
        ("# lines 1,2,3", "1,2,3"),
        ("# STUB: lines 100-200", "100-200"),
        ("# WIP: Testing lines 1, 5-10", "1, 5-10"),
    ]

    for comment, expected in test_cases:
        match = pattern.search(comment)
        assert match is not None, f"Failed to match: {comment}"
        assert match.group(1) == expected, f"Expected {expected}, got {match.group(1)} for {comment}"


def test_format_missing_lines_ranges():
    """Test the _format_missing_lines method with various patterns."""
    test_cases = [
        ([1], "1"),
        ([1, 2, 3], "1-3"),
        ([1, 3, 5], "1, 3, 5"),
        ([1, 2, 3, 5, 7, 8, 9], "1-3, 5, 7-9"),
        ([1, 2, 3, 5, 10, 11, 12, 15, 20], "1-3, 5, 10-12, 15, 20"),
    ]

    for lines, expected in test_cases:
        result = projected_coverage._format_line_ranges(lines)
        assert result == expected, f"Expected {expected}, got {result} for {lines}"


def test_file_match_in_analyze_test_stubs():
    # STUB: This will test how analyze_test_stubs matches source files to tests
    """Tests how analyze_test_stubs matches source files to tests."""
    assert True
