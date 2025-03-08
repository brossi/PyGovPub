# PyGovPub Naming Conventions

## Overview
Standardized naming conventions for consistency across all PyGovPub components.

## Python Code

### Variables and Functions
- Use `snake_case` for all variable and function names
- Use descriptive, full-word names
```python
bill_status = get_bill_status()
committee_members = fetch_committee_members()
```

### Classes
- Use `PascalCase` for class names
- Use noun phrases for class names
```python
class BillVersion:
class CommitteeMember:
```

### Constants
- Use `UPPER_SNAKE_CASE` for constants
```python
MAX_RATE_LIMIT = 5000
DEFAULT_API_VERSION = "v1"
```

## Database

### Table Names
- Use `snake_case`
- Use plural form
- Prefix with domain where appropriate
```sql
bills
bill_versions
committee_members
auth_tokens
```

### Column Names
- Use `snake_case`
- Be explicit about foreign keys
```sql
bill_id
committee_member_id
created_at
updated_at
```

### Indexes and Constraints
- Format: `{table}_{columns}_{type}`
```sql
bills_congress_id_idx
committee_members_pkey
```

## API Endpoints

### URL Structure
- Use kebab-case for URLs
- Use plural nouns for resources
```
/api/v1/bills
/api/v1/committee-members
```

### Query Parameters
- Use snake_case
```
?bill_type=hr&congress=117
?committee_id=HSAG
```

## Documentation

### File Names
- Use kebab-case for all documentation files
```
database-schema.md
api-reference.md
```

### Directory Names
- Use kebab-case for directories
```
user-stories/
dev-references/
```

### Section Headers
- Use Title Case for main headers
- Use Sentence case for sub-headers
```markdown
# Database Schema
## Table definitions
### Primary key constraints
```

## Implementation Notes
- These conventions apply to all new code and documentation
- Existing files will be updated as they are modified
- Automated checks will be added to CI/CD
