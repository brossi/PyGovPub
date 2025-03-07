# Legislative Workflows

## Bill Management Flows

### Bill Tracking Flow

```mermaid
sequenceDiagram
    participant Client as Client Application
    participant Router as Smart Router
    participant Congress as Congress.gov
    participant GovInfo as GovInfo.gov
    participant DB as PostgreSQL
    participant Notify as Notification Service

    Client->>Router: track_bill(bill_id)
    Router->>DB: get_tracking_status()

    par Source Checks
        Router->>Congress: get_bill_status()
        Congress-->>Router: congress_status
    and
        Router->>GovInfo: get_bill_package()
        GovInfo-->>Router: govinfo_status
    end

    Router->>Router: merge_status_data()
    Router->>DB: store_bill_status()

    alt Status Changed
        Router->>Notify: notify_status_change()
        Router->>DB: log_status_update()
    end

    Router-->>Client: return_bill_status()
```

### Bill Version Management Flow

```mermaid
sequenceDiagram
    participant Client as Client Application
    participant Version as Version Manager
    participant Congress as Congress.gov
    participant GovInfo as GovInfo.gov
    participant DB as PostgreSQL

    Client->>Version: get_bill_versions(bill_id)

    par Fetch Versions
        Version->>Congress: get_bill_versions()
        Congress-->>Version: congress_versions
    and
        Version->>GovInfo: get_package_versions()
        GovInfo-->>Version: govinfo_versions
    end

    Version->>Version: merge_versions()
    Version->>DB: store_versions()

    alt New Version Available
        Version->>DB: update_version_history()
        Version-->>Client: return_updated_versions()
    else No Changes
        Version-->>Client: return_current_versions()
    end
```

## Committee Management Flows

### Committee Activity Flow

```mermaid
sequenceDiagram
    participant Client as Client Application
    participant Manager as Committee Manager
    participant Congress as Congress.gov
    participant DB as PostgreSQL
    participant Notify as Notification Service

    Client->>Manager: get_committee_activities(committee_id)
    Manager->>DB: get_cached_activities()

    alt Cache Miss
        Manager->>Congress: get_committee_schedule()
        Congress-->>Manager: schedule_data
        Manager->>Congress: get_recent_activities()
        Congress-->>Manager: activity_data

        Manager->>DB: store_activities()
        Manager->>Notify: schedule_notifications()
    end

    Manager-->>Client: return_activities()
```

### Committee Report Processing Flow

```mermaid
sequenceDiagram
    participant Scheduler as Report Scheduler
    participant Manager as Report Manager
    participant Congress as Congress.gov
    participant GovInfo as GovInfo.gov
    participant DB as PostgreSQL
    participant Vector as Vector Store

    Scheduler->>Manager: process_committee_reports()

    par Fetch Reports
        Manager->>Congress: get_new_reports()
        Congress-->>Manager: congress_reports
    and
        Manager->>GovInfo: get_report_packages()
        GovInfo-->>Manager: govinfo_reports
    end

    loop For Each Report
        Manager->>DB: check_report_status()

        alt New Report
            Manager->>DB: store_report_metadata()
            Manager->>Vector: index_report_content()
        else Updated Report
            Manager->>DB: update_report_status()
            Manager->>Vector: update_report_index()
        end
    end

    Manager->>DB: update_processing_status()
```

## Member Management Flows

### Member Activity Tracking Flow

```mermaid
sequenceDiagram
    participant Client as Client Application
    participant Manager as Member Manager
    participant Congress as Congress.gov
    participant DB as PostgreSQL
    participant Vector as Vector Store

    Client->>Manager: track_member_activity(member_id)

    par Activity Checks
        Manager->>Congress: get_sponsored_bills()
        Congress-->>Manager: bill_data
    and
        Manager->>Congress: get_voting_record()
        Congress-->>Manager: vote_data
    and
        Manager->>Congress: get_committee_work()
        Congress-->>Manager: committee_data
    end

    Manager->>DB: store_member_activities()
    Manager->>Vector: index_activities()
    Manager-->>Client: return_activity_summary()
```

### Member Voting Record Flow

```mermaid
sequenceDiagram
    participant Client as Client Application
    participant Manager as Vote Manager
    participant Congress as Congress.gov
    participant DB as PostgreSQL
    participant Analytics as Analytics Engine

    Client->>Manager: get_member_votes(member_id, session)
    Manager->>DB: check_vote_cache()

    alt Cache Miss
        Manager->>Congress: get_vote_history()
        Congress-->>Manager: vote_data
        Manager->>DB: store_vote_data()
    end

    Manager->>Analytics: analyze_voting_pattern()
    Analytics-->>Manager: voting_analysis

    Manager->>DB: store_analysis()
    Manager-->>Client: return_vote_record()
```

