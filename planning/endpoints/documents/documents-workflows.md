# Document Workflows

## Document Retrieval Flow

```mermaid
sequenceDiagram
    participant Client as Client Application
    participant Router as Smart Router
    participant Cache as Cache Layer
    participant Congress as Congress.gov
    participant GovInfo as GovInfo.gov
    participant DB as PostgreSQL

    Client->>Router: get_document(id)
    Router->>Cache: check_cache(id)

    alt Cache Hit
        Cache-->>Router: cached_document
        Router-->>Client: return_document
    else Cache Miss
        par Source Check
            Router->>Congress: check_availability()
            Congress-->>Router: congress_status
        and
            Router->>GovInfo: check_availability()
            GovInfo-->>Router: govinfo_status
        end

        alt Available in Congress.gov
            Router->>Congress: fetch_document()
            Congress-->>Router: document_data
        else Available in GovInfo.gov
            Router->>GovInfo: fetch_document()
            GovInfo-->>Router: document_data
        else Not Found
            Router-->>Client: document_not_found
        end

        Router->>Cache: store_document()
        Router->>DB: log_retrieval()
        Router-->>Client: return_document
    end
```

## Document Authentication Flow

```mermaid
sequenceDiagram
    participant Client as Client Application
    participant Auth as Auth Manager
    participant GovInfo as GovInfo.gov
    participant DB as PostgreSQL
    participant Cache as Cache Layer

    Client->>Auth: verify_document(id)
    Auth->>Cache: check_verification_cache(id)

    alt Cache Hit
        Cache-->>Auth: cached_verification
        Auth-->>Client: return_verification_status
    else Cache Miss
        Auth->>GovInfo: get_signature()
        GovInfo-->>Auth: document_signature

        Auth->>Auth: verify_signature()

        alt Valid Signature
            Auth->>DB: store_verification()
            Auth->>Cache: cache_verification()
            Auth-->>Client: verification_success()
        else Invalid Signature
            Auth->>DB: log_verification_failure()
            Auth-->>Client: verification_failed()
        end
    end
```

## Document Version Tracking Flow

```mermaid
sequenceDiagram
    participant Client as Client Application
    participant Version as Version Manager
    participant DB as PostgreSQL
    participant Sources as Data Sources
    participant Notify as Notification Service

    Client->>Version: track_document(id)
    Version->>DB: get_version_history()

    par Version Check
        Version->>Sources: get_latest_version()
        Sources-->>Version: source_version
    and
        Version->>DB: get_stored_version()
        DB-->>Version: stored_version
    end

    alt New Version Available
        Version->>DB: store_new_version()
        Version->>Notify: notify_version_update()
        Version-->>Client: version_updated()
    else Current Version
        Version-->>Client: version_current()
    end
```

## Document Relationship Management Flow

```mermaid
sequenceDiagram
    participant Client as Client Application
    participant Manager as Relationship Manager
    participant DB as PostgreSQL
    participant Congress as Congress.gov
    participant GovInfo as GovInfo.gov

    Client->>Manager: get_document_relationships(id)

    par Fetch Relationships
        Manager->>Congress: get_related_documents()
        Congress-->>Manager: congress_relationships
    and
        Manager->>GovInfo: get_package_relationships()
        GovInfo-->>Manager: govinfo_relationships
    end

    Manager->>Manager: merge_relationships()
    Manager->>DB: store_relationships()

    alt Has Related Documents
        Manager->>DB: update_relationship_graph()
        Manager-->>Client: return_relationships()
    else No Relationships
        Manager-->>Client: no_relationships_found()
    end
```

## Document Content Synchronization Flow

```mermaid
sequenceDiagram
    participant Sync as Sync Manager
    participant Sources as Data Sources
    participant DB as PostgreSQL
    participant Cache as Cache Layer

    Sync->>DB: get_sync_status()

    alt Needs Sync
        Sync->>Sources: get_document_updates()
        Sources-->>Sync: document_changes

        par Process Updates
            Sync->>DB: update_document_content()
            Sync->>Cache: invalidate_cache()
        end

        Sync->>DB: update_sync_timestamp()
    else Up to Date
        Sync->>DB: log_sync_check()
    end
```
