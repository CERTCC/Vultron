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
    subgraph RM:VALIDATED 
        subgraph as:Accept
            RmValidateReport
        end
        subgraph as:Create
            CreateCase
        end
    end
    subgraph RM:INVALID
        subgraph as:Reject
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

!!! tip "Re-Engaging a Case"

    Re-engaging a deferred case uses the same `RmEngageCase` (`as:Join`)
    activity. Because the RM model permits reversible transitions between
    `ACCEPTED` and `DEFERRED`, re-engagement is simply an `accept` transition
    emitted from the `DEFERRED` state — there is no separate `RmReEngageCase`
    activity. Using `as:Undo` was considered but rejected: `Undo` implies
    retracting the *effects* of a prior action, whereas re-engagement is a
    forward state transition.

{% include-markdown "./_close_case.md" heading-offset=1 %}
{% include-markdown "./_close_report.md" heading-offset=1 %}

!!! tip "Close Case vs Close Report"

    Closing a report is only relevant when the report is not valid, because 
    valid reports should be converted to cases. Hence, we define the 
    `RmCloseReport` activity as a an option for when a report is invalidated
    before a case is created. Both `RmCloseReport` and `RmCloseCase` are
    defined as subclasses of `as:Leave` to indicate that they are both
    activities that indicate that the actor's participation in the case or
    report has ended.
