# Actor Knowledge Model Specification

## Overview

This specification defines the **Actor Knowledge Model** — the principle that
a Vultron Actor's knowledge of the world is strictly bounded by the
ActivityStreams 2.0 activities it has received. Actors MUST NOT assume
recipients have objects that have not been explicitly included in prior
activities. DataLayer access is private and non-shareable; all inter-Actor
communication occurs exclusively through the AS2 wire protocol.

**Source**: `plan/IDEAS.md` IDEA-26041601, IDEA-26041602  
**Consolidates**: `specs/case-management.yaml` CM-01-001 (actor isolation),
`specs/message-validation.yaml` MV-09-001 (full inline object requirement)  
**Cross-references**: `specs/message-validation.yaml` MV-09-001 through MV-10-004,
`specs/case-management.yaml` CM-01-001, `specs/outbox.yaml` OX-07-002,
`specs/multi-actor-demo.yaml` DEMOMA-00-001

---

## DataLayer Isolation (MUST)

- `AKM-01-001` Each Actor's DataLayer is private to that Actor and MUST NOT
  be accessible to any other Actor.
  - There is no "efficiency" framing here: Actors do not have access to each
    other's DataLayers, full stop. This is an architectural invariant, not an
    optimization.
  - An Actor MUST NOT read from or write to another Actor's DataLayer directly
    under any circumstances, including co-located deployment.
  - All inter-Actor coordination MUST pass through the ActivityStreams inbox/outbox
    API.
  - Cross-reference: CM-01-001 implements this principle.
  - Cross-reference: DEMOMA-00-001 restates this for multi-actor demo scenarios.

- `AKM-01-002` Actors that are co-located on the same server or within the same
  process MUST still interact via the wire protocol and MUST NOT communicate via
  direct DataLayer access or in-process calls bypassing the inbox/outbox API.
  - This constraint applies regardless of physical deployment topology.

## Knowledge Boundaries (MUST)

- `AKM-02-001` An Actor MUST NOT assume that a recipient has knowledge of any
  object that has not been explicitly included in a prior activity sent to that
  recipient.
  - An Actor's knowledge is bounded by what it has received via AS2 activities.
  - Object references (bare string URIs, `as_Link` objects) are opaque to the
    recipient unless the referenced object was included in a prior activity.

- `AKM-02-002` Actors MUST NOT use object references in place of full inline
  objects when the recipient cannot be expected to have the referenced object
  in its own DataLayer.
  - When in doubt, include the full object inline.
  - Cross-reference: MV-09-001 implements this rule for outbound initiating
    activities.

- `AKM-02-003` The sole exception to the full-inline-object rule is the
  `target` field of an `Invite` activity in selective-disclosure scenarios.
  - Cross-reference: MV-10-001 through MV-10-004 define stub objects as the
    only approved exception.

## Outbound Activity Object Integrity (MUST)

- `AKM-03-001` Outbound initiating activities (Create, Offer, Invite, Announce,
  Add, Remove, Update, Join, Ignore, Leave) MUST carry the `object` field as a
  fully inline typed domain object.
  - Bare string URIs and `as_Link` references are NOT permitted in outbound
    initiating activities.
  - Rationale: The recipient has no access to the sender's DataLayer. A bare
    string URI leaves the object type opaque, causing semantic pattern matching
    to fail or produce incorrect results.
  - Cross-reference: MV-09-001 formalizes this rule with enforcement details.
  - Cross-reference: MV-09-002 specifies the runtime guard in the outbox
    handler.

- `AKM-03-002` The outbox handler MUST enforce object integrity at delivery
  time as a last-resort runtime guard.
  - If an outbound activity's `object_` field is a bare string or `as_Link`
    after any DataLayer expansion attempt, the outbox handler MUST raise
    `VultronOutboxObjectIntegrityError` and abort delivery.
  - Cross-reference: MV-09-002 specifies the exact enforcement behavior.

## Future: Known-Object Tracking (MAY)

- `AKM-04-001` `PROD_ONLY` A future implementation MAY track which objects have
  been shared with each participant (e.g., via `CaseLogEntry` hash-chain
  records) to avoid redundant full-object transmission.
  - This optimization is deferred to a future production implementation.
  - Until implemented, Actors MUST default to including full inline objects
    in all outbound initiating activities.
  - This optimization, if implemented, MUST be scoped so that Actors still
    include full objects when there is any uncertainty about recipient
    knowledge state.

## Verification

### AKM-01-001, AKM-01-002 Verification

- Code review: Confirm no handler, use case, or adapter imports or calls a
  DataLayer belonging to a different actor.
- Architecture test: Verify that actor containers in multi-actor demos use
  logically isolated DataLayer instances (DEMOMA-01-001).
- Code review: `vultron/core/` and `vultron/wire/` have no imports from
  other actors' DataLayer instances.

### AKM-02-001, AKM-02-002 Verification

- Code review: Outbound activity builders always pass full domain objects
  (not string IDs) as `object_`.
- Unit test: Verify that `VultronOutboxObjectIntegrityError` is raised when
  an outbound activity carries a bare string `object_`.
- Integration test: Send an activity with a bare string `object_` to the
  outbox handler; confirm 500 / `VultronOutboxObjectIntegrityError`.

### AKM-03-001, AKM-03-002 Verification

- Unit test: `outbox_handler` raises `VultronOutboxObjectIntegrityError` for
  bare string `object_` after expansion attempt fails.
- Cross-reference: MV-09-001 verification section in `message-validation.md`.
