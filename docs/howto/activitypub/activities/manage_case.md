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

    The `RmReEngageCase` activity is used to re-engage a case that has been
    deferred. Deferring a case is modeled as an `as:Ignore`
    activity, since it is indicating that a participant has not entirely left
    the case, but has instead deferred their participation for a period of
    time. Re-engaging a case is modeled as an `as:Undo` activity, since it is
    undoing the `as:Ignore` activity that was used to defer the case.
    Alternatively, we could have just used the same `RmEngageCase` (`as:Join`) 
    activity. That might still be a better option, but we'll leave it as an
    implementation choice for now.

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
