"""Performance tests for encrypted field operations."""
import json
import time
from pathlib import Path
from typing import Dict, Any, List

import pytest
import matplotlib.pyplot as plt
import numpy as np

from pygovpub.storage.security import StorageSecurity
from pygovpub.storage.secure_search_fallback import SecureSearchFallback


def generate_test_data(item_count: int = 10000) -> List[Dict[str, Any]]:
    """Generate test data for encrypted field performance testing."""
    test_data = []
    for i in range(item_count):
        item = {
            "id": f"item-{i}",
            "api_key": f"api-key-{i % 100}",
            "classification": f"classification-{i % 10}",
            "restricted_note": f"restricted-note-{i}",
            "personal_data": f"personal-data-{i % 50}",
            "public_field": f"public-field-{i}"
        }
        test_data.append(item)
    return test_data


@pytest.mark.performance
def test_encrypted_field_performance():
    """Test performance with 10k+ encrypted fields."""
    # Initialize security and search fallback
    security = StorageSecurity(encryption_enabled=True)
    search_fallback = SecureSearchFallback(security)
    
    # Generate test data
    field_counts = [100, 1000, 5000, 10000]
    results = {}
    
    for count in field_counts:
        # Generate the data
        test_data = generate_test_data(count)
        
        # Run performance test
        start_time = time.time()
        performance_data = search_fallback.test_performance(count)
        total_time = time.time() - start_time
        
        # Store results
        results[count] = {
            "total_time_ms": int(total_time * 1000),
            "performance_data": performance_data
        }
    
    # Save the results to JSON file
    output_dir = Path(__file__).parent
    metrics_file = output_dir / "encrypted_field_performance.json"
    with open(metrics_file, "w") as f:
        json.dump(results, f, indent=2)
    
    # Generate performance charts
    generate_performance_charts(results, output_dir)
    
    # Check that the performance is acceptable
    assert results[10000]["performance_data"]["summary"]["average_search_time_ms"] < 5000, \
        "Average search time exceeds 5 seconds for 10,000 items"


def generate_performance_charts(results: Dict[int, Dict[str, Any]], output_dir: Path):
    """Generate performance charts from test results."""
    field_counts = sorted(results.keys())
    
    # Extract metrics
    encryption_times = [results[count]["performance_data"]["summary"]["encryption_time_ms"] for count in field_counts]
    avg_search_times = [results[count]["performance_data"]["summary"]["average_search_time_ms"] for count in field_counts]
    exact_match_times = [results[count]["performance_data"]["exact_match"]["duration_ms"] for count in field_counts]
    prefix_search_times = [results[count]["performance_data"]["prefix"]["duration_ms"] for count in field_counts]
    contains_search_times = [results[count]["performance_data"]["contains"]["duration_ms"] for count in field_counts]
    range_search_times = [results[count]["performance_data"]["range"]["duration_ms"] for count in field_counts]
    batch_times = [results[count]["performance_data"]["batch_operations"]["duration_ms"] for count in field_counts]
    
    # Encryption time
    plt.figure(figsize=(10, 6))
    plt.plot(field_counts, [t/1000 for t in encryption_times], marker='o')
    plt.title("Encryption Time vs. Number of Items")
    plt.xlabel("Number of Items")
    plt.ylabel("Time (seconds)")
    plt.grid(True)
    plt.savefig(output_dir / "encryption_time.png")
    plt.close()
    
    # Search operation times
    plt.figure(figsize=(10, 6))
    plt.plot(field_counts, [t/1000 for t in exact_match_times], marker='o', label="Exact Match")
    plt.plot(field_counts, [t/1000 for t in prefix_search_times], marker='s', label="Prefix")
    plt.plot(field_counts, [t/1000 for t in contains_search_times], marker='^', label="Contains")
    plt.plot(field_counts, [t/1000 for t in range_search_times], marker='d', label="Range")
    plt.plot(field_counts, [t/1000 for t in batch_times], marker='*', label="Batch")
    plt.title("Search Operation Time vs. Number of Items")
    plt.xlabel("Number of Items")
    plt.ylabel("Time (seconds)")
    plt.legend()
    plt.grid(True)
    plt.savefig(output_dir / "search_operation_time.png")
    plt.close()
    
    # Average search time
    plt.figure(figsize=(10, 6))
    plt.plot(field_counts, [t/1000 for t in avg_search_times], marker='o')
    plt.title("Average Search Time vs. Number of Items")
    plt.xlabel("Number of Items")
    plt.ylabel("Time (seconds)")
    plt.grid(True)
    plt.savefig(output_dir / "average_search_time.png")
    plt.close()
    
    # Throughput (items per second)
    plt.figure(figsize=(10, 6))
    ops = ["exact_match", "prefix", "contains", "range", "batch_operations"]
    for op in ops:
        throughput = [results[count]["performance_data"][op]["throughput_items_per_sec"] for count in field_counts]
        plt.plot(field_counts, throughput, marker='o', label=op)
    plt.title("Search Throughput vs. Number of Items")
    plt.xlabel("Number of Items")
    plt.ylabel("Items per Second")
    plt.legend()
    plt.grid(True)
    plt.savefig(output_dir / "search_throughput.png")
    plt.close()