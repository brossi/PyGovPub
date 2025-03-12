# Query Plan Analysis for Vector Search Operations

PyGovPub provides comprehensive query plan analysis and optimization for vector and hybrid search operations. This document explains how to use these features to improve search performance and understand query behavior.

## Overview

Query plan analysis helps you understand how vector and hybrid search operations will be executed, allowing you to:

1. Identify performance bottlenecks before running expensive queries
2. Optimize search parameters for better results
3. Monitor and improve search execution
4. Apply recommended optimizations automatically

## Basic Usage

### Analyzing Vector Searches

```python
from pygovpub.storage.interface import StorageInterface
from pygovpub.models.documents import Document

# Initialize storage interface
storage = StorageInterface("lancedb:///path/to/db")

# Create a query vector (example: 384 dimensions)
query_vector = [0.1, 0.2, ...] # 384 dimensions

# Get query plan without executing search
plan = storage.get_vector_search_plan(
    provider_type="lancedb",
    model_class=Document,
    query_vector=query_vector,
    filter_criteria={"category": "legal"}
)

# Examine plan details
print(f"Estimated cost: {plan.estimated_cost}")
print(f"Estimated time: {plan.estimated_time_ms}ms")
print(f"Has vector index: {plan.has_index}")

# See recommended optimizations
for opt in plan.optimizations:
    print(f"Optimization: {opt['description']} (saves {opt['cost_reduction']})")

# Execute search with query analysis
results = storage.vector_search_with_provider(
    provider_type="lancedb",
    model_class=Document,
    query_vector=query_vector,
    filter_criteria={"category": "legal"},
    analyze_query=True  # Enable query analysis (default)
)
```

### Analyzing Hybrid Searches

```python
# Get hybrid search plan
plan = storage.get_hybrid_search_plan(
    provider_type="lancedb",
    model_class=Document,
    query_text="supreme court ruling on privacy",
    query_vector=query_vector,  # Optional
    filter_criteria={"year": 2023}
)

# Execute hybrid search with analysis
results = storage.hybrid_search_with_provider(
    provider_type="lancedb",
    model_class=Document,
    query_text="supreme court ruling on privacy",
    filter_criteria={"year": 2023}
)
```

## Understanding Query Plans

Query plans contain the following information:

### Vector Search Plans

```python
VectorSearchPlan(
    provider_type="lancedb",
    table_name="documents",
    vector_dim=384,
    filter_count=2,
    has_index=True,
    estimated_result_count=50,
    estimated_cost=10.5,
    estimated_time_ms=150,
    optimizations=[...]
)
```

Key attributes:
- `provider_type`: The storage provider type
- `table_name`: Target table or collection
- `vector_dim`: Vector dimension
- `filter_count`: Number of filtering criteria
- `has_index`: Whether a vector index exists
- `estimated_result_count`: Estimated number of results
- `estimated_cost`: Arbitrary cost metric (lower is better)
- `estimated_time_ms`: Estimated execution time in milliseconds
- `optimizations`: List of suggested optimizations

### Hybrid Search Plans

Hybrid plans include all vector search plan attributes, plus:
- `text_query_length`: Number of words in the text query
- `operation`: Set to "hybrid_search" automatically

## Performance Monitoring

Query plan execution is automatically monitored with Prometheus metrics:

- `query_plans_created_total`: Count of query plans created
- `query_plan_cost`: Distribution of estimated query costs
- `query_optimizations_applied_total`: Count of optimizations applied
- `query_plan_execution_time_seconds`: Actual execution times

## Common Optimizations

The query optimizer may suggest the following optimizations:

1. **Vector Index Creation**: Creating vector indices for faster similarity search
2. **Filter Reduction**: Reducing the number of filters for better performance
3. **Dimension Reduction**: Using lower-dimensional embeddings for faster search
4. **Text Query Simplification**: Simplifying text queries to key terms
5. **Query Execution Strategy**: Using specialized execution strategies

## Best Practices

1. **Pre-analyze expensive queries**: Use `get_vector_search_plan()` or `get_hybrid_search_plan()` before running expensive operations
2. **Create vector indices**: Always create indices for large collections
3. **Monitor query costs**: Watch for high-cost queries in metrics
4. **Limit filter complexity**: Keep filter criteria minimal
5. **Use hybrid search wisely**: Carefully balance text and vector components

## Implementation Details

- **Cost Model**: Cost estimations use a heuristic model based on vector dimension, index presence, and filter complexity
- **Optimization Selection**: Optimizations are chosen based on potential cost reduction
- **Execution Time Estimation**: Time estimates are derived from cost with provider-specific scaling factors

## Customizing Query Analysis

To disable query analysis for specific searches:

```python
results = storage.vector_search_with_provider(
    provider_type="lancedb",
    model_class=Document,
    query_vector=query_vector,
    analyze_query=False  # Disable query analysis
)
```