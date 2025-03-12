# PyGovPub Complex Indexing Strategy

This document outlines the complex indexing strategy implemented for PyGovPub to optimize database performance when working with legislative, regulatory, and related data from Congress.gov and GovInfo.gov.

## Index Types Implemented

PyGovPub provides a comprehensive set of indexing functions to maximize query performance for different types of data and access patterns:

### 1. Composite Indexes

Composite indexes allow efficient querying on multiple columns simultaneously. These are particularly useful for common query patterns in legislative data such as:

```python
create_composite_index('bills', ['congress', 'bill_type', 'bill_number'], unique=True)
```

This index enables efficient lookups of bills using their standard identification attributes.

### 2. Functional Indexes

Functional indexes support efficient querying on expressions rather than raw column values, allowing for case-insensitive searches, pattern matching, and data transformation:

```python
create_functional_index('bills', 'LOWER(title)', 'idx_bills_lower_title')
```

This enables efficient case-insensitive text searches on bill titles.

### 3. Partial Indexes

Partial indexes only include rows matching specific conditions, dramatically reducing index size for segmented data access patterns:

```python
create_partial_index('bills', ['introduced_date'], "status = 'INTRODUCED'")
```

This allows optimized queries on recently introduced bills without the overhead of indexing all bills.

### 4. Specialized Index Types

#### B-tree Indexes

Our primary index type, B-tree indexes provide efficient equality and range queries. Suitable for most numeric and time-based data:

```python
create_btree_index('bills', ['introduced_date'])
```

#### Hash Indexes

Hash indexes provide constant-time lookups for exact equality matches. Ideal for foreign key columns, IDs, and exact-match lookups:

```python
create_hash_index('bills', 'bill_id')
```

#### GIN Indexes

GIN (Generalized Inverted Index) indexes are designed for complex data types. They're essential for full-text search, JSONB, and array columns:

```python
create_gin_index('bills', 'full_text', index_operator_class='tsvector_ops')
create_gin_index('documents', 'metadata', index_operator_class='jsonb_path_ops')
```

#### GiST Indexes

GiST (Generalized Search Tree) indexes support geometric data and specialized operators. Used for spatial data, range types, and complex queries:

```python
create_gist_index('congressional_districts', 'geometry')
```

## Index Management

### Index Information Retrieval

Retrieve detailed information about existing indexes on a table:

```python
indexes = get_index_info('bills')
for idx in indexes:
    print(f"{idx['index_name']}: {idx['index_type']} on {idx['column_names']}")
    print(f"Size: {idx['index_size']}, Unique: {idx['is_unique']}")
```

### Index Maintenance

Drop an index when no longer needed:

```python
drop_index('idx_bills_congress_bill_type_bill_number')
```

Create an automated maintenance function to continuously optimize indexes:

```python
create_index_maintenance_function()
```

This PostgreSQL function allows you to:
1. Identify unused indexes that can be dropped
2. Find and rebuild bloated indexes
3. Suggest new indexes based on query patterns

## Indexing Strategy by Entity Type

### Bills and Legislation

- Composite index on `(congress, bill_type, bill_number)` for standard lookups
- B-tree index on `introduced_date` for timeline queries
- GIN index on `full_text` for text search
- Hash index on `bill_id` for direct lookups
- Functional index on `LOWER(title)` for case-insensitive title search
- Partial index on recently active bills with status conditions

### Committee and Member Data

- Hash indexes on primary identifiers (`bioguide_id`, `committee_id`) 
- B-tree indexes on temporal attributes (`term_start`, `term_end`)
- Functional indexes on name fields for flexible name searches

### Regulatory Documents

- Composite indexes for document hierarchies
- GIN indexes for full-text search
- GiST indexes for date ranges
- Partial indexes by document status or publication date ranges

## Performance Considerations

1. **Selective indexing**: Only create indexes for frequent query patterns
2. **Index size monitoring**: Track index growth with `get_index_info()`
3. **Index bloat management**: Use `maintain_indexes()` to identify and rebuild bloated indexes
4. **Regular maintenance**: Schedule periodic cleanup of unused indexes

## Implementation Details

All index management functions and their implementations are located in `pygovpub.core.query_optimization`. These functions are designed to work with PostgreSQL databases for optimal performance in production environments.

The indexing strategy directly supports the PyGovPub core objectives of smart routing, optimized performance, and efficient data integration across government data sources.