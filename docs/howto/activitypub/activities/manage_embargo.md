# Managing an Embargo

{% include-markdown "../../../includes/not_normative.md" %}

This diagram is similar to the one shown in [Establishing an Embargo](./establish_embargo.md), but it also shows the
decisions and activities that are used to manage an embargo once it has been established.
Once established, an embargo can be modified via a propose/accept/reject cycle.
It can also be terminated or removed from a case.

<!-- for vertical spacing -->
<br/>
<br/>

{% include-markdown "./_em_blurb.md" %}

```mermaid
flowchart TB
    subgraph as:Invite
        EmProposeEmbargo
    end
    subgraph as:Accept
        EmAcceptEmbargo
    end
    subgraph as:Reject
        EmRejectEmbargo
    end
    subgraph as:Add
        ActivateEmbargo
        AddEmbargoToCase
    end
    subgraph as:Remove
        RemoveEmbargoFromCase
    end
    subgraph as:Announce
        AnnounceEmbargo
    end 
    start([Start])
    start --> f{Ask first?}
    f -->|n| AddEmbargoToCase
    v -->|y| t{Terminate?}
    p{Propose?} -->|y| EmProposeEmbargo
    EmAcceptEmbargo --> ActivateEmbargo
    EmProposeEmbargo --> a{Accept?}
    EmRejectEmbargo --> v
    f -->|y| v{Active?}
    a -->|y| EmAcceptEmbargo
    a -->|n| EmRejectEmbargo
    t -->|n| p
    t{Terminate?} -->|y| RemoveEmbargoFromCase
    ActivateEmbargo --> t
    AddEmbargoToCase --> t
    v -->|n| p
    p -->|n| v
    RemoveEmbargoFromCase --> p
```

{% include-markdown "./_propose_embargo.md"  heading-offset=1 %}
{% include-markdown "./_accept_embargo.md" heading-offset=1 %}
{% include-markdown "./_reject_embargo.md" heading-offset=1 %}
{% include-markdown "./_activate_embargo.md" heading-offset=1 %}
{% include-markdown "./_add_embargo_to_case.md" heading-offset=1 %}
{% include-markdown "./_announce_embargo.md" heading-offset=1 %}

{% include-markdown "./_remove_embargo_from_case.md" heading-offset=1 %}

## Demo

!!! example "Try it: `vultron-demo manage-embargo`"

    Run this workflow end-to-end with the unified demo CLI:

    ```bash
    vultron-demo manage-embargo
    ```

    Or with Docker Compose:

    ```bash
    DEMO=manage-embargo docker compose -f docker/docker-compose.yml run --rm demo
    ```
