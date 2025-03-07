# Bill Status Implementation Guide

## Overview
This guide references USGPO's experimental bill status tool implementation, which serves as a reference for handling bill objects in the PyGovPub SDK.

## Documentation Reference
```xml
<bill_status_docs>
source=dev-references/govInfo-bill-status-tool.txt
status=reference_implementation
priority=high
scope=bill_objects
implementation=reference_only
</bill_status_docs>
```

## Implementation Context

```xml
<context>
usage=reference_model
constraints=experimental
adherence=strict
modifications=prohibited
</context>
```

## Constructor-LLM Instructions

```xml
<llm_instructions>
priority=high
reference_doc=dev-references/govInfo-bill-status-tool.txt
usage=[
    "bill_object_handling",
    "status_tracking",
    "metadata_processing"
]
constraints=[
    "follow_reference_patterns",
    "no_pattern_modifications",
    "document_deviations",
    "maintain_compatibility"
]
validation=required
</llm_instructions>
```

## Implementation Requirements

```xml
<requirements>
pattern_matching=strict
compatibility=required
documentation=inline
testing=comprehensive
validation=required
</requirements>
```

## Reference Points

```xml
<reference_points>
bill_objects=true
status_tracking=true
metadata_handling=true
version_control=true
relationship_mapping=true
</reference_points>
```

## Usage Guidelines

1. **Pattern Adherence**
   - Use as reference for bill object implementations
   - Follow established patterns strictly
   - Document any necessary deviations

2. **Compatibility**
   - Ensure compatibility with USGPO tools
   - Maintain consistent object representations
   - Follow status tracking patterns

3. **Implementation Scope**
   - Bill object structure
   - Status tracking mechanisms
   - Metadata processing
   - Version control handling

4. **Documentation**
   - Reference source patterns
   - Document compatibility measures
   - Explain implementation decisions

## Quality Requirements

```xml
<quality>
pattern_adherence=strict
compatibility=100%
documentation=required
testing=comprehensive
validation=required
</quality>
```

This guide serves as a reference for implementing bill object handling in accordance with USGPO's experimental tool patterns.
