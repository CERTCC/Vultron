# Vultron API v2 Implementation Plan

## Overview

This plan tracks forward-looking work against `specs/*` and
`plan/PRIORITIES.md`. Contains only pending, in-progress, and blocked tasks.

**Completed tasks**: see `plan/IMPLEMENTATION_HISTORY.md` (append-only archive).

**Priority ordering note:** `plan/PRIORITIES.md` is authoritative for project
priority. Section order here groups related work by execution context and MUST
NOT override `plan/PRIORITIES.md` when the two differ.

---

## PRIORITY-348 — Demo Review 2026-04-20: Protocol and Architecture Fixes

**Reference**: `notes/demo-review-26042001.md`

These issues were identified during multi-actor demo runs (two-actor,
three-actor, multi-vendor). All high-severity items block every demo scenario.
Architectural decisions for each issue are documented in
`plan/IMPLEMENTATION_NOTES.md` under **REVIEW-26042001**.

- [ ] **DR-05 — Accept.object_ must carry the original Invite (Medium,
  three-actor, multi-vendor):**
  When constructing `RmAcceptInviteToCaseActivity` and
  `EmAcceptEmbargoActivity`, the `object_` field must be the original invite
  activity, not the case object or embargo event. Fix: the
  `InviteReceivedUseCase` (both RM and EM variants) MUST stash the invite
  activity on the BT blackboard. The `AcceptInvite` BT node reads the invite
  from the blackboard rather than querying the DataLayer or passing a
  convenience object.

- [ ] **DR-06 — Multi-party embargo: per-participant consent state machine
  (High, three-actor, multi-vendor):**
  The `VulnerabilityCase` EM state is an aggregate view. Refactor so that each
  `CaseParticipant` tracks their own embargo consent via a 5-state machine
  (`NO_EMBARGO` / `INVITED` / `SIGNATORY` / `LAPSED` / `DECLINED`) backed by
  the existing `ParticipantStatus.embargo_adherence: bool` (which becomes a
  derived property returning `state == SIGNATORY`). Implement using the
  `transitions` library in `vultron/core/states/participant_embargo_consent.py`.
  The case owner's `Accept(Invite/Offer(Embargo))` is the only action that
  transitions the shared `CaseStatus.em_state` to `ACTIVE`. Non-owner accepts
  update only their own consent state to `SIGNATORY`. When shared EM enters
  `REVISE`, all SIGNATORY participants transition to `LAPSED`. Timer-based
  "pocket-veto" transitions from `INVITED` and `LAPSED` to `DECLINED` are
  configurable (policy setting: `embargo_invitation_timeout`).
  See `notes/participant-embargo-consent.md` for full state machine spec.

  **Embargo/case acceptance semantics (new):**
  - `Accept(Invite(case))` while embargo is ACTIVE → IMPLIES accepting the
    active embargo; set consent to `SIGNATORY` in addition to rm_state=ACCEPTED
  - `Accept(Offer/Invite(embargo))` → DOES NOT imply case participation
  - Full case details MUST NOT be sent until BOTH rm_state=ACCEPTED AND
    embargo_adherence=True (or no active embargo)

- [ ] **DR-07 — ActivityPattern discrimination requirement (Low/arch, all):**
  Audit `SEMANTICS_ACTIVITY_PATTERNS` in `vultron/wire/as2/extractor.py`.
  Every pattern must match on at minimum `(Activity type, Object type)`.
  No bare Activity-type-only patterns. Deeply nested activities (e.g.,
  `Accept(Invite(...))`) must also check the nested object type where needed
  to disambiguate (e.g., `Accept(Invite(embargo))` vs
  `Accept(Invite(case))`). `AnnounceLogEntryActivity` pattern immediate fix
  is already complete.

  **Remaining:** `InviteActorToCasePattern` needs `object_` discriminator, but
  `AOtype.ACTOR` cannot be used directly — the pattern matcher uses exact
  `type_` string equality, while real actors use subtypes (`Person`,
  `Organization`, `Service`). Requires either subtype-aware matching in
  `_match_field()` or a custom actor-type predicate.

- [ ] **DR-09 — Actor ID normalization: full URI only (Low, all):**
  Normalize actor IDs to full URIs at the point they are first established
  (actor creation / seed / session context). `add_activity_to_outbox` and all
  other functions MUST only ever receive full URIs; short UUIDs MUST NOT be in
  circulation internally. Audit actor ID assignment in seed/init code paths.

- [ ] **DR-10 — Stub objects for Invite.target (Low/arch, three-actor,
  multi-vendor):**
  Implement stub-object support as described in `notes/stub-objects.md` as
  part of the Invite/embargo flow fix. When constructing an `Invite` to a case,
  the `target` field MUST be a stub object `{id: ..., type: VulnerabilityCase}`
  rather than the full case (selective disclosure: the invitee has not yet
  accepted the embargo). Requirements:
  - Pydantic stub model for `VulnerabilityCase` (and other types as needed).
  - Semantic extraction supports stubs: stub `type` field must route correctly.
  - Recipient-side handling: stubs MUST NOT overwrite a full object in the
    DataLayer.
  - Formal spec in `specs/message-validation.md` MV-10-001–006.

  **Stub upgrade path (new):**
  Full case delivery to a newly accepted participant triggers ONLY when BOTH:
  1. `rm_state = ACCEPTED` (accepted case invite)
  2. `embargo_adherence = True` (SIGNATORY state), OR no active embargo
  The case owner's `AcceptInviteActorToCase` handler (BT subtree) MUST
  check both conditions and emit `Announce(VulnerabilityCase)` with the
  full object when both are satisfied. This is a BT cascade — not post-BT
  procedural code.

