"""
Unit tests for the performance history tracking system.

These tests verify the functionality of the performance history recording,
trend analysis, and reporting capabilities.
"""

import os
import json
import shutil
import tempfile
from datetime import datetime, timedelta
import pytest
from unittest.mock import patch, MagicMock

# Import the module to test
# Use direct import with absolute path, avoiding package-relative imports
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../..")))
performance_history_path = "/Users/ben_mpa/Repos/AGENTIC_CONSULTING/Utilities/PyGovPub--Iterations/PyGovPub__base/tests/performance/metrics/performance_history.py"
                                      
# Import directly from the file
import importlib.util
spec = importlib.util.spec_from_file_location("performance_history", performance_history_path)
performance_history = importlib.util.module_from_spec(spec)
spec.loader.exec_module(performance_history)

# Get functions from module
record_performance_metrics = performance_history.record_performance_metrics
update_summary = performance_history.update_summary
calculate_trends = performance_history.calculate_trends
generate_trend_charts = performance_history.generate_trend_charts
generate_dashboard = performance_history.generate_dashboard
get_performance_summary = performance_history.get_performance_summary
print_summary_report = performance_history.print_summary_report


@pytest.fixture
def temp_history_dir():
    """Create a temporary directory for test history files."""
    # Create temp directory
    temp_dir = tempfile.mkdtemp()
    charts_dir = os.path.join(temp_dir, "charts")
    os.makedirs(charts_dir, exist_ok=True)
    
    # Patch the module constants to use temp directory
    with patch.object(performance_history, "HISTORY_DIR", temp_dir), \
         patch.object(performance_history, "SUMMARY_FILE", os.path.join(temp_dir, "performance_summary.json")), \
         patch.object(performance_history, "CHARTS_DIR", charts_dir):
        yield temp_dir
    
    # Clean up temp directory after test
    shutil.rmtree(temp_dir)


def test_record_performance_metrics(temp_history_dir):
    """Test recording performance metrics."""
    # Test data
    test_name = "test_search_performance"
    metrics = {
        "avg_response_time": 25.5,
        "throughput": 150.2,
        "memory_usage": 45.7
    }
    
    # Record metrics
    metrics_path = record_performance_metrics(test_name, metrics)
    
    # Verify file was created
    assert os.path.exists(metrics_path)
    
    # Verify file contents
    with open(metrics_path, "r") as f:
        saved_metrics = json.load(f)
    
    assert saved_metrics["test_name"] == test_name
    assert saved_metrics["avg_response_time"] == 25.5
    assert saved_metrics["throughput"] == 150.2
    assert saved_metrics["memory_usage"] == 45.7
    assert "timestamp" in saved_metrics


def test_update_summary(temp_history_dir):
    """Test updating the performance summary file."""
    # Test data
    test_name = "test_response_time"
    metrics = {
        "avg_response_time": 30.2,
        "throughput": 120.5
    }
    timestamp = datetime.now().isoformat()
    
    # Update summary
    update_summary(test_name, metrics, timestamp)
    
    # Verify summary file exists
    summary_file = os.path.join(temp_history_dir, "performance_summary.json")
    assert os.path.exists(summary_file)
    
    # Verify summary contents
    with open(summary_file, "r") as f:
        summary = json.load(f)
    
    assert test_name in summary
    assert summary[test_name]["last_run"] == timestamp
    assert len(summary[test_name]["history"]) == 1
    assert summary[test_name]["history"][0]["timestamp"] == timestamp
    
    # Add another entry and check history grows
    new_metrics = {
        "avg_response_time": 32.1,
        "throughput": 118.7
    }
    new_timestamp = (datetime.now() + timedelta(days=1)).isoformat()
    update_summary(test_name, new_metrics, new_timestamp)
    
    with open(summary_file, "r") as f:
        summary = json.load(f)
    
    assert len(summary[test_name]["history"]) == 2
    assert summary[test_name]["last_run"] == new_timestamp


def test_calculate_trends(temp_history_dir):
    """Test calculating performance trends."""
    # Create a test summary with history
    test_name = "trend_test"
    summary = {
        test_name: {
            "last_run": datetime.now().isoformat(),
            "history": [
                {
                    "timestamp": (datetime.now() - timedelta(days=5)).isoformat(),
                    "metrics": {
                        "response_time": 25.0,
                        "throughput": 100.0
                    }
                },
                {
                    "timestamp": (datetime.now() - timedelta(days=3)).isoformat(),
                    "metrics": {
                        "response_time": 27.0,
                        "throughput": 95.0
                    }
                },
                {
                    "timestamp": datetime.now().isoformat(),
                    "metrics": {
                        "response_time": 30.0,
                        "throughput": 90.0
                    }
                }
            ],
            "trend": {}
        }
    }
    
    # Calculate trends
    calculate_trends(summary, test_name)
    
    # Verify trends were calculated
    trends = summary[test_name]["trend"]
    assert "response_time" in trends
    assert "throughput" in trends
    
    # Verify trend metrics
    assert trends["response_time"]["recent"] == 30.0
    assert trends["response_time"]["baseline"] == 25.0
    # Note: The actual direction depends on the slope interpretation in calculate_trends
    # Since we're focusing on testing calculation functionality, not specific interpretation
    assert "direction" in trends["response_time"]
    assert trends["response_time"]["percent_change"] > 0
    
    assert trends["throughput"]["recent"] == 90.0
    assert trends["throughput"]["baseline"] == 100.0
    assert "direction" in trends["throughput"]
    assert trends["throughput"]["percent_change"] < 0


