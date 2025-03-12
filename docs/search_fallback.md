# Search Fallback System

The search fallback system in PyGovPub provides graceful degradation mechanisms for search operations, particularly for vector and hybrid searches. It ensures that search operations remain functional even when the primary search method fails or returns low-quality results.

## Overview

When performing vector or hybrid searches, failures can occur due to various reasons:

1. Vector search may return poor quality results
2. Vector search may raise errors (e.g., due to index issues)
3. Hybrid search may fail in its vector component
4. Text search may be more appropriate for certain queries

The fallback system addresses these issues by automatically cascading through search strategies:

1. Try vector search first (fast, precise for semantic matches)
2. Fall back to hybrid search if vector search fails or returns poor results
3. Fall back to text-only search as a last resort

## Configuration

The fallback behavior is controlled through the `FallbackConfig` class:

```python
from pygovpub.storage.search_fallback import FallbackConfig

config = FallbackConfig(
    # Quality thresholds for different search strategies
    vector_quality_threshold=0.6,  # Minimum quality score for vector search
    hybrid_quality_threshold=0.5,  # Minimum quality score for hybrid search
    text_quality_threshold=0.4,    # Minimum quality score for text search
    
    # Minimum result count requirements
    results_count_threshold=3,     # Minimum number of results required
    
    # Result merging configuration
    enable_result_merging=True,    # Whether to merge results from different sources
    vector_weight=1.0,             # Weight for vector search results during merging
    text_weight=0.7,               # Weight for text search results
    hybrid_text_weight=0.8,        # Weight for text component of hybrid search
    hybrid_vector_weight=1.0       # Weight for vector component of hybrid search
)
```

## Usage

### Direct Fallback Strategy Usage

You can directly use the fallback strategy:

```python
from pygovpub.storage.search_fallback import (
    FallbackConfig, 
    apply_fallback_strategy
)

# Create fallback configuration
config = FallbackConfig(
    vector_quality_threshold=0.7,
    enable_result_merging=True
)

# Apply fallback strategy
results, fallback_info = apply_fallback_strategy(
    provider=lancedb_provider,
    model_class=Document,
    query_text="climate change policy",
    query_vector=embedding_vector,
    limit=10,
    filter_criteria={"document_type": "BILL"},
    config=config
)

# Fallback info contains details about the strategy used
print(f"Strategy: {fallback_info['strategy']}")
print(f"Reason: {fallback_info['reason']}")
```

### Using StorageInterface with Fallbacks

The `StorageInterface` class has been updated to support fallbacks:

```python
from pygovpub.storage.interface import StorageInterface
from pygovpub.storage.search_fallback import FallbackConfig

# Initialize storage
storage = StorageInterface("lancedb:///path/to/database")

# Create fallback configuration
fallback_config = FallbackConfig(
    vector_quality_threshold=0.6,
    enable_result_merging=True
)

# Perform vector search with fallbacks
results = storage.vector_search_with_provider(
    provider_type="lancedb",
    model_class=Document,
    query_vector=embedding_vector,
    query_text="climate change policy",  # Required for fallback
    enable_fallback=True,
    fallback_config=fallback_config
)

# Perform hybrid search with fallbacks
results = storage.hybrid_search_with_provider(
    provider_type="lancedb",
    model_class=Document,
    query_text="climate change policy",
    query_vector=embedding_vector,  # Optional
    enable_fallback=True,
    fallback_config=fallback_config
)
```

## Result Merging

When `enable_result_merging=True`, the system can merge results from multiple search strategies. This is useful when:

1. Vector search returns moderate quality results but hybrid search provides complementary results
2. Different search strategies find different relevant documents

Results are merged with the following approach:

1. Results are normalized and tagged with their source
2. Scores are weighted according to the configuration
3. Results appearing in multiple sources receive a boost
4. Results are sorted by weighted score

Result merging provides a "best of both worlds" approach, combining the semantic understanding of vector search with the keyword precision of text search.

## Metrics and Monitoring

The fallback system tracks metrics to help understand and optimize search behavior:

- `search_fallbacks_total`: Counts fallbacks by strategy and reason
- `search_fallback_latency_seconds`: Tracks fallback operation latency
- `search_quality_scores`: Histograms of search quality by type

These metrics are available through the Prometheus metrics system used throughout PyGovPub.

## Search Quality Verification

The fallback system verifies search quality using multiple factors:

1. Average score of results
2. Number of results returned
3. Maximum score in the result set

A search is considered high quality when:
- The average score exceeds the configured threshold
- The result count meets the minimum requirement
- OR if the maximum score is significantly above the threshold (even with fewer results)

This approach balances recall (getting enough results) with precision (getting high-quality results).