## Legislative Process Flows

### Bill Introduction Flow

```mermaid
sequenceDiagram
    participant Source as Data Source
    participant Router as Smart Router
    participant DB as PostgreSQL
    participant Vector as Vector Store
    participant Notify as Notification Service

    Source->>Router: new_bill_introduced()
    Router->>DB: check_bill_exists()

    alt New Bill
        Router->>DB: store_bill_metadata()
        Router->>Vector: index_bill_content()

        par Notifications
            Router->>Notify: notify_subscribers()
            Router->>DB: log_introduction()
        end
    else Existing Bill
        Router->>DB: update_bill_status()
    end
```

### Amendment Processing Flow

```mermaid
sequenceDiagram
    participant Source as Data Source
    participant Manager as Amendment Manager
    participant Congress as Congress.gov
    participant GovInfo as GovInfo.gov
    participant DB as PostgreSQL
    participant Vector as Vector Store

    Source->>Manager: process_amendment(amendment_id)

    par Fetch Amendment Data
        Manager->>Congress: get_amendment_details()
        Congress-->>Manager: amendment_data
    and
        Manager->>GovInfo: get_amendment_text()
        GovInfo-->>Manager: amendment_text
    end

    Manager->>DB: store_amendment()
    Manager->>Vector: index_amendment()

    alt Related Bill Exists
        Manager->>DB: update_bill_amendments()
        Manager->>Vector: update_bill_index()
    end
```

### Floor Action Tracking Flow

```mermaid
sequenceDiagram
    participant Monitor as Floor Monitor
    participant Manager as Action Manager
    participant Congress as Congress.gov
    participant DB as PostgreSQL
    participant Notify as Notification Service

    Monitor->>Manager: track_floor_actions()

    loop Regular Interval
        Manager->>Congress: get_floor_updates()
        Congress-->>Manager: floor_data

        alt New Actions
            Manager->>DB: store_floor_actions()
            Manager->>Notify: notify_subscribers()
        end
    end
```

### Voting Record Processing Flow

```mermaid
sequenceDiagram
    participant Source as Data Source
    participant Manager as Vote Manager
    participant Congress as Congress.gov
    participant DB as PostgreSQL
    participant Analytics as Analytics Engine

    Source->>Manager: process_vote_record(vote_id)

    Manager->>Congress: get_vote_details()
    Congress-->>Manager: vote_data

    par Processing Tasks
        Manager->>DB: store_vote_record()
        Manager->>Analytics: analyze_vote_breakdown()
    end

    Analytics-->>Manager: vote_analysis
    Manager->>DB: store_analysis()

    alt Related Bill Exists
        Manager->>DB: update_bill_votes()
    end
```

## Legislative Reference Flows

### Cross-Reference Resolution Flow

```mermaid
sequenceDiagram
    participant Client as Client Application
    participant Resolver as Reference Resolver
    participant DB as PostgreSQL
    participant Congress as Congress.gov
    participant GovInfo as GovInfo.gov

    Client->>Resolver: resolve_references(doc_id)

    Resolver->>DB: get_document()
    DB-->>Resolver: doc_data

    loop For Each Reference
        alt Congress.gov Reference
            Resolver->>Congress: get_reference_target()
            Congress-->>Resolver: reference_data
        else GovInfo.gov Reference
            Resolver->>GovInfo: get_reference_content()
            GovInfo-->>Resolver: reference_content
        end

        Resolver->>DB: store_resolved_reference()
    end

    Resolver-->>Client: return_resolved_references()
```

### Legislative Hierarchy Flow

```mermaid
sequenceDiagram
    participant Client as Client Application
    participant Manager as Hierarchy Manager
    participant DB as PostgreSQL
    participant Congress as Congress.gov
    participant GovInfo as GovInfo.gov

    Client->>Manager: get_legislative_hierarchy(item_id)

    par Hierarchy Checks
        Manager->>Congress: get_legislative_context()
        Congress-->>Manager: context_data
    and
        Manager->>GovInfo: get_package_hierarchy()
        GovInfo-->>Manager: hierarchy_data
    end

    Manager->>Manager: merge_hierarchies()
    Manager->>DB: store_hierarchy()
    Manager-->>Client: return_hierarchy()
```
