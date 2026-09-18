# Managing Case Participants

{% include-markdown "../../../includes/not_normative.md" %}

Typically most cases involve multiple participants, having various roles
within the case. While the most common activities are inviting and adding
participants, this section also covers activities for removing participants.

```mermaid
flowchart TB
    subgraph as:Invite 
        RmInviteToCase
    end
    subgraph as:Accept
        RmAcceptInviteToCase
    end
    subgraph as:Reject
        RmRejectInviteToCase
    end
    subgraph as:Create
        CreateParticipant
        CreateParticipantStatus
    end
    subgraph as:Add
        AddParticipantToCase
        AddStatusToParticipant
    end
    subgraph as:Remove
        RemoveParticipantFromCase
    end
    start([Start])
    start --> RmInviteToCase
    RmInviteToCase --> a{Accept?}
    a -->|y| RmAcceptInviteToCase
    a -->|n| RmRejectInviteToCase
    RmAcceptInviteToCase --> CreateParticipant
    
    CreateParticipantStatus --> AddStatusToParticipant
    CreateParticipant --> AddParticipantToCase
    AddParticipantToCase --> s{Status?}
    s -->|y| CreateParticipantStatus
    s -->|n| r{Remove?}
    AddStatusToParticipant --> r
    r -->|y| RemoveParticipantFromCase
    r -->|n| s
```

!!! info "CASE_MANAGER routing (PCR-08-007, PCR-08-008)"

    The `Invite` in this flow is sent by the **CASE_MANAGER** (not the Case Owner
    directly). The Case Owner triggers the invite action, but the CASE_MANAGER MUST
    be the ActivityStreams `actor` on the outbound `Invite` activity. The invited
    actor MUST send their `Accept` or `Reject` reply to the **CASE_MANAGER**, not
    directly to the Case Owner. See [Inviting an Actor to a Case](invite_actor.md)
    for the full sequence diagram.

The flow above separates `as:Create` from `as:Add`. You can send fewer
activities by carrying an object inline in the `as:Add` that attaches it, but
keep the verbs distinct — a `Create` carrying a `target` matches no Vultron
pattern. See
[Activity Vocabulary Design](../../../topics/activity_vocabulary_design.md)
for why the steps are documented separately and what a peer's dispatch requires.

{% include-markdown "./_invite_to_case.md" heading-offset=1 %}
{% include-markdown "./_accept_invite_to_case.md" heading-offset=1 %}
{% include-markdown "./_reject_invite_to_case.md" heading-offset=1 %}
{% include-markdown "./_create_participant.md" heading-offset=1 %}
{% include-markdown "./_add_coordinator_participant_to_case.md" heading-offset=1 %}

## Create Participant Status

The vendor actor is creating a participant status representing the vendor's status in the context of a specific case.

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import create_participant_status, json2md

print(json2md(create_participant_status()))
```

## Add Status to Participant

The vendor is adding a status to their participant object in the context of the specific case.

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import add_status_to_participant, json2md

print(json2md(add_status_to_participant()))
```

## Remove Participant from Case

A coordinator is removing a vendor from a case.

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import remove_participant_from_case, json2md

print(json2md(remove_participant_from_case()))
```

## Demo

!!! example "Try it: `vultron-demo manage-participants`"

    Run this workflow end-to-end with the unified demo CLI:

    ```bash
    vultron-demo manage-participants
    ```

    Or with Docker Compose:

    ```bash
    DEMO=manage-participants docker compose -f docker/docker-compose.yml run --rm demo
    ```
