# How to Revise or Terminate an Embargo

Use this guide once a case already has an active embargo.
A revision runs the same propose, accept, or reject cycle that established the
embargo; a termination removes it outright.
You finish with the case at Embargo Management (EM) state `EM.ACTIVE` under new
terms, or at `EM.EXITED`.

---

## Prerequisites

{% include-markdown "./_demo_prerequisites.md" %}

- A case at `EM.ACTIVE`. See
  [How to Establish an Embargo](establish_embargo.md).
- The Case Owner role, for activating a revision or terminating the embargo. Any
  participant can propose a revision.

!!! note "Embargo Management is a model of its own"

    The Vultron protocol carries considerable detail about
    [Embargo Management](../../../topics/process_models/em/index.md) and how
    participants are expected to interact with embargoes.
    Read that section before designing embargo behavior.

---

## The exchange

The flowchart below extends the establishment flow with the moves available once
an embargo is active.
The `Terminate?` branch is where an active embargo ends; the `Propose?` branch is
where it changes.

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

---

## Revise the terms

1. Send `EmProposeEmbargo` with the revised `EmbargoEvent`. The case moves to
   `EM.REVISE`.
2. Each participant answers with `EmAcceptEmbargo` or `EmRejectEmbargo`.
3. As Case Owner, send `ActivateEmbargo` once the revision has carried, then
   `AnnounceEmbargo`.

A revision uses the same activities as an initial proposal.
The receiver tells the two apart from the case's EM state: a proposal that arrives
while the embargo is active is a revision (MSM-02).

If the revision is rejected, the case returns to `EM.ACTIVE` under the original
terms.
The embargo does not lapse because a revision failed.

---

## Terminate the embargo

Send `RemoveEmbargoFromCase`, then `AnnounceEmbargo` so participants see that the
embargo is gone.
The case moves to `EM.EXITED`, with immediate effect.

!!! warning "Termination is not a revision"

    `RemoveEmbargoFromCase` ends the embargo now, rather than proposing a shorter
    one.
    If you want the embargo to end sooner but still exist, propose a revision
    with an earlier end time.

An embargo also terminates on its own when the case reaches public awareness.
See
[Early Termination](../../../topics/process_models/em/early_termination.md).

---

## Verify

| What you sent | What to confirm |
|---|---|
| `EmProposeEmbargo` on an active embargo | The case `em_state` is `REVISE`. |
| `ActivateEmbargo` after a revision | The case `em_state` is `ACTIVE` and the active embargo carries the new terms. |
| `EmRejectEmbargo` on a revision | The case `em_state` is `ACTIVE` and the terms are unchanged. |
| `RemoveEmbargoFromCase` | The case `em_state` is `EXITED` and no embargo is active. |

---

## See it end to end

!!! example "Try it: `vultron-demo manage-embargo`"

    ```bash
    vultron-demo manage-embargo
    ```

    Or with Docker Compose:

    ```bash
    DEMO=manage-embargo docker compose -f docker/docker-compose.yml run --rm demo
    ```

    The scenario runs an activate-then-terminate path and a
    reject-then-repropose path.

---

## Further reading

- [Embargo Management (EM) Messages](../../../reference/messages/em.md) — the wire
  format and a rendered example for each activity above, and the state-context
  rule that distinguishes a revision from a proposal
- [Embargo Management](../../../topics/process_models/em/index.md) — the state
  machine these activities drive
- [Participant Embargo Consent](../../../topics/process_models/em/participant-embargo-consent.md)
  — how each participant's own commitment is tracked alongside the case EM state
