# Vultron API v2 Implementation Plan

## Overview

This plan tracks forward-looking work against `specs/*` and
`plan/PRIORITIES.md`. Contains only pending, in-progress, and blocked tasks.

**Completed tasks**: see `plan/IMPLEMENTATION_HISTORY.md` (append-only archive).

**Priority ordering note:** `plan/PRIORITIES.md` is authoritative for project
priority. Section order here groups related work by execution context and MUST
NOT override `plan/PRIORITIES.md` when the two differ.

---

## PRIORITY-347 — Demo Puppeteering, Trigger Completeness, BT Generalization

**Reference**: `plan/PRIORITIES.md` PRIORITY 347;
`plan/IMPLEMENTATION_NOTES.md` BUG-26041701

All tasks in this section are prerequisites for **D5-7-HUMAN** sign-off.
The section can proceed in parallel with PRIORITY-360.

- [ ] **P347-BUGFIX**: Fix `CreateFinderParticipantNode.update()` in
  `vultron/core/behaviors/case/nodes.py`: replace
  `VultronActivity(type_="Add", object_=participant.id_, ...)` with
  `AddParticipantToCaseActivity(object_=participant, ...)`.
  Refs: BUG-26041701, MV-09-001.

- [ ] **P347-NODEGENERAL**: Generalize `CreateFinderParticipantNode` →
  `CreateCaseParticipantNode(actor_id, role)` so that the node is
  parameterized and not hard-coded to the finder/reporter role.
  The existing call site(s) should pass role and actor identity as
  constructor arguments.
  Update all call sites and tests.
  Refs: IDEA-26041702.

- [ ] **P347-BRIDGE**: Extend the outbox expansion bridge in
  `vultron/core/use_cases/received/outbox_handler.py` from
  `("Create", "Announce")` to also include `"Add"`, `"Invite"`, and
  `"Accept"`. Document that `"Join"` and `"Remove"` will need the same
  treatment when implemented.

- [ ] **P347-SUGGESTBT**: Implement a proper BT in
  `SuggestActorToCaseReceivedUseCase.execute()`:
  - Precondition: the receiving actor is the case owner
    (`case.attributed_to == actor_id`); skip silently if not.
  - Emit `AcceptActorRecommendationActivity(to=[recommender_id])` and queue
    in outbox.
  - Emit `RmInviteToCaseActivity(actor=case_actor, object_=invitee,
    target=case, to=[invitee_id])` and queue in outbox.
  - Idempotent: if an invite for this actor+case already exists in the
    DataLayer, skip and log.
  Update tests to verify both activities are emitted and idempotency holds.

- [ ] **P347-TRIGGERS**: Add new trigger endpoints:
  - `create-case` and `add-report-to-case` in
    `vultron/adapters/driving/fastapi/routers/trigger_case.py` with
    corresponding `SvcCreateCaseUseCase` and `SvcAddReportToCaseUseCase` in
    `vultron/core/use_cases/triggers/`.
  - New router file `trigger_actor.py` with `suggest-actor-to-case` and
    `accept-case-invite` trigger endpoints, backed by
    `SvcSuggestActorToCaseUseCase` and `SvcAcceptCaseInviteUseCase`.

- [ ] **P347-EMBARGOTRIGGERS**:
  - Rename `evaluate-embargo` endpoint → `accept-embargo` (update router,
    `_trigger_adapter.py`, `SvcEvaluateEmbargoUseCase` →
    `SvcAcceptEmbargoUseCase`, all call sites, tests, and spec references).
  - Add `reject-embargo` trigger endpoint + `SvcRejectEmbargoUseCase`.
  - Add `propose-embargo-revision` trigger endpoint +
    `SvcProposeEmbargoRevisionUseCase`.
  - Update `specs/triggerable-behaviors.md` to reflect all embargo trigger
    renames and additions.

- [ ] **P347-DEMOORG**: Reorganize `vultron/demo/` into two sub-packages:
  - `vultron/demo/exchange/` — individual protocol-fragment demos
    (direct inbox injection; demonstrating message semantics).
    Move: all single-activity demos (`receive_report_demo.py`,
    `suggest_actor_demo.py`, `establish_embargo_demo.py`, etc.).
  - `vultron/demo/scenario/` — end-to-end multi-actor workflow demos
    (trigger-based puppeteering).
    Move: `two_actor_demo.py`, `three_actor_demo.py`, `multi_vendor_demo.py`.
  - Update `vultron/demo/cli.py`, all Docker Compose files, and Makefile
    imports/references.
  - Add `README.md` to each sub-package explaining the distinction.

- [ ] **P347-PUPPETEER**: Convert scenario demos to trigger-based puppeteering:
  - `three_actor_demo.py`: replace `coordinator_creates_case_on_case_actor`,
    `coordinator_adds_report_to_case`, `coordinator_invites_actor`,
    `actor_accepts_case_invite`, and `actor_accepts_embargo` with calls to
    the trigger endpoints added in P347-TRIGGERS and P347-EMBARGOTRIGGERS.
  - `multi_vendor_demo.py`: same pattern for its equivalent spoofing
    functions.
  - `two_actor_demo.py`: audit and convert any remaining direct inbox
    injections.

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
