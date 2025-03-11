"""
Performance history tracker for PyGovPub.

This module provides functionality to record and track performance metrics over time,
allowing for historical comparison and trend analysis of system performance.
"""

import os
import json
import time
import datetime
import statistics
from typing import Dict, List, Any, Optional, Tuple
import matplotlib.pyplot as plt
import numpy as np

# Paths
HISTORY_DIR = os.path.join("tests", "performance", "metrics", "history")
SUMMARY_FILE = os.path.join(HISTORY_DIR, "performance_summary.json")
CHARTS_DIR = os.path.join(HISTORY_DIR, "charts")

# Ensure directories exist
os.makedirs(HISTORY_DIR, exist_ok=True)
os.makedirs(CHARTS_DIR, exist_ok=True)


def record_performance_metrics(
    test_name: str,
    metrics: Dict[str, Any],
    timestamp: Optional[str] = None
) -> str:
    """
    Record performance metrics to the history file.
    
    Args:
        test_name: Name of the test
        metrics: Dictionary of performance metrics
        timestamp: Optional timestamp (default: current time)
        
    Returns:
        Path to the saved metrics file
    """
    # Create timestamp if not provided
    if timestamp is None:
        timestamp = datetime.datetime.now().isoformat()
    
    # Create a filename based on test name and timestamp
    safe_timestamp = timestamp.replace(":", "-").replace(".", "-")
    metrics_filename = f"{test_name}_{safe_timestamp}.json"
    metrics_path = os.path.join(HISTORY_DIR, metrics_filename)
    
    # Add timestamp to metrics
    metrics_with_timestamp = metrics.copy()
    metrics_with_timestamp["timestamp"] = timestamp
    metrics_with_timestamp["test_name"] = test_name
    
    # Save metrics to file
    with open(metrics_path, "w") as f:
        json.dump(metrics_with_timestamp, f, indent=2)
    
    # Update summary file
    update_summary(test_name, metrics, timestamp)
    
    return metrics_path


def update_summary(test_name: str, metrics: Dict[str, Any], timestamp: str) -> None:
    """
    Update the performance summary file with latest metrics.
    
    Args:
        test_name: Name of the test
        metrics: Dictionary of performance metrics
        timestamp: Timestamp for the metrics
    """
    # Load existing summary if it exists
    summary = {}
    if os.path.exists(SUMMARY_FILE):
        try:
            with open(SUMMARY_FILE, "r") as f:
                summary = json.load(f)
        except json.JSONDecodeError:
            # Handle corrupted summary file
            summary = {}
    
    # Initialize test section if needed
    if test_name not in summary:
        summary[test_name] = {
            "last_run": None,
            "history": [],
            "trend": {}
        }
    
    # Extract key metrics (customize based on what metrics are important)
    key_metrics = {}
    metric_extractors = {
        "search_response_time": lambda m: m.get("avg_response_time", 0),
        "throughput": lambda m: m.get("throughput", 0),
        "memory_usage": lambda m: m.get("max_memory", 0),
        "concurrent_performance": lambda m: m.get("max_concurrent_response_time", 0)
    }
    
    # Extract metrics if available
    for metric_name, extractor in metric_extractors.items():
        try:
            key_metrics[metric_name] = extractor(metrics)
        except (KeyError, TypeError):
            # Skip metrics that aren't in this test
            pass
    
    # Add to history
    history_entry = {
        "timestamp": timestamp,
        "metrics": key_metrics
    }
    summary[test_name]["history"].append(history_entry)
    
    # Keep only last 30 entries to avoid file getting too large
    if len(summary[test_name]["history"]) > 30:
        summary[test_name]["history"] = summary[test_name]["history"][-30:]
    
    # Update last run
    summary[test_name]["last_run"] = timestamp
    
    # Calculate trends
    calculate_trends(summary, test_name)
    
    # Save updated summary
    with open(SUMMARY_FILE, "w") as f:
        json.dump(summary, f, indent=2)


