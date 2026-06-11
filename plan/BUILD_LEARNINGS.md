## Implementation Notes

Longer-term notes can be found in `/notes/*.md`. This file is ephemeral
and will be reset periodically, so it's meant to capture more immediate
insights, issues, and learnings during the implementation process.

Append new items below any existing ones, marking them with the date and a
header.

### 2026-06-08 ISSUE-654 — Surrogate-key routing collision handling

- Surrogate-key resolution must treat ambiguous matches as errors, not
  first-match wins; otherwise actor/case lookups become non-deterministic when
  multiple canonical IDs share a tail segment.
- Case-key resolution should continue to short-key fallback even when
  `dl.read(key)` returns a non-case object; otherwise non-case IDs can shadow
  valid case keys and produce false 404/validation failures.
  
### 2026-06-08 ISSUE-757 — Shared participant lookup must support both case participant surfaces

- `VulnerabilityCase` fixtures and call sites are mixed: some populate
  `case_participants`, others rely on `actor_participant_index`.
- A shared BT lookup node that only scans `case_participants` regresses
  status workflows that previously used `actor_participant_index` checks.
- The reusable participant-finder logic should seed from the
  `actor_participant_index` direct hit first, then scan `case_participants`.

### 2026-06-08 ISSUE-718 — Shared-inbox stubs must fail fast with a concrete type

- A docstring-only adapter stub does not satisfy OX-11-004 because accidental
  imports/callers get no runtime signal.
- Stubbed transport adapters should define an explicit class and raise
  `NotImplementedError` in `__init__` with spec reference context so failures
  are immediate and diagnosable.

### 2026-06-08 ISSUE-721 — Transport-role naming must stay explicit in paths and classes

- Outbound adapter names that imply behavior (`delivery_queue`) instead of role
  (`demo_http_delivery`) create broad documentation and import drift.
- When renaming protocol-significant adapter modules, update parallel
  references together (core ports docs, adapter notes, ADR references, and
  codebase reference pages) to keep agent guidance aligned with runtime code.

### 2026-06-08 ISSUE-750 — Embargo subtree decomposition must preserve idempotent side effects

- Decomposing a god node into sequential BT leaves can silently change
  duplicate-run behavior when side-effect leaves always execute.
- Preserve previous semantics explicitly with a blackboard flag that tracks
  whether the current execution actually initialized a new embargo.
- When moving EM transition logic to `EmbargoLifecycle.propose_embargo`,
  keep event creation and participant-seeding behavior aligned with existing
  duplicate-report tests to avoid introducing warning-level regressions.

### 2026-06-08 ISSUE-769 — Inbox test seam must preserve production deferral semantics

- A test-only inbox pipeline that reimplements defer/replay logic can drift
  from production behavior unless it reuses the same expiry path.
- Case deferral tests should set canonical `to` recipients so actor-scoped
  queues are exercised under the same addressing assumptions as inbox
  processing.

### 2026-06-09 ISSUE-711 — Surface domain transition failures from BT action nodes

- When strict state-machine transitions move into BT action nodes, use cases
  still need original domain exception types (for example
  `VultronInvalidStateTransitionError`) to preserve caller/test semantics.
- A small BT node result channel (`result_out["error"]`) lets the use case
  re-raise lifecycle domain errors directly instead of collapsing everything
  into a generic BT failure message.
  
### 2026-06-09 ISSUE-751 — Conditional BT branches can replace inline node `if` logic cleanly

- For god-node decomposition, represent optional behavior as an explicit
  `Selector` subtree (`active-branch` then `no-active` guard) instead of inline
  branching in a single `update()` method.
- Blackboard handoff keys (`new_case_participant`, `participant_case`,
  `new_participant_id`) make each leaf independently testable while preserving
  end-to-end behavior.

### 2026-06-09 ISSUE-742 — Subpackage splits should preserve import surfaces explicitly

- When replacing a flat use-case module with a subpackage, add explicit
  `__init__.py` re-exports for both use-case classes and any request models
  callers previously imported transitively from the old module.
- Mirror the source split in test layout with a matching subdirectory to keep
  file organization aligned and reduce future merge-conflict hotspots.

