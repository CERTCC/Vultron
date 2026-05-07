---
title: Two-Actor Demo Design
status: active
description: >
  Authoritative design note for the two-actor (Reporter + Vendor) CVD demo.
  Covers the complete workflow from report submission through case closure,
  the Case Actor handoff mechanism, the CASE_MANAGER role, milestone
  verifications, and the puppeteering-only trigger constraint.
related_specs:
  - specs/multi-actor-demo.yaml
  - specs/case-bootstrap-trust.yaml
  - specs/participant-case-replica.yaml
  - specs/participant-role-management.yaml
  - specs/sync-log-replication.yaml
  - specs/event-driven-control-flow.yaml
  - specs/embargo-default-semantics.yaml
related_notes:
  - notes/case-bootstrap-trust.md
  - notes/case-creation-sequence.md
  - notes/participant-case-replica.md
  - notes/participant-role-management.md
  - notes/event-driven-control-flow.md
  - notes/embargo-default-semantics.md
  - notes/sync-log-replication.md
relevant_packages:
  - vultron/demo/scenario
  - vultron/adapters/driving/fastapi/routers
  - vultron/core/use_cases/triggers
  - vultron/core/behaviors/case
---

# Two-Actor Demo Design

**Source**: 2026-05-07 design session (grill-me).

---

## Purpose

The two-actor demo is the foundational scenario for the Vultron prototype.
It demonstrates a complete, clean CVD workflow between a Reporter (Finder) and
a Vendor, with a dedicated Case Actor managing case state. All other demo
scenarios build on this one — if it fails, nothing else works.

**Final case state**: `VFDPxa` — Vendor aware, Fix ready, Fix Deployed, Public
aware, no exploit public, no active attacks.

---

## Actors

| Entity | Role(s) | Container |
|--------|---------|-----------|
| Reporter (Finder) | REPORTER | `finder` container |
| Vendor | VENDOR, CASE_OWNER | `vendor` container |
| Case Actor | CASE_MANAGER | `vendor` container (separate actor record) |

**Docker topology**: two containers only (`finder`, `vendor`). The Case Actor
is an actor record co-located in the vendor container with its own distinct
actor ID and inbox URL (e.g.,
`http://vendor:7999/api/v2/actors/{case_actor_uuid}`). No separate
`case-actor` container is used for the two-actor demo.

### CASE_MANAGER vs CASE_ACTOR terminology

The **entity** is called the "Case Actor" (it is an ActivityPub Actor with an
inbox). The **role** it holds within the case is `CASE_MANAGER` (a
`CVDRole` enum value). This disambiguates entity from role. `CASE_ACTOR` as a
role name is retired.

See `vultron/core/states/roles.py` (`CVDRole.CASE_MANAGER`) and
`notes/participant-role-management.md`.

---

## Puppeteering Constraint

The demo runner MUST NOT:

- POST raw ActivityStreams JSON directly to any actor's inbox
- Access or manipulate actor internals directly
- Spoof activities on behalf of actors

The demo runner MUST only:

- Call trigger endpoints (`POST /actors/{id}/trigger/{behavior}` or
  `POST /actors/{id}/demo/{behavior}`)
- Read DataLayer endpoints for milestone verification

See `specs/multi-actor-demo.yaml` DEMOMA-05-001, DEMOMA-05-002.

---

## Complete Workflow

### Phase 0 — Setup

1. Reset both containers to a clean baseline.
2. Seed actors: Reporter on finder container; Vendor on vendor container;
   each registered as a known peer on the other container.

### Phase 1 — Report Submission and Case Creation

1. **Demo puppeteers Reporter**: `POST .../demo/submit-report` (or
   `trigger/submit-report`). Reporter constructs `Offer(VulnerabilityReport)`
   and delivers it to the Vendor's inbox.

2. **Vendor BT (automatic)**: On receiving the Offer, the Vendor runs the
   case-creation BT:
   a. Creates a stub `VulnerabilityCase` with the report attached.
   b. Adds itself as a participant (roles: VENDOR, CASE_OWNER, CASE_MANAGER).
   c. Adds the Reporter as a participant (role: REPORTER).
   d. Spawns the **Case Actor** entity (new actor record in vendor container).
   e. Adds Case Actor as a participant (role: CASE_MANAGER); removes its own
      CASE_MANAGER role, retaining only VENDOR and CASE_OWNER.
   f. Sends `Offer(VulnerabilityCase, context=report_offer_id)` to the Case
      Actor's inbox — this is a **CASE_MANAGER role delegation** (see below).