- [ ] **DR-13 — `SubmitReportReceivedUseCase`: remove vendor/target
  assumptions (Medium, three-actor):**
  Refactor `SubmitReportReceivedUseCase` to eliminate the `vendor_actor_id` /
  `Offer.target` lookup entirely. Actors are generically typed; the
  finder/vendor/coordinator labels are demo conventions, not protocol roles
  baked into core. New logic:
  - If the receiving actor's ID is in the `Offer.to` field → proceed to create
    a case.
  - If the receiving actor's ID is in `Offer.cc` → `cc` addressing is NOT
    supported; log a WARNING and discard the activity without creating a case.
  - If the receiving actor's ID is in neither `to` nor `cc` → log WARNING
    (activity arrived at wrong destination); discard.
  - Update `specs/handler-protocol.md` HP-09-001 (already done) to document
    the `to`-only case-creation rule and the unsupported `cc` behavior.

- [ ] **DR-14 — Dead-letter handling for unresolvable-object_ UNKNOWN
  (Medium, all):**
  When `find_matching_semantics()` returns `MessageSemantics.UNKNOWN` because
  `object_` is a bare string URI that could not be rehydrated (VAM-01-009),
  the background processing MUST NOT raise `VultronApiHandlerMissingSemanticError`.
  Instead:
  - Log a WARNING: `"Activity {id} not processed: object_ URI {uri} unresolvable
    after rehydration"`
  - Store a dead-letter record in the DataLayer containing: full activity JSON,
    unresolvable URI, actor ID, timestamp
  - Return silently (the 202 was already sent before background processing)
  - For any future synchronous processing path, return HTTP 422 with an
    explanatory error body identifying the unresolvable URI
  Implement by distinguishing UNKNOWN cause in the dispatcher:
  `UNKNOWN_NO_PATTERN` (raise error) vs `UNKNOWN_UNRESOLVABLE_OBJECT` (dead-letter).
  See `specs/semantic-extraction.md` SE-04-002 through SE-04-004.

---

## PRIORITY-347 — Demo Puppeteering, Trigger Completeness, BT Generalization

**Reference**: `plan/PRIORITIES.md` PRIORITY 347;
`plan/IMPLEMENTATION_NOTES.md` BUG-26041701

All tasks in this section are prerequisites for **D5-7-HUMAN** sign-off.
The section can proceed in parallel with PRIORITY-360.

- [ ] **P347-SPECS**: Spec and notes updates:
  - `specs/triggerable-behaviors.md`: reflect trigger renames and additions
    from P347-EMBARGOTRIGGERS; add `create-case`, `add-report-to-case`,
    `suggest-actor-to-case`, `accept-case-invite`.
  - `specs/multi-actor-demo.md`: add requirement that scenario demos MUST
    use trigger endpoints (not direct inbox injection) for all actor-initiated
    actions.
  - `notes/protocol-event-cascades.md`: document the 4-step
    suggest→invite→accept→record cascade as a concrete named example.

---

## D5-7-HUMAN — Project Owner Sign-off on Demo Feedback Resolution

**State**: BLOCKED — waiting for P347-* and SYNC-4 completion

- [ ] **D5-7-HUMAN**: Project owner sign off. Agents are forbidden from
  updating this task; a human must confirm that all of the following are
  complete before signing off:
  - All P347-* tasks above
  - SYNC-4 (multi-peer log synchronization)
  - Multi-actor demos pass end-to-end with log-sync in place

---

## PRIORITY-330 — Replicated Log Synchronization (SYNC-4)

**Reference**: `plan/PRIORITIES.md` PRIORITY 330,
`notes/sync-log-replication.md`

OUTBOX-MON-1, SYNC-1, SYNC-2, and SYNC-3 are complete (see HISTORY). The
remaining open task is SYNC-4.

- [ ] **SYNC-4**: Multi-peer synchronization with per-peer replication state.
  Enables RAFT consensus for CaseActor process.
  **Depends on**: SYNC-3 (complete).

---

## PRIORITY-360 — BT Composability Audit

**Reference**: `plan/PRIORITIES.md` PRIORITY 360; IDEA-26041703

Can proceed in parallel with PRIORITY-347.

- [ ] **P360-NOTES**: Create `notes/bt-reusability.md` capturing the fractal
  composability pattern from `vultron/bt/`, the "trunkless branch" intent,
  and anti-patterns (one-off nodes, hard-coded actor roles, demo-specific
  subtrees). Reference `notes/vultron-bt.txt` as the canonical BT structure
  blueprint.