### 2026-06-09 ISSUE-825 — Actor-participant cache checks should fail only on contradictions

- Canonical actor→participant resolution should use `case_participants` as the
  source of truth and treat `actor_participant_index` as a derived cache.
- Fail fast when the cache contradicts canonical data (wrong/stale participant),
  but do not treat a missing cache entry as fatal when canonical participant
  data exists.

### 2026-06-09 ISSUE-710 — Embargo received-side BT adoption

- BT node parameter shadowing: When migrating procedural logic to BT nodes,
  ensure constructor parameters are used or removed. The unused `actor_id_source`
  parameter in LookupParticipantNode was defined but never used, creating
  confusion about parameter intent.
- Actor-id mismatch in invite trees: InviteToEmbargoOnCaseReceivedUseCase
  passes wrong actor_id to bridge.execute_with_setup() when invitee_id differs
  from sender actor_id. Must pass invitee_id (not sender) so
  OptionalLookupParticipantNode resolves correct participant record.
- Lenient vs strict node variants: OptionalLookupParticipantNode pattern
  (succeed-on-missing) is correct for operations that should skip when
  participant missing (invite, reject), but LookupParticipantNode
  (fail-on-missing) is still needed for operations that require participant
  (acceptance recording).
- Cascade subtree must be part of tree execution: All BT factories include
  CommitLogCascadeNode as a leaf; cascade is never a post-BT callback.
- Post-implementation code review caught actor_id bug before merge; review
  gates on correctness, not style.
- BT-14-001 compliance is CRITICAL for peer broadcast nodes: CommitLogCascadeNode
  MUST return FAILURE when cascade dispatch fails, not SUCCESS. Masking delivery
  failure with SUCCESS causes silent state divergence (missed by initial code
  review, found on PR review). Always check peer-broadcast nodes against BT-14-001.
- Lenient vs strict patterns need documentation: OptionalLookupParticipantNode
  (lenient) is correct for optional workflows where participant may not exist
  locally yet, but the architectural rationale must be explicit in docstrings
  so future reviewers understand why "Always SUCCESS" is intentional, not a bug.
  The pattern supports broadcasting log entries even when participant doesn't
  exist on this peer yet (state gap resolved by broadcast reception).

### 2026-06-09 ISSUE-801 — Wire actor vocabulary overrides must preserve base-module registration

- Overriding all actor keys in `VOCABULARY` from `vultron_actor.py` can leave
  `vultron.wire.as2.vocab.base.objects.actors` with zero registered concrete
  types, tripping the registry-completeness invariant.
- Keep at least one base-actors-module registration (for now `Actor` →
  `as_Actor`) and override concrete keys (`Person`, `Organization`, etc.) with
  wire-branch Vultron actor subclasses.
  
### 2026-06-09 ISSUE-690 — Case-log snapshots and demo log exports need source-aware fallbacks

- `CommitCaseLogEntryNode` must forward a serialized activity payload snapshot
  from the BT blackboard into `create_commit_log_entry_tree()`; otherwise
  `CaseLogEntry.payloadSnapshot` silently defaults to `{}` despite valid
  inbound activity context.
- Two-actor demo log export should always emit a `case-actor` JSONL artifact,
  but dedicated case-actor container reads may be empty in D5-2 by design;
  export logic should fall back to the vendor container's case-actor sub-actor
  route key instead of failing the demo run.

### 2026-06-09 ISSUE-848 — BTBridge migration for embargo revision use case

- The pre-condition EM state check (ACTIVE/REVISE guard) can move cleanly
  into a `DataLayerAction` node (`ValidateEmbargoRevisionStateNode`) that
  reads the case, checks `current_status.em_state`, and writes the domain
  error into `result_out["error"]` for re-raise by the use case.
- Avoid reusing a local variable `error` across two branches with different
  concrete types (e.g., `VultronValidationError` then
  `VultronInvalidStateTransitionError`) — mypy infers the type from the first
  assignment and flags the second as incompatible. Use distinct variable names
  per branch.
