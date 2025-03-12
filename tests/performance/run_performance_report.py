#!/usr/bin/env python
"""
Performance report generator for PyGovPub.

This script runs all performance tests and generates a comprehensive report
with trend analysis and visualization.
"""

import os
import sys
import time
import argparse
import json
import datetime
import subprocess
from pathlib import Path

# Make sure pygovpub package is in path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from tests.performance.metrics.performance_history import (
    record_performance_metrics,
    generate_trend_charts,
    print_summary_report,
    get_performance_summary
)

# Paths
REPORT_DIR = Path("tests/performance/metrics/history")
CHARTS_DIR = REPORT_DIR / "charts"
SUMMARY_FILE = REPORT_DIR / "performance_summary.json"
HTML_REPORT = REPORT_DIR / "performance_report.html"

# Test paths
TESTS = {
    "search_performance": "tests/performance/metrics/test_search_performance.py",
    "throughput_capacity": "tests/performance/metrics/test_throughput_capacity.py",
}


def run_tests(tests=None, repeat=1):
    """Run the performance tests and collect results.
    
    Args:
        tests: List of test names to run (None for all)
        repeat: Number of times to repeat each test
        
    Returns:
        Dictionary of test results
    """
    results = {}
    test_paths = []
    
    if tests is None:
        tests = list(TESTS.keys())
    
    for test_name in tests:
        if test_name in TESTS:
            test_paths.append(TESTS[test_name])
    
    if not test_paths:
        print("No valid tests specified")
        return results
    
    # Ensure directories exist
    os.makedirs(REPORT_DIR, exist_ok=True)
    os.makedirs(CHARTS_DIR, exist_ok=True)
    
    # Run tests
    for _ in range(repeat):
        for test_path in test_paths:
            test_name = next((k for k, v in TESTS.items() if v == test_path), "unknown")
            print(f"Running test: {test_name}")
            
            # Run test using pytest
            try:
                # Run pytest and capture output
                cmd = ["pytest", test_path, "-v"]
                proc = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
                )
                stdout, stderr = proc.communicate()
                
                if proc.returncode != 0:
                    print(f"Test failed: {test_name}")
                    print(f"Error: {stderr}")
                    continue
                
                # Parse test output to extract metrics
                metrics = parse_test_output(stdout, test_name)
                
                if metrics:
                    # Record metrics to history
                    record_performance_metrics(test_name, metrics)
                    results[test_name] = metrics
            except Exception as e:
                print(f"Error running test {test_name}: {e}")
    
    return results


