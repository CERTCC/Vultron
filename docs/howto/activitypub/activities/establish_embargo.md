# How to Establish an Embargo

Use this guide to put a case under embargo. An embargo can be negotiated, by proposing
terms and collecting acceptances, or added outright by the Case Owner when the terms are
already settled. You finish with the case at Embargo Management (EM) state `EM.ACTIVE`
and the terms announced to every participant.

---

## Prerequisites

{% include-markdown "./_demo_prerequisites.md" %}

- An existing case with no active embargo. A case carries at most one.
- The Case Owner role, for adding or activating an embargo. Any participant can propose
  one.
- The embargo terms you intend to propose — at minimum, an end date and time.

!!! note "Embargo Management is a model of its own"

    The Vultron protocol carries considerable detail about
    [Embargo Management](../../../topics/process_models/em/index.md) and how
    participants are expected to interact with embargoes. Read that section before
    designing embargo behavior.

---

## The exchange

The flowchart below shows both routes to `EM.ACTIVE`. The `Ask first?` branch is the
choice between negotiating the terms and adding them directly.

```mermaid
---
title: Establishing an Embargo: Negotiated and Direct Paths
---
flowchart TB
    subgraph as:Invite
        EmProposeEmbargo["Embargo Proposal (EP) / Embargo Revision Proposal (EV)<br/>Invite(Event)"]
    end
    subgraph as:Question
        ChoosePreferredEmbargo
    end
    subgraph as:Accept
        EmAcceptEmbargo["Embargo Proposal Acceptance (EA) / Embargo Revision Acceptance (EC)<br/>Accept(Invite(Event))"]
    end
    subgraph as:Reject
        EmRejectEmbargo["Embargo Proposal Rejection (ER) / Embargo Revision Rejection (EJ)<br/>Reject(Invite(Event))"]
    end
    subgraph as:Announce
        AnnounceEmbargo["Announce the embargo terms<br/>Announce(Event)"]
    end
    subgraph as:Add
        ActivateEmbargo["Activate the agreed embargo<br/>Add(Event), inReplyTo: Invite(Event)"]
        AddEmbargoToCase["Attach the embargo to the case<br/>Add(Event), no inReplyTo"]
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

---

## Negotiate the terms

Embargo Proposal (EP) is implemented in ActivityStreams as `Invite(Event)`. The same
activity carries a revision, Embargo Revision Proposal (EV); a receiver tells the two
apart from the case's EM state rather than from the activity (MSM-02).

1. Send `Invite(Event)` with the proposed `EmbargoEvent` as its `object` and the case as
   its `context`. The case moves to `EM.PROPOSED`.
2. Each participant answers with Embargo Proposal Acceptance (EA),
   `Accept(Invite(Event))`, or Embargo Proposal Rejection (ER), `Reject(Invite(Event))`.
3. As Case Owner, send `Add(Event)` once the proposal has carried, with `inReplyTo`
   naming the `Invite(Event)` it answers. The case moves to `EM.ACTIVE`.
4. Send `Announce(Event)` so every participant has the terms in hand.

If the proposal is rejected, the case returns to `EM.NONE` and the negotiation is open
again. Propose revised terms with another `Invite(Event)`.

!!! warning "Polling across candidate embargoes does not round-trip yet"

    The vocabulary carries a `Question(anyOf=[Event])` activity for polling participants
    across several candidate embargoes. No registered pattern claims that form and no
    `MessageSemantics` value maps to it, so a receiving Vultron actor does not dispatch
    it (#3433). Propose one set of terms at a time until that gap is closed.

---

## Add an embargo without proposing it

Send `Add(Event)` with no `inReplyTo`, then `Announce(Event)`.

This is the same wire form as step 3 above, and `inReplyTo` is the only thing that
separates them: both dispatch to the same pattern, so a receiver distinguishes "activate
the embargo we agreed" from "impose these terms directly" by whether the `Add` answers
an earlier `Invite(Event)`.

The formal message set has a single name, Embargo Proposal (EP), covering the proposal,
the attachment and the announcement alike. ActivityStreams gives each its own activity,
so no one formal name identifies which of the three you are sending.

Use this route when the terms need no negotiation:

- no other participant has joined the case yet, or
- your published `EmbargoPolicy` applies and nobody has proposed anything to the
  contrary.

Actors invited later decide for themselves whether to accept the embargo, so adding it
outright does not bind anyone who was absent.

!!! note "A new case may already be embargoed"

    An embargo-eligible case begins with an active embargo even when no proposal
    exchange is visible, because a Protocol Default applies when no proposal and no
    actor default does. See
    [Default Embargoes](../../../topics/process_models/em/defaults.md).

---

## Verify

| What you sent | What to confirm |
|---|---|
| `Invite(Event)` | The case `em_state` is `PROPOSED`. |
| `Accept(Invite(Event))` | Your consent state is `SIGNATORY`. |
| `Add(Event)`, with or without `inReplyTo` | The case `em_state` is `ACTIVE` and the case names one active embargo. |
| `Announce(Event)` | Every participant's replica carries the same active embargo ID. |

---

## See it end to end

!!! example "Try it: `vultron-demo establish-embargo`"

    ```bash
    vultron-demo establish-embargo
    ```

    Or with Docker Compose:

    ```bash
    DEMO=establish-embargo docker compose -f docker/docker-compose.yml run --rm demo
    ```

    The scenario runs both the accepted and the rejected proposal.

---

## Further reading

- [Embargo Management (EM) Messages](../../../reference/messages/em.md) — the wire
  format and a rendered example for each activity above
- [Embargo Management](../../../topics/process_models/em/index.md) — the state
  machine these activities drive
- [Negotiating Embargoes](../../../topics/process_models/em/negotiating.md) — how
  to choose terms other parties will accept
- [How to Revise or Terminate an Embargo](manage_embargo.md) — what to do once the
  embargo is active
- [Trigger API Reference](../../../reference/trigger-api.md#embargo-management) —
  request schema and endpoint details for `propose-embargo`, `accept-embargo`,
  and `reject-embargo`
