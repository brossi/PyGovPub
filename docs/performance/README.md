# PyGovPub Performance Testing Guide

This document outlines the performance testing strategy and procedures for the PyGovPub project.

## Performance Testing Philosophy

PyGovPub follows these performance testing principles:

1. **Continuous Benchmarking**: Performance tests are run regularly to detect regressions early
2. **Realistic Load Testing**: Tests simulate realistic API usage patterns based on expected user behavior
3. **Comprehensive Metrics**: We track response time, throughput, memory usage, and resource utilization
4. **Trend Analysis**: Historical performance data is tracked to identify trends and regressions

## Available Performance Tests

The following performance tests are available:

### Search Performance Tests

These tests verify the performance of the search functionality:

- **Response Time**: Measures response time for different query patterns
- **Memory Usage**: Tracks memory consumption during search operations
- **Concurrent Search**: Tests performance under concurrent load
- **Provider Performance**: Compares response times across different search providers

### API Performance Tests

These tests verify the performance of the API endpoints:

- **Throughput Capacity**: Measures maximum sustainable query rate
- **Response Degradation**: Tracks how response time changes under increasing load
- **Resource Utilization**: Monitors CPU, memory and connection usage

## Running Performance Tests

To run all performance tests:

```bash
# Make sure your virtual environment is activated
source venv/bin/activate

# Run all performance tests and generate reports
pytest tests/performance/metrics/ -v
```

To run specific performance tests:

```bash
# Search response time tests
pytest tests/performance/metrics/test_search_performance.py::test_search_response_time -v

# Memory usage tests
pytest tests/performance/metrics/test_search_performance.py::test_search_memory_usage -v

# Concurrent search tests
pytest tests/performance/metrics/test_search_performance.py::test_concurrent_search_performance -v

# Throughput capacity tests
pytest tests/performance/metrics/test_throughput_capacity.py -v
```

## Performance Report Generation

PyGovPub automatically generates performance reports and trend analysis. To generate a comprehensive performance report:

```bash
# Generate performance report
python -m tests.performance.metrics.performance_history
```

The report will be available in `tests/performance/metrics/history/charts/performance_dashboard.png` with detailed charts in the same directory.

## Interpreting Results

Performance test results are compared against the following targets:

| Metric | Target | Warning Threshold | Critical Threshold |
|--------|--------|-------------------|-------------------|
| Search Response Time | < 100ms | > 200ms | > 500ms |
| API Response Time | < 50ms | > 100ms | > 250ms |
| Throughput | > 100 QPS | < 50 QPS | < 20 QPS |
| Memory Growth | < 50MB | > 100MB | > 200MB |
| CPU Usage | < 50% | > 75% | > 90% |

## Performance Trend Tracking

Performance trends are automatically tracked across test runs. The system captures:

1. **Baseline Performance**: Initial benchmark measurements
2. **Recent Performance**: Latest test results
3. **Trend Direction**: Whether performance is improving, degrading, or stable
4. **Percent Change**: Quantifies performance changes over time

The performance history is stored in:
- Individual test results: `tests/performance/metrics/history/`
- Summary file: `tests/performance/metrics/history/performance_summary.json`
- Trend charts: `tests/performance/metrics/history/charts/`

## Maintenance and Continuous Improvement

To maintain effective performance testing:

1. Run performance tests regularly (at least weekly and before major releases)
2. Update performance targets as requirements evolve
3. Add new tests for new functionality
4. Investigate any performance degradations promptly
5. Periodically review and update test parameters to maintain relevance

## Integration with CI/CD

Performance tests are integrated with the CI/CD pipeline:

- Basic performance tests run on every pull request
- Comprehensive tests run nightly
- Performance alerts are sent when metrics exceed warning thresholds
- Performance dashboards are automatically updated with each test run