def parse_test_output(output, test_name):
    """Parse test output to extract performance metrics.
    
    Args:
        output: The test output string
        test_name: Name of the test
        
    Returns:
        Dictionary of extracted metrics
    """
    metrics = {}
    
    # Extract different metrics based on test name
    if test_name == "search_performance":
        # Extract response times
        response_times = {}
        for line in output.split("\n"):
            if line.startswith("Search pattern "):
                parts = line.split("'")
                if len(parts) >= 3:
                    pattern = parts[1]
                    # Extract values using string operations
                    time_part = parts[2].strip(": ")
                    avg_ms = float(time_part.split("avg=")[1].split("ms")[0])
                    min_ms = float(time_part.split("min=")[1].split("ms")[0])
                    max_ms = float(time_part.split("max=")[1].split("ms")[0])
                    response_times[pattern] = {"avg": avg_ms, "min": min_ms, "max": max_ms}
        
        if response_times:
            # Average across all patterns
            avg_values = [data["avg"] for data in response_times.values()]
            max_values = [data["max"] for data in response_times.values()]
            metrics["avg_response_time"] = sum(avg_values) / len(avg_values)
            metrics["max_response_time"] = max(max_values)
            metrics["response_times_by_pattern"] = response_times
        
        # Extract memory usage
        memory_lines = [line for line in output.split("\n") if "memory" in line.lower()]
        for line in memory_lines:
            if "initial memory" in line.lower():
                try:
                    metrics["initial_memory_mb"] = float(line.split(":")[1].split("MB")[0].strip())
                except (IndexError, ValueError):
                    pass
            if "maximum memory increase" in line.lower():
                try:
                    metrics["max_memory_increase_mb"] = float(line.split(":")[1].split("MB")[0].strip())
                    # Calculate max memory
                    if "initial_memory_mb" in metrics:
                        metrics["max_memory"] = metrics["initial_memory_mb"] + metrics["max_memory_increase_mb"]
                except (IndexError, ValueError):
                    pass
        
        # Extract concurrent performance
        concurrency_data = {}
        for line in output.split("\n"):
            if line.startswith("Concurrency "):
                try:
                    parts = line.split("Concurrency ")[1].split(":")
                    concurrency = int(parts[0])
                    metrics_part = parts[1]
                    
                    avg_response = float(metrics_part.split("avg_response=")[1].split("ms")[0])
                    max_response = float(metrics_part.split("max_response=")[1].split("ms")[0])
                    throughput = float(metrics_part.split("throughput=")[1].split("qps")[0])
                    
                    concurrency_data[concurrency] = {
                        "avg_response_ms": avg_response,
                        "max_response_ms": max_response,
                        "throughput_qps": throughput
                    }
                except (IndexError, ValueError):
                    pass
        
        if concurrency_data:
            # Get highest concurrency metrics
            max_concurrency = max(concurrency_data.keys())
            metrics["max_concurrency"] = max_concurrency
            metrics["concurrent_response_time"] = concurrency_data[max_concurrency]["avg_response_ms"]
            metrics["max_throughput"] = concurrency_data[max_concurrency]["throughput_qps"]
            metrics["concurrency_data"] = concurrency_data
    
    elif test_name == "throughput_capacity":
        # Extract throughput metrics
        for line in output.split("\n"):
            if "Throughput:" in line:
                try:
                    throughput = float(line.split("Throughput:")[1].split("requests/sec")[0].strip())
                    metrics["throughput"] = throughput
                except (IndexError, ValueError):
                    pass
            
            if "Average response time:" in line:
                try:
                    avg_time = float(line.split("Average response time:")[1].split("ms")[0].strip())
                    metrics["avg_response_time"] = avg_time
                except (IndexError, ValueError):
                    pass
                    
            if "CPU usage" in line and "%" in line:
                try:
                    cpu_usage = float(line.split("CPU usage")[1].split("%")[0].strip())
                    metrics["cpu_usage_percent"] = cpu_usage
                except (IndexError, ValueError):
                    pass
    
    # Add timestamp
    metrics["timestamp"] = datetime.datetime.now().isoformat()
    
    return metrics


