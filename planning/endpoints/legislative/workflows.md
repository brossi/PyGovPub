# Legislative Workflows

## Related Workflows
```yaml
dependencies:
  - workflow: "../authentication/workflows.md#api-key-validation-flow"
    relationship: "Required for Congress.gov API access"
  - workflow: "../documents/workflows.md#document-retrieval-flow"
    relationship: "Handles bill document retrieval"
  - workflow: "../updates/workflows.md#real-time-updates-flow"
    relationship: "Provides real-time legislative updates"

consumers:
  - workflow: "../documents/workflows.md#document-version-tracking-flow"
    usage: "Provides bill content and versions"
  - workflow: "../regulatory/workflows.md#federal-register-agency-rule-flow"
    usage: "Provides legislative context for rules"
  - workflow: "../updates/workflows.md#webhook-validation-flow"
    usage: "Subscribes to legislative updates"
```

// ... rest of legislative workflows ...
