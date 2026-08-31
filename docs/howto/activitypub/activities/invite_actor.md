# Inviting an Actor to a Case

{% include-markdown "../../../includes/not_normative.md" %}

Inviting an actor to a case is a way to add them as a participant in the case.
The invitation is sent to the actor as an `as:Invite` activity.
Depending on the actor's response, they may become a participant in the case.

<!-- for vertical spacing -->
<br/>
<br/>
<br/>

```mermaid
---
title: Invite Actor to Case
---
sequenceDiagram
    actor O as Case Owner
    participant CA as Case Actor
    actor A as Actor
    activate O
    O ->> CA: [trigger invite]
    activate CA
    CA ->>+ A: Invite(actor=CaseActor, object=Actor, target=Case, attributedTo=CaseOwner)
    note over A: Consider invitation
    alt Accept Invitation
        A -->> CA: Accept(object=Invite)
        CA ->> CA: Create(object=CaseParticipant(actor=Actor), target=Case)
        note over CA: Actor becomes participant in case
    else Reject Invitation
        A -->> CA: Reject(object=Invite)
        note over CA: Actor is not participant in case
    end
    deactivate A
    deactivate CA
    deactivate O
```

!!! info "CaseActor routing (PCR-08-007, PCR-08-008)"

    The `Invite` activity is sent by the **Case Actor**, not the Case Owner.
    The Case Owner triggers the invite, but the Case Actor MUST be the
    ActivityStreams `actor` on the outbound `Invite`. The `attributedTo` field
    on the activity MAY carry the Case Owner's ID to record who initiated it.

    The invitee MUST address their `Accept` or `Reject` reply to the **Case Actor**,
    not directly back to the Case Owner. The Case Actor is the authoritative
    recipient of all case-management handshake messages after case creation.

!!! question "Invite vs Add?"

    When a case is first created, the Case Owner and any known participants (e.g., the Reporter)
    should be automatically added to the case. It's not even necessary for these to be emitted as
    separate `as:Add` activities. The `as:Create` activity for the case can include the Case Owner
    and any known participants as `CaseParticipant` objects.
    See [Initializing a Case](initialize_case.md) for more.

    However, over the lifespan of a case, there may be other actors that were
    not already involved at the time the case was created, but who should be invited to participate
    in the case. This is where the `as:Invite` activity comes in.

!!! tip "Avoid bogging down in details"

    Adding a participant to a case involves creating the participant object and a participant status object.
    As we discuss elsewhere, it's probably overkill to emit separate `as:Create` and `as:Add` events for each
    of these events.

    ```mermaid
    flowchart LR
    
    a[create participant] --> b[create participant status]
    b --> c[add participant status to participant]
    c --> d[add participant to case]
    ```
   
    Instead, we could emit a single `as:Create` event for the participant, already containing a status object, and
    have the `target` of the `as:Create` event be the case object.

    ```mermaid
    flowchart LR
    a[create particpant with status] -->|target| b[case]
    ```

{% include-markdown "./_invite_to_case.md" heading-offset=1 %}
{% include-markdown "./_accept_invite_to_case.md" heading-offset=1 %}
{% include-markdown "./_reject_invite_to_case.md" heading-offset=1 %}
{% include-markdown "./_add_coordinator_participant_to_case.md" heading-offset=1 %}

## Demo

!!! example "Try it: `vultron-demo invite-actor`"

    Run this workflow end-to-end with the unified demo CLI:

    ```bash
    vultron-demo invite-actor
    ```

    Or with Docker Compose:

    ```bash
    DEMO=invite-actor docker compose -f docker/docker-compose.yml run --rm demo
    ```