3. **Case Actor BT (automatic)**: On receiving the CASE_MANAGER delegation:
   a. Verifies that the sender holds CASE_OWNER on the case.
   b. Verifies that itself is listed as a CASE_MANAGER participant.
   c. Accepts the delegation (sends `Accept(delegation)` back to Vendor).
   d. Runs the case initialization BT:
      - Establishes the default embargo from the Vendor's embargo policy.
      - Sets both Vendor and Reporter to embargo SIGNATORY state immediately
        (no invite/accept round-trip — they were present at case creation).
      - Updates EM state to ACTIVE.

4. **Vendor (automatic)**: After the Case Actor accepts, Vendor sends
   `Create(VulnerabilityCase)` to the Reporter. This is the **trust bootstrap**
   (DEMOMA-08-001): the full case snapshot includes all three participants
   (Vendor, Reporter, Case Actor), so the Reporter can bind the Case Actor's
   identity to this case. See `notes/case-bootstrap-trust.md`.

> **Milestone M1**: Case exists in Vendor DataLayer with 3 participants
> (Vendor, Reporter, Case Actor), EM.ACTIVE, default embargo present.
> Both Vendor and Reporter DataLayers are checked.

### Phase 2 — Report Validation

1. **Demo puppeteers Vendor**: `POST .../trigger/validate-report`.
   Vendor's BT advances report RM state RECEIVED → VALID, then automatically
   cascades to engage-case (VALID → ACCEPTED). Vendor queues
   state-change activities to outbox; Case Actor receives them and announces
   log entries.

> **Milestone M2**: Reporter DataLayer contains case replica (outbox delivery
> confirmed). Both actor DataLayers are checked for matching
> `actor_participant_index`, `active_embargo`, and log tail hash.

### Phase 3 — Notes Exchange

1. **Demo puppeteers Reporter**: `POST .../demo/add-note-to-case`.
   Reporter constructs `Add(Note, target=Case)` and sends to Case Actor inbox.
   Case Actor broadcasts note to all other participants.

2. **Demo puppeteers Vendor**: `POST .../demo/add-note-to-case` (reply note).
   Same mechanism.

### Phase 4 — Fix Lifecycle

1. **Demo puppeteers Vendor**: `POST .../demo/notify-fix-ready`.
    Vendor sends `Add(ParticipantStatus(CS.VF), target=Case)` to Case Actor.
    Case Actor verifies sender is a known participant, updates participant
    status, announces to all other participants.

> **Milestone M4**: Both Vendor and Reporter replicas show CS state includes
> `F` (fix ready).

1. **Demo puppeteers Vendor**: `POST .../demo/notify-fix-deployed`.
    Vendor sends `Add(ParticipantStatus(CS.VFD), target=Case)` to Case Actor.

> **Milestone M5**: Both replicas show CS state includes `D` (fix deployed).

### Phase 5 — Publication and Embargo Teardown

1. **Demo puppeteers Vendor**: `POST .../demo/notify-published`.
    Vendor sends `Add(ParticipantStatus(CS.VFDPxa), target=Case)` to Case
    Actor. Case Actor updates participant status and, because the Case Owner
    has declared CS.P, automatically triggers embargo teardown
    (`terminate-embargo`).

2. **Case Actor BT (automatic)**: Terminates embargo. Announces embargo
    termination to all participants. Both Vendor and Reporter receive it and
    update their local EM states to EXITED.

3. **Demo puppeteers Reporter** (after receiving termination):
    `POST .../demo/notify-published`. Reporter sends
    `Add(ParticipantStatus(CS.VFDPxa), target=Case)` to Case Actor.

> **Milestone M6**: Both replicas show CS.VFDPxa and EM terminated.

### Phase 6 — Case Closure

1. **Demo puppeteers Vendor**: `POST .../demo/close-case`.
    Vendor sends `Add(ParticipantStatus(rm=RM.CLOSED), target=Case)` to Case
    Actor.

2. **Demo puppeteers Reporter**: `POST .../demo/close-case`.
    Same for Reporter.

