# Establishing an Embargo

{% include-markdown "../../../includes/not_normative.md" %}

The process to establish an embargo for a case can start in
one of two ways:

- Any participant can propose an embargo for a case. This is the most common
  way to establish an embargo.
- The case owner can add an embargo to a case without proposing it first. In some circumstances, this might be an
  appropriate way to establish an embargo.

<!-- for vertical spacing -->
<br/>

{% include-markdown "./_em_blurb.md" %}

!!! question "Why would you add an embargo without asking first?"

    There are a few reasons why you might want to add an embargo to a case without
    asking first. For example, when the finder is also the case owner and hasn't invited any other participants to join
    the case yet, the finder can just add an embargo. Then when the finder invites others to join the case, the invited
    participants can
    decide whether to accept the embargo or not. This could be an appropriate way to address the concept of
    [Default Embargoes](../../../topics/process_models/em/defaults.md).

```mermaid
flowchart TB
    subgraph as:Invite
        EmProposeEmbargo
    end
    subgraph as:Question
        ChoosePreferredEmbargo
    end
    subgraph as:Accept
        EmAcceptEmbargo
    end
    subgraph as:Reject
        EmRejectEmbargo
    end
    subgraph as:Announce
        AnnounceEmbargo
    end
    subgraph as:Add
        ActivateEmbargo
        AddEmbargoToCase
    end
    start([Start]) --> f{Ask first?}
    f -->|n| AddEmbargoToCase
    f -->|y| EmProposeEmbargo
    EmProposeEmbargo --> a{Accept?}
    a -->|y| EmAcceptEmbargo
    a -->|n| EmRejectEmbargo
    EmProposeEmbargo --> ChoosePreferredEmbargo
    ChoosePreferredEmbargo --> a
    EmAcceptEmbargo --> ActivateEmbargo
    AddEmbargoToCase --> AnnounceEmbargo
    ActivateEmbargo --> AnnounceEmbargo
```

{% include-markdown "./_propose_embargo.md" heading-offset=1 %}
{% include-markdown "./_choose_preferred_embargo.md" heading-offset=1 %}
{% include-markdown "./_accept_embargo.md" heading-offset=1 %}
{% include-markdown "./_reject_embargo.md" heading-offset=1 %}
{% include-markdown "./_add_embargo_to_case.md" heading-offset=1 %}
{% include-markdown "./_activate_embargo.md" heading-offset=1 %}
{% include-markdown "./_announce_embargo.md" heading-offset=1 %}
