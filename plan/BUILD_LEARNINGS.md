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
