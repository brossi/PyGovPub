# Checklist Development Guide
<version>1.0.0</version>

## Overview
This guide establishes the standard format and rules for creating implementation checklists. All checklists must follow these patterns to ensure comprehensive test coverage and proper implementation sequencing.

## Checklist Structure

### Section Header Format
```markdown
## [Component Name]
Description: Brief description of the component's purpose
Dependencies: List of other components this depends on
```

### Required Test Categories
Every section must begin with test definitions. Use this ordered structure:

```markdown
### Test Requirements
- [ ] DATA: Data Model Tests
    - [ ] TEST: Validate data model attributes
    - [ ] TEST: Verify model relationships
    - [ ] TEST: Confirm data validation rules

- [ ] API: Integration Tests
    - [ ] TEST: API endpoint behavior
    - [ ] TEST: Error handling scenarios
    - [ ] TEST: Response format validation

- [ ] GOV: Government Compliance Tests
    - [ ] TEST: USLM XML validation
    - [ ] TEST: Legislative data accuracy
    - [ ] TEST: Official process compliance

- [ ] ACC: Accessibility Tests
    - [ ] TEST: Section 508 compliance
    - [ ] TEST: WCAG 2.1 AA requirements
    - [ ] TEST: Screen reader compatibility

- [ ] DOC: Documentation Tests
    - [ ] TEST: API documentation accuracy
    - [ ] TEST: Schema documentation completeness
    - [ ] TEST: Process documentation validity

- [ ] SEC: Security Tests
    - [ ] TEST: Authentication flows
    - [ ] TEST: Authorization rules
    - [ ] TEST: Data protection measures

- [ ] PROC: Legislative Process Tests
    - [ ] TEST: Workflow sequence validation
    - [ ] TEST: Status transition accuracy
    - [ ] TEST: Process documentation compliance
```

### Implementation Tasks
Only after all test requirements are defined:

```markdown
### Implementation Tasks
- [ ] SETUP: Environment Configuration
- [ ] IMPL: Core Implementation
- [ ] VALID: Validation Implementation
- [ ] DOC: Documentation Updates
```

## Checklist Rules

### Test-First Rule
- All test items must be defined before implementation items
- Each implementation item must have corresponding test items
- No implementation task can be added without test coverage

### Prefix Requirements
- TEST: For test definitions
- IMPL: For implementation tasks
- VALID: For validation tasks
- DOC: For documentation tasks
- SEC: For security tasks
- ACC: For accessibility tasks

### Dependency Marking
```markdown
- [ ] TEST: Component A Test
- [ ] IMPL: Component A Implementation
    └─ Depends on: Component B Tests
```

### Validation Requirements
- Each section must have validation steps
- Validation must reference specific test cases
- Documentation updates must be verified

## Example Section

```markdown
## Legislative Data Processor
Description: Processes USLM XML data from Congress.gov API
Dependencies: Authentication Service, XML Parser

### Test Requirements
- [ ] DATA: XML Schema Tests
    - [ ] TEST: Validate USLM XML schema compliance
    - [ ] TEST: Verify document structure parsing
    - [ ] TEST: Confirm metadata extraction

- [ ] API: Congress.gov Integration Tests
    - [ ] TEST: API authentication flow
    - [ ] TEST: Data retrieval methods
    - [ ] TEST: Rate limit handling

- [ ] GOV: Legislative Compliance Tests
    - [ ] TEST: Legislative markup accuracy
    - [ ] TEST: Process step validation
    - [ ] TEST: Status code mapping

### Implementation Tasks
- [ ] IMPL: Set up XML processor
    └─ Depends on: DATA: XML Schema Tests
- [ ] IMPL: Integrate Congress.gov API
    └─ Depends on: API: Congress.gov Integration Tests
- [ ] VALID: Verify processing accuracy
    └─ Depends on: GOV: Legislative Compliance Tests
- [ ] DOC: Update API documentation
```

## Checklist Validation

### Test Coverage
- All features have corresponding tests
- All compliance requirements have tests
- All error conditions have tests

### Dependency Clarity
- All dependencies are explicitly marked
- No circular dependencies exist
- Dependencies are properly sequenced

### Compliance Completeness
- Section 508 requirements addressed
- Security considerations included
- Documentation requirements specified

### Implementation Completeness
- All tests have corresponding implementation tasks
- All implementation tasks have validation steps
- All features have documentation tasks

## Maintenance Rules

### Updates
- New tests must be added before new features
- Existing tests must be updated for changes
- Documentation must be updated with changes