def calculate_trends(summary: Dict[str, Any], test_name: str) -> None:
    """
    Calculate performance trends for a given test.
    
    Args:
        summary: Performance summary dictionary
        test_name: Name of the test to calculate trends for
    """
    history = summary[test_name]["history"]
    
    # Need at least 2 data points for trends
    if len(history) < 2:
        return
    
    trends = {}
    
    # Get the metrics from the first entry to know what metrics we have
    if history and "metrics" in history[0]:
        first_metrics = history[0]["metrics"]
        
        for metric_name in first_metrics:
            # Extract metric values across history
            values = []
            for entry in history:
                if "metrics" in entry and metric_name in entry["metrics"]:
                    values.append(entry["metrics"][metric_name])
            
            # Skip if not enough values
            if len(values) < 2:
                continue
            
            # Calculate basic statistics
            avg = statistics.mean(values)
            recent = values[-1]
            baseline = values[0]
            
            # Calculate percent change from first to last
            if baseline != 0:
                percent_change = ((recent - baseline) / baseline) * 100
            else:
                percent_change = 0
            
            # Calculate trend direction
            if len(values) >= 3:
                # Simple linear regression
                x = list(range(len(values)))
                y = values
                
                # Calculate slope using numpy
                slope, _ = np.polyfit(x, y, 1)
                
                # Interpret trend
                if abs(slope) < 0.01 * avg:  # Less than 1% change per sample
                    direction = "stable"
                elif slope > 0:
                    # For metrics where higher is worse (like response time)
                    if metric_name in ["search_response_time", "memory_usage", "concurrent_performance"]:
                        direction = "degrading"
                    else:
                        direction = "improving"
                else:
                    # For metrics where lower is worse (like throughput)
                    if metric_name in ["throughput"]:
                        direction = "degrading"
                    else:
                        direction = "improving"
            else:
                direction = "insufficient data"
            
            # Store trend information
            trends[metric_name] = {
                "recent": recent,
                "baseline": baseline,
                "average": avg,
                "percent_change": percent_change,
                "direction": direction
            }
    
    summary[test_name]["trend"] = trends


def generate_trend_charts() -> List[str]:
    """
    Generate charts showing trends for all performance metrics.
    
    Returns:
        List of generated chart filenames
    """
    # Check if summary file exists
    if not os.path.exists(SUMMARY_FILE):
        return []
    
    # Load summary
    with open(SUMMARY_FILE, "r") as f:
        summary = json.load(f)
    
    generated_charts = []
    
    # Create a chart for each test
    for test_name, test_data in summary.items():
        history = test_data.get("history", [])
        
        # Skip if not enough data
        if len(history) < 2:
            continue
        
        # Get metrics from first entry
        if history and "metrics" in history[0]:
            metric_names = history[0]["metrics"].keys()
            
            # For each metric, create a trend chart
            for metric_name in metric_names:
                # Extract data
                dates = []
                values = []
                
                for entry in history:
                    if "metrics" in entry and metric_name in entry["metrics"]:
                        # Parse timestamp
                        try:
                            timestamp = datetime.datetime.fromisoformat(entry["timestamp"])
                            dates.append(timestamp)
                            values.append(entry["metrics"][metric_name])
                        except (ValueError, TypeError):
                            # Skip entries with invalid timestamps
                            pass
                
                if len(dates) < 2:
                    continue
                
                # Create chart
                plt.figure(figsize=(12, 6))
                plt.plot(dates, values, marker='o')
                
                # Add trend line
                x = np.arange(len(dates))
                z = np.polyfit(x, values, 1)
                p = np.poly1d(z)
                plt.plot(dates, p(x), "r--", alpha=0.8)
                
                # Formatting
                plt.title(f"{test_name}: {metric_name} Trend")
                plt.ylabel(metric_name)
                plt.grid(True)
                
                # Format dates on x-axis
                plt.gcf().autofmt_xdate()
                
                # Save chart
                chart_filename = f"{test_name}_{metric_name}_trend.png"
                chart_path = os.path.join(CHARTS_DIR, chart_filename)
                plt.savefig(chart_path)
                plt.close()
                
                generated_charts.append(chart_path)
    
    # Generate combined dashboard if we have enough tests
    if len(summary) >= 2:
        generate_dashboard(summary)
    
    return generated_charts


