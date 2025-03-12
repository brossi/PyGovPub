# STORAGE-001: Core Storage Infrastructure
## Implementation Checklist

### 1. Database Type Detection & Session Management [STORAGE, TEST]
[*] - Implement: Connection type detection matrix
[ ] - Implement: Add support for <mcsymbol name="RateLimitUsage" filename="database-schema.md"></mcsymbol> model sharding
[ ] - Test: Verify async session fallback for non-async databases
[ ] - Test: Verify connection pool exhaustion handling
[ ] - Test: Verify session cleanup during exceptions
[ ] - Test: Verify connection string sanitization
[ ] - Test: Verify cross-db type session isolation
[*] - Implement: Session factory with pool management

### 2. Feature Detection & Capability Reporting [STORAGE, TEST]
[ ] - Test: Verify naming follows <mcfile name="naming-conventions.md"></mcfile>:
  - Connection pools: `snake_case` 
  - Provider classes: `PascalCase`
[ ] - Implement: Add linter checks for storage components
[ ] - Test: Verify pgVector presence detection (PostgreSQL)
[ ] - Test: Verify FTS5 detection (SQLite)
[ ] - Test: Verify LanceDB SDK availability check
[ ] - Test: Verify cloud provider feature flags
[*] - Implement: Runtime capability probing
[ ] - Implement: Feature availability API
[ ] - Document: Feature detection matrix

### 3. Basic Circuit Breaking [STORAGE, TEST]
[ ] - Test: Verify connection failure detection (5 error types)
[ ] - Test: Verify retry backoff timing (exponential/jitter)
[ ] - Test: Verify fallback to in-memory cache
[ ] - Implement: Circuit breaker foundation
[ ] - Document: Resiliency patterns