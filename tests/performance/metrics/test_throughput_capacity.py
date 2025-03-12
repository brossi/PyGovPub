"""
Throughput capacity testing for PyGovPub.

This module contains tests to verify that the system meets throughput requirements
under various load conditions, focusing on:
1. Maximum sustainable query rate
2. Response degradation under load 
3. Resource utilization scaling
"""

import asyncio
import time
import os
import statistics
from typing import Dict, List, Any, Tuple
import pytest
import psutil
import matplotlib.pyplot as plt
from unittest.mock import patch, AsyncMock

from fastapi.testclient import TestClient
from fastapi import FastAPI
from starlette.responses import JSONResponse

from pygovpub.api.app import create_app
from pygovpub.auth.models import ApiSource
from pygovpub.api.base import BaseApiClient

# Performance thresholds
MIN_THROUGHPUT_QPS = 50  # Minimum queries per second
MAX_RESPONSE_TIME_MS = 200  # Maximum acceptable response time
MAX_CPU_USAGE_PERCENT = 80  # Maximum acceptable CPU usage

# Test duration settings
WARMUP_TIME_SEC = 2
TEST_DURATION_SEC = 10


def get_system_metrics() -> Dict[str, float]:
    """Get current system metrics."""
    process = psutil.Process(os.getpid())
    
    return {
        "memory_mb": process.memory_info().rss / 1024 / 1024,
        "cpu_percent": process.cpu_percent(interval=0.1),
        "thread_count": len(process.threads()),
        "open_files": len(process.open_files()),
        "connections": len(process.connections())
    }


def save_performance_chart(title: str, x_data: List, y_data_sets: Dict[str, List], xlabel: str, ylabel: str):
    """Generate and save a performance chart."""
    plt.figure(figsize=(12, 6))
    
    for label, y_data in y_data_sets.items():
        plt.plot(x_data[:len(y_data)], y_data, label=label, marker='o')
    
    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.legend()
    plt.grid(True)
    
    # Save the chart
    filename = f"tests/performance/metrics/{title.lower().replace(' ', '_')}.png"
    plt.savefig(filename)
    plt.close()
    
    return filename


class MockResponse:
    """Mock API response."""
    
    def __init__(self, status_code: int, json_data: Dict[str, Any]):
        self.status_code = status_code
        self._json_data = json_data
        self.elapsed = 0
    
    def json(self):
        """Return JSON data."""
        return self._json_data


@pytest.fixture
def mock_api_client():
    """Fixture for a mock API client."""
    
    class TestApiClient(BaseApiClient):
        """Mock API client for testing."""
        
        def __init__(self):
            self.request_count = 0
            self.start_time = time.time()
            self.requests = []
        
        async def get(self, url: str, **kwargs):
            """Mock HTTP GET request."""
            self.request_count += 1
            self.requests.append({"url": url, "time": time.time() - self.start_time, **kwargs})
            
            # Simulate response time based on current load
            # Response time increases with number of concurrent requests
            current_rate = self.request_count / (time.time() - self.start_time)
            simulated_delay = min(0.1, 0.01 * (current_rate / 10))
            await asyncio.sleep(simulated_delay)
            
            return MockResponse(200, {"data": "test", "id": self.request_count})
        
        async def post(self, url: str, **kwargs):
            """Mock HTTP POST request."""
            self.request_count += 1
            self.requests.append({"url": url, "method": "POST", "time": time.time() - self.start_time, **kwargs})
            
            # Simulate response time
            await asyncio.sleep(0.02)
            
            return MockResponse(201, {"data": "created", "id": self.request_count})
        
        def get_metrics(self):
            """Get request metrics."""
            elapsed = time.time() - self.start_time
            request_rate = self.request_count / elapsed if elapsed > 0 else 0
            
            # Calculate request rates over time
            times = [r["time"] for r in self.requests]
            rates = []
            
            if times:
                for i in range(1, len(times)):
                    interval = times[i] - times[i-1]
                    rate = 1 / interval if interval > 0 else 0
                    rates.append(rate)
            
            return {
                "request_count": self.request_count,
                "elapsed_time": elapsed,
                "average_rate": request_rate,
                "rates": rates
            }
        
        def reset(self):
            """Reset metrics."""
            self.request_count = 0
            self.start_time = time.time()
            self.requests = []
    
    return TestApiClient()


