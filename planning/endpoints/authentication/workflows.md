# Authentication Workflows

## Related Workflows
```yaml
dependencies:
  - workflow: "../updates/workflows.md#webhook-validation-flow"
    relationship: "Provides authentication for webhook endpoints"
  - workflow: "../documents/workflows.md#document-authentication-flow"
    relationship: "Provides signature verification services"
  - workflow: "../legislative/workflows.md#bill-tracking-flow"
    relationship: "Handles API key validation for Congress.gov"
  - workflow: "../regulatory/workflows.md#federal-register-publication-flow"
    relationship: "Handles API key validation for GovInfo.gov"

consumers:
  - workflow: "../updates/workflows.md#webhook-validation-flow"
    usage: "Validates webhook signatures"
  - workflow: "../documents/workflows.md#document-retrieval-flow"
    usage: "Validates API access"
  - workflow: "../legislative/workflows.md"
    usage: "Provides rate limiting and key validation"
  - workflow: "../regulatory/workflows.md"
    usage: "Provides rate limiting and key validation"
```

// ... rest of authentication workflows ...