- The counter-revision path (EM.REVISE → EM.REVISE) must be tested separately
  from ACTIVE → REVISE because `_cascade_pec_revise` only fires on the
  ACTIVE → REVISE transition; a counter-revision must leave PEC states
  unchanged.
  
### 2026-06-09 ISSUE-752 — God-node splits should preserve node-local failure semantics

- Decomposing a monolithic BT action into leaf nodes can change failure shape
  if required blackboard keys are read without `KeyError` handling.
- Leaf nodes that require blackboard context should convert missing-key reads
  into explicit node `FAILURE` with a clear error message, not bridge-level
  exception failures.

### 2026-06-10 PR-886 — PCR-08 violation fix: ResolveCaseManagerNode requires CASE_MANAGER participant in fixtures

- Replacing `case_addressees()` with canonical `_resolve_case_manager_id()` / `ResolveCaseManagerNode`
  causes tests to fail in a non-obvious way when CASE_MANAGER is absent: the engage
  path's RM transition fires (→ ACCEPTED), the send then fails, the defer path fires
  (→ DEFERRED), and the test sees RM=DEFERRED instead of the expected RM=ACCEPTED.
  The failure manifests as wrong state, not a clear "participant not found" error.
- All test fixtures for BT paths that involve `ResolveCaseManagerNode` MUST include a
  `VultronParticipant` with `CVDRole.CASE_MANAGER` registered in `actor_participant_index`.
- `VulnerabilityCase.add_participant()` has a pyright type mismatch with `VultronParticipant`
  (core vs. wire-layer `CaseParticipant`). In tests, set `case_participants` and
  `actor_participant_index` directly in the `VulnerabilityCase` constructor instead of
  calling `add_participant()`.
- Chained use cases in integration tests must ALL receive `trigger_activity`: if
  `SubmitReportReceivedUseCase` is called without it, `CreateCaseActorNode` never runs
  and the CASE_MANAGER participant is never registered, causing the downstream
  `ValidateReport` engage BT to fail silently. Pass `TriggerActivityAdapter(dl)` to
  every use case in the chain, not just the last one.

### 2026-06-10 ISSUE-755 — SYNC god-node decomposition works best as context handoff leaves

- For replay/fan-out flows, split nodes around blackboard context boundaries:
  collect context, derive index/recipients, then perform side effects.
- Condition+action hybrid nodes are clearer and safer as `Selector` composites:
  a pure condition leaf first, then side-effect action fallback.

### 2026-06-10 PR-886 — Global py_trees blackboard not thread-safe under FastAPI BackgroundTasks

- FastAPI runs synchronous `BackgroundTask` callables via
  `anyio.to_thread.run_sync`, putting them on a thread-pool. Two BT
  executions can therefore run on different threads simultaneously,
  both writing to `py_trees.blackboard.Blackboard.storage` (process-global).
- The race: Thread A's `execute_with_setup` writes `actor_id=A` and
  `datalayer=DL_A`; Thread B overwrites them with `actor_id=B` / `datalayer=DL_B`;
  Thread A then reads the wrong `actor_id`, queueing its outbound activity
  under the wrong actor's outbox — the activity is silently lost. Thread B
  may also crash when Thread A's cleanup removes `/datalayer` before B reads it.
- Fix: wrap the entire setup→execute→cleanup critical section in
  `BTBridge.execute_with_setup` with a module-level `threading.RLock`.
  `RLock` (not `Lock`) is required because `lifecycle.py` BT nodes call
  `execute_with_setup` recursively — a plain `Lock` deadlocks there.
- Demo symptom: M7 check ("all participants RM.CLOSED on both replicas") timed
  out because finder's CLOSED `Add(ParticipantStatus)` was silently queued to
  the case-actor's outbox in finder's DataLayer (never processed) instead of
  finder's own outbox.
  
### 2026-06-10 ISSUE-714 — Decomposed BT nodes must preserve alternate context seams

- When replacing a god node with leaf-node sequences, preserve all original
  input seams (`case_id` from blackboard and `case_obj`-derived context).
- If downstream leaves rely on blackboard keys, add explicit fallback reads
  from staged objects/status context to avoid regressing valid call paths.
