# User Stories & Scenarios

## Directory Structure
```
user-stories/
├── README.md           # This file - directory overview
├── scenarios.md        # High-level functional domains and patterns
├── index.md           # Detailed user story tracking and references
├── legislative/       # Legislative domain stories
│   ├── bill-tracking/ # Bill tracking stories
│   └── committee/     # Committee activity stories
└── ...                # Other domain directories
```

## Documentation Organization

### 1. High-Level Overview
[scenarios.md](./scenarios.md) provides:
- Functional domain descriptions
- Core workflows and patterns
- API integration patterns
- Implementation considerations

### 2. Story Tracking
[index.md](./index.md) provides:
- Complete story catalog
- Status tracking
- Cross-references
- Implementation progress

### 3. Detailed Stories
Individual `.md` files in domain directories contain:
- Specific user stories
- Acceptance criteria
- Technical requirements
- Related references

## Usage
1. Start with `scenarios.md` for domain understanding
2. Use `index.md` to find specific stories
3. Reference individual story files for implementation details

## Persona References
When referencing personas in user stories:

1. **In User Story Definition**:
   ```markdown
   **As a** [Role Title](../../personas.md#anchor-name),
   ```

2. **In Related Personas Section**:
   ```markdown
   ### Personas
   - Primary: [Role Title](../../personas.md#anchor-name)
   - Secondary: [Role Title](../../personas.md#anchor-name)
   ```

3. **Anchor Names**:
   - Use kebab-case: `#policy-professional`
   - Based on role title, not individual name
   - Defined in personas.md using `<a name="policy-professional"></a>`

This ensures consistent referencing and maintains a single source of truth for persona definitions.

## Story Types and Templates

### Core API Integration Stories
Core stories focus on PyGovPub's fundamental API integration capabilities:

1. **Template Usage**:
   - Use [core-story.md](./templates/core-story.md) for all new stories
   - Focus on API integration, data validation, and error handling
   - Exclude application-specific features

2. **Key Sections**:
   - API Integration Requirements
   - Data Reconciliation
   - Error Handling
   - Performance Requirements
   - Technical Implementation Details

3. **Example**:
   - See [LM-BT-001](../legislative/bill-tracking/LM-BT-001.md) for a core story example

### Application Features
Application-specific features are documented in [future-implementation-scenarios.md](../../future-implementation-scenarios.md) rather than as user stories.

## Story Writing Methodology

### Core Principles
1. **Simplicity**: "Everything should be as simple as it can be, but not simpler" (Einstein)
   - Focus on essential information
   - Avoid implementation details
   - Maintain clarity without oversimplification

2. **Natural Flow**: Stories follow context → goal → acceptance → details
   - Context & Goal: What we're trying to achieve
   - Acceptance Criteria: How we know we've achieved it
   - Technical Context: What we need to consider
   - Related Information: Who's involved and what else matters

3. **Goldilocks Rule**: Keep requirements concise
   - Small, focused slice of work
   - Nested within larger development framework
   - Clear, manageable scope

### Story Structure
1. **Context & Goal**
   - Uses "As a/I want to/So that" format
   - Focuses on WHAT and WHY, not HOW
   - Links to relevant personas

2. **Acceptance Criteria**
   - Clear, measurable requirements
   - Includes edge conditions naturally
   - Specific outcomes defined

3. **Technical Context**
   - Required components
   - System constraints
   - Integration points
   - No implementation details

4. **Related Information**
   - Distinct tracking of Personas and User Stories
   - Clear dependencies and relationships

5. **Status Tracking**
   - Semantic versioning
   - Active/Deprecated status
   - Consistent datetime format
   - Change history

### Writing Guidelines
1. **Focus on Core Capabilities**
   - Each story represents a single, specific capability
   - Requirements should be cohesive and focused
   - Avoid scope creep

2. **Clear Requirements**
   - Make requirements specific and measurable
   - Include edge conditions within requirements
   - Focus on outcomes, not implementations

3. **Technical Context**
   - Include only what's needed for understanding
   - Focus on constraints and dependencies
   - Avoid implementation specifics

4. **Cross-References**
   - Use consistent persona references
   - Link related stories when necessary
   - Maintain single source of truth
