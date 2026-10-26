---
stakeholder_type: [platform-developer]
level: 400
page_type: how-to
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
    O ->> CA: Offer(Actor)[target=VulnerabilityCase]
    activate CA
    CA ->>+ A: Invite(Actor)[target=VulnerabilityCaseStub]
    note over CA: Records inert CaseParticipant (RM Received)
    note over A: Consider invitation
    alt Accept Invitation
        A -->> CA: Accept(Invite(Actor)[target=VulnerabilityCaseStub])
        note over CA: Participant becomes active (RM stays Received)<br/>then sends case, ledger replay and full-case Invite
    else Reject Invitation
        A -->> CA: Reject(Invite(Actor)[target=VulnerabilityCaseStub])
        note over CA: Closes inert record (RM Closed); kept as history
    end
    deactivate A
    deactivate CA
    deactivate O
```

---

## Send the invitation

1. Trigger the invitation as Case Owner.
   Your container sends your own `Offer(Actor)` to the CASE_MANAGER (CM-17-007).
   The `Offer` has the invited actor as its `object` and the case as its `target`.
   It lists the roles you offer in `suggestedRoles`.
   With no roles given, the CASE_MANAGER assigns a non-empty default role list (CM-16-003).
   A stub Invite always names at least one role, and the CASE_MANAGER refuses to send one with none (CM-11-019).

    {% include-markdown "../../../reference/messages/_occasions/embeds/request-invite-actor-to-case.md" %}

2. The CASE_MANAGER commits and sends `Invite(Actor)` to the actor's inbox.
   The `Invite` has a case stub as its `target`, not the case itself (CM-11-013, CM-17-001).
   The CASE_MANAGER is the ActivityStreams `actor`, and your identity is in `attributedTo` (PCR-08-007, PCR-08-008).
   The trigger's `202` response means only that your `Offer` was queued.
   Watch for the `Invite` on the CASE_MANAGER's ledger, not in the response.

    {% include-markdown "../../../reference/messages/_occasions/embeds/invite-actor-to-case.md" %}

3. Set the reply deadline on the activity's `end_time`.
   When that value is present, it takes precedence over the invitee's local policy window (CM-28-002, ADR-0065).
   When it is absent, the policy window applies instead (CM-28-002, ADR-0065).
   In both cases, the effective deadline is clamped down to the embargo's own `end_time` (EP-07-006).
   An `end_time` that outlives the embargo does not give the invitee extra time.

!!! warning "The CASE_MANAGER is the sender, not the Case Owner"

    If the Case Owner is in the `actor` field, a conformant peer does not recognize the invitation.
    The peer expects case-management handshakes to come from the CASE_MANAGER.
    Record who asked for the invitation in `attributedTo` instead.

---

## Answer an invitation

Send your reply to the CASE_MANAGER, never to the Case Owner.

- If you are joining the case, send `Accept(Invite(Actor))` with the `Invite` activity as its `object`.

    {% include-markdown "../../../reference/messages/_occasions/embeds/accept-invite-to-case.md" %}

- If you are not joining, send `Reject(Invite(Actor))` with the `Invite` as its `object`.

    {% include-markdown "../../../reference/messages/_occasions/embeds/reject-invite-to-case.md" %}

When you accept, the CASE_MANAGER does these steps (CM-17-004):

- It commits the reply to the ledger.
- It seats you at Report Management (RM) state `RM.RECEIVED`.
- It signs your [embargo consent](../../../topics/behavior_logic/use-cases/embargo-lifecycle.md#which-messages-move-consent) if an embargo is active.
- It sends `Announce(VulnerabilityCase)` to seed your replica.
- It backfills the earlier ledger entries.

{% include-markdown "../../../reference/messages/_occasions/embeds/announce-vulnerability-case.md" %}

Expect `RM.RECEIVED`, not `RM.ACCEPTED`.
An accepted invitation says you are willing to join the case.
It does not say you have validated the report, because you have not yet seen it in full (CM-11-001).

After the case and the ledger replay reach you, the CASE_MANAGER sends a second Invite, the full-case Invite.
You judge the case when you answer it — see [How to Manage a Case Roster](manage_participants.md#judge-the-case-after-joining).
Do not answer the original report Offer: you were never offered that report (CM-11-020).
Rule on the case afterwards — see [How to Advance a Case Through Report Management](manage_case.md).

A reply that arrives after the Invite's deadline is still processed.
The one exception is an `Accept` of a stub Invite that a newer one replaced.
The CASE_MANAGER refuses that `Accept` and answers with the name of the replacement.
A `Reject` of the replaced Invite is honored (CM-11-014, CM-11-016).
A replacement or re-invite names the Invite it replaces in `inReplyTo` (CM-11-015, CM-11-016).

A `Reject` or an `Accept` from an actor with no participant record is refused (CM-11-018, CM-11-021).
An actor can send an `Accept` of a stub Invite after it already joined the case, or after it was removed from it.
That `Accept` is a duplicate, and the CASE_MANAGER records and sends nothing (CM-17-012).

---

## Choose invitation over seating

Use `as:Invite` for an actor that was absent when the case was created.
Seat the Case Owner and any already-known participants, such as the Reporter, inline on the `as:Create` for the case instead — see [How to Initialize a Case](initialize_case.md).

If you are not the Case Owner but you know an actor belongs on the case, suggest the actor instead of inviting it.
See [How to Suggest an Actor for a Case](suggest_actor.md).

---

## Verify

| What you sent | What to confirm |
|---|---|
| `Invite(Actor)` | The invitee holds an `Invite` whose `actor` is the CASE_MANAGER. |
| `Accept(Invite(Actor))` | The case roster holds you, and you have a local case replica. |
| `Reject(Invite(Actor))` | The CASE_MANAGER's ledger records your `Reject`; your participant entry is closed (RM Closed) and kept as history, but you are not an active participant. |

---

## See it end to end

!!! example "Try it: `vultron-demo invite-actor`"

    {% include-markdown "./_demo_invite_actor.md" %}

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
