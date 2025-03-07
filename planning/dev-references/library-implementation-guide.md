# Library Implementation Guide

## Overview
This guide serves as the authoritative reference for library versions and implementation patterns allowed in the PyGovPub SDK.

## Documentation Reference
```xml
<library_docs>
source=dev-references/library-tool-documentation_fastapi-postgres-pydantic-sqlmodel-pytest-py_devguide.txt
status=authoritative
priority=critical
scope=all_development
implementation=mandatory
</library_docs>
```

## Library Constraints

```xml
<library_constraints>
adherence=strict
modifications=prohibited
version_control=exact
alternatives=prohibited
exceptions=require_approval
</library_constraints>
```

## Constructor-LLM Instructions

```xml
<llm_instructions>
priority=critical
reference_doc=dev-references/library-tool-documentation_fastapi-postgres-pydantic-sqlmodel-pytest-py_devguide.txt
usage=[
    "primary_reference",
    "version_validation",
    "pattern_verification",
    "implementation_guidance"
]
constraints=[
    "strict_version_adherence",
    "follow_documented_patterns",
    "no_alternative_libraries",
    "document_all_usage"
]
validation=mandatory
fallback=this_document
</llm_instructions>
```

## Implementation Requirements

```xml
<requirements>
version_matching=exact
pattern_adherence=strict
documentation=comprehensive
testing=required
validation=mandatory
</requirements>
```

## Library Stack

```xml
<stack>
web_framework=fastapi
database=postgres
orm=sqlmodel
validation=pydantic
testing=pytest
type_checking=py
</stack>
```

## Usage Guidelines

1. **Version Control**
   - Use exact versions specified
   - No version modifications allowed
   - Document any version constraints

2. **Implementation Patterns**
   - Follow documented patterns strictly
   - Use provided examples as templates
   - Maintain consistent approach

3. **Integration Requirements**
   - Follow integration guidelines
   - Use documented interfaces
   - Maintain library compatibility

4. **Testing Standards**
   - Implement required test patterns
   - Follow testing guidelines
   - Maintain coverage requirements

## Quality Requirements

```xml
<quality>
version_adherence=exact
pattern_matching=strict
documentation=required
testing=comprehensive
validation=mandatory
</quality>
```

## Validation Rules

```xml
<validation>
version_check=mandatory
pattern_verification=required
integration_testing=comprehensive
compatibility_check=required
documentation_review=mandatory
</validation>
```

## Documentation Requirements

```xml
<documentation>
library_usage=comprehensive
pattern_implementation=detailed
version_specifications=exact
integration_details=required
testing_approach=documented
</documentation>
```

This guide serves as the mandatory reference for library implementations. The constructor-LLM MUST use this as the fallback reference for any library-related questions or implementation decisions.
