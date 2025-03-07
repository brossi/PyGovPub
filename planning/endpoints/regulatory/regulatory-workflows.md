# Regulatory Workflows

## Federal Register Management

### Federal Register Publication Flow

```mermaid
sequenceDiagram
    participant Source as GovInfo.gov
    participant Manager as FR Manager
    participant DB as PostgreSQL
    participant Notify as Notification Service

    Source->>Manager: new_fr_publication()
    Manager->>DB: check_publication_exists()

    alt New Publication
        Manager->>DB: store_publication_metadata()

        par Processing Tasks
            Manager->>DB: extract_agency_references()
            Manager->>DB: extract_cfr_references()
        end

        Manager->>Notify: notify_subscribers()
    else Update Existing
        Manager->>DB: update_publication_metadata()
    end
```

### Federal Register Agency Rule Flow

```mermaid
sequenceDiagram
    participant Source as GovInfo.gov
    participant Manager as Rule Manager
    participant DB as PostgreSQL
    participant Vector as Vector Store
    participant CFR as CFR Manager

    Source->>Manager: process_agency_rule()

    par Fetch Rule Data
        Manager->>Source: get_rule_details()
        Source-->>Manager: rule_data
    and
        Manager->>Source: get_rule_history()
        Source-->>Manager: rule_history
    end

    Manager->>DB: store_rule_data()
    Manager->>Vector: index_rule_content()

    alt CFR Impact
        Manager->>CFR: analyze_cfr_changes()
        CFR->>DB: store_cfr_amendments()
        CFR->>Vector: update_cfr_index()
    end
```

## CFR Management

### CFR Update Flow

```mermaid
sequenceDiagram
    participant Source as GovInfo.gov
    participant Manager as CFR Manager
    participant DB as PostgreSQL
    participant Vector as Vector Store
    participant History as Version History

    Source->>Manager: cfr_update_available()
    Manager->>DB: get_current_version()

    par Update Processing
        Manager->>Source: get_cfr_changes()
        Source-->>Manager: change_data
    and
        Manager->>History: create_version_point()
    end

    Manager->>DB: apply_cfr_changes()
    Manager->>Vector: update_cfr_index()
    Manager->>History: finalize_version()
```

### CFR Section Tracking Flow

```mermaid
sequenceDiagram
    participant Client as Client Application
    participant Manager as Section Manager
    participant DB as PostgreSQL
    participant Source as GovInfo.gov
    participant History as Version History

    Client->>Manager: track_cfr_section(section_id)
    Manager->>DB: get_section_history()

    par Version Checks
        Manager->>Source: get_current_version()
        Source-->>Manager: current_version
    and
        Manager->>History: get_version_timeline()
        History-->>Manager: timeline_data
    end

    alt Version Changed
        Manager->>DB: update_section_version()
        Manager->>Client: notify_section_update()
    else No Change
        Manager->>Client: return_current_status()
    end
```

## Agency Management

### Agency Activity Tracking Flow

```mermaid
sequenceDiagram
    participant Monitor as Agency Monitor
    participant Manager as Agency Manager
    participant DB as PostgreSQL
    participant FR as FR Manager
    participant Vector as Vector Store

    Monitor->>Manager: track_agency_activity()

    par Activity Sources
        Manager->>FR: get_agency_publications()
        FR-->>Manager: fr_data
    end

    Manager->>DB: store_agency_activities()
    Manager->>Vector: index_agency_content()

    alt New Regulatory Actions
        Manager->>DB: update_agency_metrics()
        Manager->>Vector: update_activity_index()
    end
```

### Agency Relationship Flow

```mermaid
sequenceDiagram
    participant Client as Client Application
    participant Manager as Relationship Manager
    participant DB as PostgreSQL
    participant FR as FR Manager
    participant CFR as CFR Manager

    Client->>Manager: get_agency_relationships(agency_id)

    par Relationship Sources
        Manager->>FR: get_fr_relationships()
        FR-->>Manager: fr_relations
    and
        Manager->>CFR: get_cfr_relationships()
        CFR-->>Manager: cfr_relations
    end

    Manager->>Manager: merge_relationships()
    Manager->>DB: store_relationships()
    Manager-->>Client: return_relationships()
```

## Bulk Processing

### Bulk Data Synchronization Flow

```mermaid
sequenceDiagram
    participant Scheduler as Sync Scheduler
    participant Manager as Bulk Manager
    participant Source as GovInfo.gov
    participant DB as PostgreSQL
    participant Vector as Vector Store

    Scheduler->>Manager: sync_regulatory_data()
    Manager->>DB: get_sync_status()

    alt Initial Sync
        Manager->>Source: get_bulk_package()
        Source-->>Manager: bulk_data

        Manager->>Manager: validate_package()
        Manager->>DB: store_bulk_data()
        Manager->>Vector: index_bulk_content()
    else Delta Sync
        Manager->>Source: get_delta_updates()
        Source-->>Manager: delta_data

        Manager->>DB: apply_updates()
        Manager->>Vector: update_indices()
    end

    Manager->>DB: update_sync_timestamp()
```

### Regulatory Reference Resolution Flow

```mermaid
sequenceDiagram
    participant Client as Client Application
    participant Resolver as Reference Resolver
    participant DB as PostgreSQL
    participant FR as FR Manager
    participant CFR as CFR Manager

    Client->>Resolver: resolve_regulatory_refs(doc_id)
    Resolver->>DB: get_document()

    par Reference Types
        Resolver->>FR: resolve_fr_citations()
        FR-->>Resolver: fr_refs
    and
        Resolver->>CFR: resolve_cfr_citations()
        CFR-->>Resolver: cfr_refs
    end

    Resolver->>DB: store_resolved_refs()
    Resolver-->>Client: return_resolved_refs()
```
