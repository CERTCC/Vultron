# Managing a Case

{% include-markdown "../../../includes/not_normative.md" %}

Case management activities reflect the
[Report Management](../../../topics/process_models/rm/index.md) process model.

```mermaid
flowchart TB
    subgraph RM:RECEIVED
        subgraph as:Offer
            RmSubmitReport
        end
    end
    subgraph RM:VALID
        subgraph as:Accept
            RmValidateReport
        end
        subgraph as:Create
            CreateCase
        end
    end
    subgraph RM:INVALID
        subgraph as:TentativeReject
            RmInvalidateReport
        end
    end
    subgraph RM:ACCEPTED
        subgraph as:Join
            RmEngageCase
        end
    end
    subgraph RM:DEFERRED
        subgraph as:Ignore
            RmDeferCase
        end
    end
    subgraph RM:CLOSED
        subgraph as:Leave
            RmCloseCase
        end
        subgraph as:Reject
            RmCloseReport
        end
    end

    d{Done?}
    c{Close?}
    p{Priority?}
    v{Valid?}
    start([Start])
    start --> RmSubmitReport
    RmSubmitReport --> v
    v -->|y| RmValidateReport
    v -->|n| RmInvalidateReport
    RmInvalidateReport --> c
    c -->|y| RmCloseReport
    RmValidateReport --> CreateCase
    CreateCase --> p
    p -->|act| RmEngageCase
    d -->|n| p
    p -->|defer| RmDeferCase
    RmEngageCase --> d
    RmDeferCase --> d
    c -->|n| v
    d -->|y| RmCloseCase
```

{% include-markdown "./_submit_report.md" heading-offset=1 %}
{% include-markdown "./_invalidate_report.md" heading-offset=1 %}

{% include-markdown "./_validate_report.md" heading-offset=1 %}
{% include-markdown "./_create_case.md" heading-offset=1 %}
{% include-markdown "./_defer_case.md" heading-offset=1 %}

{% include-markdown "./_engage_case.md" heading-offset=1 %}

To re-engage a deferred case, send the same `RmEngageCase` (`as:Join`) activity
used for the first engagement. There is no separate `RmReEngageCase`.

{% include-markdown "./_close_case.md" heading-offset=1 %}
{% include-markdown "./_close_report.md" heading-offset=1 %}

Use `RmCloseReport` — `Reject(Offer(VulnerabilityReport))` — when a report was
invalidated before a case was created. Use `RmCloseCase` —
`Leave(VulnerabilityCase)` — once a case exists. For why re-engagement is not an
`as:Undo`, and why the two closures use different verbs, see
[Activity Vocabulary Design](../../../topics/activity_vocabulary_design.md).

## Demo

!!! example "Try it: `vultron-demo manage-case`"

    Run this workflow end-to-end with the unified demo CLI:

    ```bash
    vultron-demo manage-case
    ```

    Or with Docker Compose:

    ```bash
    DEMO=manage-case docker compose -f docker/docker-compose.yml run --rm demo
    ```