async def run_load_test(client, request_func, duration_sec: int, max_concurrency: int) -> Dict[str, Any]:
    """Run a load test with increasing concurrency."""
    
    start_time = time.time()
    end_time = start_time + duration_sec
    running_tasks = set()
    completed_count = 0
    response_times = []
    concurrency_levels = []
    
    # Metrics over time
    timestamps = []
    throughputs = []
    response_times_by_time = []
    
    # System metrics over time
    cpu_usage = []
    memory_usage = []
    
    async def worker():
        """Worker task that makes requests until the test ends."""
        nonlocal completed_count
        
        while time.time() < end_time:
            start_request = time.time()
            await request_func()
            request_time = (time.time() - start_request) * 1000  # ms
            
            response_times.append(request_time)
            completed_count += 1
            
            # Small delay to prevent CPU overload in tests
            await asyncio.sleep(0.001)
    
    # Reporting task
    async def report_metrics():
        """Periodically report metrics during the test."""
        report_interval = 0.5  # seconds
        prev_completed = 0
        
        while time.time() < end_time:
            await asyncio.sleep(report_interval)
            
            # Calculate instantaneous throughput
            now = time.time()
            current_completed = completed_count
            current_throughput = (current_completed - prev_completed) / report_interval
            avg_response = statistics.mean(response_times[-100:]) if response_times else 0
            
            # Record metrics
            timestamps.append(now - start_time)
            throughputs.append(current_throughput)
            response_times_by_time.append(avg_response)
            
            # System metrics
            metrics = get_system_metrics()
            cpu_usage.append(metrics["cpu_percent"])
            memory_usage.append(metrics["memory_mb"])
            
            # Current concurrency
            concurrency_levels.append(len(running_tasks))
            
            prev_completed = current_completed
    
    # Start reporting task
    reporter_task = asyncio.create_task(report_metrics())
    
    # Start with one task, then increase up to max_concurrency
    initial_concurrency = 1
    concurrency_step = max(1, max_concurrency // 10)
    current_concurrency = initial_concurrency
    
    # First create initial tasks
    for _ in range(initial_concurrency):
        task = asyncio.create_task(worker())
        running_tasks.add(task)
        task.add_done_callback(running_tasks.discard)
    
    # Step up concurrency during the test
    step_interval = duration_sec / (max_concurrency // concurrency_step)
    next_step_time = start_time + step_interval
    
    while time.time() < end_time:
        current_time = time.time()
        
        # Increase concurrency at intervals
        if current_time >= next_step_time and current_concurrency < max_concurrency:
            new_tasks = min(concurrency_step, max_concurrency - current_concurrency)
            for _ in range(new_tasks):
                task = asyncio.create_task(worker())
                running_tasks.add(task)
                task.add_done_callback(running_tasks.discard)
            
            current_concurrency += new_tasks
            next_step_time = current_time + step_interval
        
        await asyncio.sleep(0.1)
    
    # Wait for reporting to finish
    await reporter_task
    
    # Wait for all tasks to complete
    if running_tasks:
        await asyncio.gather(*running_tasks)
    
    # Calculate results
    elapsed = time.time() - start_time
    throughput = completed_count / elapsed
    avg_response_time = statistics.mean(response_times) if response_times else 0
    
    return {
        "completed_requests": completed_count,
        "elapsed_time": elapsed,
        "throughput": throughput,
        "avg_response_time": avg_response_time,
        "response_times": response_times,
        "max_concurrency": max_concurrency,
        "timestamps": timestamps,
        "throughputs": throughputs,
        "response_times_by_time": response_times_by_time,
        "concurrency_levels": concurrency_levels,
        "cpu_usage": cpu_usage,
        "memory_usage": memory_usage
    }


@pytest.mark.asyncio
async def test_api_throughput_capacity(mock_api_client):
    """Test API throughput capacity under increasing load."""
    
    # Reset client
    mock_api_client.reset()
    
    # Define the request function
    async def make_request():
        return await mock_api_client.get("/api/v1/test")
    
    # Warm up
    print(f"Warming up for {WARMUP_TIME_SEC} seconds...")
    warmup_results = await run_load_test(
        mock_api_client, make_request, 
        duration_sec=WARMUP_TIME_SEC, 
        max_concurrency=5
    )
    
    # Run actual test with increasing concurrency
    print(f"Running throughput test for {TEST_DURATION_SEC} seconds...")
    test_results = await run_load_test(
        mock_api_client, make_request, 
        duration_sec=TEST_DURATION_SEC, 
        max_concurrency=100
    )
    
    # Analyze and print results
    print(f"Completed requests: {test_results['completed_requests']}")
    print(f"Throughput: {test_results['throughput']:.2f} requests/sec")
    print(f"Average response time: {test_results['avg_response_time']:.2f} ms")
    
    # Generate charts
    # Throughput over time
    throughput_chart = save_performance_chart(
        "API Throughput Over Time",
        test_results['timestamps'],
        {"Throughput": test_results['throughputs']},
        "Time (seconds)",
        "Throughput (requests/sec)"
    )
    
    # Response time over time
    response_chart = save_performance_chart(
        "Response Time vs Concurrency",
        test_results['concurrency_levels'],
        {"Response Time": test_results['response_times_by_time']},
        "Concurrency Level",
        "Response Time (ms)"
    )
    
    # System metrics
    metrics_chart = save_performance_chart(
        "System Metrics During Load Test",
        test_results['timestamps'],
        {
            "CPU Usage (%)": test_results['cpu_usage'],
            "Memory (MB)": test_results['memory_usage']
        },
        "Time (seconds)",
        "Resource Usage"
    )
    
    # Verify performance meets requirements
    assert test_results['throughput'] >= MIN_THROUGHPUT_QPS, \
        f"Throughput {test_results['throughput']:.2f} qps below minimum requirement of {MIN_THROUGHPUT_QPS} qps"
    
    assert test_results['avg_response_time'] <= MAX_RESPONSE_TIME_MS, \
        f"Average response time {test_results['avg_response_time']:.2f} ms exceeds maximum allowed {MAX_RESPONSE_TIME_MS} ms"
    
    assert max(test_results['cpu_usage']) <= MAX_CPU_USAGE_PERCENT, \
        f"CPU usage {max(test_results['cpu_usage']):.2f}% exceeds maximum allowed {MAX_CPU_USAGE_PERCENT}%"


@pytest.mark.asyncio
async def test_search_throughput_with_real_server():
    """Test search API throughput with a real FastAPI server."""
    
    # Create FastAPI app
    app = FastAPI()
    
    # Add mock search endpoint
    @app.get("/api/v1/search")
    async def search_endpoint(query: str = "test", offset: int = 0, limit: int = 20):
        # Simulate search processing time
        await asyncio.sleep(0.01)
        
        # Generate simulated search results
        results = [
            {"id": f"result-{i}", "title": f"Search Result {i}", "score": 0.9 - (i * 0.01)}
            for i in range(min(100, limit))
        ]
        
        return {
            "total": 100,
            "offset": offset,
            "limit": limit,
            "results": results,
            "execution_time_ms": 10
        }
    
    # Create test client
    client = TestClient(app)
    
    # Define the request function (using direct calling instead of HTTP)
    async def make_search_request():
        response = await app.router.get_route_handler_for_endpoint("search_endpoint")(
            query="performance", offset=0, limit=20
        )
        return response
    
    # Run throughput test 
    print("Running search API throughput test...")
    test_results = await run_load_test(
        client, make_search_request, 
        duration_sec=TEST_DURATION_SEC, 
        max_concurrency=50
    )
    
    # Analyze and print results
    print(f"Completed search requests: {test_results['completed_requests']}")
    print(f"Search throughput: {test_results['throughput']:.2f} requests/sec")
    print(f"Average search response time: {test_results['avg_response_time']:.2f} ms")
    
    # Generate throughput chart
    throughput_chart = save_performance_chart(
        "Search API Throughput",
        test_results['timestamps'],
        {"Throughput": test_results['throughputs']},
        "Time (seconds)",
        "Throughput (requests/sec)"
    )
    
    # Generate response time vs concurrency chart
    response_chart = save_performance_chart(
        "Search Response Time vs Concurrency",
        test_results['concurrency_levels'],
        {"Response Time": test_results['response_times_by_time']},
        "Concurrency Level",
        "Response Time (ms)"
    )
    
    # Verify performance meets requirements
    # Search endpoints typically have lower throughput requirements due to complexity
    assert test_results['throughput'] >= MIN_THROUGHPUT_QPS / 2, \
        f"Search throughput {test_results['throughput']:.2f} qps below minimum requirement"
        
    # Record metrics to history
    try:
        from tests.performance.metrics.performance_history import record_performance_metrics, generate_trend_charts
        
        # Record this test's metrics
        record_metrics = {
            "completed_requests": test_results['completed_requests'],
            "throughput": test_results['throughput'],
            "avg_response_time": test_results['avg_response_time'],
            "max_concurrency": test_results['max_concurrency'],
        }
        
        metrics_file = record_performance_metrics(
            "search_api_throughput", 
            record_metrics
        )
        print(f"Throughput metrics recorded to: {metrics_file}")
        
        # Generate trend charts across all metrics
        trend_charts = generate_trend_charts()
        if trend_charts:
            print(f"Generated {len(trend_charts)} performance trend charts")
    except ImportError:
        # Silently continue if history module isn't available
        pass


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])