def generate_dashboard(summary: Dict[str, Any]) -> str:
    """
    Generate a performance dashboard showing key metrics across all tests.
    
    Args:
        summary: Performance summary data
        
    Returns:
        Path to the dashboard image
    """
    # Get all tests with enough history
    valid_tests = []
    for test_name, test_data in summary.items():
        if len(test_data.get("history", [])) >= 2:
            valid_tests.append(test_name)
    
    if not valid_tests:
        return ""
    
    # Create dashboard
    dashboard_rows = len(valid_tests)
    fig, axes = plt.subplots(dashboard_rows, 2, figsize=(15, 5 * dashboard_rows))
    
    # Ensure axes is always a 2D array
    if dashboard_rows == 1:
        axes = np.array([axes])
    
    # For each test, add metrics to dashboard
    for i, test_name in enumerate(valid_tests):
        test_data = summary[test_name]
        history = test_data.get("history", [])
        
        # Skip if not enough data
        if not history:
            continue
        
        # Get the first two metrics (typically most important)
        metrics = list(history[0].get("metrics", {}).keys())
        if not metrics:
            continue
        
        # Left plot: First metric
        if len(metrics) > 0:
            metric1 = metrics[0]
            dates = []
            values = []
            
            for entry in history:
                if "metrics" in entry and metric1 in entry["metrics"]:
                    try:
                        timestamp = datetime.datetime.fromisoformat(entry["timestamp"])
                        dates.append(timestamp)
                        values.append(entry["metrics"][metric1])
                    except (ValueError, TypeError):
                        pass
            
            if dates:
                axes[i, 0].plot(dates, values, marker='o')
                axes[i, 0].set_title(f"{test_name}: {metric1}")
                axes[i, 0].grid(True)
                fig.autofmt_xdate()
        
        # Right plot: Second metric or summary
        if len(metrics) > 1:
            metric2 = metrics[1]
            dates = []
            values = []
            
            for entry in history:
                if "metrics" in entry and metric2 in entry["metrics"]:
                    try:
                        timestamp = datetime.datetime.fromisoformat(entry["timestamp"])
                        dates.append(timestamp)
                        values.append(entry["metrics"][metric2])
                    except (ValueError, TypeError):
                        pass
            
            if dates:
                axes[i, 1].plot(dates, values, marker='o')
                axes[i, 1].set_title(f"{test_name}: {metric2}")
                axes[i, 1].grid(True)
        else:
            # If only one metric, show summary in right plot
            axes[i, 1].axis('off')
            trends = test_data.get("trend", {})
            summary_text = f"Test: {test_name}\n\n"
            
            for metric, trend in trends.items():
                direction = trend.get("direction", "unknown")
                change = trend.get("percent_change", 0)
                recent = trend.get("recent", 0)
                
                # Format with color based on direction
                if direction == "improving":
                    color = "green"
                elif direction == "degrading":
                    color = "red"
                else:
                    color = "black"
                
                summary_text += f"{metric}: {recent:.2f} ({change:.1f}%, {direction})\n"
            
            axes[i, 1].text(0.05, 0.95, summary_text, transform=axes[i, 1].transAxes, 
                          verticalalignment='top', fontsize=10)
    
    plt.tight_layout()
    
    # Save dashboard
    dashboard_path = os.path.join(CHARTS_DIR, "performance_dashboard.png")
    plt.savefig(dashboard_path)
    plt.close()
    
    return dashboard_path


def get_performance_summary() -> Dict[str, Any]:
    """
    Get the latest performance summary.
    
    Returns:
        Dictionary with performance summary data
    """
    if os.path.exists(SUMMARY_FILE):
        with open(SUMMARY_FILE, "r") as f:
            return json.load(f)
    return {}


def print_summary_report() -> None:
    """Print a summary report of performance trends."""
    summary = get_performance_summary()
    
    if not summary:
        print("No performance history available.")
        return
    
    print("\n===== PyGovPub Performance Summary =====\n")
    
    for test_name, test_data in summary.items():
        print(f"Test: {test_name}")
        last_run = test_data.get("last_run", "Never")
        if isinstance(last_run, str) and last_run != "Never":
            try:
                last_run_date = datetime.datetime.fromisoformat(last_run).strftime("%Y-%m-%d %H:%M")
            except ValueError:
                last_run_date = last_run
        else:
            last_run_date = "Never"
            
        print(f"Last run: {last_run_date}")
        
        # Print trends
        trends = test_data.get("trend", {})
        if trends:
            print("Trends:")
            for metric, trend in trends.items():
                direction = trend.get("direction", "unknown")
                change = trend.get("percent_change", 0)
                recent = trend.get("recent", 0)
                
                # Format with symbols
                if direction == "improving":
                    direction_symbol = "↑"
                elif direction == "degrading":
                    direction_symbol = "↓"
                else:
                    direction_symbol = "→"
                
                print(f"  {metric}: {recent:.2f} ({change:+.1f}%) {direction_symbol}")
        
        print("\n")
    
    print(f"Detailed charts available in: {CHARTS_DIR}")
    print("=========================================")


if __name__ == "__main__":
    # Generate charts and print summary when run directly
    generate_trend_charts()
    print_summary_report()