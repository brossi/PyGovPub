# Search Fallback System

The search fallback system in PyGovPub provides graceful degradation mechanisms for search operations in two key areas:

1. **Vector and Hybrid Search Fallbacks**: Ensures that search operations remain functional even when the primary search method fails or returns low-quality results.

2. **Secure Search Fallbacks for Encrypted Fields**: Enables searching on encrypted fields that cannot be directly queried in the database.

## General Search Fallback Overview

When performing vector or hybrid searches, failures can occur due to various reasons:

1. Vector search may return poor quality results
2. Vector search may raise errors (e.g., due to index issues)
3. Hybrid search may fail in its vector component
4. Text search may be more appropriate for certain queries

The fallback system addresses these issues by automatically cascading through search strategies:

1. Try vector search first (fast, precise for semantic matches)
2. Fall back to hybrid search if vector search fails or returns poor results
3. Fall back to text-only search as a last resort

## Secure Search Fallback Overview

When fields are encrypted for security purposes, they cannot be directly searched in the database. The secure search fallback mechanism provides a way to search encrypted fields by:

1. Retrieving a set of potentially matching records based on non-encrypted fields
2. Decrypting the encrypted fields in memory
3. Applying search predicates to the decrypted values
4. Returning only the records that match the search criteria after decryption

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

## Secure Search Fallback for Encrypted Fields

### Setting Up Secure Search

```python
from pygovpub.storage.security import StorageSecurity
from pygovpub.storage.secure_search_fallback import SecureSearchFallback

# Initialize security and search fallback
security = StorageSecurity()
secure_search = SecureSearchFallback(security)
```

### Search Operations on Encrypted Fields

#### Exact Match Search

```python
# Search for documents with an exact API key
documents = secure_search.search_by_exact_match(
    results,              # List of documents to search within
    "api_key",            # Encrypted field name
    "my-secret-api-key",  # Value to match
    case_sensitive=False  # Case sensitivity
)
```

#### Prefix Search

```python
# Search for classifications starting with "TOP_"
documents = secure_search.search_by_prefix(
    results,
    "metadata.security.classification",  # Can use nested field paths
    "TOP_",
    case_sensitive=True
)
```

#### Contains Search

```python
# Search for documents containing "RESTRICTED" in notes
documents = secure_search.search_by_contains(
    results,
    "restricted_note",
    "RESTRICTED"
)
```

#### Range Search

```python
# Search for documents with values in a specific range
documents = secure_search.search_by_range(
    results,
    "personal_data",
    min_value="A",     # Minimum value (inclusive)
    max_value="D999"   # Maximum value (inclusive)
)
```

#### Batch Operations

For better performance when applying multiple search conditions:

```python
# Apply multiple operations in a single pass
operations = [
    {
        "operation": "prefix",
        "field": "classification",
        "value": "TOP_",
        "case_sensitive": True
    },
    {
        "operation": "contains",
        "field": "restricted_note",
        "value": "NUCLEAR",
        "case_sensitive": False
    }
]

# Get documents matching ALL conditions
documents = secure_search.perform_batch_operations(results, operations)
```

### Performance Considerations

When working with encrypted fields:

1. **Initial Query**: First perform a database query using non-encrypted fields to narrow down the result set.
2. **Secure Search**: Then use secure search only on that smaller result set.
3. **Batching**: Use batch operations when applying multiple search criteria.

Example workflow:

```python
# First, query using non-encrypted fields
initial_results = storage.query(
    Document,
    filter_criteria={"document_type": "CLASSIFIED", "year": 2023}
)

# Then apply secure search on the smaller result set
final_results = secure_search.search_by_prefix(
    initial_results,
    "classification",
    "TOP_SECRET"
)
```

### Performance Testing

The secure search module includes built-in performance testing:

```python
# Test with 10,000 encrypted fields
perf_results = secure_search.test_performance(field_count=10000)

# Print performance metrics
print(f"Encryption time: {perf_results['summary']['encryption_time_ms']} ms")
print(f"Average search time: {perf_results['summary']['average_search_time_ms']} ms")
print(f"Exact match throughput: {perf_results['exact_match']['throughput_items_per_sec']} items/sec")
```

### Secure Search Metrics

The secure search fallback system tracks metrics to help understand and optimize search performance:

- `secure_search_duration_seconds`: Tracks duration of secure search operations
- `secure_search_operations_total`: Counts secure search operations by type and status
- `encryption_processing_duration_seconds`: Measures time spent on encryption/decryption

These metrics help identify performance bottlenecks and optimize search operations on encrypted data.

## Best Practices

### General Search Fallbacks

1. **Configure thresholds** based on your data and use case
2. **Enable result merging** when you want both semantic and keyword matching
3. **Monitor fallback metrics** to identify when fallbacks are being used frequently

### Secure Search Fallbacks

1. **Minimize encrypted fields**: Only encrypt fields that absolutely need encryption.
2. **Index non-sensitive fields**: Use non-sensitive fields for initial filtering.
3. **Batch processing**: Use batch operations when applying multiple search conditions.
4. **Result size limits**: Set reasonable limits on the result set size before applying secure search.
5. **Caching**: Consider caching frequently accessed encrypted fields after decryption (with appropriate security measures).
6. **Key rotation**: When rotating encryption keys, be aware that you may need to re-encrypt existing data for optimal search performance.