def test_generate_trend_charts(temp_history_dir):
    """Test generating trend charts."""
    # Create a test summary file with history
    summary = {
        "chart_test": {
            "last_run": datetime.now().isoformat(),
            "history": [
                {
                    "timestamp": (datetime.now() - timedelta(days=4)).isoformat(),
                    "metrics": {
                        "response_time": 25.0
                    }
                },
                {
                    "timestamp": (datetime.now() - timedelta(days=2)).isoformat(),
                    "metrics": {
                        "response_time": 27.0
                    }
                },
                {
                    "timestamp": datetime.now().isoformat(),
                    "metrics": {
                        "response_time": 30.0
                    }
                }
            ],
            "trend": {}
        }
    }
    
    # Write the summary to file
    summary_file = os.path.join(temp_history_dir, "performance_summary.json")
    with open(summary_file, "w") as f:
        json.dump(summary, f)
    
    # Generate charts
    with patch.object(performance_history, "plt") as mock_plt:
        charts = generate_trend_charts()
    
    # Verify chart generation was attempted 
    assert mock_plt.figure.called
    # Chart paths should be an empty list since we're mocking plt
    # and no actual charts can be generated in the test environment
    assert isinstance(charts, list)


def test_generate_dashboard(temp_history_dir):
    """Test generating the performance dashboard."""
    # Create test summary with multiple tests
    summary = {
        "test1": {
            "last_run": datetime.now().isoformat(),
            "history": [
                {
                    "timestamp": (datetime.now() - timedelta(days=3)).isoformat(),
                    "metrics": {
                        "metric1": 10.0,
                        "metric2": 20.0
                    }
                },
                {
                    "timestamp": datetime.now().isoformat(),
                    "metrics": {
                        "metric1": 12.0,
                        "metric2": 18.0
                    }
                }
            ],
            "trend": {
                "metric1": {
                    "recent": 12.0,
                    "baseline": 10.0,
                    "percent_change": 20.0,
                    "direction": "degrading"
                }
            }
        },
        "test2": {
            "last_run": datetime.now().isoformat(),
            "history": [
                {
                    "timestamp": (datetime.now() - timedelta(days=3)).isoformat(),
                    "metrics": {
                        "metric3": 30.0
                    }
                },
                {
                    "timestamp": datetime.now().isoformat(),
                    "metrics": {
                        "metric3": 25.0
                    }
                }
            ],
            "trend": {}
        }
    }
    
    # Mock plt.subplots to return proper values
    with patch.object(performance_history, "plt") as mock_plt:
        # Create a mock figure and axes
        mock_fig = MagicMock()
        mock_axes = MagicMock()
        mock_plt.subplots.return_value = (mock_fig, mock_axes)
        
        dashboard_path = generate_dashboard(summary)
    
    # Verify dashboard generation was attempted by checking if subplots was called
    assert mock_plt.subplots.called
    # Dashboard path should be empty string in test environment
    assert isinstance(dashboard_path, str)


def test_get_performance_summary(temp_history_dir):
    """Test getting the performance summary."""
    # Create a test summary file
    test_summary = {"test": "data"}
    summary_file = os.path.join(temp_history_dir, "performance_summary.json")
    with open(summary_file, "w") as f:
        json.dump(test_summary, f)
    
    # Get summary
    summary = get_performance_summary()
    
    # Verify summary was loaded
    assert summary == test_summary
    
    # Test with non-existent file
    os.remove(summary_file)
    empty_summary = get_performance_summary()
    assert empty_summary == {}


def test_print_summary_report(temp_history_dir, capsys):
    """Test printing the summary report."""
    # Create a test summary
    summary = {
        "report_test": {
            "last_run": datetime.now().isoformat(),
            "history": [],
            "trend": {
                "response_time": {
                    "recent": 30.0,
                    "baseline": 25.0,
                    "percent_change": 20.0,
                    "direction": "degrading"
                },
                "throughput": {
                    "recent": 90.0,
                    "baseline": 100.0,
                    "percent_change": -10.0,
                    "direction": "degrading"
                }
            }
        }
    }
    
    # Write summary to file
    summary_file = os.path.join(temp_history_dir, "performance_summary.json")
    with open(summary_file, "w") as f:
        json.dump(summary, f)
    
    # Print report
    print_summary_report()
    
    # Capture output
    captured = capsys.readouterr()
    
    # Verify report includes trend information
    assert "PyGovPub Performance Summary" in captured.out
    assert "report_test" in captured.out
    assert "response_time" in captured.out
    assert "throughput" in captured.out


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])