### Review Process
- Checklists must be reviewed for completeness
- Test coverage must be verified
- Dependencies must be validated

## Checklist Format Rules

### Strict Ordering
- All checklists MUST be completed in sequential order
- NO skipping ahead or parallel development
- Each section MUST be completed before proceeding
- Any deviation MUST be marked with "DEVIATION REQUESTED: [reason]" and await explicit approval

### LLM Interaction Rules
```markdown
# Section Status Markers
[NOT STARTED] - Section not yet begun
[IN PROGRESS] - Currently working on section
[BLOCKED] - Cannot proceed, reason specified
[COMPLETED] - All items checked and verified
[DEVIATION REQUESTED] - Awaiting approval to modify standard process

# Required Section Headers
[TESTS DEFINED] - All tests specified
[TESTS IMPLEMENTED] - All tests coded
[TESTS PASSING] - All tests verified
[IMPLEMENTATION READY] - Ready for feature implementation
```

### Checkpoint Format
```markdown
## Checkpoint: [Name]
Status: [Status Marker]
Last Updated: [Timestamp]
Blocked: [If yes, reason]

### Tests
- [ ] TEST-1: [Description]
    └─ Log: /logs/[component]/TEST-1.md
```

### Deviation Request Format
```markdown
!!! DEVIATION REQUEST !!!
Checkpoint: [Name]
Reason: [Detailed explanation]
Impact: [What rules/requirements would be bypassed]
Mitigation: [How to handle skipped steps later]
Status: AWAITING APPROVAL
```

### LLM Instructions
- NEVER skip test definition steps
- NEVER begin implementation before tests are complete
- NEVER mark items complete without verification
- ALWAYS request explicit approval for deviations
- ALWAYS maintain section status markers
- ALWAYS check dependencies before proceeding

## Work Log Requirements

### Log Entry Format
```markdown
## [Checklist Item ID]: [Brief Title]
Completed: [Timestamp]

### What We Did
[Clear description of the actual work completed]

### Why We Did It
[Explanation of the purpose and expected value]

### How We Did It
[Technical details of the implementation approach]

### Plan vs Reality
Original Plan: [What we thought we would do]
Actual Outcome: [What actually happened]
Key Differences: [Major variations from plan]
What We Got Right: [Aspects correctly predicted]

### Lessons Learned
- [Key insight 1]
- [Key insight 2]
- [Future considerations]
```

### Example Log Entry
```markdown
## DATA-TEST-1: USLM XML Schema Validation Test
Completed: 2025-03-07 15:45:22

### What We Did
Created test suite for validating USLM XML documents against official schema

### Why We Did It
Need to ensure all processed legislative documents strictly conform to USLM standards

### How We Did It
Used xmlschema library with custom validation hooks for Congress.gov specific requirements

### Plan vs Reality
Original Plan: Simple schema validation against XSD
Actual Outcome: Required custom validation rules for Congress.gov extensions
Key Differences:
- Discovered unofficial schema extensions in use
- Needed to handle multiple schema versions
What We Got Right:
- Basic validation approach was correct
- Predicted need for custom error messages

### Lessons Learned
- Congress.gov uses schema extensions not in public documentation
- Need to version-check schema before validation
- Should build schema validation registry for different document types
- Consider caching validated schema patterns
```

### LLM Logging Rules
- MUST complete log entry immediately after completing each checklist item
- MUST be specific and detailed about differences from original plan
- MUST include actionable lessons learned
- MUST relate insights to future development considerations
- NEVER skip logging even if task went exactly as planned

## Work Log File Requirements

### File Naming Convention
```markdown
/logs/[component-name]/[task-id].md

Examples:
/logs/legislative-processor/DATA-TEST-1.md
/logs/authentication/SEC-TEST-2.md
/logs/xml-parser/IMPL-3.md
```

### Checklist-Log Relationship Rules
- Each checklist item MUST have a corresponding log file
- Log file MUST exist before checkbox can be marked complete
- Log filename MUST match task ID exactly
- Checkbox format updated to include log file reference

### LLM Validation Rules
- NEVER mark a checkbox complete without creating log file
- ALWAYS verify log file exists before updating checkbox
- ALWAYS include full log file path in checkbox entry
- MUST alert if checkbox is marked but log file missing: "INVALID COMPLETION: No log file found for [task-id]"

### File Structure Example
```markdown
planning/
├── checklists/
│   └── legislative-processor.md
├── logs/
│   └── legislative-processor/
│       ├── DATA-TEST-1.md
│       ├── DATA-TEST-2.md
│       ├── API-TEST-1.md
│       └── IMPL-1.md
```