def generate_html_report():
    """Generate an HTML performance report.
    
    Returns:
        Path to the generated HTML report
    """
    summary = get_performance_summary()
    
    # Generate trend charts
    chart_files = generate_trend_charts()
    
    # Get relative paths for charts
    chart_paths = [os.path.relpath(chart, REPORT_DIR.parent.parent) for chart in chart_files]
    
    # Create HTML content
    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>PyGovPub Performance Report</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 0; padding: 20px; color: #333; }
            h1, h2, h3 { color: #2c3e50; }
            .container { max-width: 1200px; margin: 0 auto; }
            .summary { margin: 20px 0; padding: 15px; background-color: #f8f9fa; border-radius: 5px; }
            .improving { color: green; }
            .degrading { color: red; }
            .stable { color: #666; }
            .chart { margin: 30px 0; text-align: center; }
            .chart img { max-width: 100%; border: 1px solid #ddd; border-radius: 5px; }
            table { border-collapse: collapse; width: 100%; margin: 20px 0; }
            th, td { text-align: left; padding: 12px; border: 1px solid #ddd; }
            th { background-color: #f2f2f2; }
            tr:nth-child(even) { background-color: #f9f9f9; }
            .footer { margin-top: 40px; padding-top: 20px; border-top: 1px solid #eee; color: #666; font-size: 0.9em; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>PyGovPub Performance Report</h1>
            <p>Generated on: """ + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S") + """</p>
            
            <div class="summary">
                <h2>Performance Summary</h2>
    """
    
    if not summary:
        html += "<p>No performance history available.</p>"
    else:
        # Add summary table
        html += """
                <table>
                    <thead>
                        <tr>
                            <th>Test</th>
                            <th>Metric</th>
                            <th>Current Value</th>
                            <th>Change</th>
                            <th>Trend</th>
                        </tr>
                    </thead>
                    <tbody>
        """
        
        for test_name, test_data in summary.items():
            trends = test_data.get("trend", {})
            last_run = test_data.get("last_run", "Never")
            
            if not trends:
                html += f"""
                        <tr>
                            <td>{test_name}</td>
                            <td colspan="4">No trend data available</td>
                        </tr>
                """
                continue
            
            # Add rows for each metric
            first_metric = True
            for metric, trend in trends.items():
                direction = trend.get("direction", "unknown")
                change = trend.get("percent_change", 0)
                recent = trend.get("recent", 0)
                
                # CSS class based on direction
                css_class = direction if direction in ["improving", "degrading", "stable"] else ""
                
                # Direction indicator
                if direction == "improving":
                    trend_indicator = "↑ Improving"
                elif direction == "degrading":
                    trend_indicator = "↓ Degrading"
                else:
                    trend_indicator = "→ Stable"
                
                html += f"""
                        <tr>
                            <td>{test_name if first_metric else ""}</td>
                            <td>{metric}</td>
                            <td>{recent:.2f}</td>
                            <td class="{css_class}">{change:+.1f}%</td>
                            <td class="{css_class}">{trend_indicator}</td>
                        </tr>
                """
                first_metric = False
        
        html += """
                    </tbody>
                </table>
        """
    
    # Add charts
    html += """
            </div>
            
            <h2>Performance Trend Charts</h2>
    """
    
    if not chart_paths:
        html += "<p>No trend charts available.</p>"
    else:
        for chart_path in chart_paths:
            # Get filename without extension for title
            chart_name = os.path.basename(chart_path).split(".")[0].replace("_", " ").title()
            html += f"""
            <div class="chart">
                <h3>{chart_name}</h3>
                <img src="../../{chart_path}" alt="{chart_name}">
            </div>
            """
    
    # Add recommendations
    html += """
            <h2>Performance Recommendations</h2>
            <div class="summary">
                <p>Based on current performance metrics, the following recommendations are made:</p>
                <ul>
    """
    
    # Generate recommendations based on metrics
    recommendations = []
    
    # Look for high response times
    for test_name, test_data in summary.items():
        trends = test_data.get("trend", {})
        for metric, trend in trends.items():
            if "response_time" in metric and trend.get("recent", 0) > 100:
                recommendations.append(f"Optimize {test_name} to reduce response time below 100ms (currently {trend.get('recent', 0):.2f}ms)")
            
            if "throughput" in metric and trend.get("recent", 0) < 50:
                recommendations.append(f"Improve throughput capacity for {test_name} (currently {trend.get('recent', 0):.2f} QPS)")
            
            if "memory" in metric and trend.get("recent", 0) > 200:
                recommendations.append(f"Reduce memory usage in {test_name} (currently {trend.get('recent', 0):.2f}MB)")
            
            if trend.get("direction") == "degrading" and abs(trend.get("percent_change", 0)) > 10:
                recommendations.append(f"Investigate performance degradation in {metric} for {test_name} ({abs(trend.get('percent_change', 0)):.1f}% worse)")
    
    # Add generic recommendations if none found
    if not recommendations:
        recommendations = [
            "Continue monitoring performance trends with each release",
            "Expand test coverage to more components",
            "Consider adding load testing for API endpoints",
            "Run performance tests in production-like environment",
            "Set up automated alerts for performance regressions"
        ]
    
    # Add recommendations to HTML
    for recommendation in recommendations:
        html += f"<li>{recommendation}</li>\n"
    
    # Close HTML
    html += """
                </ul>
            </div>
            
            <div class="footer">
                <p>Performance report generated by PyGovPub performance testing framework.</p>
                <p>For details on running performance tests, see: <a href="../../../docs/performance/README.md">Performance Testing Guide</a></p>
            </div>
        </div>
    </body>
    </html>
    """
    
    # Write HTML to file
    with open(HTML_REPORT, "w") as f:
        f.write(html)
    
    return HTML_REPORT


def main():
    """Run the performance report generator."""
    parser = argparse.ArgumentParser(description="Run performance tests and generate reports")
    parser.add_argument("--tests", nargs="+", help="Specific tests to run")
    parser.add_argument("--repeat", type=int, default=1, help="Number of test runs")
    parser.add_argument("--report-only", action="store_true", help="Generate report without running tests")
    args = parser.parse_args()
    
    if not args.report_only:
        # Run tests
        run_tests(args.tests, args.repeat)
    
    # Generate trend charts
    chart_files = generate_trend_charts()
    print(f"Generated {len(chart_files)} trend charts")
    
    # Print summary
    print_summary_report()
    
    # Generate HTML report
    report_path = generate_html_report()
    print(f"Generated HTML report: {report_path}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())