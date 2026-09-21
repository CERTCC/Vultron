# How to Establish an Embargo

Use this guide to put a case under embargo.
An embargo can be negotiated, by proposing terms and collecting acceptances, or
added outright by the Case Owner when the terms are already settled.
You finish with the case at Embargo Management (EM) state `EM.ACTIVE` and the
terms announced to every participant.

---

## Prerequisites

{% include-markdown "./_demo_prerequisites.md" %}

- An existing case with no active embargo. A case carries at most one.
- The Case Owner role, for adding or activating an embargo. Any participant can
  propose one.
- The embargo terms you intend to propose — at minimum, an end date and time.

!!! note "Embargo Management is a model of its own"

    The Vultron protocol carries considerable detail about
    [Embargo Management](../../../topics/process_models/em/index.md) and how
    participants are expected to interact with embargoes.
    Read that section before designing embargo behavior.

---

## The exchange

The flowchart below shows both routes to `EM.ACTIVE`.
The `Ask first?` branch is the choice between negotiating the terms and adding
them directly.

```mermaid
---
title: Establishing an Embargo: Negotiated and Direct Paths
---
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

---

## Negotiate the terms

1. Send `EmProposeEmbargo` with the proposed `EmbargoEvent` as its `object` and
   the case as its `context`. The case moves to `EM.PROPOSED`.
2. Each participant answers with `EmAcceptEmbargo` or `EmRejectEmbargo`.
3. As Case Owner, send `ActivateEmbargo` once the proposal has carried. The case
   moves to `EM.ACTIVE`.
4. Send `AnnounceEmbargo` so every participant has the terms in hand.

If the proposal is rejected, the case returns to `EM.NONE` and the negotiation is
open again.
Propose revised terms with another `EmProposeEmbargo`.

!!! warning "`ChoosePreferredEmbargo` is being retired"

    The vocabulary still carries a `ChoosePreferredEmbargo` (`as:Question`) activity
    for polling participants across several candidate embargoes.
    Do not use it.
    It has no registered pattern and no `MessageSemantics` value, so no recipient
    can act on it, and it is being removed rather than completed
    ([ADR-0100](../../../adr/0100-no-multi-candidate-embargo-poll.md)).

    Propose one set of terms at a time.
    That is not a workaround — it is how the protocol resolves competing terms.
    You may put several sets of terms on the table by sending a separate
    `EmProposeEmbargo` for each, and each is then accepted or rejected on its own;
    Participants take the proposal with the earliest end date first.
    See [Default Embargoes](../../../topics/process_models/em/defaults.md).

---

## Add an embargo without proposing it

Send `AddEmbargoToCase`, then `AnnounceEmbargo`.

Use this route when the terms need no negotiation:

- no other participant has joined the case yet, or
- your published `EmbargoPolicy` applies and nobody has proposed anything to the
  contrary.

Actors invited later decide for themselves whether to accept the embargo, so
adding it outright does not bind anyone who was absent.

!!! note "A new case may already be embargoed"

    An embargo-eligible case begins with an active embargo even when no proposal
    exchange is visible, because a Protocol Default applies when no proposal and
    no actor default does.
    See
    [Default Embargoes](../../../topics/process_models/em/defaults.md).

---

## Verify

| What you sent | What to confirm |
|---|---|
| `EmProposeEmbargo` | The case `em_state` is `PROPOSED`. |
| `EmAcceptEmbargo` | Your consent state is `SIGNATORY`. |
| `ActivateEmbargo` or `AddEmbargoToCase` | The case `em_state` is `ACTIVE` and the case names one active embargo. |
| `AnnounceEmbargo` | Every participant's replica carries the same active embargo ID. |

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
