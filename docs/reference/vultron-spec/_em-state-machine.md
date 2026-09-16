## 7. Embargo Management (EM) State Machine [N]

### 7.1 States

{% include-markdown "./includes/_em-states-table.md" %}

This is the **case-level** collective embargo state, distinct from
per-participant consent (see [§9](index.md#9-participant-embargo-consent-pec-state-machine-n)).

!!! warning "`NO_EMBARGO` names a state in two different machines"
    `EM.NO_EMBARGO` exists as an alias for `EM.NONE` — the case-level "no embargo
    is in effect". The PEC machine has a *separate* state also named
    `NO_EMBARGO`, meaning "no embargo is in scope **for this participant**"
    ([§9.1](index.md#91-states)).

    These are different states in different machines, and the machines are
    orthogonal ([§7.3](index.md#73-relationship-to-pec)). A case at `EM.ACTIVE` may hold a participant at
    `PEC.NO_EMBARGO`. Implementations SHOULD prefer `EM.NONE` in code and
    documentation to reduce the collision surface.

### 7.2 Transitions and Guards

Triggers are `PROPOSE`, `ACCEPT`, `REJECT`, `TERMINATE`:

| From | Trigger | To |
|---|---|---|
| `NONE` | `PROPOSE` | `PROPOSED` |
| `PROPOSED` | `PROPOSE` | `PROPOSED` (further proposals) |
| `PROPOSED` | `REJECT` | `NONE` |
| `PROPOSED` | `ACCEPT` | `ACTIVE` |
| `ACTIVE` | `PROPOSE` | `REVISE` |
| `REVISE` | `PROPOSE` | `REVISE` |
| `REVISE` | `REJECT` | `ACTIVE` (revision declined; prior terms stand) |
| `REVISE` | `ACCEPT` | `ACTIVE` (revised terms adopted) |
| `ACTIVE` | `TERMINATE` | `EXITED` |
| `REVISE` | `TERMINATE` | `EXITED` |

`REJECT` from `REVISE` returns to `ACTIVE`, not to `NONE` — rejecting a
*revision* does not end the embargo, it leaves the existing terms in force. This
differs from `REJECT` at `PROPOSED`, which returns to `NONE` because no terms
were ever in force.

**Embargo duration selection.** Where multiple embargo proposals are outstanding,
participants SHOULD accept the shortest and propose the remainder as revisions.
This is a SHOULD, and it is one of several admissible policies — an
implementation may instead defer to the Case Owner, or apply its own
organizational policy. This specification does not mandate shortest-wins.

**Tacit acceptance.** Where a receiver has a default embargo policy, a sender
submitting a report without proposing terms constitutes tacit acceptance of the
receiver's default. Tacit acceptance is a property of the *default-policy* path,
not a general substitute for explicit consent: embargo agreement or rejection
SHOULD NOT otherwise be tacit.

### 7.3 Relationship to PEC

EM and PEC are orthogonal dimensions. EM tracks whether a case has an active
embargo; PEC ([§9](index.md#9-participant-embargo-consent-pec-state-machine-n)) tracks whether each participant has consented to it.

These orthogonal dimensions interact at specific trigger points:

- **EM entering `REVISE`** triggers a bulk `SIGNATORY → LAPSED` transition in
  all participants' PEC machines. Prior consent no longer covers the revised
  terms.
- **EM exiting (`EXITED`)** triggers `RESET` on all participants' PEC machines.
  All participants return to `NO_EMBARGO`.

!!! info "See also"
    - [Participant Embargo Consent](../../topics/process_models/em/index.md)
    - ADR-0048

---
