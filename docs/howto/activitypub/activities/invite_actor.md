---
stakeholder_type: [platform-developer]
level: 300
---

# How to Invite an Actor to a Case

Use this guide to bring an actor into a case it was not present for.
An invitation asks rather than asserts, so the actor joins only if it accepts.
You finish with the actor either seated as a participant or recorded as having declined.

---

## Prerequisites

{% include-markdown "./_demo_prerequisites.md" %}

- An existing case, and the Case Owner role on it.
- The actor's Uniform Resource Identifier (URI).
- The CASE_MANAGER's actor URI.
  It sends the invitation and receives the reply.

---

## The exchange

The sequence diagram below shows both outcomes.
The Case Owner asks the CASE_MANAGER for the invitation with one `Offer`.
Every later message is between the CASE_MANAGER and the invited actor.

```mermaid
---
title: Invite Actor to Case
---
sequenceDiagram
    actor O as Case Owner
    participant CA as CASE_MANAGER
    actor A as Actor
    activate O
    O ->> CA: Offer(actor=CaseOwner, object=Actor, target=Case, suggestedRoles)
    activate CA
    CA ->>+ A: Invite(actor=CASE_MANAGER, object=Actor, target=CaseStub, attributedTo=CaseOwner)
    note over CA: Records inert CaseParticipant (RM Received)
    note over A: Consider invitation
    alt Accept Invitation
        A -->> CA: Accept(object=Invite)
        note over CA: Participant becomes active (RM stays Received)<br/>then sends case, ledger replay and full-case Invite
    else Reject Invitation
        A -->> CA: Reject(object=Invite)
        note over CA: Closes inert record (RM Closed); kept as history
    end
    deactivate A
    deactivate CA
    deactivate O
```

---

## Send the invitation

1. Trigger the invitation as Case Owner.
   Your container sends your own `Offer(Actor)` to the CASE_MANAGER, with the invited actor as its `object`, the case as its `target`, and the roles you offer in `suggestedRoles` (CM-17-007).
   With no roles given, the CASE_MANAGER assigns a non-empty default role list (CM-16-003).
   A stub Invite always names at least one role, and the CASE_MANAGER refuses to send one with none (CM-11-019).
2. The CASE_MANAGER commits and sends `Invite(Actor)` to the actor's inbox, with a case stub as its `target` rather than the case itself (CM-11-013, CM-17-001), with itself as the ActivityStreams `actor` and your identity in `attributedTo` (PCR-08-007, PCR-08-008).
   The trigger's `202` response means only that your `Offer` was queued, so watch for the `Invite` on the CASE_MANAGER's ledger, not in the response.
3. Set the reply deadline on the activity's `end_time`.
   When it is present that value settles precedence over the invitee's local policy window; when it is absent the policy window applies instead (CM-28-002, ADR-0065).
   Either way the effective deadline is clamped down to the embargo's own `end_time`, so an `end_time` that outlives the embargo does not buy the invitee extra time (EP-07-006).

!!! warning "The CASE_MANAGER is the sender, not the Case Owner"

    Putting the Case Owner in the `actor` field makes the invitation unrecognizable to a conformant peer, which expects case-management handshakes to come from the CASE_MANAGER.
    Record who asked for the invitation in `attributedTo` instead.

---

## Answer an invitation

Send your reply to the CASE_MANAGER, never to the Case Owner.

- If you are joining the case, send `Accept(Invite(Actor))` with the `Invite` activity as its `object`.
- If you are not joining, send `Reject(Invite(Actor))` with the `Invite` as its `object`.

On acceptance, the CASE_MANAGER commits the reply to the ledger, seats you at Report Management (RM) state `RM.RECEIVED`, signs your [embargo consent](../../../topics/behavior_logic/use-cases/embargo-lifecycle.md#which-messages-move-consent) if an embargo is active, sends `Announce(VulnerabilityCase)` to seed your replica, and backfills the earlier ledger entries (CM-17-004).

Expect `RM.RECEIVED`, not `RM.ACCEPTED`.
Accepting an invitation says you are willing to join the case; it does not say you have validated the report, which you have not yet seen in full (CM-11-001).
After the case and the ledger replay reach you, the CASE_MANAGER sends a second Invite, the full-case Invite, and you judge the case by answering it — see [How to Manage a Case Roster](manage_participants.md#judge-the-case-after-joining).
Do not answer the original report Offer: you were never offered that report (CM-11-020).
Rule on the case afterwards — see [How to Advance a Case Through Report Management](manage_case.md).

A reply that arrives after the Invite's deadline is still processed.
The one exception is an `Accept` of a stub Invite that a newer one replaced, which the CASE_MANAGER refuses and answers by naming the replacement; a `Reject` of it is honored (CM-11-014, CM-11-016).
A replacement or re-invite names the Invite it replaces in `inReplyTo` (CM-11-015, CM-11-016).
A `Reject` from an actor with no participant record is refused (CM-11-018).

---

## Choose invitation over seating

Use `as:Invite` for an actor that was absent when the case was created.
Seat the Case Owner and any already-known participants, such as the Reporter, inline on the `as:Create` for the case instead — see [How to Initialize a Case](initialize_case.md).

If you are not the Case Owner but you know an actor belongs on the case, suggest it rather than inviting it: see [How to Suggest an Actor for a Case](suggest_actor.md).

---

## Verify

| What you sent | What to confirm |
|---|---|
| `Invite(Actor)` | The invitee holds an `Invite` whose `actor` is the CASE_MANAGER. |
| `Accept(Invite(Actor))` | The case roster holds you, and you have a local case replica. |
| `Reject(Invite(Actor))` | The CASE_MANAGER's ledger records your refusal; your participant entry is closed (RM Closed) and kept as history, but you are not an active participant. |

---

## See it end to end

!!! example "Try it: `vultron-demo invite-actor`"

    ```bash
    vultron-demo invite-actor
    ```

    Or with Docker Compose:

    ```bash
    DEMO=invite-actor docker compose -f docker/docker-compose.yml run --rm demo
    ```

    The scenario invites one coordinator that accepts and a second that rejects.

---

## Further reading

- [Case Management Messages](../../../reference/messages/case_management.md) — the wire format and a rendered example for each activity above
- [Activity Vocabulary Design](../../../topics/activity_vocabulary_design.md) — why late arrivals are invited rather than added
- [Case Initialization](../../../topics/case_lifecycle/case_initialization.md) — the case lifecycle these invitations sit inside