- [ ] **P360-SPEC**: Create `specs/behavior-tree-node-design.md` with formal
  requirements for BT node parameterization and composability, e.g.:
  - BT nodes MUST NOT hard-code actor roles; identity and role MUST be
    constructor parameters.
  - Reusable logic that appears in multiple subtrees MUST be extracted into
    a shared composable subtree.
  - New BT subtrees SHOULD be verified against `notes/vultron-bt.txt` to
    confirm they match the intended structure.

- [ ] **P360-AUDIT**: Audit existing BT nodes in `vultron/core/behaviors/`
  against the above requirements. Produce a task list of nodes/subtrees
  requiring refactoring.

---

## PRIORITY-350 — Maintenance and Tooling

**Reference**: `plan/PRIORITIES.md` PRIORITY 350

- [ ] **TOOLS-1**: Evaluate Python 3.14 compatibility. Run the test suite on a
  Python 3.14 branch; if tests pass without issue, update `requires-python`
  in `pyproject.toml` to `>=3.14`, and update docker base images to use
  Python 3.14.

- [ ] **DOCS-3**: Update `notes/user-stories-trace.md` (the traceability
  matrix) to map every user story in `docs/topics/user_stories` to the
  exact implementing requirements in `specs/`. Add a mapping for each story
  and mark stories lacking requirement coverage. Add a new section in
  `plan/IMPLEMENTATION_NOTES.md` listing stories with insufficient coverage.

- [ ] **CONFIG-1**: Replace or supplement JSON/env-var actor configuration
  with YAML config files loaded into validated Pydantic models
  (IDEA-260402-01).
  - Load YAML into a dict (`yaml.safe_load()`), validate via a Pydantic
    `ActorConfig` model with typed nested sections (actor identity, peer
    mesh, DataLayer backend settings).
  - Replace the current `VULTRON_SEED_CONFIG` JSON path with a YAML
    equivalent; keep env-var overrides for backwards compatibility.
  - Update `vultron/demo/cli.py` `seed` sub-command to accept YAML seed
    configs in addition to JSON.
  - Add unit tests for round-trip load/validate of example seed configs.
  - `pyyaml` is already an indirect dependency (via `docker-compose` test
    helper); add `pyyaml` and `types-pyyaml` to `pyproject.toml` if not
    already present.

- [ ] **DOCMAINT-2**: Fix stale references to archived notes. Several files
  still reference notes that were moved to `archived_notes/` or merged into
  other notes files (commit `0922e1f1`). Search for and update all stale
  cross-references.

  **Files moved to `archived_notes/`** — update references to use the new
  path:
  - `notes/state-machine-findings.md` → `archived_notes/state-machine-findings.md`
    (referenced in `plan/PRIORITIES.md`,
    `specs/behavior-tree-integration.md`)
  - `notes/multi-actor-architecture.md` →
    `archived_notes/multi-actor-architecture.md`
  - `notes/two-actor-feedback.md` → `archived_notes/two-actor-feedback.md`
  - `notes/datalayer-refactor.md` → `archived_notes/datalayer-refactor.md`
  - `notes/architecture-review.md` → `archived_notes/architecture-review.md`
    (referenced in `specs/architecture.md`)

  **Files merged** — update references to point to the merged destination:
  - `notes/canonical-bt-reference.md` → `notes/bt-integration.md`
    (referenced in `plan/IDEAS.md`,
    `specs/behavior-tree-integration.md`)

  **Also**: Update `notes/datalayer-sqlite-design.md` status header from
  "Status: Planned" to "Status: Complete".

---

## Deferred (Per PRIORITIES.md)

- USE-CASE-01 **`CloseCaseUseCase` wire-type construction** — Replace direct
  construction of `VultronActivity(as_type="Leave")` with domain event
  emission through the `ActivityEmitter` port. Defer until outbound delivery
  integration beyond OX-1.0 is implemented.
- USE-CASE-02 **UseCase Protocol generic enforcement** — Decide on a consistent
  `UseCaseResult` Pydantic return envelope; enforce via mypy. Defer to after
  TECHDEBT-21/22.
- **EP-02/EP-03** — EmbargoPolicy API + compatibility evaluation (`PROD_ONLY`)
- **AR-04/AR-05/AR-06** — Job tracking, pagination, bulk ops (`PROD_ONLY`)
- AGENTIC-00 **Agentic AI integration** (Priority 1000) — out of scope until
  protocol foundation is stable
- FUZZ-00 **Fuzzer node re-implementation** (Priority 500) — see
  `notes/bt-fuzzer-nodes.md`
- IDEA-260402-02 **Per-participant case replica management** — Each Participant
  Actor maintains their own copy of the case object, synchronised from the
  CaseActor via `Announce(CaseLogEntry)` replication. SYNC-1 through SYNC-4
  implement the CaseActor side; the participant-side case replica handler
  (routing inbound `Announce` to the correct local case copy) is part of
  SYNC-2 scope. See `plan/IDEAS.md` IDEA-260402-02 and
  `notes/sync-log-replication.md` for the design.