3. **Case Actor BT (automatic)**: Once all participants are RM.CLOSED,
    Case Actor closes the case (updates case status).

> **Milestone M7**: Both replicas show all participants RM.CLOSED; case is
> closed. Final CS state: VFDPxa.

---

## CASE_MANAGER Role Delegation

The Vendor delegates operational case management to the Case Actor entity
using a **CASE_MANAGER delegation** protocol. This is a **distinct mechanism**
from the existing CASE_OWNER transfer:

| Mechanism | Activity type | Effect |
|-----------|--------------|--------|
| `OFFER_CASE_OWNERSHIP_TRANSFER` (existing) | Transfers CASE_OWNER role from one actor to another | The offering actor loses CASE_OWNER |
| `OFFER_CASE_MANAGER_ROLE` (new) | Delegates CASE_MANAGER operational authority to Case Actor | The offering actor (Vendor) retains CASE_OWNER permanently |

New `MessageSemantics` values required:

- `OFFER_CASE_MANAGER_ROLE`
- `ACCEPT_CASE_MANAGER_ROLE`
- `REJECT_CASE_MANAGER_ROLE` (optional; for completeness)

These must be added to `vultron/core/models/events/base.py`,
`vultron/wire/as2/extractor.py` (patterns), and the use-case map.

---

## ParticipantStatus Trigger Pattern

CS state transitions (F, D, P, X, A) and RM case closure all flow through
participant status updates, not through dedicated low-level API endpoints.

**Layered implementation** (bottom-up):

1. `SvcAddObjectToCaseUseCase` (existing) — generic Add(object, target=Case)
2. `SvcAddParticipantStatusUseCase` (new) — builds a `ParticipantStatus` with
   the requested CS/RM state fields populated, then delegates to
   `SvcAddObjectToCaseUseCase`
3. Demo trigger endpoints in `demo_triggers.py` (new):
   - `POST /actors/{id}/demo/notify-fix-ready` → CS.F
   - `POST /actors/{id}/demo/notify-fix-deployed` → CS.D
   - `POST /actors/{id}/demo/notify-published` → CS.P
   - `POST /actors/{id}/demo/close-case` → RM.CLOSED

**"notify" not "announce"**: The endpoints use `notify` to avoid the
ActivityStreams verb `Announce`. The underlying activity is
`Add(ParticipantStatus, target=Case)`, not an `Announce`.

**Case Actor received-side handler**: On receipt of
`ADD_PARTICIPANT_STATUS_TO_PARTICIPANT`, the Case Actor:

1. Verifies the activity `actor` is a known participant of the case.
2. Updates the participant's status record.
3. Announces the update to all other case participants.
4. If CS.P is newly set by the Case Owner → triggers embargo teardown.
5. If all participants are RM.CLOSED → closes the case.

---

## Milestone Verification Rules

All milestone checks MUST verify **both** the Vendor DataLayer and the
Reporter (Finder) DataLayer. Direct DataLayer reads are acceptable in demo
scripts for verification — they are read-only assertions, not puppeteering.

| Milestone | What to verify |
|-----------|---------------|
| M1 | Vendor: case exists, 3 participants, EM.ACTIVE, embargo present. Reporter: has case replica, matching `actor_participant_index`, matching `active_embargo`. |
| M2 | Reporter DataLayer has case ID. Both sides: matching participant index, matching embargo, matching log tail hash (SYNC-2). |
| M4 | Both replicas: participant status includes CS.F. |
| M5 | Both replicas: participant status includes CS.D. |
| M6 | Both replicas: CS.VFDPxa; EM state terminated/exited. |
| M7 | Both replicas: all participants RM.CLOSED; case status closed. |

---

## Relation to Priority 476 Bugs

Issues #449–#454 were identified against earlier demo implementations.
During implementation of the new demo, each bug must be either:

- Resolved by the new implementation (close the issue with a reference), or
- Confirmed still relevant and kept open with a cross-reference note.

Do not close these issues before implementation confirms their status.

---

## Related Archived Notes

- `notes/demo-review-26042001.md` — archived; point-in-time bug analysis
  from 2026-04-20 that informed the demo redesign
- `archived_notes/two-actor-feedback.md` — detailed bug feedback from
  earlier demo runs
