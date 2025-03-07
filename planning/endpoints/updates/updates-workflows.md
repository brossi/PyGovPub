# Update Workflows

## Real-time Updates Flow

```mermaid
sequenceDiagram
    participant Scheduler as Sync Scheduler
    participant Manager as Sync Manager
    participant Monitor as Rate Monitor
    participant Sources as Data Sources
    participant DB as PostgreSQL
    participant Vector as ChromaDB
    participant Auth as Auth Manager

    Scheduler->>Manager: schedule_sync()
    activate Manager

    Manager->>DB: get_last_sync_status()
    DB-->>Manager: sync_info

    alt Initial Sync
        Manager->>Monitor: check_bulk_limits()
        Monitor-->>Manager: bulk_allowed

        Manager->>Sources: get_bulk_data()
        Sources-->>Manager: bulk_content
    else Delta Sync
        Manager->>Monitor: check_rate_limits()
        Monitor-->>Manager: rate_status

        Manager->>Sources: get_updates(last_sync)
        Sources-->>Manager: delta_updates
    end

    par Data Processing
        Manager->>DB: store_structured_data()
        Manager->>Vector: update_embeddings()
    and Status Update
        Manager->>DB: update_sync_status()
        Manager->>DB: log_sync_metrics()
    end

    Manager-->>Scheduler: sync_complete
    deactivate Manager
```

## Webhook Validation Flow

```mermaid
sequenceDiagram
    participant Client as Client App
    participant Hook as Webhook Endpoint
    participant Val as Validator
    participant Queue as Event Queue
    participant DB as PostgreSQL

    Client->>Hook: incoming_webhook()
    Hook->>Val: validate_signature()

    alt Valid Signature
        Val->>Val: decode_payload()
        Val->>DB: verify_subscription()

        alt Valid Subscription
            Val->>Queue: enqueue_event()
            Queue->>DB: store_event()
            Hook-->>Client: 200 OK
        else Invalid Subscription
            Val->>DB: log_invalid_subscription()
            Hook-->>Client: 403 Forbidden
        end
    else Invalid Signature
        Val->>DB: log_invalid_signature()
        Hook-->>Client: 401 Unauthorized
    end
```

## Cache Invalidation Flow

```mermaid
sequenceDiagram
    participant Update as Update Event
    participant Cache as Cache Manager
    participant DB as PostgreSQL
    participant Vector as ChromaDB

    Update->>Cache: content_changed()

    par Invalidation Tasks
        Cache->>DB: invalidate_related_data()
        Cache->>Vector: mark_embeddings_stale()
    end

    Cache->>DB: log_invalidation()
```

## Rate Limit Recovery Flow

```mermaid
sequenceDiagram
    participant Service as Service Layer
    participant Monitor as Rate Monitor
    participant Queue as Request Queue
    participant DB as PostgreSQL

    Service->>Monitor: check_rate_limit()

    alt Limit Exceeded
        Monitor->>Queue: enqueue_request()
        Monitor->>DB: log_rate_limit()

        loop Until Rate Reset
            Queue->>Monitor: check_limits()
            alt Limits Reset
                Monitor->>Queue: process_backlog()
                Queue->>Service: retry_requests()
            else Still Limited
                Monitor->>Queue: maintain_backlog()
            end
        end
    else Limit OK
        Monitor-->>Service: proceed()
    end
```

## Version Conflict Resolution Flow

```mermaid
sequenceDiagram
    participant Sync as Sync Manager
    participant Source1 as Congress.gov
    participant Source2 as GovInfo.gov
    participant DB as PostgreSQL
    participant Queue as Event Queue

    Sync->>DB: detect_version_conflict()

    par Fetch Latest Versions
        Sync->>Source1: get_latest_version()
        Source1-->>Sync: congress_version
    and
        Sync->>Source2: get_latest_version()
        Source2-->>Sync: govinfo_version
    end

    alt Resolvable Conflict
        Sync->>DB: store_merged_version()
        Sync->>Queue: notify_resolution()
    else Manual Resolution Required
        Sync->>DB: mark_conflict_unresolved()
        Sync->>Queue: enqueue_manual_review()
    end
```

## Event Processing Flow

```mermaid
sequenceDiagram
    participant Queue as Event Queue
    participant Processor as Event Processor
    participant DB as PostgreSQL
    participant Notifier as Notification Service

    Queue->>Processor: process_event()

    alt Valid Event
        Processor->>DB: update_event_state()

        par Processing Tasks
            Processor->>DB: store_event_data()
            Processor->>Notifier: prepare_notifications()
        end

        alt Has Subscribers
            Notifier->>DB: get_subscribers()
            Notifier->>Queue: enqueue_notifications()
        end
    else Invalid Event
        Processor->>DB: log_invalid_event()
        Processor->>Queue: handle_failure()
    end
```

## Notification Delivery Flow

```mermaid
sequenceDiagram
    participant Queue as Event Queue
    participant Notifier as Notification Service
    participant DB as PostgreSQL
    participant Client as Subscriber

    Queue->>Notifier: deliver_notification()
    Notifier->>DB: get_delivery_preferences()

    alt Webhook Delivery
        Notifier->>Client: send_webhook()
        alt Delivery Success
            Client-->>Notifier: 200_OK
            Notifier->>DB: mark_delivered()
        else Delivery Failed
            Client-->>Notifier: error
            Notifier->>Queue: retry_with_backoff()
            Notifier->>DB: log_failure()
        end
    else Stream Delivery
        Notifier->>Client: stream_update()
        alt Stream Active
            Client-->>Notifier: ack
            Notifier->>DB: mark_streamed()
        else Stream Failed
            Notifier->>DB: mark_stream_failed()
            Notifier->>Queue: requeue_for_webhook()
        end
    end
```
