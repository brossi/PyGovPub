# USLM Implementation Guide

## Overview
The United States Legislative Markup (USLM) is becoming the standard XML schema for legislative and regulatory content. This guide provides implementation context for supporting both current XML formats and USLM.

## Documentation Reference
```xml
<uslm_docs>
source=dev-references/usgpo-uslm-documentation.txt
version=2.0.0
status=migration_target
priority=high
implementation=required
</uslm_docs>
```

## Implementation Requirements

### Dual Parser Support
```xml
<parser_requirements>
current=standard_xml
future=uslm
transition_strategy=parallel_support
validation=strict
</parser_requirements>
```

### Schema Handling
```xml
<schema_support>
current_schemas=[
    "standard_congress_xml",
    "standard_govinfo_xml"
]
future_schemas=[
    "uslm_2.0.0",
    "uslm_extensions"
]
validation_mode=strict
fallback=false
</schema_support>
```

### Migration Strategy
```xml
<migration_strategy>
phase=preparation
approach=parallel_implementation
rollback=supported
testing=comprehensive
coverage=required
</migration_strategy>
```

## Critical Implementation Points

1. **Dual Format Support**
   - Implement USLM parser alongside current XML parser
   - Maintain both until USGPO completes migration
   - Support seamless switching between formats

2. **Schema Validation**
   - Strict validation against USLM schema
   - Comprehensive error handling
   - Clear error messages for schema violations

3. **Content Processing**
   - Handle both formats in content pipelines
   - Maintain consistent internal representation
   - Support format-specific features

4. **Data Transformation**
   - Convert between current XML and USLM when needed
   - Preserve all metadata during conversion
   - Validate transformation results

## Testing Requirements

```xml
<test_requirements>
coverage.uslm=100
coverage.current=maintained
validation.schema=strict
validation.content=comprehensive
scenarios=[
    "mixed_format_processing",
    "format_detection",
    "schema_validation",
    "error_handling",
    "conversion_accuracy"
]
</test_requirements>
```

## Implementation Phases

1. **Phase 1: USLM Parser Implementation**
   - Implement USLM schema validation
   - Create USLM parser
   - Develop comprehensive test suite

2. **Phase 2: Parallel Processing Support**
   - Add format detection
   - Implement dual processing pipelines
   - Create format conversion utilities

3. **Phase 3: Integration & Testing**
   - Integrate with existing systems
   - Comprehensive testing of both formats
   - Performance optimization

4. **Phase 4: Migration Preparation**
   - Document migration procedures
   - Create rollback plans
   - Prepare monitoring tools

## Constructor-LLM Instructions

```xml
<llm_instructions>
priority=high
context=migration_preparation
focus=[
    "dual_format_support",
    "strict_validation",
    "error_handling",
    "conversion_accuracy"
]
constraints=[
    "no_assumptions",
    "strict_schema_adherence",
    "comprehensive_testing",
    "documented_only"
]
reference_doc=dev-references/usgpo-uslm-documentation.txt
</llm_instructions>
```

## Quality Assurance

```xml
<qa_requirements>
validation.schema=100%
validation.content=100%
testing.coverage=100%
testing.scenarios=comprehensive
documentation=required
review=mandatory
</qa_requirements>
```

## Migration Monitoring

```xml
<monitoring>
metrics=[
    "format_usage",
    "parsing_success",
    "validation_errors",
    "conversion_accuracy",
    "performance_impact"
]
alerts=[
    "schema_violations",
    "conversion_failures",
    "performance_degradation"
]
reporting=required
</monitoring>
```

## Documentation Requirements

```xml
<documentation>
code_comments=comprehensive
api_docs=required
examples=provided
schema_reference=included
migration_guide=required
testing_guide=required
</documentation>
```

This guide serves as the primary reference for implementing USLM support while maintaining current XML functionality. The constructor-LLM should refer to this guide and the referenced USLM documentation when implementing XML parsing capabilities.
